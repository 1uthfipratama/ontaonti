"""Phase 3: WhatsApp webhook (verify, signature, dedupe, statuses), sending, window,
Messenger/Instagram adapters behind feature flags."""

import json
from datetime import timedelta

import httpx
import pytest
import respx
from sqlalchemy import select, update

from app import queue
from app.config import settings
from app.db import SessionLocal, utcnow
from app.models import Conversation, LlmUsage, Message
from tests.meta_payloads import dumps, messenger_text, sign, wa_message, wa_status, wa_text

GRAPH_WA = "https://graph.test/v25.0/1111111111/messages"
GRAPH_PAGE = "https://graph.test/v25.0/3333333333/messages"


@pytest.fixture
def graph():
    """Mock the Graph API: records every JSON body sent."""
    sent: list[dict] = []
    counter = iter(range(1, 10_000))

    def wa(request: httpx.Request):
        body = json.loads(request.content)
        sent.append(body)
        if body.get("status") == "read":
            return httpx.Response(200, json={"success": True})
        return httpx.Response(200, json={"messages": [{"id": f"wamid.OUT{next(counter)}"}]})

    def page(request: httpx.Request):
        sent.append(json.loads(request.content))
        return httpx.Response(
            200, json={"recipient_id": "x", "message_id": f"m_out{next(counter)}"}
        )

    with respx.mock(assert_all_called=False) as mock:
        mock.post(GRAPH_WA).mock(side_effect=wa)
        mock.post(GRAPH_PAGE).mock(side_effect=page)
        yield sent


async def post_signed(
    client, payload: dict, channel: str = "whatsapp", signature: str | None = None
):
    body = dumps(payload)
    headers = {"Content-Type": "application/json", "X-Hub-Signature-256": signature or sign(body)}
    r = await client.post(f"/webhook/{channel}", content=body, headers=headers)
    await queue.drain()
    return r


async def messages() -> list[Message]:
    async with SessionLocal() as s:
        return (await s.execute(select(Message).order_by(Message.id))).scalars().all()


# --- verification ---------------------------------------------------------------


async def test_webhook_verify_ok(client):
    r = await client.get(
        "/webhook/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test-verify-token",
            "hub.challenge": "12345",
        },
    )
    assert r.status_code == 200 and r.text == "12345"


@pytest.mark.parametrize(
    "params",
    [
        {"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "1"},
        {"hub.mode": "unsubscribe", "hub.verify_token": "test-verify-token", "hub.challenge": "1"},
        {},
    ],
)
async def test_webhook_verify_rejects(client, params):
    assert (await client.get("/webhook/whatsapp", params=params)).status_code == 403


# --- signatures -----------------------------------------------------------------


async def test_valid_signature_is_processed_and_answered(client, graph):
    r = await post_signed(client, wa_text("Berapa lama pengobatan TBC?"))
    assert r.status_code == 200 and r.json() == {"ok": True}
    msgs = await messages()
    inbound = [m for m in msgs if m.direction == "in"]
    assert len(inbound) == 1 and inbound[0].text == "Berapa lama pengobatan TBC?"
    texts = [b for b in graph if b.get("type") == "text"]
    assert len(texts) == 2  # consent notice + answer
    assert texts[0]["to"] == "6281234567890"
    assert any(b.get("status") == "read" for b in graph)  # marked as read
    out = [m for m in msgs if m.direction == "out"]
    assert all(m.status == "sent" and m.external_id.startswith("wamid.OUT") for m in out)
    async with SessionLocal() as s:
        conv = (await s.execute(select(Conversation))).scalar_one()
    assert conv.window_expires_at is not None


@pytest.mark.parametrize("signature", ["sha256=" + "0" * 64, "garbage", ""])
async def test_invalid_signature_is_403(client, graph, signature):
    body = dumps(wa_text("halo"))
    headers = {"Content-Type": "application/json"}
    if signature:
        headers["X-Hub-Signature-256"] = signature
    r = await client.post("/webhook/whatsapp", content=body, headers=headers)
    await queue.drain()
    assert r.status_code == 403
    assert await messages() == []


async def test_signature_is_over_raw_body(client, graph):
    payload = wa_text("halo")
    tampered = dumps(payload).replace(b"halo", b"HALO")
    r = await client.post(
        "/webhook/whatsapp",
        content=tampered,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": sign(dumps(payload))},
    )
    assert r.status_code == 403


# --- dedupe, statuses, non-text ----------------------------------------------------


async def test_duplicate_delivery_is_processed_once(client, graph):
    payload = wa_text("Apa itu TBC?", msg_id="wamid.DUPLICATE1")
    await post_signed(client, payload)
    sends_after_first = len(graph)
    await post_signed(client, payload)
    inbound = [m for m in await messages() if m.direction == "in"]
    assert len(inbound) == 1
    assert len(graph) == sends_after_first  # no second reply


async def test_delivery_and_read_statuses_update_message(client, graph):
    await post_signed(client, wa_text("Halo"))
    out = [m for m in await messages() if m.direction == "out"][-1]
    await post_signed(client, wa_status(out.external_id, "sent"))  # ignored
    await post_signed(client, wa_status(out.external_id, "delivered"))
    assert [m for m in await messages() if m.id == out.id][0].status == "delivered"
    await post_signed(client, wa_status(out.external_id, "read"))
    await post_signed(client, wa_status(out.external_id, "delivered"))  # late: never goes back
    assert [m for m in await messages() if m.id == out.id][0].status == "read"


async def test_non_text_gets_polite_reply_without_llm(client, graph):
    await post_signed(
        client, wa_message({"type": "image", "image": {"id": "MEDIA1", "mime_type": "image/jpeg"}})
    )
    texts = [b["text"]["body"] for b in graph if b.get("type") == "text"]
    assert any("pesan teks" in t for t in texts)
    async with SessionLocal() as s:
        purposes = [u.purpose for u in (await s.execute(select(LlmUsage))).scalars()]
    assert purposes == []
    inbound = [m for m in await messages() if m.direction == "in"][0]
    assert inbound.kind == "image" and inbound.media_url == "wa-media:MEDIA1"


async def test_reactions_are_ignored(client, graph):
    await post_signed(
        client, wa_message({"type": "reaction", "reaction": {"message_id": "x", "emoji": "👍"}})
    )
    assert await messages() == []


async def test_failed_send_is_recorded(client):
    with respx.mock() as mock:
        mock.post(GRAPH_WA).mock(return_value=httpx.Response(
            400, json={"error": {"message": "Recipient phone number not in allowed list", "code": 131030}}
        ))  # fmt: skip
        await post_signed(client, wa_text("Halo"))
    out = [m for m in await messages() if m.direction == "out"]
    assert out and all(m.status == "failed" for m in out)
    assert "allowed list" in out[0].error


# --- staff replies and the 24-hour window ---------------------------------------------


async def test_staff_reply_outside_24h_window_is_refused(admin, graph):
    await post_signed(admin, wa_text("Halo"))
    async with SessionLocal() as s:
        await s.execute(update(Conversation).values(last_inbound_at=utcnow() - timedelta(hours=25)))
        await s.commit()
        conv_id = (await s.execute(select(Conversation.id))).scalar_one()
    r = await admin.post(f"/conversations/{conv_id}/messages", json={"text": "Halo dari staf"})
    assert r.status_code == 409 and "24-hour" in r.json()["detail"]


async def test_staff_reply_inside_window_is_sent(admin, graph):
    await post_signed(admin, wa_text("Halo"))
    async with SessionLocal() as s:
        conv_id = (await s.execute(select(Conversation.id))).scalar_one()
    r = await admin.post(f"/conversations/{conv_id}/messages", json={"text": "Halo dari staf"})
    assert r.status_code == 200 and r.json()["status"] == "sent"
    assert graph[-1]["text"]["body"] == "Halo dari staf"


# --- Messenger / Instagram ----------------------------------------------------------


async def test_messenger_inbound_is_answered(client, graph):
    r = await post_signed(client, messenger_text("Apa itu TBC?"), channel="messenger")
    assert r.status_code == 200
    sends = [b for b in graph if "recipient" in b]
    assert sends and sends[-1]["recipient"] == {"id": "PSID123"}
    assert sends[-1]["messaging_type"] == "RESPONSE"


async def test_instagram_uses_same_flow(client, graph):
    r = await post_signed(
        client, messenger_text("Halo", psid="IGSID9", obj="instagram"), channel="instagram"
    )
    assert r.status_code == 200
    assert any(b.get("recipient") == {"id": "IGSID9"} for b in graph)


async def test_messenger_staff_reply_after_24h_uses_human_agent_tag(admin, graph):
    await post_signed(admin, messenger_text("Halo"), channel="messenger")
    async with SessionLocal() as s:
        await s.execute(update(Conversation).values(last_inbound_at=utcnow() - timedelta(days=3)))
        await s.commit()
        conv_id = (await s.execute(select(Conversation.id))).scalar_one()
    r = await admin.post(f"/conversations/{conv_id}/messages", json={"text": "Follow-up dari staf"})
    assert r.status_code == 200, r.text
    assert graph[-1]["messaging_type"] == "MESSAGE_TAG" and graph[-1]["tag"] == "HUMAN_AGENT"
    async with SessionLocal() as s:
        await s.execute(update(Conversation).values(last_inbound_at=utcnow() - timedelta(days=8)))
        await s.commit()
    r = await admin.post(f"/conversations/{conv_id}/messages", json={"text": "terlambat"})
    assert r.status_code == 409


async def test_disabled_channels_are_404(client, monkeypatch):
    monkeypatch.setattr(settings, "enable_messenger", False)
    monkeypatch.setattr(settings, "enable_instagram", False)
    body = dumps(messenger_text("x"))
    r = await client.post(
        "/webhook/messenger", content=body, headers={"X-Hub-Signature-256": sign(body)}
    )
    assert r.status_code == 404
    assert (
        await client.get("/webhook/instagram", params={"hub.mode": "subscribe"})
    ).status_code == 404


async def test_messenger_signature_checked(client):
    body = dumps(messenger_text("x"))
    r = await client.post(
        "/webhook/messenger", content=body, headers={"X-Hub-Signature-256": "sha256=00"}
    )
    assert r.status_code == 403


async def test_phone_number_id_is_learned_from_webhooks(client, graph, monkeypatch):
    """Without WA_PHONE_NUMBER_ID, replies use the number the message came in on."""
    monkeypatch.setattr(settings, "wa_phone_number_id", "")
    monkeypatch.setattr(settings, "wa_business_account_id", "")
    r = await post_signed(client, wa_text("Apa itu TBC?"))
    assert r.status_code == 200
    assert any(b.get("type") == "text" for b in graph)  # sent via .../1111111111/messages
    from app.channels.whatsapp import business_account_id, phone_number_id

    assert await phone_number_id() == "1111111111"
    assert await business_account_id() == "2222222222"


async def test_meta_sample_payload_does_not_overwrite_ids(client, graph, monkeypatch):
    monkeypatch.setattr(settings, "wa_phone_number_id", "")
    sample = wa_text("this is a text message")
    sample["entry"][0]["id"] = "0"
    sample["entry"][0]["changes"][0]["value"]["metadata"] = {
        "display_phone_number": "16505551111",
        "phone_number_id": "123456123",
    }
    await post_signed(client, sample)
    from app.channels.whatsapp import phone_number_id

    assert await phone_number_id() == ""
