"""Office hours: when staff are around.

The bot answers 24/7. Outside office hours, a contact whose chat is with staff
(HUMAN mode, e.g. after a safety flag) gets one away message per closed period,
so nobody waits all night for a reply that only comes in the morning.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import settings as env
from app.constants import SENDER_BOT
from app.db import utcnow
from app.models import Conversation
from app.services import outbound
from app.services.settings_service import Config

TZ_ABBR = {
    "Asia/Jakarta": "WIB",
    "Asia/Pontianak": "WIB",
    "Asia/Makassar": "WITA",
    "Asia/Jayapura": "WIT",
}
DAY_NAMES = {
    "id": ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}


def _tz() -> ZoneInfo:
    return ZoneInfo(env.timezone)


def _hm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def _days(cfg: Config) -> set[int]:
    return {int(d) for d in cfg["office_days"]}  # ISO weekday: Monday=1


def is_open(cfg: Config, now: datetime | None = None) -> bool:
    if not cfg["office_hours_enabled"]:
        return True
    local = (now or utcnow()).astimezone(_tz())
    return local.isoweekday() in _days(cfg) and _hm(cfg["office_open"]) <= local.time() < _hm(
        cfg["office_close"]
    )


def closed_since(cfg: Config, now: datetime) -> datetime:
    """Start of the current closed period: the latest closing time at or before now."""
    tz, close, days = _tz(), _hm(cfg["office_close"]), _days(cfg)
    local = now.astimezone(tz)
    for back in range(8):
        d = (local - timedelta(days=back)).date()
        if d.isoweekday() not in days:
            continue
        closing = datetime.combine(d, close, tzinfo=tz)
        if closing <= local:
            return closing
    return datetime(2000, 1, 1, tzinfo=tz)


def describe(cfg: Config, lang: str) -> str:
    """'Senin–Jumat, 08.00–16.00 WIB' (runs of consecutive days joined with a dash)."""
    names = DAY_NAMES.get(lang, DAY_NAMES["id"])
    days = sorted(_days(cfg))
    runs: list[list[int]] = []
    for d in days:
        if runs and d == runs[-1][-1] + 1:
            runs[-1].append(d)
        else:
            runs.append([d])
    parts = [
        names[r[0] - 1] if len(r) == 1 else f"{names[r[0] - 1]}–{names[r[-1] - 1]}" for r in runs
    ]
    sep = "." if lang == "id" else ":"
    hours = f"{cfg['office_open'].replace(':', sep)}–{cfg['office_close'].replace(':', sep)}"
    return f"{', '.join(parts)}, {hours} {TZ_ABBR.get(env.timezone, env.timezone)}".strip()


async def maybe_send_away(
    session, conv: Conversation, cfg: Config, lang: str, now: datetime | None = None
) -> bool:
    """Send the away message if we're closed and haven't sent it this closed period."""
    now = now or utcnow()
    if is_open(cfg, now):
        return False
    since = closed_since(cfg, now)
    sent = conv.away_sent_at
    if sent is not None and sent.tzinfo is None:  # SQLite drops tzinfo
        sent = sent.replace(tzinfo=ZoneInfo("UTC"))
    if sent is not None and sent >= since:
        return False
    conv.away_sent_at = now
    await session.commit()
    hours = describe(cfg, lang)
    text = cfg.text("away_message", lang).replace("{jam}", hours).replace("{hours}", hours)
    await outbound.send_text(session, conv, text, sender_type=SENDER_BOT, meta={"away": True})
    return True
