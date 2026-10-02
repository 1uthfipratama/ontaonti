"""Phase 1: simulator -> worker -> bot reply; HUMAN mode; staff replies; audit."""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuditLog, LlmUsage
from tests.conftest import simulate, thread


async def test_login_rejects_wrong_password(client):
    r = await client.post("/auth/login", json={"email": "admin@test.local", "password": "nope"})
    assert r.status_code == 401


async def test_me_after_login(admin):
    r = await admin.get("/auth/me")
    assert r.json()["role"] == "admin"


async def test_simulator_message_gets_bot_reply(admin, fake_retrieval):
    out = await simulate(admin, "Berapa lama pengobatan TBC?")
    msgs = await thread(admin, out["conversation_id"])
    bot = [m for m in msgs if m["sender_type"] == "bot"]
    assert bot, msgs
    answer = bot[-1]
    assert answer["status"] == "sent"
    assert "[1]" not in answer["text"]  # citation markers stripped before sending
    assert answer["meta"]["sources"][0]["doc"] == "p05"
    assert len(answer["text"]) <= 900
    assert fake_retrieval[0][1] == 4  # fixed retrieval k


async def test_llm_usage_is_logged(admin):
    await simulate(admin, "Apa itu TBC?")
    async with SessionLocal() as s:
        rows = (await s.execute(select(LlmUsage))).scalars().all()
    assert any(r.purpose == "answer" for r in rows)


async def test_human_mode_blocks_bot(admin):
    out = await simulate(admin, "Halo")
    conv_id = out["conversation_id"]
    r = await admin.post(f"/conversations/{conv_id}/mode", json={"mode": "HUMAN"})
    assert r.json()["mode"] == "HUMAN"
    before = [m for m in await thread(admin, conv_id) if m["sender_type"] == "bot"]
    await simulate(admin, "Ada orang?")
    after = [m for m in await thread(admin, conv_id) if m["sender_type"] == "bot"]
    assert len(after) == len(before)  # stored, but no bot reply


async def test_staff_reply_takes_over_and_is_audited(admin):
    out = await simulate(admin, "Halo kak")
    conv_id = out["conversation_id"]
    r = await admin.post(f"/conversations/{conv_id}/messages", json={"text": "Halo, saya staf."})
    assert r.status_code == 200, r.text
    conv = (await admin.get(f"/conversations/{conv_id}")).json()
    assert conv["mode"] == "HUMAN"
    msgs = await thread(admin, conv_id)
    assert msgs[-1]["sender_type"] == "agent"
    async with SessionLocal() as s:
        actions = {a.action for a in (await s.execute(select(AuditLog))).scalars()}
    assert {"conversation.reply", "conversation.view", "simulator.message"} <= actions


async def test_conversation_list_filters(admin):
    await simulate(admin, "Halo", user_id="a", channel="whatsapp")
    await simulate(admin, "Hello", user_id="b", channel="instagram")
    ig = (await admin.get("/conversations", params={"channel": "instagram"})).json()
    assert len(ig) == 1 and ig[0]["channel"] == "instagram"
    assert len((await admin.get("/conversations")).json()) == 2


async def test_reviewer_cannot_reply(admin, client):
    r = await admin.post(
        "/staff",
        json={"email": "rev@test.local", "role": "reviewer", "password": "reviewer-pass-1"},
    )
    assert r.status_code == 200, r.text
    out = await simulate(admin, "Halo")
    await client.post("/auth/logout")
    await client.post(
        "/auth/login", json={"email": "rev@test.local", "password": "reviewer-pass-1"}
    )
    r = await client.post(f"/conversations/{out['conversation_id']}/messages", json={"text": "x"})
    assert r.status_code == 403
