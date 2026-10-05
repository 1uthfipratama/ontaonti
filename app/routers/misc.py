"""Health, live events (SSE), staff list, audit log."""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app import events, serializers
from app.audit import audit
from app.db import get_session
from app.deps import admin_only, any_staff, client_ip, require_roles
from app.models import AuditLog, StaffUser
from app.redis_client import get_redis
from app.security import hash_password

router = APIRouter(tags=["misc"])


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)):
    from app.bot.kb import index_status

    out: dict = {"ok": True}
    try:
        await session.execute(text("SELECT 1"))
        out["db"] = "ok"
    except Exception:
        out["db"], out["ok"] = "down", False
    redis = get_redis()
    if redis is not None:
        try:
            await redis.ping()
            out["redis"] = "ok"
        except Exception:
            out["redis"], out["ok"] = "down", False
    usable, reason = await asyncio.to_thread(index_status)
    out["kb_index"] = "ok" if usable else reason
    return out


@router.get("/events")
async def stream_events(request: Request, user: StaffUser = Depends(any_staff)):
    async def gen():
        yield {"event": "hello", "data": json.dumps({"user_id": user.id})}
        async for ev in events.subscribe():
            if await request.is_disconnected():
                break
            yield {"event": ev.get("type", "message"), "data": json.dumps(ev, default=str)}

    return EventSourceResponse(gen(), ping=15)


@router.get("/staff")
async def list_staff(
    user: StaffUser = Depends(any_staff), session: AsyncSession = Depends(get_session)
):
    rows = (await session.execute(select(StaffUser).order_by(StaffUser.id))).scalars().all()
    return [serializers.staff(u) for u in rows]


class StaffIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    name: str = Field(default="", max_length=120)
    role: str = Field(pattern="^(admin|agent|reviewer)$")
    password: str = Field(min_length=10, max_length=72)


@router.post("/staff")
async def create_staff(
    body: StaffIn,
    request: Request,
    user: StaffUser = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
):
    email = body.email.lower()
    if (await session.execute(select(StaffUser).where(StaffUser.email == email))).first():
        raise HTTPException(409, "Email already exists")
    new = StaffUser(
        email=email, name=body.name, role=body.role, password_hash=hash_password(body.password)
    )
    session.add(new)
    await session.flush()
    audit(session, user, "staff.create", "staff", new.id, {"email": email, "role": body.role},
          client_ip(request))  # fmt: skip
    await session.commit()
    return serializers.staff(new)


class StaffPatch(BaseModel):
    role: str | None = Field(default=None, pattern="^(admin|agent|reviewer)$")
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=10, max_length=72)
    reset_2fa: bool | None = None  # staff lost their phone: they log in with the password alone


@router.patch("/staff/{staff_id}")
async def update_staff(
    staff_id: int,
    body: StaffPatch,
    request: Request,
    user: StaffUser = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
):
    target = await session.get(StaffUser, staff_id)
    if not target:
        raise HTTPException(404, "Not found")
    if target.id == user.id and (body.is_active is False or (body.role and body.role != "admin")):
        raise HTTPException(400, "You can't demote or deactivate yourself")
    changes = {}
    if body.role:
        target.role, changes["role"] = body.role, body.role
    if body.is_active is not None:
        target.is_active, changes["is_active"] = body.is_active, body.is_active
        target.session_epoch += 1
    if body.password:
        target.password_hash = hash_password(body.password)
        target.session_epoch += 1
        changes["password"] = "changed"
    if body.reset_2fa and target.totp_enabled:
        target.totp_enabled, target.totp_secret, target.totp_last_step = False, None, None
        target.session_epoch += 1
        changes["2fa"] = "reset"
    audit(session, user, "staff.update", "staff", staff_id, changes, client_ip(request))
    await session.commit()
    return serializers.staff(target)


@router.get("/audit")
async def list_audit(
    limit: int = 200,
    action: str | None = None,
    user: StaffUser = Depends(require_roles("admin", "reviewer")),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 1000))
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "created_at": serializers.iso(r.created_at),
            "actor_email": r.actor_email,
            "action": r.action,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "details": r.details,
            "ip": r.ip,
        }
        for r in rows
    ]
