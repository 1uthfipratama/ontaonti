"""Knowledge base: kb/*.md -> the thesis-rag chunker and index (rag/).

The RAG module was built for PDFs: Paper (manifest entry) + ParsedDoc (sections of
blocks) -> rag.chunk.chunk_doc -> rag.index.build. Markdown maps onto that
directly: the paragraph(s) before the first "##" become the abstract (carried by
the paper card), every "##" heading a section, every paragraph a block. No
second chunking or indexing code path.
"""

import hashlib
import re
from pathlib import Path

import yaml

from app.config import settings as env

FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
KB_AUTHOR = "Onti-KB"  # a token no user types, so rag.retrieve.named_papers stays quiet


def kb_files(kb_dir: Path | None = None) -> list[Path]:
    return sorted(p for p in (kb_dir or env.kb_dir).glob("*.md") if p.name.lower() != "readme.md")


def kb_sha(files: list[Path]) -> str:
    h = hashlib.sha256()
    for p in files:
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def parse_markdown(path: Path):
    from rag.manifest import Paper
    from rag.schemas import Block, ParsedDoc, Section

    raw = path.read_text(encoding="utf-8")
    m = FRONT_MATTER.match(raw)
    if not m:
        raise ValueError(f"{path.name}: missing front matter (id, title, short_cite)")
    meta = yaml.safe_load(m.group(1)) or {}
    body = raw[m.end() :]
    paper = Paper(
        id=meta["id"],
        file=path.name,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        title=meta["title"],
        authors=[KB_AUTHOR],
        year=int(meta.get("year", 2026)),
        venue="Onti Erlina knowledge base",
        short_cite=meta.get("short_cite", meta["title"]),
        layout="one_column",
        open_access=True,
    )

    def block(text: str) -> Block:
        return Block(page=1, bbox=(0, 0, 0, 0), text=text, font_size=10, is_bold=False, kind="text")

    sections: list[Section] = []
    intro: list[str] = []
    current: Section | None = None
    for para in re.split(r"\n\s*\n", body.strip()):
        para = para.strip()
        if not para:
            continue
        heading = re.match(r"^#{1,3}\s+(.+)$", para.splitlines()[0])
        if heading:
            current = Section(
                label="other", heading=heading.group(1).strip(), page_start=1, blocks=[]
            )
            sections.append(current)
            rest = "\n".join(para.splitlines()[1:]).strip()
            if rest:
                current.blocks.append(block(rest))
        elif current is None:
            intro.append(para)
        else:
            current.blocks.append(block(para))
    if intro:
        abstract = Section(
            label="abstract", heading="Ringkasan", page_start=1, blocks=[block(" ".join(intro))]
        )
        sections.insert(0, abstract)
    doc = ParsedDoc(
        paper_id=paper.id, title=paper.title, sections=sections, tables=[], references=[],
        page_layouts={1: "one_column"}, backend="markdown", dropped={},
    )  # fmt: skip
    return paper, doc


def build_index(kb_dir: Path | None = None) -> dict:
    """Chunk and index every KB file; writes data_dir/index.sqlite and manifest.yaml."""
    from rag import index
    from rag.chunk import chunk_doc
    from rag.config import settings as rag_settings

    files = kb_files(kb_dir)
    if not files:
        raise RuntimeError(f"no knowledge-base files in {kb_dir or env.kb_dir}")
    papers, chunks = [], []
    for f in files:
        paper, doc = parse_markdown(f)
        papers.append(paper)
        chunks += chunk_doc(paper, doc)
    ids = [p.id for p in papers]
    if len(set(ids)) != len(ids):
        raise RuntimeError(f"duplicate KB ids: {ids}")

    rag_settings.data_dir.mkdir(parents=True, exist_ok=True)
    # rag.retrieve.named_papers() reads the manifest; write one for the KB.
    rag_settings.manifest_path.write_text(
        yaml.safe_dump([p.model_dump() for p in papers], allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    meta = index.build(chunks, papers)
    db = index.connect()
    db.execute("INSERT OR REPLACE INTO meta VALUES ('kb_sha', ?)", (kb_sha(files),))
    db.commit()
    db.close()
    return {**meta, "kb_sha": kb_sha(files), "n_docs": str(len(papers))}


def index_status() -> tuple[bool, str]:
    """(usable, reason). Usable = exists, same embedder settings, same KB files."""
    from rag import index
    from rag.config import settings as rag_settings

    if not rag_settings.index_path.exists():
        return False, "missing"
    try:
        db = index.connect(readonly=True)
        try:
            meta = index.check_meta(db)
        finally:
            db.close()
    except RuntimeError as e:
        return False, str(e)
    if meta.get("kb_sha") != kb_sha(kb_files()):
        return False, "knowledge-base files changed"
    return True, "ok"
