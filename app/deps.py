"""FastAPI dependencies: DB session, current staff user, role checks."""

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import StaffUser
from app.security import COOKIE_NAME, read_session_token


async def current_user(request: Request, session: AsyncSession = Depends(get_session)) -> StaffUser:
    token = request.cookies.get(COOKIE_NAME)
    parsed = read_session_token(token) if token else None
    if not parsed:
        raise HTTPException(401, "Not signed in")
    uid, epoch = parsed
    user = await session.get(StaffUser, uid)
    if not user or not user.is_active or user.session_epoch != epoch:
        raise HTTPException(401, "Session expired")
    request.state.user = user
    return user


def require_roles(*roles: str) -> Callable:
    async def dep(user: StaffUser = Depends(current_user)) -> StaffUser:
        if user.role not in roles:
            raise HTTPException(403, "Not allowed for your role")
        return user

    return dep


# Shorthands
any_staff = current_user
can_act = require_roles("admin", "agent")  # reply, toggle, claim, simulate
admin_only = require_roles("admin")


def client_ip(request: Request) -> str:
    return request.client.host if request.client else ""
