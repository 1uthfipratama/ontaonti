"""Media files: photos, voice notes, documents.

Files live under MEDIA_DIR with a random name and Message.media_url holds
"media:<name>". Inbound media arrive as a reference that expires (WhatsApp
"wa-media:<id>", a Messenger/Instagram CDN URL), so the worker downloads them
as soon as the message comes in. Voice notes are transcribed so the bot can
answer them like text and staff can skim them.
"""

import logging
import mimetypes
import re
import secrets
from pathlib import Path

import httpx

from app import events
from app.channels.base import SendError
from app.config import settings
from app.models import Conversation, Message
from app.services import transcribe

log = logging.getLogger("onti.media")

PREFIX = "media:"
NAME_RE = re.compile(r"^[a-f0-9]{32}\.[a-z0-9]{1,5}$")
EXT = {
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/aac": ".aac",
    "audio/amr": ".amr",
    "audio/webm": ".webm",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/3gpp": ".3gp",
    "application/pdf": ".pdf",
    "text/plain": ".txt",
}
# What staff may send, and as which WhatsApp message type.
SENDABLE = {
    "image/jpeg": "image",
    "image/png": "image",
    "application/pdf": "document",
    "application/msword": "document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "document",
    "application/vnd.ms-excel": "document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "document",
    "text/plain": "document",
    "audio/mpeg": "audio",
    "audio/ogg": "audio",
    "audio/mp4": "audio",
    "audio/aac": "audio",
    "video/mp4": "video",
}
IMAGE_MAX_MB = 5  # WhatsApp's limit for images


def _dir() -> Path:
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    return settings.media_dir


def base_mime(mime: str | None) -> str:
    return (mime or "application/octet-stream").split(";")[0].strip().lower()


def ext_for(mime: str, filename: str = "") -> str:
    ext = EXT.get(base_mime(mime)) or mimetypes.guess_extension(base_mime(mime)) or ""
    if not ext and "." in filename:
        ext = "." + filename.rsplit(".", 1)[1]
    ext = ext.lower()
    return ext if re.fullmatch(r"\.[a-z0-9]{1,5}", ext) else ".bin"


def save(data: bytes, mime: str, filename: str = "") -> str:
    """Store bytes; returns the "media:<name>" reference."""
    name = secrets.token_hex(16) + ext_for(mime, filename)
    (_dir() / name).write_bytes(data)
    return PREFIX + name


def path_of(ref: str | None) -> Path | None:
    """Local file for a "media:<name>" reference (or a bare name); None if invalid/missing."""
    if not ref:
        return None
    name = ref[len(PREFIX) :] if ref.startswith(PREFIX) else ref
    if not NAME_RE.match(name):
        return None
    p = _dir() / name
    return p if p.is_file() else None


def mime_of(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


async def _fetch(conv: Conversation, ref: str) -> tuple[bytes, str]:
    if ref.startswith("wa-media:"):
        from app.channels.registry import adapter_for_channel

        return await adapter_for_channel("whatsapp").download_media(ref[len("wa-media:") :])
    if ref.startswith("http"):
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as http:
            r = await http.get(ref)
        if r.status_code >= 400:
            raise SendError(f"download failed: HTTP {r.status_code}")
        return r.content, r.headers.get("content-type", "")
    raise SendError(f"unknown media reference {ref[:40]}")


async def prepare_inbound(session, conv: Conversation, msg: Message, cfg) -> None:
    """Download inbound media and transcribe voice notes. Never raises: a message
    whose file can't be fetched is still handled (staff see the placeholder)."""
    meta = dict(msg.meta or {})
    if msg.media_url and not msg.media_url.startswith(PREFIX) and not conv.simulated:
        try:
            data, mime = await _fetch(conv, msg.media_url)
            if len(data) > settings.media_max_mb * 1024 * 1024:
                raise SendError(f"file larger than {settings.media_max_mb} MB")
            meta.update(mime=base_mime(mime), size=len(data), source=msg.media_url[:200])
            msg.media_url = save(data, mime)
        except Exception as e:  # network, Graph, disk: keep going without the file
            meta["media_error"] = str(e)[:200]
            log.warning("media download failed for message %s: %s", msg.id, e)
    if msg.kind == "audio" and cfg["transcribe_voice"] and not meta.get("transcript"):
        path = path_of(msg.media_url)
        text = await transcribe.transcribe(path) if path or conv.simulated else None
        if text:
            meta["transcript"] = True
            msg.text = text
            conv.last_preview = ("🎤 " + text)[:200]
    msg.meta = meta
    await session.commit()
    await events.publish("message.updated", conversation_id=conv.id, message_id=msg.id)
