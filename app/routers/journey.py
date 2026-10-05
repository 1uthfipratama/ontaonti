"""TB programme: patient journey board, treatment details, medication reminders, doses."""

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import events, serializers
from app.audit import audit
from app.db import get_session
from app.deps import any_staff, can_act, client_ip
from app.models import Contact, DoseLog, ScreeningSession, StaffUser, Task
from app.services.reminders import local_today

router = APIRouter(tags=["journey"])

STAGES = ("suspect", "testing", "treatment", "completed", "lost")
Stage = Literal["suspect", "testing", "treatment", "completed", "lost"]


def treatment_month(start: date | None, today: date) -> int | None:
    """1 in the first month of treatment, 2 in the second..."""
    if start is None or start > today:
        return None
    months = (today.year - start.year) * 12 + today.month - start.month
    if today.day < start.day:
        months -= 1
    return months + 1


@router.get("/journey")
async def board(user: StaffUser = Depends(any_staff), session: AsyncSession = Depends(get_session)):
    today = local_today()
    contacts = (
        (
            await session.execute(
                select(Contact)
                .where(Contact.journey_stage.is_not(None))
                .order_by(Contact.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )
    ids = [c.id for c in contacts]
    week: dict[int, dict[str, int]] = {}
    if ids:
        rows = await session.execute(
            select(DoseLog.contact_id, DoseLog.status, func.count())
            .where(DoseLog.contact_id.in_(ids), DoseLog.day > today - timedelta(days=7))
            .group_by(DoseLog.contact_id, DoseLog.status)
        )
        for cid, status, n in rows:
            week.setdefault(cid, {})[status] = n
    tasks = dict(
        (
            await session.execute(
                select(Task.contact_id, func.count())
                .where(Task.contact_id.in_(ids), Task.status == "open")
                .group_by(Task.contact_id)
            )
        ).all()
    ) if ids else {}  # fmt: skip
    staff = {s.id: s.name or s.email for s in (await session.execute(select(StaffUser))).scalars()}
    return {
        "stages": list(STAGES),
        "contacts": [
            {
                **serializers.contact(c, with_identities=False),
                "treatment_month": treatment_month(c.treatment_start, today),
                "kader_name": staff.get(c.kader_id),
                "week": week.get(c.id, {}),
                "open_tasks": tasks.get(c.id, 0),
            }
            for c in contacts
        ],
    }


class JourneyIn(BaseModel):
    stage: Stage | None = None
    clear_stage: bool = False  # take the contact off the board
    treatment_start: date | None = None
    treatment_months: int | None = Field(default=None, ge=1, le=36)
    puskesmas: str | None = Field(default=None, max_length=120)
    kader_id: int | None = None
    clear_kader: bool = False
    reminder_enabled: bool | None = None
    reminder_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


@router.patch("/contacts/{contact_id}/journey")
async def update_journey(
    contact_id: int,
    body: JourneyIn,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    c = await session.get(Contact, contact_id)
    if c is None:
        raise HTTPException(404, "Contact not found")
    changes = body.model_dump(exclude_none=True)
    if body.clear_stage:
        c.journey_stage, c.reminder_enabled = None, False
    elif body.stage:
        c.journey_stage = body.stage
        if body.stage == "treatment" and c.treatment_start is None and body.treatment_start is None:
            c.treatment_start = local_today()
        if body.stage != "treatment":
            c.reminder_enabled = False  # reminders are for people on treatment
    if body.treatment_start is not None:
        c.treatment_start = body.treatment_start
    if body.treatment_months is not None:
        c.treatment_months = body.treatment_months
    if body.puskesmas is not None:
        c.puskesmas = body.puskesmas.strip()
    if body.clear_kader:
        c.kader_id = None
    elif body.kader_id is not None:
        if await session.get(StaffUser, body.kader_id) is None:
            raise HTTPException(422, "Unknown staff member")
        c.kader_id = body.kader_id
    if body.reminder_time is not None:
        c.reminder_time = body.reminder_time
    if body.reminder_enabled is not None:
        if body.reminder_enabled and c.journey_stage != "treatment":
            raise HTTPException(409, "Reminders are for contacts on treatment")
        if body.reminder_enabled and c.opted_out:
            raise HTTPException(409, "This contact opted out (STOP). Messages can't be sent.")
        c.reminder_enabled = body.reminder_enabled
    audit(session, user, "contact.journey", "contact", contact_id,
          {k: str(v) for k, v in changes.items()}, client_ip(request))  # fmt: skip
    await session.commit()
    await events.publish("contact.updated", contact_id=contact_id)
    return serializers.contact(c)


@router.get("/contacts/{contact_id}/screening")
async def latest_screening(
    contact_id: int,
    user: StaffUser = Depends(any_staff),
    session: AsyncSession = Depends(get_session),
):
    """The contact's most recent finished screening, or null."""
    sc = (
        await session.execute(
            select(ScreeningSession)
            .where(ScreeningSession.contact_id == contact_id, ScreeningSession.status == "done")
            .order_by(ScreeningSession.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if sc is None:
        return None
    return {
        "result": sc.result,
        "answers": sc.answers,
        "finished_at": serializers.iso(sc.finished_at),
    }


@router.get("/contacts/{contact_id}/doses")
async def doses(
    contact_id: int,
    days: int = 30,
    user: StaffUser = Depends(any_staff),
    session: AsyncSession = Depends(get_session),
):
    since = local_today() - timedelta(days=min(max(days, 1), 365))
    rows = (
        (
            await session.execute(
                select(DoseLog)
                .where(DoseLog.contact_id == contact_id, DoseLog.day > since)
                .order_by(DoseLog.day)
            )
        )
        .scalars()
        .all()
    )
    return [{"day": d.day.isoformat(), "status": d.status, "note": d.note} for d in rows]
