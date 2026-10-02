"""Inbox: conversation list, thread, staff replies, Bot/Human toggle."""

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import events, serializers
from app.audit import audit
from app.constants import (
    CONV_OPEN,
    CONV_RESOLVED,
    HUMAN_AGENT_DAYS,
    MODE_BOT,
    MODE_HUMAN,
    SENDER_AGENT,
    SEVERITIES,
    SEVERITY_RANK,
)
from app.db import as_utc, get_session, utcnow
from app.deps import any_staff, can_act, client_ip
from app.models import AuditLog, Contact, Conversation, Message, StaffUser
from app.services import outbound

router = APIRouter(prefix="/conversations", tags=["inbox"])


async def get_conv(session: AsyncSession, conv_id: int) -> Conversation:
    conv = await session.get(Conversation, conv_id)
    if conv is None:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.get("")
async def list_conversations(
    channel: str | None = None,
    status: str | None = None,
    mode: str | None = None,
    flag: str | None = None,  # flagged | high | emergency
    q: str | None = None,
    assigned: str | None = None,  # me | none
    limit: int = 100,
    user: StaffUser = Depends(any_staff),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Conversation).join(Contact, Contact.id == Conversation.contact_id)
    if channel:
        stmt = stmt.where(Conversation.channel == channel)
    if status:
        stmt = stmt.where(Conversation.status == status)
    if mode:
        stmt = stmt.where(Conversation.mode == mode)
    if flag:
        floor = "low" if flag == "flagged" else flag
        if floor in SEVERITY_RANK:
            levels = [s for s in SEVERITIES if SEVERITY_RANK[s] >= SEVERITY_RANK[floor]]
            stmt = stmt.where(Conversation.flag_severity.in_(levels))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(Contact.display_name.ilike(like), Conversation.last_preview.ilike(like))
        )
    if assigned == "me":
        stmt = stmt.where(Conversation.assigned_to == user.id)
    elif assigned == "none":
        stmt = stmt.where(Conversation.assigned_to.is_(None))
    stmt = stmt.order_by(Conversation.last_message_at.desc().nulls_last()).limit(min(limit, 300))
    rows = (await session.execute(stmt)).scalars().all()
    return [serializers.conversation(c) for c in rows]


@router.get("/{conv_id}")
async def get_conversation(
    conv_id: int,
    request: Request,
    user: StaffUser = Depends(any_staff),
    session: AsyncSession = Depends(get_session),
):
    conv = await get_conv(session, conv_id)
    # Audit views, at most one row per staff member per conversation per 10 minutes.
    recent = (
        await session.execute(
            select(AuditLog.id).where(
                AuditLog.actor_id == user.id,
                AuditLog.action == "conversation.view",
                AuditLog.entity_id == str(conv_id),
                AuditLog.created_at > utcnow() - timedelta(minutes=10),
            )
        )
    ).first()
    if not recent:
        audit(session, user, "conversation.view", "conversation", conv_id, ip=client_ip(request))
        await session.commit()
    out = serializers.conversation(conv)
    out["contact"] = serializers.contact(conv.contact)
    return out


@router.get("/{conv_id}/messages")
async def list_messages(
    conv_id: int,
    limit: int = 200,
    user: StaffUser = Depends(any_staff),
    session: AsyncSession = Depends(get_session),
):
    await get_conv(session, conv_id)
    rows = (
        (
            await session.execute(
                select(Message)
                .where(Message.conversation_id == conv_id)
                .order_by(Message.id.desc())
                .limit(min(limit, 1000))
            )
        )
        .scalars()
        .all()
    )
    return [serializers.message(m) for m in reversed(rows)]


@router.post("/{conv_id}/read")
async def mark_read(
    conv_id: int, user: StaffUser = Depends(any_staff), session: AsyncSession = Depends(get_session)
):
    conv = await get_conv(session, conv_id)
    if conv.unread_count:
        conv.unread_count = 0
        await session.commit()
        await events.publish("conversation.updated", conversation_id=conv_id)
    return {"ok": True}


class ReplyIn(BaseModel):
    text: str = Field(min_length=1, max_length=4096)
    take_over: bool = True  # a staff reply switches the conversation to HUMAN


def reply_window(conv: Conversation) -> tuple[bool, bool, str]:
    """(allowed, use HUMAN_AGENT tag, reason). Simulated threads are never blocked."""
    if conv.simulated:
        return True, False, ""
    last_in = as_utc(conv.last_inbound_at)
    if last_in is None:
        return False, False, "The contact has never written; start with a template broadcast."
    age = utcnow() - last_in
    if age <= timedelta(hours=24):
        return True, False, ""
    if conv.channel in ("messenger", "instagram") and age <= timedelta(days=HUMAN_AGENT_DAYS):
        return True, True, ""
    if conv.channel == "whatsapp":
        return (
            False,
            False,
            "Outside WhatsApp's 24-hour window: only approved templates can be sent.",
        )
    return False, False, f"Outside the {HUMAN_AGENT_DAYS}-day human-agent window."


@router.post("/{conv_id}/messages")
async def reply(
    conv_id: int,
    body: ReplyIn,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    conv = await get_conv(session, conv_id)
    if conv.contact.opted_out:
        raise HTTPException(409, "This contact opted out (STOP). Messages can't be sent.")
    allowed, human_agent, reason = reply_window(conv)
    if not allowed:
        raise HTTPException(409, reason)
    if body.take_over and conv.mode != MODE_HUMAN:
        conv.mode = MODE_HUMAN
        await outbound.add_note(session, conv, f"Mode → HUMAN ({user.name or user.email} membalas)")
    if conv.assigned_to is None:
        conv.assigned_to = user.id
    audit(session, user, "conversation.reply", "conversation", conv_id,
          {"chars": len(body.text), "human_agent_tag": human_agent}, client_ip(request))  # fmt: skip
    msg = await outbound.send_text(
        session,
        conv,
        body.text.strip(),
        sender_type=SENDER_AGENT,
        staff=user,
        human_agent=human_agent,
    )
    await events.publish("conversation.updated", conversation_id=conv_id)
    if msg.status == "failed":
        raise HTTPException(502, f"Saved but not delivered: {msg.error}")
    return serializers.message(msg)


class ModeIn(BaseModel):
    mode: Literal["BOT", "HUMAN"]


@router.post("/{conv_id}/mode")
async def set_mode(
    conv_id: int,
    body: ModeIn,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    conv = await get_conv(session, conv_id)
    if conv.mode != body.mode:
        old, conv.mode = conv.mode, body.mode
        await outbound.add_note(session, conv, f"Mode → {body.mode} ({user.name or user.email})")
        audit(session, user, "conversation.mode", "conversation", conv_id,
              {"from": old, "to": body.mode}, client_ip(request))  # fmt: skip
        await session.commit()
        await events.publish("conversation.updated", conversation_id=conv_id)
    return serializers.conversation(conv)


class StatusIn(BaseModel):
    status: Literal["OPEN", "RESOLVED"]


@router.post("/{conv_id}/status")
async def set_status(
    conv_id: int,
    body: StatusIn,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    conv = await get_conv(session, conv_id)
    if conv.status != body.status:
        conv.status = body.status
        if body.status == CONV_RESOLVED:
            conv.unread_count = 0
        await outbound.add_note(
            session, conv, f"Status → {body.status} ({user.name or user.email})"
        )
        audit(session, user, "conversation.status", "conversation", conv_id,
              {"to": body.status}, client_ip(request))  # fmt: skip
        await session.commit()
        await events.publish("conversation.updated", conversation_id=conv_id)
    return serializers.conversation(conv)


class AssignIn(BaseModel):
    staff_id: int | None = None


@router.post("/{conv_id}/assign")
async def assign(
    conv_id: int,
    body: AssignIn,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    conv = await get_conv(session, conv_id)
    if body.staff_id is not None and not await session.get(StaffUser, body.staff_id):
        raise HTTPException(404, "Staff member not found")
    conv.assigned_to = body.staff_id
    audit(session, user, "conversation.assign", "conversation", conv_id,
          {"staff_id": body.staff_id}, client_ip(request))  # fmt: skip
    await session.commit()
    await events.publish("conversation.updated", conversation_id=conv_id)
    return serializers.conversation(conv)


__all__ = ["router", "get_conv", "reply_window", "CONV_OPEN", "MODE_BOT"]
