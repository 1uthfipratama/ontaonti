"""Channel webhooks. GET = Meta's subscription handshake; POST = events.

POSTs are verified (X-Hub-Signature-256 with the app secret, 403 on mismatch),
queued, and answered 200 immediately; the worker does the rest. A redelivered
payload gets the same job id (dropped by arq) and its message ids are unique in
the database, so nothing is processed twice.
"""

import hashlib
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app import queue
from app.channels.meta_common import verify_signature, verify_subscription
from app.config import settings
from app.db import SessionLocal, utcnow
from app.services import settings_service

log = logging.getLogger("onti.webhooks")
router = APIRouter(prefix="/webhook", tags=["webhooks"])


def _enabled(channel: str) -> bool:
    return {
        "whatsapp": True,
        "messenger": settings.enable_messenger,
        "instagram": settings.enable_instagram,
    }[channel]


def _secrets(channel: str) -> tuple[str, str]:
    if channel == "whatsapp":
        return settings.wa_verify_token, settings.wa_app_secret
    return settings.verify_token_meta, settings.app_secret_meta


def whatsapp_ids(payload: dict) -> tuple[str | None, str | None]:
    """(WhatsApp Business Account ID, phone number ID) carried by every WhatsApp
    webhook: entry.id and value.metadata.phone_number_id."""
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            meta = (change.get("value") or {}).get("metadata") or {}
            phone = meta.get("phone_number_id")
            # The dashboard's "Test" button sends Meta's sample payload: ignore it.
            if (
                not phone
                or phone == "123456123"
                or meta.get("display_phone_number") == "16505551111"
            ):
                continue
            return str(entry.get("id") or "") or None, str(phone)
    return None, None


async def _touch(channel: str, payload: dict) -> None:
    """Remember when each channel last called us (Settings -> channel status), and
    which WhatsApp account/number it was for: the adapter falls back to these when
    WA_PHONE_NUMBER_ID / WA_BUSINESS_ACCOUNT_ID are not set."""
    try:
        async with SessionLocal() as s:
            await settings_service.set_value(s, f"last_webhook_{channel}", utcnow().isoformat())
            if channel == "whatsapp":
                waba, phone = whatsapp_ids(payload)
                if phone:
                    await settings_service.set_value(s, "wa_detected_phone_number_id", phone)
                if waba and waba != "0":
                    await settings_service.set_value(s, "wa_detected_waba_id", waba)
            await s.commit()
    except Exception:
        log.debug("could not record webhook details", exc_info=True)


@router.get("/{channel}")
async def verify(channel: str, request: Request):
    if channel not in ("whatsapp", "messenger", "instagram") or not _enabled(channel):
        raise HTTPException(404)
    challenge = verify_subscription(dict(request.query_params), _secrets(channel)[0])
    if challenge is None:
        log.warning("%s webhook verification failed", channel)
        raise HTTPException(403, "Verification failed")
    log.info("%s webhook verified", channel)
    return PlainTextResponse(challenge)


@router.post("/{channel}")
async def receive(channel: str, request: Request):
    if channel not in ("whatsapp", "messenger", "instagram") or not _enabled(channel):
        raise HTTPException(404)
    raw = await request.body()
    if not verify_signature(raw, request.headers.get("x-hub-signature-256"), _secrets(channel)[1]):
        log.warning("%s webhook: bad or missing signature", channel)
        raise HTTPException(403, "Invalid signature")
    try:
        payload = json.loads(raw)
    except ValueError as e:
        raise HTTPException(400, "Invalid JSON") from e
    await _touch(channel, payload)
    job_id = f"wh-{channel}-{hashlib.sha256(raw).hexdigest()[:32]}"
    await queue.enqueue("process_webhook", channel, payload, _job_id=job_id)
    return {"ok": True}
