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


async def _touch(channel: str) -> None:
    """Remember when each channel last called us (Settings -> channel status)."""
    try:
        async with SessionLocal() as s:
            await settings_service.set_value(s, f"last_webhook_{channel}", utcnow().isoformat())
            await s.commit()
    except Exception:
        log.debug("could not record webhook time", exc_info=True)


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
    await _touch(channel)
    job_id = f"wh-{channel}-{hashlib.sha256(raw).hexdigest()[:32]}"
    await queue.enqueue("process_webhook", channel, payload, _job_id=job_id)
    return {"ok": True}
