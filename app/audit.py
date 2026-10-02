"""Audit log: who viewed, replied, toggled, claimed, changed what. Caller commits."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, StaffUser


def audit(
    session: AsyncSession,
    actor: StaffUser | None,
    action: str,
    entity_type: str = "",
    entity_id: object = "",
    details: dict | None = None,
    ip: str = "",
) -> None:
    session.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            actor_email=actor.email if actor else "system",
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else "",
            details=details or {},
            ip=ip,
        )
    )
