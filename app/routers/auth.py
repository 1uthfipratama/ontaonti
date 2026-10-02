import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import serializers
from app.audit import audit
from app.db import get_session, utcnow
from app.deps import client_ip, current_user
from app.models import StaffUser
from app.security import COOKIE_NAME, cookie_kwargs, make_session_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# Failed logins per IP: 10 per 15 minutes (in-process; enough for a prototype).
_failures: defaultdict[str, list[float]] = defaultdict(list)
WINDOW, MAX_FAILS = 900, 10


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    ip = client_ip(request)
    now = time.time()
    _failures[ip] = [t for t in _failures[ip] if now - t < WINDOW]
    if len(_failures[ip]) >= MAX_FAILS:
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")
    user = (
        await session.execute(
            select(StaffUser).where(func.lower(StaffUser.email) == body.email.strip().lower())
        )
    ).scalar_one_or_none()
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        _failures[ip].append(now)
        raise HTTPException(401, "Wrong email or password")
    user.last_login_at = utcnow()
    audit(session, user, "auth.login", "staff", user.id, ip=ip)
    await session.commit()
    response.set_cookie(value=make_session_token(user.id, user.session_epoch), **cookie_kwargs())
    return serializers.staff(user)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
async def me(user: StaffUser = Depends(current_user)):
    return serializers.staff(user)
