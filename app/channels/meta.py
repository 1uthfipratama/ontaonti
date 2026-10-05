"""Messenger and Instagram messaging (Messenger Platform, via the linked Facebook Page).

Behind ENABLE_MESSENGER / ENABLE_INSTAGRAM. Within 24 h of the user's last message
we reply with messaging_type RESPONSE; staff may answer up to 7 days later with
the HUMAN_AGENT tag (the app needs Meta's Human Agent permission for that).
"""

import json
import logging
from datetime import UTC, datetime

from app.channels.base import ChannelAdapter, InternalMessage, SendError, StatusUpdate
from app.channels.meta_common import graph_request
from app.config import settings

log = logging.getLogger("onti.meta")

OBJECT = {"messenger": "page", "instagram": "instagram"}
MAX_TEXT = {"messenger": 2000, "instagram": 1000}


def _ms(value) -> datetime:
    try:
        return datetime.fromtimestamp(int(value) / 1000, UTC)
    except (TypeError, ValueError):
        return datetime.now(UTC)


class MetaMessagingAdapter(ChannelAdapter):
    def __init__(self, channel: str) -> None:
        if channel not in OBJECT:
            raise ValueError(channel)
        self.channel = channel

    def _events(self, payload: dict):
        if payload.get("object") != OBJECT[self.channel]:
            return
        own_ids = {settings.meta_page_id, settings.meta_ig_account_id} - {""}
        for entry in payload.get("entry") or []:
            for ev in entry.get("messaging") or []:
                sender = (ev.get("sender") or {}).get("id")
                if not sender or sender in own_ids:
                    continue
                yield ev

    def parse_inbound(self, payload: dict) -> list[InternalMessage]:
        out = []
        for ev in self._events(payload):
            msg = ev.get("message")
            if not msg or msg.get("is_echo") or not msg.get("mid"):
                continue
            text, kind, media = msg.get("text", ""), "text", None
            if not text and msg.get("attachments"):
                att = msg["attachments"][0]
                kind = att.get("type", "unsupported")  # image | video | audio | file | ...
                media = (att.get("payload") or {}).get("url")
            if msg.get("quick_reply") and not text:
                text = msg["quick_reply"].get("payload", "")
            out.append(
                InternalMessage(
                    channel=self.channel,
                    external_user_id=ev["sender"]["id"],
                    external_message_id=msg["mid"],
                    text=text,
                    kind=kind,
                    media_url=media,
                    timestamp=_ms(ev.get("timestamp")),
                    raw=ev,
                )
            )
        return out

    def parse_statuses(self, payload: dict) -> list[StatusUpdate]:
        out = []
        for ev in self._events(payload):
            delivery = ev.get("delivery")
            if delivery:
                for mid in delivery.get("mids") or []:
                    out.append(StatusUpdate(mid, "delivered", _ms(delivery.get("watermark"))))
        return out

    def parse_reads(self, payload: dict) -> list[tuple[str, datetime]]:
        """(user id, watermark): everything we sent before the watermark was read."""
        return [
            (ev["sender"]["id"], _ms(ev["read"].get("watermark")))
            for ev in self._events(payload)
            if ev.get("read")
        ]

    async def send(self, conversation, text: str, *, human_agent: bool = False) -> str | None:
        if not settings.meta_page_id:
            raise SendError("META_PAGE_ID is not set", code="config")
        if len(text) > MAX_TEXT[self.channel]:
            raise SendError(
                f"{self.channel} messages are limited to {MAX_TEXT[self.channel]} characters"
            )
        body: dict = {
            "recipient": {"id": conversation.identity.external_id},
            "message": {"text": text},
            "messaging_type": "MESSAGE_TAG" if human_agent else "RESPONSE",
        }
        if human_agent:
            body["tag"] = "HUMAN_AGENT"
        data = await graph_request(
            "POST", f"{settings.meta_page_id}/messages", settings.meta_page_access_token, json=body
        )
        return data.get("message_id")

    async def send_buttons(self, conversation, text: str, buttons: list[tuple[str, str]], *,
                           human_agent: bool = False) -> str | None:  # fmt: skip
        if not settings.meta_page_id:
            raise SendError("META_PAGE_ID is not set", code="config")
        body: dict = {
            "recipient": {"id": conversation.identity.external_id},
            "message": {"text": text[: MAX_TEXT[self.channel]], "quick_replies": [
                {"content_type": "text", "title": title[:20], "payload": bid}
                for bid, title in buttons[:13]
            ]},
            "messaging_type": "MESSAGE_TAG" if human_agent else "RESPONSE",
        }  # fmt: skip
        if human_agent:
            body["tag"] = "HUMAN_AGENT"
        data = await graph_request(
            "POST", f"{settings.meta_page_id}/messages", settings.meta_page_access_token, json=body
        )
        return data.get("message_id")

    async def send_media(self, conversation, path, mime: str, kind: str, caption: str,
                         filename: str, *, human_agent: bool = False) -> str | None:  # fmt: skip
        if self.channel == "instagram":
            # Instagram only takes attachments by public URL; the hub's files are private.
            raise SendError("Instagram can't receive files from the hub yet. Send a link instead.")
        if not settings.meta_page_id:
            raise SendError("META_PAGE_ID is not set", code="config")
        form = {
            "recipient": json.dumps({"id": conversation.identity.external_id}),
            "message": json.dumps({"attachment": {
                "type": "file" if kind == "document" else kind,
                "payload": {"is_reusable": False},
            }}),
            "messaging_type": "MESSAGE_TAG" if human_agent else "RESPONSE",
        }  # fmt: skip
        if human_agent:
            form["tag"] = "HUMAN_AGENT"
        data = await graph_request(
            "POST", f"{settings.meta_page_id}/messages", settings.meta_page_access_token,
            data=form, files={"filedata": (filename, path.read_bytes(), mime)},
        )  # fmt: skip
        mid = data.get("message_id")
        if caption:  # Messenger attachments carry no caption: send it as a text after the file
            await self.send(conversation, caption, human_agent=human_agent)
        return mid
