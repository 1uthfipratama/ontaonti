"""Simulator: chat as a fake WhatsApp/Messenger/Instagram user, no Meta needed."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import queue, serializers
from app.audit import audit
from app.channels.simulator import SimulatorAdapter
from app.db import get_session
from app.deps import can_act, client_ip
from app.models import ContactIdentity, Conversation, StaffUser
from app.services.inbound import ingest

router = APIRouter(prefix="/simulator", tags=["simulator"])
adapter = SimulatorAdapter()


class SimMessageIn(BaseModel):
    channel: Literal["whatsapp", "messenger", "instagram"] = "whatsapp"
    user_id: str = Field(default="demo", min_length=1, max_length=60, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(default="", max_length=120)
    text: str = Field(default="", max_length=4096)
    kind: Literal["text", "image", "audio", "sticker", "location"] = "text"


@router.post("/messages")
async def send_as_user(
    body: SimMessageIn,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    if body.kind == "text" and not body.text.strip():
        raise HTTPException(422, "Text is empty")
    (im,) = adapter.parse_inbound(body.model_dump())
    result = await ingest(session, im)
    if result is None:
        raise HTTPException(409, "Duplicate message")
    audit(session, user, "simulator.message", "conversation", result.conversation.id,
          {"channel": body.channel, "user_id": body.user_id}, client_ip(request))  # fmt: skip
    await session.commit()
    await queue.enqueue("handle_inbound", result.message.id, _job_id=f"in-{result.message.id}")
    return {
        "conversation_id": result.conversation.id,
        "message": serializers.message(result.message),
    }


@router.get("/conversations")
async def simulated_conversations(
    user: StaffUser = Depends(can_act), session: AsyncSession = Depends(get_session)
):
    rows = (
        (
            await session.execute(
                select(Conversation)
                .join(ContactIdentity, ContactIdentity.id == Conversation.identity_id)
                .where(Conversation.simulated.is_(True))
                .order_by(Conversation.last_message_at.desc().nulls_last())
            )
        )
        .scalars()
        .all()
    )
    return [serializers.conversation(c) for c in rows]
