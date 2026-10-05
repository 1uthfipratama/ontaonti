"""Simulator channel: an admin chats as a fake user, labelled WhatsApp/Messenger/
Instagram, without Meta. Outgoing messages are only stored and pushed over SSE."""

import uuid

from app.channels.base import ChannelAdapter, InternalMessage
from app.constants import CHANNELS


class SimulatorAdapter(ChannelAdapter):
    channel = "simulator"

    def parse_inbound(self, payload: dict) -> list[InternalMessage]:
        channel = payload.get("channel", "whatsapp")
        if channel not in CHANNELS:
            raise ValueError(f"channel must be one of {CHANNELS}")
        user = str(payload.get("user_id") or "demo").strip()[:60]
        kind = payload.get("kind") or "text"
        return [
            InternalMessage(
                channel=channel,
                external_user_id=f"sim-{user}",
                external_message_id=f"sim-{uuid.uuid4().hex}",
                text=(payload.get("text") or "").strip(),
                kind=kind,
                user_name=(payload.get("name") or f"Simulasi {user}").strip()[:120],
                simulated=True,
                raw=payload,
            )
        ]

    async def send(self, conversation, text: str, *, human_agent: bool = False) -> str | None:
        return f"sim-out-{uuid.uuid4().hex}"

    async def send_media(self, conversation, path, mime: str, kind: str, caption: str,
                         filename: str, *, human_agent: bool = False) -> str | None:  # fmt: skip
        return f"sim-out-{uuid.uuid4().hex}"
