"""Create the first admin from ADMIN_EMAIL / ADMIN_PASSWORD (idempotent).

python -m app.seed
"""

import asyncio
import logging

from sqlalchemy import func, select

from app.config import settings
from app.db import SessionLocal
from app.models import StaffUser
from app.security import hash_password

log = logging.getLogger("onti.seed")


async def ensure_admin() -> StaffUser | None:
    if not settings.admin_email or not settings.admin_password:
        log.warning("ADMIN_EMAIL / ADMIN_PASSWORD not set: no admin seeded")
        return None
    email = settings.admin_email.strip().lower()
    async with SessionLocal() as s:
        user = (
            await s.execute(select(StaffUser).where(func.lower(StaffUser.email) == email))
        ).scalar_one_or_none()
        if user:
            return user  # never overwrite an existing password from env
        user = StaffUser(
            email=email,
            name=settings.admin_name,
            role="admin",
            password_hash=hash_password(settings.admin_password),
        )
        s.add(user)
        await s.commit()
        log.info("seeded admin %s", email)
        return user


if __name__ == "__main__":
    from app.logging_setup import setup_logging

    setup_logging()
    asyncio.run(ensure_admin())
