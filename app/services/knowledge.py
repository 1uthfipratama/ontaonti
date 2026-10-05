"""Knowledge base editing: articles live in the database, the bot reads an index.

Flow: staff edit articles on the Knowledge page -> "Publish" queues `reindex_kb`
-> the worker exports published articles to KB_LIVE_DIR as Markdown and rebuilds
the index (app/bot/kb.py) -> every process picks the new index up on its next
search (rag_service reconnects when the file changes).

The shipped kb/*.md files are imported once, the first time the page is opened.
"""

import asyncio
import logging
import re
from datetime import datetime

import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import events
from app.bot import kb
from app.config import settings as env
from app.db import SessionLocal, as_utc, utcnow
from app.models import Conversation, KbArticle, KbGap, Message
from app.services import settings_service

log = logging.getLogger("onti.knowledge")

STATUS_KEY = "kb_reindex"  # {"state": idle|queued|running|error, "at": iso, "error": str}
PUBLISHED_KEY = "kb_published_at"
EDITED_KEY = "kb_edited_at"


async def ensure_imported(session: AsyncSession) -> None:
    """First use: copy the active Markdown articles into the database."""
    if await session.scalar(select(func.count()).select_from(KbArticle)):
        return
    for path in kb.kb_files():
        meta, body = kb.split_front_matter(path.read_text(encoding="utf-8"))
        if not meta.get("id") or not meta.get("title"):
            continue
        session.add(KbArticle(doc_id=str(meta["id"]), title=str(meta["title"]), body=body.strip()))
    await session.commit()


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or "artikel"


def to_markdown(a: KbArticle) -> str:
    front = yaml.safe_dump(
        {"id": a.doc_id, "title": a.title, "short_cite": a.title},
        allow_unicode=True,
        sort_keys=False,
    )
    return f"---\n{front}---\n{a.body.strip()}\n"


async def export(session: AsyncSession) -> int:
    """Write published articles to KB_LIVE_DIR (replacing what was there)."""
    rows = (
        (await session.execute(select(KbArticle).where(KbArticle.published.is_(True))))
        .scalars()
        .all()
    )
    if not rows:
        raise RuntimeError("No published articles: the bot needs at least one.")
    live = env.kb_live_dir
    live.mkdir(parents=True, exist_ok=True)
    for old in live.glob("*.md"):
        old.unlink()
    for i, a in enumerate(sorted(rows, key=lambda a: a.doc_id), 1):
        (live / f"{i:02d}-{_slug(a.title)}.md").write_text(to_markdown(a), encoding="utf-8")
    return len(rows)


async def set_status(session: AsyncSession, state: str, error: str = "") -> None:
    await settings_service.set_value(
        session, STATUS_KEY, {"state": state, "at": utcnow().isoformat(), "error": error}
    )
    await session.commit()
    await events.publish("kb.status", state=state)


async def reindex() -> None:
    """Worker job: export + rebuild the index. Errors are shown on the Knowledge page."""
    async with SessionLocal() as session:
        await set_status(session, "running")
        try:
            n = await export(session)
            await asyncio.to_thread(kb.build_index, env.kb_live_dir)
        except Exception as e:
            log.exception("knowledge-base re-index failed")
            await set_status(session, "error", str(e)[:300])
            return
        await settings_service.set_value(session, PUBLISHED_KEY, utcnow().isoformat())
        await set_status(session, "idle")
        log.info("knowledge base re-indexed: %s articles", n)


async def mark_edited(session: AsyncSession) -> None:
    await settings_service.set_value(session, EDITED_KEY, utcnow().isoformat())


async def status(session: AsyncSession) -> dict:
    st = await settings_service.get_value(session, STATUS_KEY) or {"state": "idle"}
    published = await settings_service.get_value(session, PUBLISHED_KEY)
    edited = await settings_service.get_value(session, EDITED_KEY)
    pending = bool(edited) and (
        not published
        or as_utc(datetime.fromisoformat(edited)) > as_utc(datetime.fromisoformat(published))
    )
    open_gaps = await session.scalar(
        select(func.count()).select_from(KbGap).where(KbGap.status == "open")
    )
    return {**st, "published_at": published, "pending": pending, "open_gaps": open_gaps or 0}


async def record_gap(session: AsyncSession, conv: Conversation, msg: Message) -> None:
    session.add(KbGap(question=(msg.text or "")[:1000], conversation_id=conv.id, message_id=msg.id))
    await session.commit()
    await events.publish("kb.gap", conversation_id=conv.id)
