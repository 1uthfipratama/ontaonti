"""Office hours: one away message per closed period while staff have the chat."""

from datetime import UTC, datetime

from app.services import office_hours
from app.services.settings_service import DEFAULTS, Config
from tests.conftest import simulate, thread


def cfg(**over) -> Config:
    return Config({**DEFAULTS, "office_hours_enabled": True, **over})


# Jakarta is UTC+7: 03:00 UTC = 10:00 WIB.
MON_10 = datetime(2026, 10, 5, 3, 0, tzinfo=UTC)  # Monday 10:00 WIB
MON_20 = datetime(2026, 10, 5, 13, 0, tzinfo=UTC)  # Monday 20:00 WIB
SAT_10 = datetime(2026, 10, 10, 3, 0, tzinfo=UTC)  # Saturday 10:00 WIB


def test_open_and_closed():
    c = cfg()
    assert office_hours.is_open(c, MON_10)
    assert not office_hours.is_open(c, MON_20)
    assert not office_hours.is_open(c, SAT_10)
    assert office_hours.is_open(cfg(office_hours_enabled=False), SAT_10)


def test_closed_period_starts_at_last_closing():
    c = cfg()
    # Monday evening -> closed since Monday 16:00 WIB (09:00 UTC).
    assert office_hours.closed_since(c, MON_20) == datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
    # Saturday -> closed since Friday 16:00 WIB.
    assert office_hours.closed_since(c, SAT_10) == datetime(2026, 10, 9, 9, 0, tzinfo=UTC)


def test_describe_hours():
    assert office_hours.describe(cfg(), "id") == "Senin–Jumat, 08.00–16.00 WIB"
    assert office_hours.describe(cfg(office_days=[1, 3, 4, 6]), "en") == (
        "Monday, Wednesday–Thursday, Saturday, 08:00–16:00 WIB"
    )


async def test_settings_validate_times_and_days(admin):
    bad = await admin.put("/settings", json={"values": {"office_open": "25:00"}})
    assert bad.status_code == 422
    bad = await admin.put("/settings", json={"values": {"office_days": [0, 8]}})
    assert bad.status_code == 422
    ok = await admin.put("/settings", json={"values": {"office_days": [5, 1, 1]}})
    assert ok.status_code == 200
    fields = {f["key"]: f for g in ok.json()["groups"] for f in g["fields"]}
    assert fields["office_days"]["value"] == [1, 5]
    assert fields["office_days"]["type"] == "days" and fields["office_open"]["type"] == "time"


async def test_away_message_once_while_closed(admin):
    # open == close: never open, so "now" is always outside office hours.
    r = await admin.put(
        "/settings",
        json={"values": {"office_hours_enabled": True, "office_days": [1, 2, 3, 4, 5, 6, 7],
                         "office_open": "00:00", "office_close": "00:00"}},
    )  # fmt: skip
    assert r.status_code == 200, r.text

    out = await simulate(admin, "Saya batuk darah banyak sejak tadi", user_id="malam")
    msgs = await thread(admin, out["conversation_id"])
    away = [m for m in msgs if m["meta"].get("away")]
    assert len(away) == 1 and "Senin–Minggu" in away[0]["text"]
    # The safety reply comes first, the away message after it.
    bot = [m for m in msgs if m["sender_type"] == "bot"]
    assert bot[-2]["meta"].get("safety_reply") and bot[-1]["meta"].get("away")

    # Staff have the chat now; more messages tonight don't repeat it.
    await simulate(admin, "Halo? Ada yang bisa bantu?", user_id="malam")
    msgs = await thread(admin, out["conversation_id"])
    assert len([m for m in msgs if m["meta"].get("away")]) == 1


async def test_no_away_message_when_disabled_or_bot_mode(admin):
    out = await simulate(admin, "Saya batuk darah banyak sejak tadi", user_id="siang")
    msgs = await thread(admin, out["conversation_id"])
    assert not [m for m in msgs if m["meta"].get("away")]  # office hours off by default
