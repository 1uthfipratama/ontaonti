"""Templates and broadcasts. Viewing: any staff; creating and sending: admin."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import audit
from app.channels.base import SendError
from app.db import get_session
from app.deps import admin_only, any_staff, client_ip
from app.models import Broadcast, BroadcastRecipient, Contact, StaffUser, WaTemplate
from app.serializers import iso
from app.services import broadcasts as svc
from app.services import settings_service

router = APIRouter(tags=["broadcasts"])


def template_json(t: WaTemplate) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "language": t.language,
        "category": t.category,
        "status": t.status,
        "body_text": t.body_text,
        "variable_count": t.variable_count,
        "source": t.source,
        "updated_at": iso(t.updated_at),
    }


async def broadcast_json(session: AsyncSession, b: Broadcast) -> dict:
    t = await session.get(WaTemplate, b.template_id)
    return {
        "id": b.id,
        "name": b.name,
        "template": template_json(t) if t else None,
        "variables": b.variables,
        "status": b.status,
        "recipient_count": b.recipient_count,
        "rate_idr": b.rate_idr,
        "est_cost_idr": b.est_cost_idr,
        "created_at": iso(b.created_at),
        "started_at": iso(b.started_at),
        "finished_at": iso(b.finished_at),
        "stats": await svc.stats(session, b.id),
    }


async def _template(session: AsyncSession, template_id: int) -> WaTemplate:
    t = await session.get(WaTemplate, template_id)
    if t is None:
        raise HTTPException(404, "Template not found")
    return t


@router.get("/templates")
async def list_templates(
    user: StaffUser = Depends(any_staff), session: AsyncSession = Depends(get_session)
):
    rows = (await session.execute(select(WaTemplate).order_by(WaTemplate.name))).scalars().all()
    return [template_json(t) for t in rows]


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=512, pattern=r"^[a-z0-9_]+$")
    language: str = Field(default="id", max_length=20)
    category: str = Field(default="UTILITY", pattern="^(MARKETING|UTILITY|AUTHENTICATION)$")
    body_text: str = Field(min_length=1, max_length=1024)


@router.post("/templates")
async def register_template(
    body: TemplateIn,
    request: Request,
    user: StaffUser = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
):
    """Register a template by hand (it must already be approved in WhatsApp Manager
    under the same name and language, or sends will fail)."""
    exists = (
        await session.execute(
            select(WaTemplate).where(
                WaTemplate.name == body.name, WaTemplate.language == body.language
            )
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "Template with this name and language exists")
    t = WaTemplate(
        name=body.name, language=body.language, category=body.category, body_text=body.body_text,
        variable_count=svc.count_variables(body.body_text), status="MANUAL", source="manual",
        components=[{"type": "BODY", "text": body.body_text}],
    )  # fmt: skip
    session.add(t)
    audit(session, user, "template.register", "template", body.name, ip=client_ip(request))
    await session.commit()
    return template_json(t)


@router.post("/templates/sync")
async def sync_templates(
    request: Request,
    user: StaffUser = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
):
    try:
        n = await svc.sync_templates(session)
    except SendError as e:
        raise HTTPException(502, f"Template sync failed: {e}") from e
    audit(session, user, "template.sync", "template", "", {"count": n}, client_ip(request))
    await session.commit()
    return {"synced": n}


class ComposeIn(BaseModel):
    template_id: int
    variables: list[str] = Field(default_factory=list, max_length=20)
    name: str = Field(default="", max_length=200)


def _check_vars(t: WaTemplate, variables: list[str]) -> list[str]:
    if len(variables) != t.variable_count:
        raise HTTPException(
            422, f"Template needs {t.variable_count} variable(s), got {len(variables)}"
        )
    if any(not v.strip() for v in variables):
        raise HTTPException(422, "Variables can't be empty")
    return [v.strip()[:1000] for v in variables]


@router.post("/broadcasts/estimate")
async def estimate(
    body: ComposeIn,
    user: StaffUser = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
):
    t = await _template(session, body.template_id)
    variables = _check_vars(t, body.variables)
    cfg = await settings_service.load(session)
    return await svc.estimate(session, t, variables, cfg)


@router.post("/broadcasts")
async def create_broadcast(
    body: ComposeIn,
    request: Request,
    user: StaffUser = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
):
    t = await _template(session, body.template_id)
    if t.status not in ("APPROVED", "MANUAL"):
        raise HTTPException(
            409, f"Template status is {t.status}; only approved templates can be sent"
        )
    variables = _check_vars(t, body.variables)
    cfg = await settings_service.load(session)
    bc = await svc.create(session, body.name or t.name, t, variables, user, cfg)
    audit(session, user, "broadcast.create", "broadcast", bc.id,
          {"template": t.name, "recipients": bc.recipient_count}, client_ip(request))  # fmt: skip
    await session.commit()
    return await broadcast_json(session, bc)


async def _broadcast(session: AsyncSession, broadcast_id: int) -> Broadcast:
    b = await session.get(Broadcast, broadcast_id)
    if b is None:
        raise HTTPException(404, "Broadcast not found")
    return b


@router.post("/broadcasts/{broadcast_id}/send")
async def send_broadcast(
    broadcast_id: int,
    request: Request,
    user: StaffUser = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
):
    b = await _broadcast(session, broadcast_id)
    if b.status != "draft":
        raise HTTPException(409, f"Broadcast is {b.status}")
    audit(session, user, "broadcast.send", "broadcast", b.id,
          {"recipients": b.recipient_count, "est_cost_idr": b.est_cost_idr}, client_ip(request))  # fmt: skip
    await session.commit()
    queued = await svc.start(session, b)
    return {"queued": queued, **(await broadcast_json(session, b))}


@router.post("/broadcasts/{broadcast_id}/cancel")
async def cancel_broadcast(
    broadcast_id: int,
    request: Request,
    user: StaffUser = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
):
    b = await _broadcast(session, broadcast_id)
    if b.status not in ("draft", "sending"):
        raise HTTPException(409, f"Broadcast is {b.status}")
    audit(session, user, "broadcast.cancel", "broadcast", b.id, ip=client_ip(request))
    await session.commit()
    await svc.cancel(session, b)
    return await broadcast_json(session, b)


@router.get("/broadcasts")
async def list_broadcasts(
    user: StaffUser = Depends(any_staff), session: AsyncSession = Depends(get_session)
):
    rows = (
        (await session.execute(select(Broadcast).order_by(Broadcast.id.desc()).limit(100)))
        .scalars()
        .all()
    )
    return [await broadcast_json(session, b) for b in rows]


@router.get("/broadcasts/{broadcast_id}")
async def get_broadcast(
    broadcast_id: int,
    user: StaffUser = Depends(any_staff),
    session: AsyncSession = Depends(get_session),
):
    b = await _broadcast(session, broadcast_id)
    rows = (
        await session.execute(
            select(BroadcastRecipient, Contact)
            .join(Contact, Contact.id == BroadcastRecipient.contact_id)
            .where(BroadcastRecipient.broadcast_id == broadcast_id)
            .order_by(BroadcastRecipient.id)
            .limit(1000)
        )
    ).all()
    return {
        **(await broadcast_json(session, b)),
        "recipients": [
            {
                "id": r.id,
                "contact_id": c.id,
                "contact_name": c.display_name,
                "status": r.status,
                "attempts": r.attempts,
                "error": r.error,
                "sent_at": iso(r.sent_at),
                "delivered_at": iso(r.delivered_at),
                "read_at": iso(r.read_at),
            }
            for r, c in rows
        ],
    }
