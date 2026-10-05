"""Channel adapter interface.

Every channel (simulator, WhatsApp, Messenger, Instagram) turns its webhook
payload into InternalMessage objects and knows how to send text back.
parse_inbound returns a list: Meta batches several messages into one webhook.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.db import utcnow


@dataclass
class InternalMessage:
    channel: str  # whatsapp | messenger | instagram
    external_user_id: str  # wa_id / PSID / IGSID / sim-...
    external_message_id: str
    text: str = ""
    kind: str = "text"  # text | image | audio | video | document | sticker | location | ...
    user_name: str = ""
    media_url: str | None = None
    timestamp: datetime = field(default_factory=utcnow)
    simulated: bool = False
    raw: dict = field(default_factory=dict)


@dataclass
class StatusUpdate:
    external_message_id: str
    status: str  # delivered | read | failed
    timestamp: datetime
    error: str | None = None


class SendError(Exception):
    def __init__(self, message: str, retryable: bool = False, code: str | None = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.code = code


class ChannelAdapter(ABC):
    channel: str = ""

    @abstractmethod
    def parse_inbound(self, payload: dict) -> list[InternalMessage]: ...

    def parse_statuses(self, payload: dict) -> list[StatusUpdate]:
        return []

    @abstractmethod
    async def send(self, conversation, text: str, *, human_agent: bool = False) -> str | None:
        """Send text to the conversation's identity; return the channel message id."""

    async def send_media(self, conversation, path: Path, mime: str, kind: str, caption: str,
                         filename: str, *, human_agent: bool = False) -> str | None:  # fmt: skip
        """Send a file (kind: image | document | audio | video); return the channel id."""
        raise SendError(f"Sending files isn't supported on {self.channel}")

    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        """(bytes, mime type) of an inbound attachment."""
        raise SendError(f"Downloading media isn't supported on {self.channel}")

    async def mark_read(self, external_message_id: str) -> None:
        return None
