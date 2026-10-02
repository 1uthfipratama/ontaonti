"""Model -> JSON dicts for the admin API."""

from app.db import as_utc
from app.models import Contact, ContactIdentity, Conversation, Message, StaffUser


def iso(dt) -> str | None:
    dt = as_utc(dt)
    return dt.isoformat() if dt else None


def staff(u: StaffUser | None) -> dict | None:
    if u is None:
        return None
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role, "is_active": u.is_active}


def identity(i: ContactIdentity) -> dict:
    return {
        "id": i.id,
        "contact_id": i.contact_id,
        "channel": i.channel,
        "external_id": i.external_id,
        "display_name": i.display_name,
        "simulated": i.simulated,
        "last_seen_at": iso(i.last_seen_at),
    }


def contact(c: Contact, with_identities: bool = True) -> dict:
    out = {
        "id": c.id,
        "display_name": c.display_name,
        "phone": c.phone,
        "notes": c.notes,
        "opted_out": c.opted_out,
        "broadcast_opt_in": c.broadcast_opt_in,
        "created_at": iso(c.created_at),
    }
    if with_identities:
        out["identities"] = [identity(i) for i in c.identities]
    return out


def conversation(c: Conversation) -> dict:
    return {
        "id": c.id,
        "contact_id": c.contact_id,
        "contact_name": c.contact.display_name if c.contact else "",
        "identity": identity(c.identity) if c.identity else None,
        "channel": c.channel,
        "simulated": c.simulated,
        "status": c.status,
        "mode": c.mode,
        "assigned_to": c.assigned_to,
        "window_expires_at": iso(c.window_expires_at),
        "last_message_at": iso(c.last_message_at),
        "last_inbound_at": iso(c.last_inbound_at),
        "last_preview": c.last_preview,
        "unread_count": c.unread_count,
        "flag_severity": c.flag_severity,
        "flag_category": c.flag_category,
        "opted_out": c.contact.opted_out if c.contact else False,
    }


def message(m: Message) -> dict:
    return {
        "id": m.id,
        "conversation_id": m.conversation_id,
        "direction": m.direction,
        "sender_type": m.sender_type,
        "sender_staff_id": m.sender_staff_id,
        "text": m.text,
        "kind": m.kind,
        "media_url": m.media_url,
        "status": m.status,
        "error": m.error,
        "flag_severity": m.flag_severity,
        "flag_category": m.flag_category,
        "flag_reason": m.flag_reason,
        "tokens_in": m.tokens_in,
        "tokens_out": m.tokens_out,
        "cost_idr": round(m.cost_idr or 0, 2),
        "meta": m.meta or {},
        "created_at": iso(m.created_at),
    }
