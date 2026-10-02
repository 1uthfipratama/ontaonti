"""Staff notifications: the dashboard badge comes from SSE events; email is sent
too when SMTP_* is configured. Email failures are logged, never raised."""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import StaffUser

log = logging.getLogger("onti.notify")


async def _recipients() -> list[str]:
    explicit = [e.strip() for e in settings.alert_emails.split(",") if e.strip()]
    if explicit:
        return explicit
    async with SessionLocal() as s:
        rows = await s.execute(
            select(StaffUser.email).where(
                StaffUser.is_active.is_(True), StaffUser.role.in_(("admin", "agent"))
            )
        )
        return [r[0] for r in rows]


def _send(to: list[str], subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)


async def email_staff(subject: str, body: str) -> None:
    if not settings.smtp_host:
        return
    try:
        to = await _recipients()
        if to:
            await asyncio.to_thread(_send, to, subject, body)
            log.info("alert email sent to %d recipient(s)", len(to))
    except Exception:
        log.exception("alert email failed")


def case_email(
    case_id: int, severity: str, category: str, contact: str, channel: str, text: str
) -> tuple[str, str]:
    subject = f"[Onti Erlani] {severity.upper()} case #{case_id}: {category}"
    body = (
        f"A {severity} {category} flag needs a staff member.\n\n"
        f"Contact: {contact} ({channel})\n"
        f"Message: {text[:500]}\n\n"
        f"Open the Cases page: {settings.web_base_url}/cases?id={case_id}\n\n"
        "The bot sent the fixed safety reply and switched the conversation to Human mode.\n"
        "(Prototype — test data only.)"
    )
    return subject, body
