import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import serializers, totp
from app.audit import audit
from app.db import get_session, utcnow
from app.deps import client_ip, current_user
from app.models import StaffUser
from app.security import (
    COOKIE_NAME,
    cookie_kwargs,
    hash_password,
    make_session_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Failed logins per IP: 10 per 15 minutes (in-process; enough for a prototype).
_failures: defaultdict[str, list[float]] = defaultdict(list)
WINDOW, MAX_FAILS = 900, 10


class LoginIn(BaseModel):
    email: str
    password: str
    code: str | None = None  # 2FA code, when the account has it on


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
    if user.totp_enabled:
        if not body.code:
            raise HTTPException(401, "Two-factor code required")
        step = totp.verify(user.totp_secret or "", body.code, user.totp_last_step)
        if step is None:
            _failures[ip].append(now)
            raise HTTPException(401, "Invalid code")
        user.totp_last_step = step
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


class PasswordIn(BaseModel):
    current: str
    new: str = Field(min_length=10, max_length=72)


@router.post("/password")
async def change_password(
    body: PasswordIn,
    request: Request,
    response: Response,
    user: StaffUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    if not verify_password(body.current, user.password_hash):
        raise HTTPException(400, "Current password is wrong")
    user.password_hash = hash_password(body.new)
    user.session_epoch += 1  # signs out every other session
    audit(session, user, "auth.password", "staff", user.id, ip=client_ip(request))
    await session.commit()
    response.set_cookie(value=make_session_token(user.id, user.session_epoch), **cookie_kwargs())
    return {"ok": True}


# --- two-factor login ---------------------------------------------------------------


@router.post("/2fa/setup")
async def setup_2fa(
    user: StaffUser = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    """New secret (not active until confirmed with a code from the app)."""
    if user.totp_enabled:
        raise HTTPException(409, "Two-factor login is already on")
    user.totp_secret = totp.new_secret()
    await session.commit()
    link = totp.uri(user.totp_secret, user.email)
    return {"secret": user.totp_secret, "uri": link, "qr": totp.qr_data_uri(link)}


class CodeIn(BaseModel):
    code: str


@router.post("/2fa/enable")
async def enable_2fa(
    body: CodeIn,
    request: Request,
    user: StaffUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    if not user.totp_secret:
        raise HTTPException(409, "Start the setup first")
    step = totp.verify(user.totp_secret, body.code)
    if step is None:
        raise HTTPException(400, "Invalid code")
    user.totp_enabled, user.totp_last_step = True, step
    audit(session, user, "auth.2fa_on", "staff", user.id, ip=client_ip(request))
    await session.commit()
    return serializers.staff(user)


class DisableIn(BaseModel):
    password: str


@router.post("/2fa/disable")
async def disable_2fa(
    body: DisableIn,
    request: Request,
    user: StaffUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(400, "Current password is wrong")
    user.totp_enabled, user.totp_secret, user.totp_last_step = False, None, None
    audit(session, user, "auth.2fa_off", "staff", user.id, ip=client_ip(request))
    await session.commit()
    return serializers.staff(user)
