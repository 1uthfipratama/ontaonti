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


@dataclass
class Snippet:
    n: int
    doc_id: str
    title: str
    heading: str
    text: str


def _connect():
    global _db
    if _db is None:
        from rag import index

        db = index.connect(readonly=True)
        index.check_meta(db)
        _db = db
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
