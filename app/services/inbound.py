"""Store an inbound message: dedupe, find or create contact/identity/conversation."""

import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import events
from app.channels.base import InternalMessage
from app.constants import (
    CONV_OPEN,
    CONV_RESOLVED,
    DIR_IN,
    MSG_RECEIVED,
    SENDER_USER,
    WINDOW_HOURS,
)
from app.models import Contact, ContactIdentity, Conversation, Message

log = logging.getLogger("onti.inbound")

NON_TEXT_LABELS = {
    "image": "[gambar]",
    "audio": "[pesan suara]",
    "video": "[video]",
    "document": "[dokumen]",
    "sticker": "[stiker]",
    "location": "[lokasi]",
    "contacts": "[kontak]",
}


@dataclass
class Ingested:
    message: Message
    conversation: Conversation
    new_contact: bool


async def is_duplicate(session: AsyncSession, external_id: str) -> bool:
    found = await session.execute(select(Message.id).where(Message.external_id == external_id))
    return found.first() is not None


async def get_or_create_identity(
    session: AsyncSession, channel: str, external_id: str, name: str, simulated: bool
) -> tuple[ContactIdentity, bool]:
    ident = (
        await session.execute(
            select(ContactIdentity).where(
                ContactIdentity.channel == channel, ContactIdentity.external_id == external_id
            )
        )
    ).scalar_one_or_none()
    if ident:
        if name and not ident.display_name:
            ident.display_name = name
        return ident, False
    phone = external_id if channel == "whatsapp" and not simulated else None
    contact = Contact(display_name=name or external_id, phone=phone)
    session.add(contact)
    await session.flush()
    ident = ContactIdentity(
        contact_id=contact.id,
        channel=channel,
        external_id=external_id,
        display_name=name,
        simulated=simulated,
    )
    session.add(ident)
    await session.flush()
    return ident, True


async def conversation_for(session: AsyncSession, ident: ContactIdentity) -> Conversation:
    """One running thread per identity; a resolved thread reopens on a new message."""
    conv = (
        await session.execute(
            select(Conversation)
            .where(Conversation.identity_id == ident.id)
            .order_by(Conversation.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if conv is None:
        conv = Conversation(
            contact_id=ident.contact_id,
            identity_id=ident.id,
            channel=ident.channel,
            simulated=ident.simulated,
        )
        session.add(conv)
        await session.flush()
    return conv


async def ingest(session: AsyncSession, im: InternalMessage) -> Ingested | None:
    """Returns None for a message already stored (redelivered webhook)."""
    if await is_duplicate(session, im.external_message_id):
        log.info("duplicate inbound %s ignored", im.external_message_id)
        return None
    ident, new_contact = await get_or_create_identity(
        session, im.channel, im.external_user_id, im.user_name, im.simulated
    )
    conv = await conversation_for(session, ident)
    text = (
        im.text if im.kind == "text" else (im.text or NON_TEXT_LABELS.get(im.kind, f"[{im.kind}]"))
    )
    msg = Message(
        conversation_id=conv.id,
        direction=DIR_IN,
        sender_type=SENDER_USER,
        text=text,
        kind=im.kind,
        media_url=im.media_url,
        external_id=im.external_message_id,
        status=MSG_RECEIVED,
        created_at=im.timestamp,
        meta={
            **({"user_name": im.user_name} if im.user_name else {}),
            # The text is only a "[pesan suara]"-style label: the UI hides it next to the file.
            **({"placeholder": True} if im.kind != "text" and not im.text else {}),
        },
    )
    session.add(msg)
    ident.last_seen_at = im.timestamp
    if conv.status == CONV_RESOLVED:
        conv.status = CONV_OPEN
    conv.last_message_at = im.timestamp
    conv.last_inbound_at = im.timestamp
    conv.window_expires_at = im.timestamp + timedelta(hours=WINDOW_HOURS)
    conv.last_preview = text[:200]
    conv.unread_count = (conv.unread_count or 0) + 1
    try:
        await session.commit()
    except IntegrityError:  # lost a race with a concurrent redelivery
        await session.rollback()
        log.info("duplicate inbound %s (race) ignored", im.external_message_id)
        return None
    await events.publish("message.created", conversation_id=conv.id, message_id=msg.id)
    if new_contact:
        await events.publish("contact.created", contact_id=ident.contact_id)
    return Ingested(msg, conv, new_contact)
