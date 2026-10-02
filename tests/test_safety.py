"""Phase 2: keyword rules, classifier, fixed safety replies, cases, resolve -> BOT."""

import pytest
from sqlalchemy import select

from app.bot import safety
from app.db import SessionLocal
from app.models import Case, LlmUsage
from app.services.settings_service import DEFAULTS, default_flag_rules
from tests.conftest import simulate, thread

RULES = default_flag_rules()


@pytest.mark.parametrize(
    ("text", "severity", "category"),
    [
        ("Saya batuk darah sangat banyak dari tadi pagi", "emergency", "EMERGENCY"),
        ("sesak napas berat, tolong", "emergency", "EMERGENCY"),
        ("Ibu saya PÍNGSAN setelah batuk", "emergency", "EMERGENCY"),  # case + diacritics
        ("I can't breathe properly", "emergency", "EMERGENCY"),
        ("rasanya aku ingin mati saja", "emergency", "SELF_HARM"),
        ("sometimes I want to kill myself", "emergency", "SELF_HARM"),
        ("mataku jadi kuning sejak minum obat", "high", "ADVERSE_DRUG"),  # suffix + gap
        ("Saya muntah-muntah terus dari kemarin", "high", "ADVERSE_DRUG"),  # hyphen
        ("penglihatan saya kabur", "high", "ADVERSE_DRUG"),
        ("obatnya sudah habis kak", "high", "ADHERENCE"),
        ("saya mau berhenti pengobatan saja", "high", "ADHERENCE"),
        ("lupa minum obat berhari-hari", "high", "ADHERENCE"),
    ],
)
def test_keyword_rules_per_category(text, severity, category):
    flag = safety.keyword_flag(text, RULES)
    assert (flag.severity, flag.category) == (severity, category)
    assert flag.source == "keyword"


@pytest.mark.parametrize(
    "text",
    ["Berapa lama pengobatan TBC?", "Apa itu TBC?", "Halo kak", "terima kasih banyak", ""],
)
def test_no_flag_for_ordinary_messages(text):
    assert safety.keyword_flag(text, RULES).severity == "none"


def test_highest_severity_category_wins():
    flag = safety.keyword_flag("obat habis dan sekarang sesak napas berat", RULES)
    assert flag.severity == "emergency"


def test_classifier_parse_failure_is_low():
    for bad in ("no json here", "", '{"severity": "catastrophic"}', "{not json}"):
        flag = safety.parse_classifier(bad)
        assert flag.severity == "low"


def test_classifier_parses_valid_json():
    flag = safety.parse_classifier(
        'Sure: {"severity": "high", "category": "adverse_drug", "reason": "jaundice"}'
    )
    assert (flag.severity, flag.category, flag.reason) == ("high", "ADVERSE_DRUG", "jaundice")


def test_final_severity_is_max():
    kw = safety.Flag("high", "ADHERENCE", "kw", "keyword")
    cls = safety.Flag("emergency", "EMERGENCY", "cls", "classifier")
    assert safety.combine(kw, cls).severity == "emergency"
    assert safety.combine(kw, safety.Flag("low", "OTHER", "", "classifier")).severity == "high"


async def _cases():
    async with SessionLocal() as s:
        return (await s.execute(select(Case))).scalars().all()


async def test_emergency_sends_fixed_reply_opens_case_and_hands_over(admin):
    out = await simulate(admin, "Tolong, saya batuk darah banyak sekali")
    conv_id = out["conversation_id"]
    msgs = await thread(admin, conv_id)
    bot = [m for m in msgs if m["sender_type"] == "bot"]
    assert bot[-1]["text"] == DEFAULTS["safety_emergency_id"]  # fixed text, not generated
    inbound = [m for m in msgs if m["direction"] == "in"][-1]
    assert inbound["flag_severity"] == "emergency" and inbound["flag_category"] == "EMERGENCY"
    conv = (await admin.get(f"/conversations/{conv_id}")).json()
    assert conv["mode"] == "HUMAN" and conv["flag_severity"] == "emergency"
    cases = await _cases()
    assert len(cases) == 1 and cases[0].severity == "emergency"
    async with SessionLocal() as s:
        purposes = [u.purpose for u in (await s.execute(select(LlmUsage))).scalars()]
    assert "answer" not in purposes  # the LLM never wrote the safety reply


async def test_english_self_harm_gets_english_safety_text(admin):
    out = await simulate(admin, "I feel like I want to kill myself")
    bot = [m for m in await thread(admin, out["conversation_id"]) if m["sender_type"] == "bot"]
    assert bot[-1]["text"] == DEFAULTS["safety_self_harm_en"]


async def test_classifier_only_flag_escalates(admin):
    # No keyword phrase matches; the (fake) classifier says high/EMERGENCY.
    out = await simulate(admin, "agak sesak sedikit kalau naik tangga")
    msgs = await thread(admin, out["conversation_id"])
    inbound = [m for m in msgs if m["direction"] == "in"][-1]
    assert inbound["flag_severity"] == "high"
    assert inbound["flag_reason"].startswith("classifier")
    assert len(await _cases()) == 1


async def test_classifier_garbage_is_low_and_bot_still_answers(admin):
    out = await simulate(admin, "Apa makanan yang baik? [fake-invalid-json]")
    msgs = await thread(admin, out["conversation_id"])
    inbound = [m for m in msgs if m["direction"] == "in"][-1]
    assert inbound["flag_severity"] == "low"
    assert any(m["sender_type"] == "bot" for m in msgs)
    assert await _cases() == []


async def test_resolve_returns_conversation_to_bot(admin):
    out = await simulate(admin, "obat saya habis")
    conv_id = out["conversation_id"]
    (case,) = (await admin.get("/cases")).json()
    assert case["severity"] == "high" and case["category"] == "ADHERENCE"
    r = await admin.post(f"/cases/{case['id']}/claim")
    assert r.json()["status"] == "CLAIMED"
    r = await admin.post(f"/cases/{case['id']}/notes", json={"text": "Called the patient."})
    assert r.json()["notes"][0]["text"] == "Called the patient."
    r = await admin.post(f"/cases/{case['id']}/resolve", json={"return_to_bot": True})
    assert r.json()["status"] == "RESOLVED"
    conv = (await admin.get(f"/conversations/{conv_id}")).json()
    assert conv["mode"] == "BOT" and conv["flag_severity"] == "none"
    # The bot answers again.
    before = len([m for m in await thread(admin, conv_id) if m["sender_type"] == "bot"])
    await simulate(admin, "Berapa lama pengobatannya?")
    after = len([m for m in await thread(admin, conv_id) if m["sender_type"] == "bot"])
    assert after == before + 1


async def test_human_mode_flag_opens_case_without_reply(admin):
    out = await simulate(admin, "Halo")
    conv_id = out["conversation_id"]
    await admin.post(f"/conversations/{conv_id}/mode", json={"mode": "HUMAN"})
    bots = len([m for m in await thread(admin, conv_id) if m["sender_type"] == "bot"])
    await simulate(admin, "saya pingsan tadi")
    assert len([m for m in await thread(admin, conv_id) if m["sender_type"] == "bot"]) == bots
    assert (await _cases())[0].severity == "emergency"


async def test_cases_sorted_by_severity_and_badge_counts(admin):
    await simulate(admin, "obat saya habis", user_id="a")  # high
    await simulate(admin, "saya batuk darah banyak", user_id="b")  # emergency
    cases = (await admin.get("/cases")).json()
    assert [c["severity"] for c in cases] == ["emergency", "high"]
    s = (await admin.get("/notifications/summary")).json()
    assert s["open_cases"] == 2 and s["emergency"] == 1 and s["high"] == 1


async def test_ai_summary(admin):
    out = await simulate(admin, "Saya sudah batuk tiga minggu")
    r = await admin.post(f"/conversations/{out['conversation_id']}/summary")
    assert r.status_code == 200, r.text
    assert "Saya sudah batuk" in r.json()["summary"]


async def test_case_email_when_smtp_configured(admin, monkeypatch):
    from app import notify
    from app.config import settings

    sent = []
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(notify, "_send", lambda to, subject, body: sent.append((to, subject)))
    await simulate(admin, "saya ingin bunuh diri")
    assert sent and "EMERGENCY" in sent[0][1].upper() and sent[0][0] == ["admin@test.local"]
