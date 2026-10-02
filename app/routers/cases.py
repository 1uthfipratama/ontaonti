"""Cases page: severity-sorted queue, claim, notes, status, resolve & return to bot."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import case as sql_case
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import events
from app.audit import audit
from app.constants import CASE_CLAIMED, CASE_OPEN, CASE_RESOLVED, CONV_OPEN, MODE_HUMAN
from app.db import get_session, utcnow
from app.deps import any_staff, can_act, client_ip
from app.models import Case, CaseNote, Contact, Conversation, Message, StaffUser
from app.serializers import iso
from app.services import cases as case_service

router = APIRouter(tags=["cases"])

SEV_ORDER = sql_case({"emergency": 3, "high": 2, "low": 1}, value=Case.severity, else_=0)


async def _serialize(session: AsyncSession, c: Case, notes: bool = False) -> dict:
    conv = await session.get(Conversation, c.conversation_id)
    contact = await session.get(Contact, c.contact_id)
    trigger = await session.get(Message, c.trigger_message_id) if c.trigger_message_id else None
    assignee = await session.get(StaffUser, c.assigned_to) if c.assigned_to else None
    out = {
        "id": c.id,
        "conversation_id": c.conversation_id,
        "contact_id": c.contact_id,
        "contact_name": contact.display_name if contact else "",
        "channel": conv.channel if conv else "",
        "conversation_mode": conv.mode if conv else None,
        "severity": c.severity,
        "category": c.category,
        "reason": c.reason,
        "status": c.status,
        "assigned_to": c.assigned_to,
        "assigned_name": (assignee.name or assignee.email) if assignee else None,
        "trigger_text": trigger.text if trigger else None,
        "created_at": iso(c.created_at),
        "claimed_at": iso(c.claimed_at),
        "resolved_at": iso(c.resolved_at),
    }
    if notes:
        rows = (
            await session.execute(
                select(CaseNote, StaffUser)
                .outerjoin(StaffUser, StaffUser.id == CaseNote.author_id)
                .where(CaseNote.case_id == c.id)
                .order_by(CaseNote.id)
            )
        ).all()
        out["notes"] = [
            {
                "id": n.id,
                "author": (u.name or u.email) if u else "?",
                "text": n.text,
                "created_at": iso(n.created_at),
            }
            for n, u in rows
        ]
    return out


async def _get(session: AsyncSession, case_id: int) -> Case:
    c = await session.get(Case, case_id)
    if c is None:
        raise HTTPException(404, "Case not found")
    return c


@router.get("/cases")
async def list_cases(
    status: str = "active",  # active (OPEN+CLAIMED) | OPEN | CLAIMED | RESOLVED | all
    conversation_id: int | None = None,
    user: StaffUser = Depends(any_staff),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Case)
    if status == "active":
        stmt = stmt.where(Case.status.in_((CASE_OPEN, CASE_CLAIMED)))
    elif status != "all":
        stmt = stmt.where(Case.status == status)
    if conversation_id:
        stmt = stmt.where(Case.conversation_id == conversation_id)
    stmt = stmt.order_by(SEV_ORDER.desc(), Case.created_at.asc()).limit(300)
    rows = (await session.execute(stmt)).scalars().all()
    return [await _serialize(session, c) for c in rows]


@router.get("/cases/{case_id}")
async def get_case(
    case_id: int, user: StaffUser = Depends(any_staff), session: AsyncSession = Depends(get_session)
):
    return await _serialize(session, await _get(session, case_id), notes=True)


@router.post("/cases/{case_id}/claim")
async def claim(
    case_id: int,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    c = await _get(session, case_id)
    if c.status == CASE_RESOLVED:
        raise HTTPException(409, "Case is already resolved")
    c.status, c.assigned_to, c.claimed_at = CASE_CLAIMED, user.id, utcnow()
    conv = await session.get(Conversation, c.conversation_id)
    if conv:
        conv.assigned_to = user.id
    audit(session, user, "case.claim", "case", case_id, ip=client_ip(request))
    await session.commit()
    await events.publish("case.updated", case_id=case_id, conversation_id=c.conversation_id)
    return await _serialize(session, c, notes=True)


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("/cases/{case_id}/notes")
async def add_note(
    case_id: int,
    body: NoteIn,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    c = await _get(session, case_id)
    session.add(CaseNote(case_id=case_id, author_id=user.id, text=body.text.strip()))
    audit(
        session, user, "case.note", "case", case_id, {"chars": len(body.text)}, client_ip(request)
    )
    await session.commit()
    await events.publish("case.updated", case_id=case_id, conversation_id=c.conversation_id)
    return await _serialize(session, c, notes=True)


class StatusIn(BaseModel):
    status: Literal["OPEN", "CLAIMED"]


@router.post("/cases/{case_id}/status")
async def set_status(
    case_id: int,
    body: StatusIn,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    c = await _get(session, case_id)
    old, c.status = c.status, body.status
    if body.status == CASE_OPEN:
        c.assigned_to, c.resolved_at = None, None
    audit(session, user, "case.status", "case", case_id, {"from": old, "to": body.status},
          client_ip(request))  # fmt: skip
    await session.commit()
    await events.publish("case.updated", case_id=case_id, conversation_id=c.conversation_id)
    return await _serialize(session, c, notes=True)


class ResolveIn(BaseModel):
    return_to_bot: bool = True
    note: str = Field(default="", max_length=4000)


@router.post("/cases/{case_id}/resolve")
async def resolve(
    case_id: int,
    body: ResolveIn,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    c = await _get(session, case_id)
    if body.note.strip():
        session.add(CaseNote(case_id=case_id, author_id=user.id, text=body.note.strip()))
    audit(session, user, "case.resolve", "case", case_id,
          {"return_to_bot": body.return_to_bot}, client_ip(request))  # fmt: skip
    await case_service.resolve(session, c, user, body.return_to_bot)
    return await _serialize(session, c, notes=True)


@router.get("/notifications/summary")
async def summary(
    user: StaffUser = Depends(any_staff), session: AsyncSession = Depends(get_session)
):
    rows = (
        await session.execute(
            select(Case.severity, func.count())
            .where(Case.status.in_((CASE_OPEN, CASE_CLAIMED)))
            .group_by(Case.severity)
        )
    ).all()
    by_sev = {sev: n for sev, n in rows}
    unclaimed = (
        await session.execute(
            select(func.count()).select_from(Case).where(Case.status == CASE_OPEN)
        )
    ).scalar_one()
    needs_human = (
        await session.execute(
            select(func.count())
            .select_from(Conversation)
            .where(
                Conversation.mode == MODE_HUMAN,
                Conversation.status == CONV_OPEN,
                Conversation.unread_count > 0,
            )
        )
    ).scalar_one()
    return {
        "open_cases": sum(by_sev.values()),
        "unclaimed": unclaimed,
        "emergency": by_sev.get("emergency", 0),
        "high": by_sev.get("high", 0),
        "low": by_sev.get("low", 0),
        "needs_human": needs_human,
    }
