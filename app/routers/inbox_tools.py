"""Inbox tools: saved replies, labels, internal notes, AI-suggested replies."""

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import events, serializers
from app.audit import audit
from app.constants import DIR_IN, DIR_NOTE, MSG_SENT, SENDER_AGENT
from app.db import get_session
from app.deps import any_staff, can_act, client_ip
from app.models import ConversationLabel, Label, Message, SavedReply, StaffUser
from app.routers.conversations import get_conv

router = APIRouter(tags=["inbox-tools"])


# --- saved replies ------------------------------------------------------------------


def _reply_json(r: SavedReply) -> dict:
    return {"id": r.id, "shortcut": r.shortcut, "title": r.title, "body": r.body}


class SavedReplyIn(BaseModel):
    shortcut: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=4000)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", s.strip().lower()).strip("-")[:40]


@router.get("/saved-replies")
async def list_replies(
    user: StaffUser = Depends(any_staff), session: AsyncSession = Depends(get_session)
):
    rows = (await session.execute(select(SavedReply).order_by(SavedReply.shortcut))).scalars().all()
    return [_reply_json(r) for r in rows]


@router.post("/saved-replies")
async def create_reply(
    body: SavedReplyIn,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    r = SavedReply(shortcut=_slug(body.shortcut), title=body.title.strip(), body=body.body.strip(),
                   created_by=user.id)  # fmt: skip
    if not r.shortcut:
        raise HTTPException(422, "Shortcut needs letters or numbers")
    session.add(r)
    try:
        await session.flush()
    except IntegrityError as e:
        raise HTTPException(409, "Shortcut already exists") from e
    audit(
        session,
        user,
        "reply.create",
        "saved_reply",
        r.id,
        {"shortcut": r.shortcut},
        client_ip(request),
    )
    await session.commit()
    return _reply_json(r)


@router.put("/saved-replies/{reply_id}")
async def update_reply(
    reply_id: int,
    body: SavedReplyIn,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    r = await session.get(SavedReply, reply_id)
    if r is None:
        raise HTTPException(404, "Not found")
    r.shortcut, r.title, r.body = _slug(body.shortcut), body.title.strip(), body.body.strip()
    audit(session, user, "reply.update", "saved_reply", r.id, ip=client_ip(request))
    try:
        await session.commit()
    except IntegrityError as e:
        raise HTTPException(409, "Shortcut already exists") from e
    return _reply_json(r)


@router.delete("/saved-replies/{reply_id}")
async def delete_reply(
    reply_id: int,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    r = await session.get(SavedReply, reply_id)
    if r is None:
        raise HTTPException(404, "Not found")
    await session.delete(r)
    audit(session, user, "reply.delete", "saved_reply", reply_id, ip=client_ip(request))
    await session.commit()
    return {"ok": True}


# --- labels -----------------------------------------------------------------------


class LabelIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)


@router.get("/labels")
async def list_labels(
    user: StaffUser = Depends(any_staff), session: AsyncSession = Depends(get_session)
):
    rows = (await session.execute(select(Label).order_by(Label.name))).scalars().all()
    return [{"id": lb.id, "name": lb.name} for lb in rows]


@router.post("/labels")
async def create_label(
    body: LabelIn,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    name = " ".join(body.name.split())
    existing = (await session.execute(select(Label).where(Label.name == name))).scalar_one_or_none()
    if existing:
        return {"id": existing.id, "name": existing.name}
    lb = Label(name=name)
    session.add(lb)
    await session.flush()
    audit(session, user, "label.create", "label", lb.id, {"name": name}, client_ip(request))
    await session.commit()
    return {"id": lb.id, "name": lb.name}


@router.delete("/labels/{label_id}")
async def delete_label(
    label_id: int,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    lb = await session.get(Label, label_id)
    if lb is None:
        raise HTTPException(404, "Not found")
    await session.delete(lb)
    audit(session, user, "label.delete", "label", label_id, {"name": lb.name}, client_ip(request))
    await session.commit()
    return {"ok": True}


class ConversationLabelIn(BaseModel):
    label_id: int


@router.post("/conversations/{conv_id}/labels")
async def add_label(
    conv_id: int,
    body: ConversationLabelIn,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    await get_conv(session, conv_id)
    if await session.get(Label, body.label_id) is None:
        raise HTTPException(404, "Label not found")
    if await session.get(ConversationLabel, (conv_id, body.label_id)) is None:
        session.add(ConversationLabel(conversation_id=conv_id, label_id=body.label_id))
        audit(session, user, "conversation.label", "conversation", conv_id,
              {"label_id": body.label_id}, client_ip(request))  # fmt: skip
        await session.commit()
    await events.publish("conversation.updated", conversation_id=conv_id)
    return {"ok": True}


@router.delete("/conversations/{conv_id}/labels/{label_id}")
async def remove_label(
    conv_id: int,
    label_id: int,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    await session.execute(
        delete(ConversationLabel).where(
            ConversationLabel.conversation_id == conv_id, ConversationLabel.label_id == label_id
        )
    )
    audit(session, user, "conversation.unlabel", "conversation", conv_id, {"label_id": label_id},
          client_ip(request))  # fmt: skip
    await session.commit()
    await events.publish("conversation.updated", conversation_id=conv_id)
    return {"ok": True}


# --- internal notes ---------------------------------------------------------------


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("/conversations/{conv_id}/notes")
async def add_note(
    conv_id: int,
    body: NoteIn,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    """Staff-only note inside the thread; never sent to the contact."""
    conv = await get_conv(session, conv_id)
    msg = Message(conversation_id=conv.id, direction=DIR_NOTE, sender_type=SENDER_AGENT,
                  sender_staff_id=user.id, text=body.text.strip(), status=MSG_SENT)  # fmt: skip
    session.add(msg)
    await session.flush()
    audit(session, user, "conversation.note", "conversation", conv_id, {"chars": len(body.text)},
          client_ip(request))  # fmt: skip
    await session.commit()
    await events.publish("message.created", conversation_id=conv_id, message_id=msg.id)
    return serializers.message(msg)


# --- AI-suggested reply --------------------------------------------------------------

SUGGEST_INSTRUCTION = (
    "You are drafting a reply that a human staff member of the foundation will review, "
    "edit and send under their own name. Write it as that staff member (not as the bot): "
    "warm, short, practical, same rules about diagnosis and medicines. Do not mention "
    "that you are an AI."
)


@router.post("/conversations/{conv_id}/suggest")
async def suggest_reply(
    conv_id: int,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    """Draft a reply from the knowledge base for staff to edit. Never sent automatically."""
    from app import llm
    from app.bot import answer
    from app.services import limits, settings_service

    conv = await get_conv(session, conv_id)
    last_in = (
        await session.execute(
            select(Message)
            .where(Message.conversation_id == conv_id, Message.direction == DIR_IN)
            .order_by(Message.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if last_in is None or not (last_in.text or "").strip():
        raise HTTPException(409, "No message from the contact to answer yet")
    cfg = await settings_service.load(session)
    budget = await limits.budget(session, cfg)
    if budget.over and cfg["budget_fallback_mode"] == "fixed_reply":
        raise HTTPException(409, "AI budget for this month is used up")
    # The newest message plus a note marker so recent_turns includes everything before it.
    try:
        ans = await answer.generate(session, conv, last_in, cfg, cfg.answer_model,
                                    purpose="suggest", extra_system=SUGGEST_INSTRUCTION)  # fmt: skip
    except llm.LLMError as e:
        raise HTTPException(502, f"Suggestion unavailable: {e}") from e
    audit(session, user, "conversation.suggest", "conversation", conv_id, ip=client_ip(request))
    await session.commit()
    return {"text": ans.text, "sources": ans.sources, "cost_idr": round(ans.cost_idr, 2)}
