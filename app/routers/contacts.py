"""Contacts: one person, several channel identities; merge and cross-channel timeline."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import events, serializers
from app.audit import audit
from app.db import get_session
from app.deps import any_staff, can_act, client_ip
from app.models import Case, Consent, Contact, ContactIdentity, Conversation, Message, StaffUser
from app.services import consent as consent_service

router = APIRouter(prefix="/contacts", tags=["contacts"])


async def _get(session: AsyncSession, contact_id: int) -> Contact:
    c = await session.get(Contact, contact_id)
    if c is None:
        raise HTTPException(404, "Contact not found")
    return c


@router.get("")
async def list_contacts(
    q: str | None = None,
    limit: int = 200,
    user: StaffUser = Depends(any_staff),
    session: AsyncSession = Depends(get_session),
):
    last = (
        select(Conversation.contact_id, func.max(Conversation.last_message_at).label("last"))
        .group_by(Conversation.contact_id)
        .subquery()
    )
    stmt = select(Contact, last.c.last).outerjoin(last, last.c.contact_id == Contact.id)
    if q:
        like = f"%{q.strip()}%"
        ids = select(ContactIdentity.contact_id).where(ContactIdentity.external_id.ilike(like))
        stmt = stmt.where(
            or_(Contact.display_name.ilike(like), Contact.phone.ilike(like), Contact.id.in_(ids))
        )
    stmt = stmt.order_by(last.c.last.desc().nulls_last(), Contact.id.desc()).limit(min(limit, 500))
    rows = (await session.execute(stmt)).all()
    return [{**serializers.contact(c), "last_message_at": serializers.iso(ts)} for c, ts in rows]


@router.get("/{contact_id}")
async def get_contact(
    contact_id: int,
    user: StaffUser = Depends(any_staff),
    session: AsyncSession = Depends(get_session),
):
    c = await _get(session, contact_id)
    consents = (
        (
            await session.execute(
                select(Consent).where(Consent.contact_id == contact_id).order_by(Consent.id)
            )
        )
        .scalars()
        .all()
    )
    convs = (
        (await session.execute(select(Conversation).where(Conversation.contact_id == contact_id)))
        .scalars()
        .all()
    )
    return {
        **serializers.contact(c),
        "consents": [
            {
                "kind": k.kind,
                "status": k.status,
                "source": k.source,
                "channel": k.channel,
                "created_at": serializers.iso(k.created_at),
            }
            for k in consents
        ],
        "conversations": [serializers.conversation(v) for v in convs],
    }


@router.get("/{contact_id}/timeline")
async def timeline(
    contact_id: int,
    limit: int = 500,
    user: StaffUser = Depends(any_staff),
    session: AsyncSession = Depends(get_session),
):
    """Every message with this person, across all channels, oldest first."""
    await _get(session, contact_id)
    rows = (
        await session.execute(
            select(Message, Conversation.channel)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(Conversation.contact_id == contact_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(min(limit, 2000))
        )
    ).all()
    return [{**serializers.message(m), "channel": ch} for m, ch in reversed(rows)]


class ContactPatch(BaseModel):
    display_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=5000)


@router.patch("/{contact_id}")
async def update_contact(
    contact_id: int,
    body: ContactPatch,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    c = await _get(session, contact_id)
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(c, k, v)
    audit(session, user, "contact.update", "contact", contact_id, {"fields": sorted(changes)},
          client_ip(request))  # fmt: skip
    await session.commit()
    await events.publish("contact.updated", contact_id=contact_id)
    return serializers.contact(c)


class MergeIn(BaseModel):
    source_contact_id: int


@router.post("/{contact_id}/merge")
async def merge(
    contact_id: int,
    body: MergeIn,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    """Fold another contact into this one: identities, conversations, cases and
    consents move over; the other contact is deleted. Opt-out wins."""
    if body.source_contact_id == contact_id:
        raise HTTPException(400, "Can't merge a contact into itself")
    target = await _get(session, contact_id)
    source = await _get(session, body.source_contact_id)
    for model in (ContactIdentity, Conversation, Case, Consent):
        await session.execute(
            update(model).where(model.contact_id == source.id).values(contact_id=target.id)
        )
    target.opted_out = target.opted_out or source.opted_out
    target.opted_out_at = target.opted_out_at or source.opted_out_at
    target.broadcast_opt_in = (
        target.broadcast_opt_in or source.broadcast_opt_in
    ) and not target.opted_out
    target.phone = target.phone or source.phone
    if source.notes:
        target.notes = (target.notes + "\n" + source.notes).strip()
    audit(session, user, "contact.merge", "contact", contact_id,
          {"merged": source.id, "merged_name": source.display_name}, client_ip(request))  # fmt: skip
    await session.flush()
    session.expunge(source)  # its identities now belong to target; don't cascade-delete them
    await session.execute(Contact.__table__.delete().where(Contact.id == body.source_contact_id))
    await session.commit()
    await session.refresh(target, ["identities"])
    await events.publish("contact.updated", contact_id=contact_id)
    return serializers.contact(target)


class ConsentIn(BaseModel):
    broadcast: bool


@router.post("/{contact_id}/consent")
async def set_broadcast_consent(
    contact_id: int,
    body: ConsentIn,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    """Record broadcast consent given outside the chat (e.g. a signed form)."""
    c = await _get(session, contact_id)
    if body.broadcast and c.opted_out:
        raise HTTPException(409, "Contact opted out (STOP); they must send MULAI first")
    consent_service.subscribe(session, c, body.broadcast, None, f"staff:{user.id}")
    audit(session, user, "contact.consent", "contact", contact_id, {"broadcast": body.broadcast},
          client_ip(request))  # fmt: skip
    await session.commit()
    await events.publish("contact.updated", contact_id=contact_id)
    return serializers.contact(c)
