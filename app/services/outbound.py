"""Send a message on a conversation's channel and keep the stored copy in sync."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app import events
from app.channels.base import SendError
from app.channels.registry import adapter_for
from app.constants import DIR_NOTE, DIR_OUT, MSG_FAILED, MSG_QUEUED, MSG_SENT, SENDER_SYSTEM
from app.db import utcnow
from app.models import Conversation, Message, StaffUser

log = logging.getLogger("onti.outbound")


async def send_text(
    session: AsyncSession,
    conv: Conversation,
    text: str,
    *,
    sender_type: str,
    staff: StaffUser | None = None,
    meta: dict | None = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_idr: float = 0.0,
    human_agent: bool = False,
) -> Message:
    """Store first (status queued), then send, then record the outcome. A failed
    send stays visible in the thread with its error instead of vanishing."""
    msg = Message(
        conversation_id=conv.id,
        direction=DIR_OUT,
        sender_type=sender_type,
        sender_staff_id=staff.id if staff else None,
        text=text,
        status=MSG_QUEUED,
        meta=meta or {},
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_idr=cost_idr,
    )
    session.add(msg)
    now = utcnow()
    conv.last_message_at = now
    conv.last_preview = text[:200]
    await session.commit()
    try:
        external_id = await adapter_for(conv).send(conv, text, human_agent=human_agent)
        msg.external_id = external_id
        msg.status = MSG_SENT
    except SendError as e:
        msg.status = MSG_FAILED
        msg.error = str(e)[:500]
        log.warning("send failed on conversation %s: %s", conv.id, e)
    except Exception as e:  # never lose the stored copy over an adapter bug
        msg.status = MSG_FAILED
        msg.error = f"unexpected error: {type(e).__name__}"
        log.exception("send crashed on conversation %s", conv.id)
    await session.commit()
    await events.publish("message.created", conversation_id=conv.id, message_id=msg.id)
    return msg


async def add_note(
    session: AsyncSession, conv: Conversation, text: str, meta: dict | None = None
) -> Message:
    """Internal note in the thread (never sent): mode switches, assignments, flags."""
    msg = Message(
        conversation_id=conv.id,
        direction=DIR_NOTE,
        sender_type=SENDER_SYSTEM,
        text=text,
        status=MSG_SENT,
        meta=meta or {},
    )
    session.add(msg)
    await session.flush()
    return msg
