"""Knowledge page: edit the bot's articles, publish them, review unanswered questions."""

import asyncio
import mimetypes
import re
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import queue
from app.audit import audit
from app.db import get_session, utcnow
from app.deps import admin_only, any_staff, can_act, client_ip
from app.models import KbArticle, KbGap, StaffUser
from app.serializers import iso
from app.services import doc_parser, knowledge, media

router = APIRouter(prefix="/kb", tags=["knowledge"])


def _article(a: KbArticle, full: bool = True) -> dict:
    out = {
        "id": a.id,
        "doc_id": a.doc_id,
        "title": a.title,
        "published": a.published,
        "updated_at": iso(a.updated_at),
        "source_name": a.source_name,
        "source_url": a.source_file,
    }
    if full:
        out["body"] = a.body
    return out


class ArticleIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=1_000_000)  # whole guidelines fit
    published: bool = True


@router.get("/articles")
async def list_articles(
    user: StaffUser = Depends(any_staff), session: AsyncSession = Depends(get_session)
):
    await knowledge.ensure_imported(session)
    rows = (await session.execute(select(KbArticle).order_by(KbArticle.doc_id))).scalars().all()
    return [_article(a, full=False) for a in rows]


@router.get("/articles/{article_id}")
async def get_article(
    article_id: int,
    user: StaffUser = Depends(any_staff),
    session: AsyncSession = Depends(get_session),
):
    a = await session.get(KbArticle, article_id)
    if a is None:
        raise HTTPException(404, "Not found")
    return _article(a)


async def _next_doc_id(session: AsyncSession) -> str:
    ids = (await session.execute(select(KbArticle.doc_id))).scalars().all()
    nums = [int(m.group(1)) for d in ids if (m := re.fullmatch(r"p(\d+)", d))]
    return f"p{(max(nums, default=0) + 1):02d}"


@router.post("/articles")
async def create_article(
    body: ArticleIn,
    request: Request,
    user: StaffUser = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
):
    await knowledge.ensure_imported(session)
    a = KbArticle(doc_id=await _next_doc_id(session), title=body.title.strip(), body=body.body,
                  published=body.published, updated_by=user.id)  # fmt: skip
    session.add(a)
    try:
        await session.flush()
    except IntegrityError as e:
        raise HTTPException(409, "Article id already exists") from e
    await knowledge.mark_edited(session)
    audit(session, user, "kb.create", "kb_article", a.id, {"doc_id": a.doc_id}, client_ip(request))
    await session.commit()
    return _article(a)


@router.post("/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    user: StaffUser = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
):
    """PDF / Word / text -> a hidden draft article for staff to check, then publish."""
    name = (file.filename or "dokumen").replace("/", "_").replace("\\", "_")[:200]
    data = await file.read(doc_parser.MAX_MB * 1024 * 1024 + 1)
    try:
        parsed = await asyncio.to_thread(doc_parser.parse, data, name)
    except doc_parser.ParseError as e:
        raise HTTPException(422, str(e)) from e
    await knowledge.ensure_imported(session)
    mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
    a = KbArticle(doc_id=await _next_doc_id(session), title=parsed.title, body=parsed.markdown,
                  published=False, source_name=name, source_file=media.save(data, mime, name),
                  updated_by=user.id)  # fmt: skip
    session.add(a)
    await session.flush()
    await knowledge.mark_edited(session)
    audit(session, user, "kb.upload", "kb_article", a.id,
          {"file": name, "words": parsed.words}, client_ip(request))  # fmt: skip
    await session.commit()
    return {
        "article": _article(a, full=False),
        "report": {"pages": parsed.pages, "sections": parsed.sections, "words": parsed.words,
                   "warnings": parsed.warnings},
    }  # fmt: skip


@router.put("/articles/{article_id}")
async def update_article(
    article_id: int,
    body: ArticleIn,
    request: Request,
    user: StaffUser = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
):
    a = await session.get(KbArticle, article_id)
    if a is None:
        raise HTTPException(404, "Not found")
    a.title, a.body, a.published, a.updated_by = (
        body.title.strip(),
        body.body,
        body.published,
        user.id,
    )
    a.updated_at = utcnow()
    await knowledge.mark_edited(session)
    audit(session, user, "kb.update", "kb_article", a.id, {"doc_id": a.doc_id}, client_ip(request))
    await session.commit()
    return _article(a)


@router.delete("/articles/{article_id}")
async def delete_article(
    article_id: int,
    request: Request,
    user: StaffUser = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
):
    a = await session.get(KbArticle, article_id)
    if a is None:
        raise HTTPException(404, "Not found")
    await knowledge.mark_edited(session)
    audit(session, user, "kb.delete", "kb_article", a.id, {"doc_id": a.doc_id}, client_ip(request))
    await session.delete(a)
    await session.commit()
    return {"ok": True}


@router.get("/status")
async def kb_status(
    user: StaffUser = Depends(any_staff), session: AsyncSession = Depends(get_session)
):
    return await knowledge.status(session)


@router.post("/publish")
async def publish(
    request: Request,
    user: StaffUser = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
):
    st = await knowledge.status(session)
    if st["state"] in ("queued", "running"):
        raise HTTPException(409, "Already updating the knowledge base")
    await knowledge.set_status(session, "queued")
    audit(session, user, "kb.publish", "kb", "", ip=client_ip(request))
    await session.commit()
    await queue.enqueue("reindex_kb", _job_id=f"kb-{utcnow().timestamp():.0f}")
    return await knowledge.status(session)


# --- unanswered questions ---------------------------------------------------------


@router.get("/gaps")
async def list_gaps(
    status: Literal["open", "done", "ignored", "all"] = "open",
    user: StaffUser = Depends(any_staff),
    session: AsyncSession = Depends(get_session),
):
    q = select(KbGap).order_by(KbGap.created_at.desc()).limit(300)
    if status != "all":
        q = q.where(KbGap.status == status)
    rows = (await session.execute(q)).scalars().all()
    return [
        {
            "id": g.id,
            "question": g.question,
            "conversation_id": g.conversation_id,
            "status": g.status,
            "created_at": iso(g.created_at),
        }
        for g in rows
    ]


class GapIn(BaseModel):
    status: Literal["open", "done", "ignored"]


@router.post("/gaps/{gap_id}")
async def set_gap(
    gap_id: int,
    body: GapIn,
    request: Request,
    user: StaffUser = Depends(can_act),
    session: AsyncSession = Depends(get_session),
):
    g = await session.get(KbGap, gap_id)
    if g is None:
        raise HTTPException(404, "Not found")
    g.status, g.handled_by, g.handled_at = body.status, user.id, utcnow()
    audit(session, user, "kb.gap", "kb_gap", g.id, {"status": body.status}, client_ip(request))
    await session.commit()
    return {"id": g.id, "status": g.status}
