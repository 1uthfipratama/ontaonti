"""WhatsApp broadcasts: approved template + variables, sent only to contacts who
gave broadcast consent, through the queue with a rate limit and retries.

Business-initiated messages on WhatsApp must use an approved template; free text
is only allowed inside the 24 h window. Delivery/read come back via webhooks.
"""

import logging
import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import events, queue
from app.channels.base import SendError
from app.config import settings
from app.constants import DIR_OUT, MSG_SENT, SENDER_SYSTEM
from app.db import SessionLocal, utcnow
from app.models import (
    Broadcast,
    BroadcastRecipient,
    Contact,
    ContactIdentity,
    Message,
    StaffUser,
    WaTemplate,
)
from app.services.inbound import conversation_for
from app.services.settings_service import Config

log = logging.getLogger("onti.broadcasts")
PLACEHOLDER = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")
NAME_TOKEN = "{{name}}"


# --- templates ---------------------------------------------------------------------


def body_of(components: list[dict]) -> str:
    return next((c.get("text", "") for c in components or [] if c.get("type") == "BODY"), "")


def count_variables(body: str) -> int:
    return len(dict.fromkeys(PLACEHOLDER.findall(body or "")))


async def sync_templates(session: AsyncSession) -> int:
    from app.channels.whatsapp import WhatsAppAdapter

    remote = await WhatsAppAdapter().list_templates()
    for t in remote:
        row = (
            await session.execute(
                select(WaTemplate).where(
                    WaTemplate.name == t["name"], WaTemplate.language == t["language"]
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = WaTemplate(name=t["name"], language=t["language"])
            session.add(row)
        body = body_of(t.get("components") or [])
        row.category = t.get("category", "UTILITY")
        row.status = t.get("status", "UNKNOWN")
        row.components = t.get("components") or []
        row.body_text = body
        row.variable_count = count_variables(body)
        row.source = "sync"
    await session.commit()
    return len(remote)


# --- recipients & cost ---------------------------------------------------------------


async def eligible(session: AsyncSession) -> list[tuple[Contact, ContactIdentity]]:
    """Contacts with broadcast consent, not opted out, with a WhatsApp identity
    (simulated identities included, so the flow can be demoed without Meta)."""
    rows = (
        await session.execute(
            select(Contact, ContactIdentity)
            .join(ContactIdentity, ContactIdentity.contact_id == Contact.id)
            .where(
                Contact.broadcast_opt_in.is_(True),
                Contact.opted_out.is_(False),
                ContactIdentity.channel == "whatsapp",
            )
            .order_by(Contact.id, ContactIdentity.simulated, ContactIdentity.id)
        )
    ).all()
    seen, out = set(), []
    for contact, ident in rows:  # one identity per contact (real before simulated)
        if contact.id not in seen:
            seen.add(contact.id)
            out.append((contact, ident))
    return out


def rate_for(template: WaTemplate, cfg: Config) -> float:
    if template.category == "MARKETING":
        return float(cfg["wa_rate_marketing_idr"])
    return float(cfg["wa_rate_utility_idr"])  # UTILITY / AUTHENTICATION / manual


def params_for(variables: list[str], contact: Contact) -> list[str]:
    return [
        (contact.display_name or "Kak") if (v or "").strip() == NAME_TOKEN else (v or "")
        for v in variables
    ]


def render(template: WaTemplate, params: list[str]) -> str:
    keys = list(dict.fromkeys(PLACEHOLDER.findall(template.body_text or "")))
    values = dict(zip(keys, params, strict=False))
    text = PLACEHOLDER.sub(lambda m: values.get(m.group(1).strip(), m.group(0)), template.body_text)
    return text or f"[template {template.name}]"


async def estimate(
    session: AsyncSession, template: WaTemplate, variables: list[str], cfg: Config
) -> dict:
    recipients = await eligible(session)
    rate = rate_for(template, cfg)
    month_start = utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = (
        await session.execute(
            select(func.count())
            .select_from(BroadcastRecipient)
            .where(BroadcastRecipient.sent_at >= month_start)
        )
    ).scalar_one()
    preview = render(template, params_for(variables, recipients[0][0])) if recipients else ""
    return {
        "recipients": len(recipients),
        "sample": [c.display_name for c, _ in recipients[:10]],
        "simulated": sum(1 for _, i in recipients if i.simulated),
        "rate_idr": rate,
        "total_idr": rate * len(recipients),
        "category": template.category,
        "preview": preview,
        "template_messages_this_month": used,
        "free_tier": int(cfg["wa_free_tier_messages"]),
    }


# --- create / send -------------------------------------------------------------------


async def create(session: AsyncSession, name: str, template: WaTemplate, variables: list[str],
                 user: StaffUser, cfg: Config) -> Broadcast:  # fmt: skip
    recipients = await eligible(session)
    rate = rate_for(template, cfg)
    bc = Broadcast(
        name=name, template_id=template.id, variables=variables, created_by=user.id,
        recipient_count=len(recipients), rate_idr=rate, est_cost_idr=rate * len(recipients),
    )  # fmt: skip
    session.add(bc)
    await session.flush()
    for contact, ident in recipients:
        session.add(
            BroadcastRecipient(broadcast_id=bc.id, contact_id=contact.id, identity_id=ident.id)
        )
    await session.commit()
    return bc


async def start(session: AsyncSession, bc: Broadcast) -> int:
    """Queue one job per recipient, spaced out to respect the send rate."""
    bc.status, bc.started_at = "sending", utcnow()
    await session.commit()
    ids = (
        (
            await session.execute(
                select(BroadcastRecipient.id)
                .where(
                    BroadcastRecipient.broadcast_id == bc.id, BroadcastRecipient.status == "pending"
                )
                .order_by(BroadcastRecipient.id)
            )
        )
        .scalars()
        .all()
    )
    rate = max(settings.broadcast_rate_per_second, 0.1)
    for i, rid in enumerate(ids):
        await queue.enqueue(
            "send_broadcast_recipient", rid, _job_id=f"bc-{rid}", _defer_by=i / rate
        )
    await events.publish("broadcast.updated", broadcast_id=bc.id)
    if not ids:
        await _maybe_finish(session, bc.id)
    return len(ids)


class RetryLater(Exception):
    def __init__(self, delay: float) -> None:
        self.delay = delay


async def send_one(recipient_id: int) -> None:
    """Worker job body. Raises RetryLater on a retryable failure (arq re-queues)."""
    async with SessionLocal() as s:
        r = await s.get(BroadcastRecipient, recipient_id)
        if r is None or r.status != "pending":
            return
        bc = await s.get(Broadcast, r.broadcast_id)
        if bc is None or bc.status != "sending":
            return
        contact = await s.get(Contact, r.contact_id)
        ident = await s.get(ContactIdentity, r.identity_id)
        template = await s.get(WaTemplate, bc.template_id)
        if contact.opted_out or not contact.broadcast_opt_in:
            r.status, r.error = "skipped", "consent withdrawn before sending"
            await s.commit()
            await _maybe_finish(s, bc.id)
            return
        params = params_for(bc.variables or [], contact)
        r.attempts += 1
        try:
            if ident.simulated:
                from app.channels.simulator import SimulatorAdapter

                wamid = await SimulatorAdapter().send(None, render(template, params))
            else:
                from app.channels.whatsapp import WhatsAppAdapter

                wamid = await WhatsAppAdapter().send_template(
                    ident.external_id, template.name, template.language, params
                )
        except SendError as e:
            if e.retryable and r.attempts < settings.broadcast_max_attempts:
                await s.commit()
                raise RetryLater(min(5 * 2**r.attempts, 120)) from e
            r.status, r.error = "failed", str(e)[:500]
            await s.commit()
            await _maybe_finish(s, bc.id)
            return
        conv = await conversation_for(s, ident)
        msg = Message(
            conversation_id=conv.id, direction=DIR_OUT, sender_type=SENDER_SYSTEM,
            text=render(template, params), status=MSG_SENT, external_id=wamid,
            meta={"broadcast_id": bc.id, "template": template.name},
        )  # fmt: skip
        s.add(msg)
        await s.flush()
        conv.last_message_at, conv.last_preview = utcnow(), msg.text[:200]
        r.status, r.message_id, r.external_id, r.sent_at = "sent", msg.id, wamid, utcnow()
        await s.commit()
        await events.publish("message.created", conversation_id=conv.id, message_id=msg.id)
        await _maybe_finish(s, bc.id)


async def _maybe_finish(session: AsyncSession, broadcast_id: int) -> None:
    pending = (
        await session.execute(
            select(func.count())
            .select_from(BroadcastRecipient)
            .where(
                BroadcastRecipient.broadcast_id == broadcast_id,
                BroadcastRecipient.status == "pending",
            )
        )
    ).scalar_one()
    bc = await session.get(Broadcast, broadcast_id)
    if pending == 0 and bc and bc.status == "sending":
        bc.status, bc.finished_at = "done", utcnow()
        await session.commit()
    await events.publish("broadcast.updated", broadcast_id=broadcast_id)


async def cancel(session: AsyncSession, bc: Broadcast) -> None:
    rows = (
        await session.execute(
            select(BroadcastRecipient).where(
                BroadcastRecipient.broadcast_id == bc.id, BroadcastRecipient.status == "pending"
            )
        )
    ).scalars()
    for r in rows:
        r.status, r.error = "skipped", "cancelled"
    bc.status, bc.finished_at = "cancelled", utcnow()
    await session.commit()
    await events.publish("broadcast.updated", broadcast_id=bc.id)


async def stats(session: AsyncSession, broadcast_id: int) -> dict:
    rows = (
        await session.execute(
            select(BroadcastRecipient.status, func.count())
            .where(BroadcastRecipient.broadcast_id == broadcast_id)
            .group_by(BroadcastRecipient.status)
        )
    ).all()
    counts = {s: n for s, n in rows}
    # "delivered" includes read; "sent" includes everything that left us.
    read = counts.get("read", 0)
    delivered = counts.get("delivered", 0) + read
    sent = counts.get("sent", 0) + delivered
    return {
        "counts": counts,
        "sent": sent,
        "delivered": delivered,
        "read": read,
        "failed": counts.get("failed", 0),
        "pending": counts.get("pending", 0),
        "skipped": counts.get("skipped", 0),
    }


# --- webhook status hook ---------------------------------------------------------------

ORDER = {"pending": 0, "sent": 1, "delivered": 2, "read": 3}


async def on_message_status(session: AsyncSession, msg: Message, st) -> None:
    r = (
        await session.execute(
            select(BroadcastRecipient).where(BroadcastRecipient.message_id == msg.id)
        )
    ).scalar_one_or_none()
    if r is None:
        return
    if st.status == "failed":
        r.status, r.error = "failed", st.error or "failed"
    elif ORDER.get(st.status, -1) > ORDER.get(r.status, -1):
        r.status = st.status
    if st.status == "delivered":
        r.delivered_at = r.delivered_at or st.timestamp
    if st.status == "read":
        r.read_at = st.timestamp
        r.delivered_at = r.delivered_at or st.timestamp
    await events.publish("broadcast.updated", broadcast_id=r.broadcast_id)
