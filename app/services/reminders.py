"""Daily medication reminders for people on TB treatment.

The worker runs `tick()` every minute:
1. Contacts in the "treatment" stage with reminders on get today's reminder at
   their reminder time (local): "Sudah minum obat hari ini?" with Sudah / Belum
   buttons. Outside WhatsApp's 24-hour window only an approved template may be
   sent (Settings > Medication reminders); without one the day is "skipped".
2. A reminder still unanswered after N hours counts as missed and gets one
   gentle follow-up. Missed several days in a row -> an ADHERENCE case and a call
   task for the contact's kader.
Answers ("Sudah" / "Belum", tapped or typed) are picked up by the pipeline
(`handle_answer`) before the bot sees them.
"""

import logging
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import events
from app.config import settings as env
from app.constants import MSG_FAILED, SENDER_BOT
from app.db import SessionLocal, as_utc, utcnow
from app.models import Contact, Conversation, DoseLog, Message, Task
from app.services import cases, outbound, settings_service
from app.services.settings_service import Config

log = logging.getLogger("onti.reminders")

BUTTONS = [("dose_taken", "Sudah ✅"), ("dose_missed", "Belum")]
SEND_LATE_HOURS = 3  # after downtime, don't send a 07:00 reminder in the evening
STAGE_TREATMENT = "treatment"

_TAKEN = re.compile(
    r"^(sudah|udah|sdh|dah|done|yes|ya|iya|already|taken)( (minum|diminum))?( obat(nya)?)?$"
)
_MISSED = re.compile(
    r"^(belum|blm|lupa|not yet|no|tidak|nggak|gak|engga|enggak)( (minum|diminum))?( obat(nya)?)?$"
)


def parse_answer(text: str | None) -> str | None:
    """'Sudah ✅' -> taken, 'belum minum' -> missed, anything longer -> None (the bot)."""
    t = " ".join(re.sub(r"[^\w\s]", " ", (text or "").lower()).split())
    if _TAKEN.match(t):
        return "taken"
    if _MISSED.match(t):
        return "missed"
    return None


def _tz() -> ZoneInfo:
    return ZoneInfo(env.timezone)


def local_today(now: datetime | None = None) -> date:
    return (now or utcnow()).astimezone(_tz()).date()


def _first_name(c: Contact) -> str:
    return (c.display_name or "").split(" (")[0].split(" ")[0] or "Kak"


def _fill(text: str, c: Contact) -> str:
    name = _first_name(c)
    return text.replace("{nama}", name).replace("{name}", name)


async def conversation_for(session: AsyncSession, contact: Contact) -> Conversation | None:
    """The contact's most recently active conversation."""
    return (
        await session.execute(
            select(Conversation)
            .where(Conversation.contact_id == contact.id)
            .order_by(Conversation.last_inbound_at.desc().nulls_last())
            .limit(1)
        )
    ).scalar_one_or_none()


def _window_open(conv: Conversation, now: datetime) -> bool:
    return conv.simulated or (
        conv.window_expires_at is not None and as_utc(conv.window_expires_at) > now
    )


async def send_reminder(
    session: AsyncSession, contact: Contact, cfg: Config, day: date, now: datetime
) -> DoseLog:
    entry = DoseLog(contact_id=contact.id, day=day, status="skipped")
    session.add(entry)
    conv = await conversation_for(session, contact)
    if conv is None:
        entry.note = "no conversation"
    else:
        entry.conversation_id = conv.id
        text = _fill(cfg.text("reminder_text", "id"), contact)
        meta = {"reminder": day.isoformat()}
        msg: Message | None = None
        if _window_open(conv, now):
            msg = await outbound.send_text(session, conv, text, sender_type=SENDER_BOT,
                                           buttons=BUTTONS, meta=meta)  # fmt: skip
        elif conv.channel == "whatsapp" and cfg["reminder_template"]:
            msg = await outbound.send_template(session, conv, cfg["reminder_template"], "id",
                                               [_first_name(contact)], text, meta)  # fmt: skip
        else:
            entry.note = "outside the 24-hour window and no reminder template"
        if msg is not None and msg.status != MSG_FAILED:
            entry.status, entry.sent_at = "pending", now
        elif msg is not None:
            entry.note = f"send failed: {msg.error or ''}"[:200]
    await session.commit()
    return entry


async def _missed_streak(session: AsyncSession, contact_id: int) -> int:
    rows = (
        (
            await session.execute(
                select(DoseLog.status)
                .where(DoseLog.contact_id == contact_id, DoseLog.status != "skipped")
                .order_by(DoseLog.day.desc())
                .limit(14)
            )
        )
        .scalars()
        .all()
    )
    streak = 0
    for st in rows:
        if st != "missed":
            break
        streak += 1
    return streak


async def escalate_if_needed(
    session: AsyncSession, contact: Contact, conv: Conversation | None, cfg: Config, now: datetime
) -> None:
    """Missed `missed_case_after` days in a row: a case for staff, a call for the kader."""
    streak = await _missed_streak(session, contact.id)
    if streak < max(1, int(cfg["missed_case_after"])) or conv is None:
        return
    reason = f"{streak} hari berturut-turut tidak minum obat (pengingat)"
    await cases.open_case(session, conv, None, "low", "ADHERENCE", reason, to_human=False)
    open_task = (
        await session.execute(
            select(Task.id).where(
                Task.contact_id == contact.id, Task.status == "open", Task.source == "missed_doses"
            )  # fmt: skip
        )
    ).first()
    if open_task is None:
        session.add(Task(
            contact_id=contact.id, kind="call", source="missed_doses",
            title=f"Hubungi {contact.display_name}: {streak} hari tidak minum obat",
            due=local_today(now), assigned_to=contact.kader_id,
        ))  # fmt: skip
        await session.commit()
        await events.publish("task.created", contact_id=contact.id)


async def handle_answer(
    session: AsyncSession, conv: Conversation, msg: Message, cfg: Config, lang: str
) -> bool:
    """A reply to today's (or yesterday's) reminder. True when handled."""
    kind = parse_answer(msg.text)
    if kind is None:
        return False
    now = utcnow()
    entry = (
        await session.execute(
            select(DoseLog)
            .where(
                DoseLog.contact_id == conv.contact_id,
                DoseLog.day >= local_today(now) - timedelta(days=1),
                DoseLog.status.in_(("pending", "missed")),
                DoseLog.answered_at.is_(None),
            )
            .order_by(DoseLog.day.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if entry is None:
        return False
    entry.status, entry.answered_at = kind, now
    await session.commit()
    key = "reminder_taken" if kind == "taken" else "reminder_missed"
    await outbound.send_text(session, conv, _fill(cfg.text(key, lang), conv.contact),
                             sender_type=SENDER_BOT, meta={"dose": kind})  # fmt: skip
    if kind == "missed":
        await escalate_if_needed(session, conv.contact, conv, cfg, now)
    await events.publish("dose.updated", contact_id=conv.contact_id)
    return True


async def tick(now: datetime | None = None) -> dict:
    """Send due reminders and follow up on unanswered ones."""
    now = now or utcnow()
    local = now.astimezone(_tz())
    today = local.date()
    out = {"sent": 0, "skipped": 0, "followups": 0}
    async with SessionLocal() as session:
        cfg = await settings_service.load(session)
        if not cfg["reminder_enabled"]:
            return out
        contacts = (
            (
                await session.execute(
                    select(Contact).where(
                        Contact.reminder_enabled.is_(True),
                        Contact.journey_stage == STAGE_TREATMENT,
                        Contact.opted_out.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )
        asked = set(
            (
                await session.execute(select(DoseLog.contact_id).where(DoseLog.day == today))
            ).scalars()
        )
        for c in contacts:
            if c.id in asked:
                continue
            h, m = (int(x) for x in (c.reminder_time or "07:00").split(":"))
            due = datetime.combine(today, time(h, m), tzinfo=_tz())
            if local < due:
                continue
            if local - due > timedelta(hours=SEND_LATE_HOURS):
                session.add(DoseLog(contact_id=c.id, day=today, status="skipped",
                                    note="reminder time passed (hub was offline)"))  # fmt: skip
                await session.commit()
                out["skipped"] += 1
                continue
            entry = await send_reminder(session, c, cfg, today, now)
            out["sent" if entry.status == "pending" else "skipped"] += 1

        # Unanswered after N hours: missed, one follow-up, maybe escalate.
        cutoff = now - timedelta(hours=float(cfg["missed_followup_hours"]))
        stale = (
            (
                await session.execute(
                    select(DoseLog).where(DoseLog.status == "pending", DoseLog.sent_at <= cutoff)
                )
            )
            .scalars()
            .all()
        )
        for entry in stale:
            entry.status, entry.note = "missed", "no answer"
            contact = await session.get(Contact, entry.contact_id)
            conv = (
                await session.get(Conversation, entry.conversation_id)
                if entry.conversation_id
                else None
            )
            await session.commit()
            if conv is not None and not entry.followup_sent and _window_open(conv, now):
                entry.followup_sent = True
                await session.commit()
                await outbound.send_text(
                    session, conv, _fill(cfg.text("missed_followup", "id"), contact),
                    sender_type=SENDER_BOT, buttons=BUTTONS, meta={"reminder_followup": True},
                )  # fmt: skip
                out["followups"] += 1
            await escalate_if_needed(session, contact, conv, cfg, now)
    if any(out.values()):
        log.info("reminders: %s", out)
    return out
