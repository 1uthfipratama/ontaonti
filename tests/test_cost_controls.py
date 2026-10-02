"""Phase 5: budget alert + fallback, rate limit, daily cap, settings, dashboard."""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuditLog, Case, LlmUsage, Message
from app.services.settings_service import DEFAULTS
from tests.conftest import simulate, thread


async def spend(idr: float) -> None:
    async with SessionLocal() as s:
        s.add(LlmUsage(provider="fake", model="x", purpose="answer", cost_idr=idr, cost_usd=0))
        await s.commit()


async def set_settings(admin, **values) -> dict:
    r = await admin.put("/settings", json={"values": values})
    assert r.status_code == 200, r.text
    return r.json()


async def bot_msgs(admin, conv_id) -> list[dict]:
    return [m for m in await thread(admin, conv_id) if m["sender_type"] == "bot"]


async def purposes() -> list[str]:
    async with SessionLocal() as s:
        return [u.purpose for u in (await s.execute(select(LlmUsage))).scalars()]


# --- budget -------------------------------------------------------------------------


async def test_budget_fallback_fixed_reply_opens_case_without_llm(admin):
    await set_settings(admin, monthly_budget_idr=1000, budget_fallback_mode="fixed_reply")
    await spend(1000)
    out = await simulate(admin, "Berapa lama pengobatan TBC?")
    assert (await bot_msgs(admin, out["conversation_id"]))[-1]["text"] == DEFAULTS[
        "budget_fallback_reply_id"
    ]
    assert await purposes() == ["answer"]  # only the seeded row: no classifier, no answer call
    async with SessionLocal() as s:
        case = (await s.execute(select(Case))).scalar_one()
    assert case.category == "BUDGET"


async def test_budget_fallback_uses_classifier_model(admin):
    await set_settings(admin, monthly_budget_idr=1000, budget_fallback_mode="classifier_model")
    await spend(5000)
    out = await simulate(admin, "Apa itu TBC?")
    answer = (await bot_msgs(admin, out["conversation_id"]))[-1]
    assert answer["meta"]["model"] == "fake-classifier"


async def test_keyword_flags_still_run_over_budget(admin):
    await set_settings(admin, monthly_budget_idr=1000, budget_fallback_mode="fixed_reply")
    await spend(99999)
    out = await simulate(admin, "saya batuk darah banyak")
    assert (await bot_msgs(admin, out["conversation_id"]))[-1]["text"] == DEFAULTS[
        "safety_emergency_id"
    ]
    async with SessionLocal() as s:
        sev = [c.severity for c in (await s.execute(select(Case))).scalars()]
    assert sev == ["emergency"]


async def test_budget_alert_fires_once_per_month(admin, monkeypatch):
    from app import notify
    from app.config import settings

    sent = []
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(notify, "_send", lambda to, subject, body: sent.append(subject))
    await set_settings(admin, monthly_budget_idr=1000)
    await spend(850)  # 85% >= 80%
    await simulate(admin, "Halo", user_id="a")
    await simulate(admin, "Halo lagi", user_id="b")
    assert len(sent) == 1 and "85%" in sent[0]


# --- limits ---------------------------------------------------------------------------


async def test_rate_limit_polite_message_once(admin):
    await set_settings(admin, rate_limit_count=3, rate_limit_window_minutes=10)
    for i in range(5):
        out = await simulate(admin, f"pertanyaan {i}")
    texts = [m["text"] for m in await bot_msgs(admin, out["conversation_id"])]
    assert texts.count(DEFAULTS["rate_limit_reply_id"]) == 1
    async with SessionLocal() as s:
        inbound = (
            (await s.execute(select(Message).where(Message.direction == "in"))).scalars().all()
        )
    assert len(inbound) == 5  # all stored for staff


async def test_daily_cap(admin):
    await set_settings(admin, daily_message_cap=2, rate_limit_count=100)
    for i in range(4):
        out = await simulate(admin, f"tanya {i}")
    texts = [m["text"] for m in await bot_msgs(admin, out["conversation_id"])]
    assert texts.count(DEFAULTS["daily_cap_reply_id"]) == 1


async def test_safety_is_not_rate_limited(admin):
    await set_settings(admin, rate_limit_count=1)
    await simulate(admin, "halo")
    await simulate(admin, "halo lagi")  # limited
    out = await simulate(admin, "saya ingin bunuh diri")
    assert (await bot_msgs(admin, out["conversation_id"]))[-1]["text"] == DEFAULTS[
        "safety_self_harm_id"
    ]


# --- settings ---------------------------------------------------------------------------


async def test_settings_roundtrip_validation_and_audit(admin):
    data = (await admin.get("/settings")).json()
    keys = {f["key"] for g in data["groups"] for f in g["fields"]}
    assert {"persona_prompt", "monthly_budget_idr", "daily_message_cap"} <= keys
    assert "EMERGENCY" in data["flag_rules"]["categories"]

    r = await admin.put("/settings", json={"values": {"monthly_budget_idr": -5}})
    assert r.status_code == 422
    r = await admin.put("/settings", json={"values": {"budget_fallback_mode": "nope"}})
    assert r.status_code == 422
    r = await admin.put("/settings", json={"values": {"unknown_key": 1}})
    assert r.status_code == 422

    data = await set_settings(admin, persona_prompt="Kamu Onti.", daily_message_cap=10)
    fields = {f["key"]: f for g in data["groups"] for f in g["fields"]}
    assert fields["daily_message_cap"]["value"] == 10 and fields["daily_message_cap"]["overridden"]
    async with SessionLocal() as s:
        row = (
            await s.execute(select(AuditLog).where(AuditLog.action == "settings.update"))
        ).scalar_one()
    assert row.details["keys"] == ["daily_message_cap", "persona_prompt"]

    data = (await admin.post("/settings/reset", json={"keys": ["daily_message_cap"]})).json()
    fields = {f["key"]: f for g in data["groups"] for f in g["fields"]}
    assert (
        fields["daily_message_cap"]["value"] == 30 and not fields["daily_message_cap"]["overridden"]
    )


async def test_flag_keywords_editable(admin):
    rules = (await admin.get("/settings")).json()["flag_rules"]
    rules["categories"]["ADHERENCE"]["keywords"].append("capek minum obat")
    await set_settings(admin, flag_rules=rules)
    out = await simulate(admin, "aku capek minum obat terus")
    conv = (await admin.get(f"/conversations/{out['conversation_id']}")).json()
    assert conv["flag_category"] == "ADHERENCE"
    bad = {"categories": {"X": {"severity": "catastrophic", "keywords": ["a"]}}}
    assert (await admin.put("/settings", json={"values": {"flag_rules": bad}})).status_code == 422


async def test_settings_admin_only(admin, client):
    await admin.post(
        "/staff", json={"email": "ag@test.local", "role": "agent", "password": "agent-pass-123"}
    )
    await client.post("/auth/logout")
    await client.post("/auth/login", json={"email": "ag@test.local", "password": "agent-pass-123"})
    assert (await client.get("/settings")).status_code == 403
    assert (await client.put("/settings", json={"values": {}})).status_code == 403


# --- dashboard --------------------------------------------------------------------------


async def test_dashboard(admin):
    await set_settings(admin, monthly_budget_idr=10000)
    await simulate(admin, "Halo", user_id="a", channel="whatsapp")
    await simulate(admin, "Hello", user_id="b", channel="instagram")
    await simulate(admin, "saya pingsan", user_id="c", channel="messenger")
    d = (await admin.get("/dashboard")).json()
    assert d["conversations"]["today"] == {"whatsapp": 1, "messenger": 1, "instagram": 1}
    assert d["open_cases"]["emergency"] == 1
    assert d["response_times"]["bot_samples"] >= 3
    assert d["response_times"]["bot_median_s"] is not None
    assert d["ai"]["budget_idr"] == 10000 and d["ai"]["calls"] >= 1
    assert d["whatsapp"]["free_tier"] == 1000
    assert d["contacts"]["total"] == 3
