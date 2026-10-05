"""Knowledge page: articles in the database, publish -> re-index, unanswered questions."""

import pytest

from app import queue
from app.bot import kb, rag_service
from app.config import settings
from tests.conftest import simulate, thread


@pytest.fixture
def built(monkeypatch):
    """Stand-in for the real index build (which embeds every passage)."""
    calls: list[list[str]] = []

    def build_index(kb_dir=None):
        calls.append(sorted(p.name for p in kb.kb_files(kb_dir)))
        for p in kb.kb_files(kb_dir):
            kb.parse_markdown(p)  # the exported files must parse
        return {}

    monkeypatch.setattr(kb, "build_index", build_index)
    return calls


async def test_shipped_articles_are_imported_once(admin):
    rows = (await admin.get("/kb/articles")).json()
    shipped = kb.kb_files(settings.kb_dir)
    assert len(rows) == len(shipped) and rows[0]["doc_id"] == "p01"
    assert len((await admin.get("/kb/articles")).json()) == len(shipped)  # not twice
    one = (await admin.get(f"/kb/articles/{rows[0]['id']}")).json()
    assert one["body"].startswith("TBC") or one["body"]


async def test_edit_then_publish_reindexes(admin, built):
    rows = (await admin.get("/kb/articles")).json()
    assert (await admin.get("/kb/status")).json()["pending"] is False
    new = await admin.post("/kb/articles", json={
        "title": "Jadwal layanan yayasan",
        "body": "Kantor buka Senin sampai Jumat.\n\n## Alamat\n\nJalan Contoh 1, Jakarta.",
    })  # fmt: skip
    assert new.status_code == 200 and new.json()["doc_id"] == f"p{len(rows) + 1:02d}"
    hidden = rows[0]
    await admin.put(f"/kb/articles/{hidden['id']}", json={"title": hidden["title"], "body": "x",
                                                        "published": False})  # fmt: skip
    assert (await admin.get("/kb/status")).json()["pending"] is True

    r = await admin.post("/kb/publish")
    assert r.status_code == 200
    await queue.drain()
    st = (await admin.get("/kb/status")).json()
    assert st["state"] == "idle" and st["pending"] is False and st["published_at"]
    assert len(built) == 1 and len(built[0]) == len(rows)  # +1 new, -1 unpublished
    assert kb.active_kb_dir() == settings.kb_live_dir
    assert any("jadwal-layanan-yayasan" in n for n in built[0])


async def test_publish_failure_is_reported(admin, monkeypatch):
    await admin.get("/kb/articles")

    def boom(kb_dir=None):
        raise RuntimeError("embedder missing")

    monkeypatch.setattr(kb, "build_index", boom)
    await admin.post("/kb/publish")
    await queue.drain()
    st = (await admin.get("/kb/status")).json()
    assert st["state"] == "error" and "embedder missing" in st["error"]


async def test_agents_read_but_cannot_edit(admin, client):
    await admin.post("/staff", json={"email": "ag@test.local", "role": "agent",
                                     "password": "agent-pass-123"})  # fmt: skip
    await client.post("/auth/logout")
    await client.post("/auth/login", json={"email": "ag@test.local", "password": "agent-pass-123"})
    assert (await client.get("/kb/articles")).status_code == 200
    assert (await client.post("/kb/articles", json={"title": "x"})).status_code == 403
    assert (await client.post("/kb/publish")).status_code == 403


async def test_unanswered_question_is_listed(admin, monkeypatch):
    monkeypatch.setattr(rag_service, "retrieve", lambda q, k: [])  # nothing in the KB
    out = await simulate(admin, "Apakah ada bantuan transport ke puskesmas?")
    bot = [m for m in await thread(admin, out["conversation_id"]) if m["sender_type"] == "bot"]
    assert bot[-1]["meta"]["unanswered"] is True
    assert "[NOINFO]" not in bot[-1]["text"]

    gaps = (await admin.get("/kb/gaps")).json()
    assert [g["question"] for g in gaps] == ["Apakah ada bantuan transport ke puskesmas?"]
    assert (await admin.get("/kb/status")).json()["open_gaps"] == 1
    await admin.post(f"/kb/gaps/{gaps[0]['id']}", json={"status": "done"})
    assert (await admin.get("/kb/gaps")).json() == []


async def test_answered_question_is_not_a_gap(admin):
    out = await simulate(admin, "Berapa lama pengobatan TBC?")
    bot = [m for m in await thread(admin, out["conversation_id"]) if m["sender_type"] == "bot"]
    assert bot[-1]["meta"]["unanswered"] is False
    assert (await admin.get("/kb/gaps")).json() == []
