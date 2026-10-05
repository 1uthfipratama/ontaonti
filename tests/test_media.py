"""Media: inbound files are downloaded, voice notes transcribed and answered,
staff can send files, and only staff can fetch them."""

import json

import httpx
import pytest
import respx
from sqlalchemy import select

from app import queue
from app.db import SessionLocal
from app.models import Conversation, Message
from tests.conftest import simulate
from tests.meta_payloads import wa_message
from tests.test_whatsapp import post_signed

GRAPH = "https://graph.test/v25.0"
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200
OGG = b"OggS" + b"0" * 200


@pytest.fixture
def graph():
    """Graph API mock: media lookups, downloads, uploads and sends."""
    sent: list = []

    def send(request: httpx.Request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"messages": [{"id": f"wamid.OUT{len(sent)}"}]})

    def upload(request: httpx.Request):
        sent.append({"upload": request.headers["content-type"].split(";")[0]})
        return httpx.Response(200, json={"id": "UPLOADED1"})

    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{GRAPH}/1111111111/messages").mock(side_effect=send)
        mock.post(f"{GRAPH}/1111111111/media").mock(side_effect=upload)
        mock.get(f"{GRAPH}/IMG1").mock(
            return_value=httpx.Response(
                200, json={"url": "https://lookaside.test/IMG1", "mime_type": "image/jpeg"}
            )
        )
        mock.get(f"{GRAPH}/VOICE1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "url": "https://lookaside.test/VOICE1",
                    "mime_type": "audio/ogg; codecs=opus",
                },
            )
        )
        mock.get("https://lookaside.test/IMG1").mock(return_value=httpx.Response(200, content=JPEG))
        mock.get("https://lookaside.test/VOICE1").mock(
            return_value=httpx.Response(200, content=OGG)
        )
        yield sent  # fmt: skip


async def inbound() -> Message:
    async with SessionLocal() as s:
        return (await s.execute(select(Message).where(Message.direction == "in"))).scalars().first()


async def test_inbound_photo_is_stored_and_served_to_staff(admin, graph):
    await post_signed(admin, wa_message({"type": "image", "image": {"id": "IMG1"}}))
    msg = await inbound()
    assert msg.media_url.startswith("media:") and msg.meta["mime"] == "image/jpeg"
    assert msg.meta["placeholder"] is True  # "[gambar]" is only a label
    r = await admin.get("/media/" + msg.media_url.removeprefix("media:"))
    assert r.status_code == 200 and r.content == JPEG and r.headers["content-type"] == "image/jpeg"
    # Photos still get the polite "text only" reply: the bot can't see them.
    assert any("pesan teks" in b.get("text", {}).get("body", "") for b in graph)


async def test_voice_note_is_transcribed_and_answered(admin, graph):
    await post_signed(
        admin, wa_message({"type": "audio", "audio": {"id": "VOICE1", "voice": True}})
    )
    msg = await inbound()
    assert msg.kind == "audio" and msg.media_url.startswith("media:")
    assert msg.meta["transcript"] is True and "pengobatan TBC" in msg.text
    texts = [b["text"]["body"] for b in graph if b.get("type") == "text"]
    assert not any("pesan teks" in t for t in texts)  # answered, not "text only"
    assert any("6 bulan" in t for t in texts)


async def test_voice_note_without_transcription_gets_text_only_reply(admin, graph):
    await admin.put("/settings", json={"values": {"transcribe_voice": False}})
    await post_signed(admin, wa_message({"type": "audio", "audio": {"id": "VOICE1"}}))
    assert not (await inbound()).meta.get("transcript")
    assert any("pesan teks" in b.get("text", {}).get("body", "") for b in graph)


async def test_failed_download_keeps_the_message(admin, graph):
    await post_signed(admin, wa_message({"type": "image", "image": {"id": "GONE"}}))
    msg = await inbound()
    assert msg.media_url == "wa-media:GONE" and msg.meta.get("media_error")


async def test_staff_sends_a_photo_on_whatsapp(admin, graph):
    await post_signed(admin, wa_message({"type": "text", "text": {"body": "Halo"}}))
    async with SessionLocal() as s:
        conv_id = (await s.execute(select(Conversation.id))).scalar_one()
    r = await admin.post(
        f"/conversations/{conv_id}/media",
        files={"file": ("jadwal.jpg", JPEG, "image/jpeg")},
        data={"caption": "Jadwal kontrol bulan ini"},
    )
    assert r.status_code == 200, r.text
    m = r.json()
    assert (
        m["kind"] == "image" and m["status"] == "sent" and m["text"] == "Jadwal kontrol bulan ini"
    )
    assert {"upload": "multipart/form-data"} in graph
    assert graph[-1]["type"] == "image"
    assert graph[-1]["image"] == {"id": "UPLOADED1", "caption": "Jadwal kontrol bulan ini"}
    conv = (await admin.get(f"/conversations/{conv_id}")).json()
    assert conv["mode"] == "HUMAN"  # sending a file takes the chat over


async def test_staff_file_checks(admin, client):
    out = await simulate(admin, "Halo")
    cid = out["conversation_id"]
    bad = await admin.post(
        f"/conversations/{cid}/media", files={"file": ("x.exe", b"MZ", "application/x-msdownload")}
    )
    assert bad.status_code == 415
    ok = await admin.post(
        f"/conversations/{cid}/media", files={"file": ("hasil.pdf", b"%PDF-1.4", "application/pdf")}
    )
    assert ok.status_code == 200 and ok.json()["kind"] == "document"
    assert ok.json()["meta"]["filename"] == "hasil.pdf"
    name = ok.json()["media_url"].removeprefix("media:")
    assert (await admin.get("/media/..%2F..%2Fsecret.txt")).status_code == 404
    assert (await admin.get("/media/not-a-name.pdf")).status_code == 404
    await admin.post("/auth/logout")
    assert (await client.get(f"/media/{name}")).status_code == 401


async def test_simulator_voice_note_is_transcribed_and_answered(admin):
    r = await admin.post(
        "/simulator/media",
        files={"file": ("voice.webm", OGG, "audio/webm")},
        data={"user_id": "suara", "name": "Uji suara"},
    )
    assert r.status_code == 200, r.text
    await queue.drain()
    msgs = (await admin.get(f"/conversations/{r.json()['conversation_id']}/messages")).json()
    voice = next(m for m in msgs if m["direction"] == "in")
    assert voice["kind"] == "audio" and voice["media_url"].startswith("media:")
    assert voice["meta"]["transcript"] is True
    assert any("6 bulan" in m["text"] for m in msgs if m["sender_type"] == "bot")
