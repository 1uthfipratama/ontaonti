"""Phase 3: consent notice, STOP / MULAI / LANGGANAN, contact merge and timeline."""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Consent, Contact
from app.services.settings_service import DEFAULTS
from tests.conftest import simulate, thread


async def bot_texts(admin, conv_id):
    return [m["text"] for m in await thread(admin, conv_id) if m["sender_type"] == "bot"]


async def test_consent_notice_only_on_first_message(admin):
    out = await simulate(admin, "Halo")
    await simulate(admin, "Apa itu TBC?")
    texts = await bot_texts(admin, out["conversation_id"])
    assert texts.count(DEFAULTS["consent_notice_id"]) == 1
    assert texts[0] == DEFAULTS["consent_notice_id"]


async def test_english_first_message_gets_english_notice(admin):
    out = await simulate(admin, "Hello, what is TB?")
    assert (await bot_texts(admin, out["conversation_id"]))[0] == DEFAULTS["consent_notice_en"]


async def test_stop_opts_out_and_bot_goes_silent(admin):
    out = await simulate(admin, "Halo")
    conv_id = out["conversation_id"]
    await simulate(admin, "STOP")
    texts = await bot_texts(admin, conv_id)
    assert texts[-1] == DEFAULTS["optout_confirm_en"] or texts[-1] == DEFAULTS["optout_confirm_id"]
    n = len(texts)
    await simulate(admin, "Apa itu TBC?")
    await simulate(admin, "berhenti")  # already out: no second confirmation
    assert len(await bot_texts(admin, conv_id)) == n
    conv = (await admin.get(f"/conversations/{conv_id}")).json()
    assert conv["opted_out"] is True
    r = await admin.post(f"/conversations/{conv_id}/messages", json={"text": "halo?"})
    assert r.status_code == 409  # staff can't message an opted-out contact either


async def test_stop_inside_a_sentence_is_not_opt_out(admin):
    out = await simulate(admin, "saya ingin berhenti minum obat")
    conv = (await admin.get(f"/conversations/{out['conversation_id']}")).json()
    assert conv["opted_out"] is False  # it's an ADHERENCE flag, not an opt-out
    assert conv["flag_category"] == "ADHERENCE"


async def test_opted_out_emergency_still_alerts_staff_without_reply(admin):
    out = await simulate(admin, "Halo")
    await simulate(admin, "BERHENTI")
    n = len(await bot_texts(admin, out["conversation_id"]))
    await simulate(admin, "saya batuk darah banyak")
    assert len(await bot_texts(admin, out["conversation_id"])) == n
    assert (await admin.get("/cases")).json()[0]["severity"] == "emergency"


async def test_mulai_opts_back_in(admin):
    out = await simulate(admin, "Halo")
    await simulate(admin, "STOP")
    await simulate(admin, "MULAI")
    conv = (await admin.get(f"/conversations/{out['conversation_id']}")).json()
    assert conv["opted_out"] is False
    assert (await bot_texts(admin, out["conversation_id"]))[-1] == DEFAULTS["optin_confirm_id"]
    async with SessionLocal() as s:
        kinds = [(c.kind, c.status) for c in (await s.execute(select(Consent))).scalars()]
    assert ("messaging", "revoked") in kinds and ("messaging", "granted") in kinds


async def test_langganan_grants_broadcast_consent(admin):
    out = await simulate(admin, "LANGGANAN")
    async with SessionLocal() as s:
        contact = (await s.execute(select(Contact))).scalar_one()
    assert contact.broadcast_opt_in is True
    assert (await bot_texts(admin, out["conversation_id"]))[-1] == DEFAULTS["subscribe_confirm_id"]
    await simulate(admin, "STOP")
    async with SessionLocal() as s:
        contact = (await s.execute(select(Contact))).scalar_one()
    assert contact.broadcast_opt_in is False  # STOP revokes broadcasts too


async def test_merge_contacts_and_cross_channel_timeline(admin):
    a = await simulate(admin, "Halo dari WhatsApp", user_id="siti", channel="whatsapp")
    b = await simulate(admin, "Halo dari Instagram", user_id="siti_ig", channel="instagram")
    ca = (await admin.get(f"/conversations/{a['conversation_id']}")).json()["contact_id"]
    cb = (await admin.get(f"/conversations/{b['conversation_id']}")).json()["contact_id"]
    assert ca != cb
    r = await admin.post(f"/contacts/{ca}/merge", json={"source_contact_id": cb})
    assert r.status_code == 200, r.text
    assert {i["channel"] for i in r.json()["identities"]} == {"whatsapp", "instagram"}
    assert (await admin.get(f"/contacts/{cb}")).status_code == 404
    timeline = (await admin.get(f"/contacts/{ca}/timeline")).json()
    channels = {m["channel"] for m in timeline if m["direction"] == "in"}
    assert channels == {"whatsapp", "instagram"}
    assert len((await admin.get("/contacts")).json()) == 1


async def test_staff_broadcast_consent_is_recorded(admin):
    out = await simulate(admin, "Halo")
    cid = (await admin.get(f"/conversations/{out['conversation_id']}")).json()["contact_id"]
    r = await admin.post(f"/contacts/{cid}/consent", json={"broadcast": True})
    assert r.json()["broadcast_opt_in"] is True
    detail = (await admin.get(f"/contacts/{cid}")).json()
    assert any(
        c["kind"] == "broadcast" and c["source"].startswith("staff") for c in detail["consents"]
    )
