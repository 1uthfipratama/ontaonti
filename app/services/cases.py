"""Cases: a flagged conversation that needs a person."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import events, notify
from app.bot.safety import Flag
from app.constants import (
    CASE_CLAIMED,
    CASE_OPEN,
    CASE_RESOLVED,
    MODE_BOT,
    MODE_HUMAN,
    SEVERITY_RANK,
    max_severity,
)
from app.db import utcnow
from app.models import Case, Conversation, Message, StaffUser
from app.services import outbound

log = logging.getLogger("onti.cases")


def flag_message(conv: Conversation, msg: Message, flag: Flag) -> None:
    """Record a flag on the message and raise the conversation's flag level."""
    if flag.severity == "none":
        return
    if SEVERITY_RANK.get(flag.severity, 0) >= SEVERITY_RANK.get(msg.flag_severity or "none", 0):
        msg.flag_severity = flag.severity
        msg.flag_category = flag.category
        msg.flag_reason = f"{flag.source}: {flag.reason}" if flag.source else flag.reason
    if SEVERITY_RANK[flag.severity] >= SEVERITY_RANK.get(conv.flag_severity or "none", 0):
        conv.flag_severity = flag.severity
        conv.flag_category = flag.category


async def active_case(session: AsyncSession, conv_id: int) -> Case | None:
    return (
        await session.execute(
            select(Case)
            .where(Case.conversation_id == conv_id, Case.status.in_((CASE_OPEN, CASE_CLAIMED)))
            .order_by(Case.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def open_case(
    session: AsyncSession,
    conv: Conversation,
    msg: Message | None,
    severity: str,
    category: str,
    reason: str,
    *,
    to_human: bool,
) -> Case:
    """Create a case, or raise the open one; optionally hand the chat to staff.
    Commits, publishes events and emails staff (if SMTP is set)."""
    case = await active_case(session, conv.id)
    created = case is None
    if created:
        case = Case(
            conversation_id=conv.id,
            contact_id=conv.contact_id,
            severity=severity,
            category=category,
            reason=reason,
            trigger_message_id=msg.id if msg else None,
        )
        session.add(case)
    else:
        if SEVERITY_RANK[severity] > SEVERITY_RANK.get(case.severity, 0):
            case.severity, case.category = severity, category
            case.trigger_message_id = msg.id if msg else case.trigger_message_id
        case.reason = (case.reason + f"\n{reason}").strip()[-2000:]
    if to_human and conv.mode != MODE_HUMAN:
        conv.mode = MODE_HUMAN
        await outbound.add_note(session, conv, f"Mode → HUMAN (otomatis: {category} {severity})")
    conv.flag_severity = max_severity(conv.flag_severity, severity)
    await session.commit()
    await events.publish(
        "case.created" if created else "case.updated",
        case_id=case.id,
        conversation_id=conv.id,
        severity=case.severity,
        category=case.category,
        contact_name=conv.contact.display_name if conv.contact else "",
    )
    await events.publish("conversation.updated", conversation_id=conv.id)
    if created and SEVERITY_RANK[severity] >= SEVERITY_RANK["high"]:
        subject, body = notify.case_email(
            case.id, severity, category,
            conv.contact.display_name if conv.contact else "?", conv.channel,
            msg.text if msg else reason,
        )  # fmt: skip
        await notify.email_staff(subject, body)
    log.info("case %s %s: %s %s (conversation %s)", case.id,
             "created" if created else "updated", severity, category, conv.id)  # fmt: skip
    return case


async def resolve(session: AsyncSession, case: Case, user: StaffUser, return_to_bot: bool) -> Case:
    case.status = CASE_RESOLVED
    case.resolved_at = utcnow()
    case.resolved_by = user.id
    conv = await session.get(Conversation, case.conversation_id)
    if conv is not None:
        others = await active_case(session, conv.id)
        if others is None or others.id == case.id:
            conv.flag_severity, conv.flag_category = "none", None
        if return_to_bot and conv.mode != MODE_BOT:
            conv.mode = MODE_BOT
            await outbound.add_note(
                session, conv, f"Kasus #{case.id} selesai → Mode BOT ({user.name or user.email})"
            )
    await session.commit()
    await events.publish("case.updated", case_id=case.id, conversation_id=case.conversation_id)
    await events.publish("conversation.updated", conversation_id=case.conversation_id)
    return case
