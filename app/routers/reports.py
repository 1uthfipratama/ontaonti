"""TB programme figures for the dashboard, and CSV exports for reporting.

Exports contain personal data: admins and reviewers only, and every download is
in the audit log.
"""

import csv
import io
from datetime import timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import audit
from app.config import settings
from app.db import as_utc, get_session, utcnow
from app.deps import any_staff, client_ip, require_roles
from app.models import Case, Contact, DoseLog, ScreeningSession, StaffUser
from app.routers.journey import STAGES, treatment_month
from app.serializers import iso
from app.services.reminders import local_today

router = APIRouter(tags=["reports"])
DAYS = 30


@router.get("/reports/programme")
async def programme(
    user: StaffUser = Depends(any_staff), session: AsyncSession = Depends(get_session)
):
    today = local_today()
    since_day = today - timedelta(days=DAYS)
    stages = dict(
        (
            await session.execute(
                select(Contact.journey_stage, func.count())
                .where(Contact.journey_stage.is_not(None))
                .group_by(Contact.journey_stage)
            )
        ).all()
    )
    doses = dict(
        (
            await session.execute(
                select(DoseLog.status, func.count())
                .where(DoseLog.day > since_day)
                .group_by(DoseLog.status)
            )
        ).all()
    )
    screened = dict(
        (
            await session.execute(
                select(ScreeningSession.result, func.count())
                .where(ScreeningSession.status == "done",
                       ScreeningSession.finished_at >= utcnow() - timedelta(days=DAYS))
                .group_by(ScreeningSession.result)
            )
        ).all()
    )  # fmt: skip
    reminders_on = await session.scalar(
        select(func.count()).select_from(Contact).where(Contact.reminder_enabled.is_(True))
    )

    # Risk flags (cases opened) per week, last 8 weeks, oldest first.
    start = today - timedelta(days=today.weekday() + 7 * 7)  # Monday, 8 weeks ago
    rows = (
        await session.execute(
            select(Case.created_at, Case.severity).where(
                Case.created_at >= utcnow() - timedelta(days=(today - start).days + 1)
            )
        )
    ).all()
    weeks = [
        {"week": (start + timedelta(weeks=i)).isoformat(), "low": 0, "high": 0, "emergency": 0}
        for i in range(8)
    ]
    for created, severity in rows:
        idx = (as_utc(created).astimezone(ZoneInfo(settings.timezone)).date() - start).days // 7
        if 0 <= idx < 8 and severity in ("low", "high", "emergency"):
            weeks[idx][severity] += 1

    return {
        "days": DAYS,
        "stages": {s: stages.get(s, 0) for s in STAGES},
        "adherence": {
            "taken": doses.get("taken", 0),
            "missed": doses.get("missed", 0),
            "skipped": doses.get("skipped", 0),
        },
        "screenings": {
            "total": sum(screened.values()),
            "presumptive": screened.get("presumptive", 0),
        },
        "reminders_on": reminders_on or 0,
        "flags_weekly": weeks,
    }


def _csv(rows: list[list], header: list[str], name: str) -> StreamingResponse:
    buf = io.StringIO()
    buf.write("﻿")  # BOM: Excel opens UTF-8 (names with accents) correctly
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="onti-{name}-{local_today()}.csv"'},
    )


@router.get("/reports/export/{kind}.csv")
async def export(
    kind: str,
    request: Request,
    user: StaffUser = Depends(require_roles("admin", "reviewer")),
    session: AsyncSession = Depends(get_session),
):
    today = local_today()
    staff = {s.id: s.name or s.email for s in (await session.execute(select(StaffUser))).scalars()}
    if kind == "patients":
        contacts = (
            await session.execute(select(Contact).where(Contact.journey_stage.is_not(None)).order_by(Contact.id))
        ).scalars().all()  # fmt: skip
        header = ["contact_id", "name", "phone", "stage", "treatment_start", "treatment_month",
                  "treatment_months", "puskesmas", "kader", "reminders", "opted_out"]  # fmt: skip
        rows = [[c.id, c.display_name, c.phone or "", c.journey_stage, c.treatment_start or "",
                 treatment_month(c.treatment_start, today) or "", c.treatment_months, c.puskesmas,
                 staff.get(c.kader_id, ""), "yes" if c.reminder_enabled else "no",
                 "yes" if c.opted_out else "no"] for c in contacts]  # fmt: skip
    elif kind == "doses":
        logs = (
            await session.execute(
                select(DoseLog, Contact.display_name)
                .join(Contact, Contact.id == DoseLog.contact_id)
                .where(DoseLog.day > today - timedelta(days=365))
                .order_by(DoseLog.day, DoseLog.contact_id)
            )
        ).all()
        header = ["day", "contact_id", "name", "status", "note", "sent_at", "answered_at"]
        rows = [[d.day, d.contact_id, name, d.status, d.note, iso(d.sent_at) or "",
                 iso(d.answered_at) or ""] for d, name in logs]  # fmt: skip
    elif kind == "screenings":
        sessions = (
            await session.execute(
                select(ScreeningSession, Contact.display_name)
                .join(Contact, Contact.id == ScreeningSession.contact_id)
                .where(ScreeningSession.status == "done")
                .order_by(ScreeningSession.finished_at)
            )
        ).all()
        questions = sorted({q for sc, _ in sessions for q in (sc.answers or {})})
        header = ["finished_at", "contact_id", "name", "result", *questions]
        rows = [[iso(sc.finished_at), sc.contact_id, name, sc.result,
                 *["yes" if sc.answers.get(q) else "no" if q in sc.answers else "" for q in questions]]
                for sc, name in sessions]  # fmt: skip
    elif kind == "cases":
        cases = (
            await session.execute(
                select(Case, Contact.display_name)
                .join(Contact, Contact.id == Case.contact_id)
                .order_by(Case.created_at)
            )
        ).all()
        header = ["case_id", "created_at", "contact_id", "name", "severity", "category", "status",
                  "assigned_to", "resolved_at"]  # fmt: skip
        rows = [[k.id, iso(k.created_at), k.contact_id, name, k.severity, k.category, k.status,
                 staff.get(k.assigned_to, ""), iso(k.resolved_at) or ""] for k, name in cases]  # fmt: skip
    else:
        raise HTTPException(404, "Unknown export")
    audit(session, user, "report.export", "report", kind, {"rows": len(rows)}, client_ip(request))
    await session.commit()
    return _csv(rows, header, kind)
