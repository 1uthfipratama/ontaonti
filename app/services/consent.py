"""Consent: first-contact privacy notice, STOP / BERHENTI opt-out, MULAI opt-in,
LANGGANAN broadcast subscription. Consents are an append-only log; the contact
row carries the current state (opted_out, broadcast_opt_in)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.safety import normalise
from app.db import utcnow
from app.models import Consent, Contact

# Whole-message keywords only: "berhenti minum obat" must NOT opt anyone out.
STOP = {"stop", "berhenti", "unsubscribe", "stop semua", "berhenti langganan", "stop all"}
START = {"mulai", "start", "unstop", "lanjut", "mulai lagi"}
SUBSCRIBE = {"langganan", "subscribe", "berlangganan"}


def command(text: str) -> str | None:
    norm = " ".join(normalise(text or ""))
    if norm in STOP:
        return "stop"
    if norm in START:
        return "start"
    if norm in SUBSCRIBE:
        return "subscribe"
    return None


def record(session: AsyncSession, contact: Contact, kind: str, status: str, source: str,
           channel: str | None = None, note: str | None = None) -> None:  # fmt: skip
    session.add(
        Consent(
            contact_id=contact.id,
            kind=kind,
            status=status,
            source=source,
            channel=channel,
            note=note,
        )  # fmt: skip
    )


async def notice_sent(session: AsyncSession, contact_id: int) -> bool:
    row = await session.execute(
        select(Consent.id).where(Consent.contact_id == contact_id, Consent.kind == "privacy_notice")
    )
    return row.first() is not None


def opt_out(session: AsyncSession, contact: Contact, channel: str, source: str = "keyword") -> None:
    contact.opted_out, contact.opted_out_at = True, utcnow()
    record(session, contact, "messaging", "revoked", source, channel)
    if contact.broadcast_opt_in:
        contact.broadcast_opt_in = False
        record(session, contact, "broadcast", "revoked", source, channel)


def opt_in(session: AsyncSession, contact: Contact, channel: str, source: str = "keyword") -> None:
    contact.opted_out, contact.opted_out_at = False, None
    record(session, contact, "messaging", "granted", source, channel)


def subscribe(session: AsyncSession, contact: Contact, granted: bool, channel: str | None,
              source: str) -> None:  # fmt: skip
    contact.broadcast_opt_in = granted
    record(session, contact, "broadcast", "granted" if granted else "revoked", source, channel)
