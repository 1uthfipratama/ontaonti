"""Delivery / read / failed updates from channel webhooks."""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import events
from app.channels.base import StatusUpdate
from app.constants import DIR_OUT, MSG_DELIVERED, MSG_FAILED, MSG_READ, MSG_SENT, STATUS_ORDER
from app.models import ContactIdentity, Conversation, Message


async def apply_status(session: AsyncSession, st: StatusUpdate) -> Message | None:
    msg = (
        await session.execute(select(Message).where(Message.external_id == st.external_message_id))
    ).scalar_one_or_none()
    if msg is None:
        return None
    if st.status == MSG_FAILED:
        msg.status, msg.error = MSG_FAILED, st.error or "failed"
    elif STATUS_ORDER.get(st.status, -1) > STATUS_ORDER.get(msg.status, -1):
        msg.status = st.status  # only move forward: sent -> delivered -> read
    meta = dict(msg.meta or {})
    meta[f"{st.status}_at"] = st.timestamp.isoformat()
    msg.meta = meta
    await _broadcast_hook(session, msg, st)
    await session.commit()
    await events.publish("message.created", conversation_id=msg.conversation_id, message_id=msg.id)
    return msg


async def apply_read_watermark(
    session: AsyncSession, channel: str, user_id: str, watermark: datetime
) -> int:
    """Messenger/Instagram 'read' events: everything sent before the watermark."""
    conv_ids = (
        select(Conversation.id)
        .join(ContactIdentity, ContactIdentity.id == Conversation.identity_id)
        .where(ContactIdentity.channel == channel, ContactIdentity.external_id == user_id)
    )
    res = await session.execute(
        update(Message)
        .where(
            Message.conversation_id.in_(conv_ids),
            Message.direction == DIR_OUT,
            Message.status.in_((MSG_SENT, MSG_DELIVERED)),
            Message.created_at <= watermark,
        )
        .values(status=MSG_READ)
    )
    await session.commit()
    return res.rowcount or 0


async def _broadcast_hook(session: AsyncSession, msg: Message, st: StatusUpdate) -> None:
    """Phase 4 keeps broadcast recipients in step with their message."""
    from app.services import broadcasts

    await broadcasts.on_message_status(session, msg, st)
