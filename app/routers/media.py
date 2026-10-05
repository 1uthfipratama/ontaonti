"""Media: staff view received files and send files from the inbox."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import events, serializers
from app.audit import audit
from app.config import settings
from app.constants import MODE_HUMAN
from app.db import get_session
from app.deps import any_staff, can_act, client_ip
from app.models import StaffUser
from app.routers.conversations import get_conv, reply_window
from app.services import media, outbound

router = APIRouter(tags=["media"])


@router.get("/media/{name}")
async def get_media(name: str, user: StaffUser = Depends(any_staff)):
    path = media.path_of(name)
    if path is None:
        raise HTTPException(404, "Not found")
    return FileResponse(
        path, media_type=media.mime_of(path), headers={"Cache-Control": "private, max-age=86400"}
    )


@router.post("/conversations/{conv_id}/media")
async def send_media(
    conv_id: int,
    request: Request,
    file: UploadFile = File(...),
    caption: str = Form(""),
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    conv = await get_conv(session, conv_id)
    if conv.contact.opted_out:
        raise HTTPException(409, "This contact opted out (STOP). Messages can't be sent.")
    allowed, human_agent, reason = reply_window(conv)
    if not allowed:
        raise HTTPException(409, reason)
    mime = media.base_mime(file.content_type)
    kind = media.SENDABLE.get(mime)
    if kind is None:
        raise HTTPException(
            415, "This file type can't be sent. Use JPG, PNG, PDF or an Office file."
        )
    data = await file.read(settings.media_max_mb * 1024 * 1024 + 1)
    limit_mb = media.IMAGE_MAX_MB if kind == "image" else settings.media_max_mb
    if len(data) > limit_mb * 1024 * 1024:
        raise HTTPException(413, f"File too large (max {limit_mb} MB)")
    filename = (file.filename or "file").replace("/", "_").replace("\\", "_")[:120]
    ref = media.save(data, mime, filename)
    if conv.mode != MODE_HUMAN:  # a staff message takes the chat over, like a typed reply
        conv.mode = MODE_HUMAN
        await outbound.add_note(session, conv, f"{user.name or user.email} membalas. Bot berhenti.")
    if conv.assigned_to is None:
        conv.assigned_to = user.id
    audit(session, user, "conversation.media", "conversation", conv_id,
          {"kind": kind, "bytes": len(data)}, client_ip(request))  # fmt: skip
    msg = await outbound.send_media(
        session, conv, ref, media.path_of(ref), mime=mime, kind=kind, filename=filename,
        caption=caption.strip(), staff=user, human_agent=human_agent,
    )  # fmt: skip
    await events.publish("conversation.updated", conversation_id=conv_id)
    if msg.status == "failed":
        raise HTTPException(502, f"Saved but not delivered: {msg.error}")
    return serializers.message(msg)
