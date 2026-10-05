"""Tasks for staff and kader: calls, home visits, anything with a due date."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import events
from app.audit import audit
from app.db import get_session, utcnow
from app.deps import any_staff, can_act, client_ip
from app.models import Contact, StaffUser, Task
from app.serializers import iso

router = APIRouter(prefix="/tasks", tags=["tasks"])

Kind = Literal["call", "visit", "other"]


def _task(t: Task, names: dict[int, str], contacts: dict[int, str]) -> dict:
    return {
        "id": t.id,
        "contact_id": t.contact_id,
        "contact_name": contacts.get(t.contact_id or 0, ""),
        "kind": t.kind,
        "title": t.title,
        "note": t.note,
        "due": t.due.isoformat() if t.due else None,
        "assigned_to": t.assigned_to,
        "assigned_name": names.get(t.assigned_to or 0),
        "status": t.status,
        "outcome": t.outcome,
        "source": t.source,
        "created_at": iso(t.created_at),
        "done_at": iso(t.done_at),
    }


async def _lookups(session: AsyncSession, tasks: list[Task]) -> tuple[dict, dict]:
    names = {s.id: s.name or s.email for s in (await session.execute(select(StaffUser))).scalars()}
    ids = {t.contact_id for t in tasks if t.contact_id}
    contacts = (
        dict(
            (
                await session.execute(
                    select(Contact.id, Contact.display_name).where(Contact.id.in_(ids))
                )
            ).all()
        )
        if ids
        else {}
    )
    return names, contacts


@router.get("")
async def list_tasks(
    scope: Literal["mine", "all"] = "all",
    status: Literal["open", "done"] = "open",
    contact_id: int | None = None,
    user: StaffUser = Depends(any_staff),
    session: AsyncSession = Depends(get_session),
):
    q = select(Task).where(Task.status == status)
    if scope == "mine":
        q = q.where(Task.assigned_to == user.id)
    if contact_id is not None:
        q = q.where(Task.contact_id == contact_id)
    q = q.order_by(Task.due.asc().nulls_last(), Task.id) if status == "open" else q.order_by(
        Task.done_at.desc()
    ).limit(200)  # fmt: skip
    rows = (await session.execute(q)).scalars().all()
    names, contacts = await _lookups(session, rows)
    return [_task(t, names, contacts) for t in rows]


class TaskIn(BaseModel):
    contact_id: int | None = None
    kind: Kind = "call"
    title: str = Field(min_length=1, max_length=200)
    note: str = Field(default="", max_length=4000)
    due: date | None = None
    assigned_to: int | None = None


@router.post("")
async def create_task(
    body: TaskIn,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    if body.contact_id is not None and await session.get(Contact, body.contact_id) is None:
        raise HTTPException(422, "Contact not found")
    t = Task(**body.model_dump(), created_by=user.id)
    session.add(t)
    await session.flush()
    audit(session, user, "task.create", "task", t.id, {"kind": t.kind}, client_ip(request))
    await session.commit()
    await events.publish("task.created", contact_id=t.contact_id)
    names, contacts = await _lookups(session, [t])
    return _task(t, names, contacts)


class TaskPatch(BaseModel):
    status: Literal["open", "done"] | None = None
    outcome: str | None = Field(default=None, max_length=4000)
    due: date | None = None
    assigned_to: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=4000)


@router.patch("/{task_id}")
async def update_task(
    task_id: int,
    body: TaskPatch,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    t = await session.get(Task, task_id)
    if t is None:
        raise HTTPException(404, "Not found")
    for field in ("outcome", "due", "assigned_to", "title", "note"):
        value = getattr(body, field)
        if value is not None:
            setattr(t, field, value)
    if body.status and body.status != t.status:
        t.status = body.status
        t.done_at = utcnow() if body.status == "done" else None
    audit(session, user, "task.update", "task", t.id, body.model_dump(exclude_none=True),
          client_ip(request))  # fmt: skip
    await session.commit()
    await events.publish("task.updated", contact_id=t.contact_id)
    names, contacts = await _lookups(session, [t])
    return _task(t, names, contacts)
