"""Test setup: a temporary SQLite file, no Redis (in-process jobs), fake LLM, mocked Meta.

Environment is set before any app import so app.config picks it up (real env
vars win over .env, so a developer's .env never leaks into tests).
"""

import os
import tempfile
from pathlib import Path

# A file (not :memory:) so every session gets its own connection, as on Postgres.
_DB = Path(tempfile.mkdtemp(prefix="onti-test-")) / "test.db"

os.environ.update(
    {
        "DATABASE_URL": f"sqlite+aiosqlite:///{_DB.as_posix()}",
        "REDIS_URL": "",
        "LLM_PROVIDER": "fake",
        "LLM_API_KEY": "",
        "LLM_MODEL_ANSWER": "",
        "LLM_MODEL_CLASSIFIER": "",
        "SECRET_KEY": "test-secret-key-0123456789",
        "COOKIE_SECURE": "false",
        "ADMIN_EMAIL": "admin@test.local",
        "ADMIN_PASSWORD": "test-password-123",
        "WA_ACCESS_TOKEN": "test-wa-access-token",
        "WA_PHONE_NUMBER_ID": "1111111111",
        "WA_BUSINESS_ACCOUNT_ID": "2222222222",
        "WA_APP_SECRET": "test-app-secret",
        "WA_VERIFY_TOKEN": "test-verify-token",
        "WA_GRAPH_VERSION": "v25.0",
        "GRAPH_BASE_URL": "https://graph.test",
        "ENABLE_MESSENGER": "true",
        "ENABLE_INSTAGRAM": "true",
        "META_PAGE_ID": "3333333333",
        "META_PAGE_ACCESS_TOKEN": "test-page-token",
        "META_APP_SECRET": "",
        "META_VERIFY_TOKEN": "",
        "SMTP_HOST": "",
        "WEB_BASE_URL": "http://localhost:3000",
        "TEST_MODE": "true",
        "LOG_LEVEL": "WARNING",
        "MEDIA_DIR": str(_DB.parent / "media"),
        "KB_LIVE_DIR": str(_DB.parent / "kb_live"),
        "TRANSCRIBE_PROVIDER": "fake",
    }
)

import httpx  # noqa: E402
import pytest  # noqa: E402

from app import queue  # noqa: E402
from app.bot import rag_service  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import ensure_admin  # noqa: E402

FAKE_SNIPPETS = [
    rag_service.Snippet(
        1, "p05", "Info TBC 05", "Lama dan tahap pengobatan",
        "Pengobatan TBC sensitif obat umumnya berlangsung minimal 6 bulan. Obat gratis di puskesmas.",
    ),
    rag_service.Snippet(
        2, "p02", "Info TBC 02", "Gejala umum TBC paru",
        "Gejala utama TBC paru adalah batuk berdahak selama dua minggu atau lebih.",
    ),
]  # fmt: skip


@pytest.fixture(autouse=True)
async def fresh_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await ensure_admin()
    yield
    await queue.drain()


@pytest.fixture(autouse=True)
def fake_retrieval(monkeypatch):
    calls: list[tuple[str, int]] = []

    def retrieve(query: str, k: int):
        calls.append((query, k))
        return FAKE_SNIPPETS[:k]

    monkeypatch.setattr(rag_service, "retrieve", retrieve)
    return calls


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def admin(client):
    r = await client.post(
        "/auth/login", json={"email": "admin@test.local", "password": "test-password-123"}
    )
    assert r.status_code == 200, r.text
    return client


async def simulate(client, text: str, user_id: str = "u1", channel: str = "whatsapp") -> dict:
    r = await client.post(
        "/simulator/messages", json={"channel": channel, "user_id": user_id, "text": text}
    )
    assert r.status_code == 200, r.text
    await queue.drain()
    return r.json()


async def thread(client, conv_id: int) -> list[dict]:
    r = await client.get(f"/conversations/{conv_id}/messages")
    assert r.status_code == 200, r.text
    return r.json()
