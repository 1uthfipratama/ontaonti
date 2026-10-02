"""Broadcasts (phase 4)."""

from sqlalchemy.ext.asyncio import AsyncSession


async def on_message_status(session: AsyncSession, msg, st) -> None:
    return None
