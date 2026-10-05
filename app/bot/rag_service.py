"""Retrieval through the vendored thesis-rag module (rag/).

rag.retrieve.search (BM25 + dense + RRF) -> rag.generate.build_passages (adds
same-section neighbours). SQLite + ONNX are synchronous, so callers run this in a
thread; one connection guarded by a lock is plenty at this scale.
"""

import logging
import re
import threading
from dataclasses import dataclass

log = logging.getLogger("onti.rag")
_lock = threading.Lock()
_db = None
_db_mtime = 0.0


@dataclass
class Snippet:
    n: int
    doc_id: str
    title: str
    heading: str
    text: str


def _connect():
    """Cached read-only connection, reopened when the index file is replaced
    (a re-index from the Knowledge page runs in the worker, not in this process)."""
    global _db, _db_mtime
    from rag import index
    from rag.config import settings as rag_settings

    try:
        mtime = rag_settings.index_path.stat().st_mtime
    except OSError:
        mtime = 0.0
    if _db is not None and mtime != _db_mtime:
        log.info("knowledge-base index changed; reconnecting")
        reset()
    if _db is None:
        db = index.connect(readonly=True)
        index.check_meta(db)
        _db, _db_mtime = db, mtime
    return _db


def reset() -> None:
    """Drop the cached connection (after a re-index)."""
    global _db
    if _db is not None:
        _db.close()
    _db = None


_CARD_NOISE = re.compile(r"^(Authors|Year|DOI|Also cited as):.*$\n?", re.M)


def retrieve(query: str, k: int) -> list[Snippet]:
    from rag.generate import build_passages
    from rag.retrieve import search

    with _lock:
        db = _connect()
        hits = search(db, query, top_k=k)
        passages = build_passages(db, hits)
    out = []
    for p in passages:
        text = p.text
        if p.hit.kind == "paper_card":
            text = _CARD_NOISE.sub("", text).replace("Abstract: ", "")
        heading = "Ringkasan" if p.hit.heading == "Paper overview" else p.hit.heading
        out.append(Snippet(p.n, p.hit.paper_id, p.hit.short_cite, heading, text.strip()))
    return out


def format_context(snippets: list[Snippet]) -> str:
    if not snippets:
        return "(tidak ada materi yang relevan)"
    return "\n\n".join(f"[{s.n}] {s.title} — {s.heading}\n{s.text}" for s in snippets)
