"""Turn an uploaded document into a knowledge-base article (Markdown).

Output shape is what app/bot/kb.py indexes: intro paragraphs, then "## Heading"
sections, paragraphs separated by blank lines.

- PDF (PyMuPDF): headings from font size and boldness relative to the body text,
  running headers/footers and page numbers removed, two-column pages read in
  order, words broken across lines rejoined. Adapted from the thesis-rag parser
  (rag/parse in RAG PROT), simplified for guidelines, SOPs and leaflets.
- Word (.docx): real heading styles, bullet lists, tables as "header: value" lines.
- Text / Markdown: kept as written ("#" headings become sections).

Scanned PDFs have no text layer; they're refused with a clear message (no OCR).
"""

import io
import re
import statistics
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import PurePath

SUPPORTED = (".pdf", ".docx", ".txt", ".md")
MAX_MB = 40


class ParseError(ValueError):
    """Shown to the user as is."""


@dataclass
class Parsed:
    title: str
    markdown: str
    pages: int = 0
    sections: int = 0
    words: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class _Item:
    kind: str  # title | h2 | h3 | p | list
    text: str


_CTRL = re.compile("[\x00-\x08\x0b-\x1f\x7f-]")
_BULLET = re.compile(r"^\s*([•●▪◦○■□➢►\-–*]|\(?[0-9]{1,2}[.)]|[a-z][.)])\s+")
_NUMBERED_HEADING = re.compile(r"^(\d+(\.\d+)*|[IVX]+|[A-Z])[.)]?\s+\S")


def clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("­", "")
    return _CTRL.sub("", text)


def _title_from(filename: str) -> str:
    stem = PurePath(filename).stem
    return re.sub(r"[_\-]+", " ", stem).strip().capitalize() or "Dokumen"


def _assemble(items: list[_Item], fallback_title: str) -> Parsed:
    title = next((i.text for i in items if i.kind == "title"), "") or fallback_title
    out: list[str] = []
    sections = 0
    for it in items:
        if it.kind == "title":
            continue
        if it.kind in ("h2", "h3"):
            if out and out[-1].startswith("#"):  # two headings in a row: keep the second
                out.pop()
                sections -= 1
            out.append(("## " if it.kind == "h2" else "### ") + it.text)
            sections += 1
        elif it.kind == "list" and out and out[-1].startswith("- "):
            out[-1] += "\n- " + it.text  # one paragraph per list
        elif it.kind == "list":
            out.append("- " + it.text)
        else:
            out.append(it.text)
    while out and out[-1].startswith("#"):  # a heading with nothing under it
        out.pop()
        sections -= 1
    markdown = "\n\n".join(out).strip()
    return Parsed(title=title[:200], markdown=markdown, sections=max(sections, 0),
                  words=len(markdown.split()))  # fmt: skip


# --- PDF -----------------------------------------------------------------------


@dataclass
class _Line:
    text: str
    size: float
    bold: bool
    bbox: tuple[float, float, float, float]


@dataclass
class _Block:
    lines: list[_Line]
    bbox: tuple[float, float, float, float]

    @property
    def text(self) -> str:
        return " ".join(ln.text for ln in self.lines)

    @property
    def size(self) -> float:
        c: Counter[float] = Counter()
        for ln in self.lines:
            c[round(ln.size, 1)] += max(1, len(ln.text))
        return c.most_common(1)[0][0] if c else 0.0

    @property
    def bold(self) -> bool:
        n = sum(len(ln.text) for ln in self.lines)
        return n > 0 and sum(len(ln.text) for ln in self.lines if ln.bold) / n > 0.6


def _line_key(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", text.lower())).strip()


def _reading_order(blocks: list[_Block], width: float) -> list[_Block]:
    """Top to bottom; on two-column stretches, left column before right."""
    blocks = sorted(blocks, key=lambda b: (round(b.bbox[1]), b.bbox[0]))
    mid = width / 2
    left = [b for b in blocks if b.bbox[2] <= mid + 10]
    right = [b for b in blocks if b.bbox[0] >= mid - 10]
    two_col = len(left) >= 3 and len(right) >= 3
    if not two_col:
        return blocks
    out, band = [], []
    for b in blocks:
        full = b.bbox[0] < mid - 10 and b.bbox[2] > mid + 10
        if full:  # a full-width block closes the band above it
            out += [x for x in band if x.bbox[2] <= mid + 10] + [
                x for x in band if x.bbox[2] > mid + 10
            ]
            out.append(b)
            band = []
        else:
            band.append(b)
    out += [x for x in band if x.bbox[2] <= mid + 10] + [x for x in band if x.bbox[2] > mid + 10]
    return out


def _join_lines(lines: list[str]) -> str:
    """Rejoin a block's lines: "pengo-" + "batan" -> "pengobatan"; bullets stay apart."""
    out = ""
    for ln in lines:
        ln = ln.strip()
        if not out:
            out = ln
        elif _BULLET.match(ln):
            out += "\n" + ln
        elif re.search(r"[a-zà-ÿ]-$", out) and ln[:1].islower():
            out = out[:-1] + ln
        else:
            out += " " + ln
    return re.sub(r"[ \t]+", " ", out)


def parse_pdf(data: bytes, filename: str) -> Parsed:
    import pymupdf

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as e:
        raise ParseError("This PDF can't be opened (damaged or not a PDF).") from e
    if doc.needs_pass:
        raise ParseError("This PDF is password-protected. Remove the password and upload again.")

    pages: list[tuple[float, float, list[_Block]]] = []
    for page in doc:
        blocks = []
        for b in page.get_text("dict")["blocks"]:
            if b.get("type") != 0:
                continue
            lines = []
            for ln in b["lines"]:
                if tuple(round(x) for x in ln["dir"]) != (1, 0):  # rotated stamps, axis labels
                    continue
                spans = [s for s in ln["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = clean("".join(s["text"] for s in ln["spans"])).strip()
                size = statistics.median(s["size"] for s in spans)
                if not text or size < 4:
                    continue
                n = sum(len(s["text"]) for s in spans)
                bold = (
                    sum(len(s["text"]) for s in spans if s["flags"] & 16 or "Bold" in s["font"]) / n
                    > 0.5
                )
                lines.append(_Line(text, size, bold, tuple(ln["bbox"])))
            if lines:
                xs0, ys0, xs1, ys1 = zip(*(ln.bbox for ln in lines), strict=True)
                blocks.append(_Block(lines, (min(xs0), min(ys0), max(xs1), max(ys1))))
        pages.append((page.rect.width, page.rect.height, blocks))
    n_pages = len(pages)
    total_chars = sum(len(b.text) for _, _, bl in pages for b in bl)
    if total_chars < 20:
        raise ParseError(
            "No text found: this PDF looks like a scan (photos of pages). "
            "Upload the original Word/PDF file, or a version with selectable text."
        )

    sizes: Counter[float] = Counter()
    for _w, _h, bl in pages:
        for b in bl:
            for ln in b.lines:
                sizes[round(ln.size, 1)] += len(ln.text)
    body = sizes.most_common(1)[0][0] if sizes else 10.0

    # Running headers/footers: small lines in the top/bottom margin repeating on half
    # the pages. Bigger text there is a section heading that happens to sit at the top.
    seen: Counter[str] = Counter()
    for _w, h, bl in pages:
        keys = {_line_key(ln.text) for b in bl for ln in b.lines
                if ln.bbox[1] < 0.1 * h or ln.bbox[3] > 0.9 * h}  # fmt: skip
        seen.update(keys)
    repeated = {k for k, n in seen.items() if n_pages >= 3 and n >= 0.5 * n_pages and len(k) >= 4}
    for _w, h, bl in pages:
        for b in bl:
            b.lines = [
                ln for ln in b.lines
                if not ((ln.bbox[1] < 0.1 * h or ln.bbox[3] > 0.9 * h) and ln.size <= body * 1.05
                        and (_line_key(ln.text) in repeated or re.fullmatch(r"[-–\s]*\d{1,4}[-–\s]*", ln.text)))
            ]  # fmt: skip
        bl[:] = [b for b in bl if b.lines]

    items: list[_Item] = []
    have_title = False
    for w, _h, bl in pages:
        for b in _reading_order(bl, w):
            text = _join_lines([ln.text for ln in b.lines]).strip()
            if not text:
                continue
            words = len(text.split())
            short = words <= 14 and len(b.lines) <= 3 and not text.endswith((".", ",", ";", ":"))
            bigger = b.size >= body * 1.15
            if (
                short
                and (bigger or (b.bold and b.size >= body * 0.95))
                and re.search(r"[A-Za-z]", text)
            ):
                heading = text.replace("\n", " ")
                if not have_title and not items and b.size >= body * 1.4:
                    items.append(_Item("title", heading))
                    have_title = True
                elif b.size >= body * 1.3 or (
                    _NUMBERED_HEADING.match(heading) and heading.count(".") <= 1
                ):
                    items.append(_Item("h2", heading))
                else:
                    items.append(_Item("h3" if not bigger else "h2", heading))
            elif "\n" in text and all(_BULLET.match(x) for x in text.split("\n")[1:]):
                head, *rest = text.split("\n")
                if _BULLET.match(head):
                    rest = [head, *rest]
                else:
                    items.append(_Item("p", head))
                items += [_Item("list", _BULLET.sub("", x).strip()) for x in rest]
            elif _BULLET.match(text):
                items.append(_Item("list", _BULLET.sub("", text).strip()))
            else:
                items.append(_Item("p", text))

    meta_title = clean((doc.metadata or {}).get("title") or "").strip()
    parsed = _assemble(items, meta_title if len(meta_title) > 3 else _title_from(filename))
    parsed.pages = n_pages
    if total_chars < 200 * n_pages:
        parsed.warnings.append(
            "Little text per page: parts may be scanned images, which aren't read."
        )
    if parsed.sections == 0:
        parsed.warnings.append(
            "No headings found: add a few (## Heading) so answers cite the right part."
        )
    return parsed


# --- Word ------------------------------------------------------------------------


def parse_docx(data: bytes, filename: str) -> Parsed:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        d = docx.Document(io.BytesIO(data))
    except Exception as e:
        raise ParseError("This Word file can't be opened. Save it as .docx and try again.") from e

    items: list[_Item] = []
    for el in d.element.body.iterchildren():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(el, d)
            text = clean(p.text).strip()
            if not text:
                continue
            style = (p.style.name if p.style is not None else "").lower()
            numbered = el.pPr is not None and el.pPr.numPr is not None
            runs = [r for r in p.runs if r.text.strip()]
            all_bold = bool(runs) and all(r.bold for r in runs)
            if style == "title":
                items.append(_Item("title", text))
            elif style.startswith("heading"):
                level = int(re.sub(r"\D", "", style) or 1)
                items.append(_Item("h2" if level <= 1 else "h3", text))
            elif "list" in style or numbered:
                items.append(_Item("list", text))
            elif all_bold and len(text.split()) <= 12 and not text.endswith("."):
                items.append(_Item("h2", text))
            else:
                items.append(_Item("p", text))
        elif tag == "tbl":
            rows = []
            for r in Table(el, d).rows:
                cells: list[str] = []
                for c in r.cells:  # merged cells repeat; keep each once
                    t = clean(c.text).strip().replace("\n", " ")
                    if not cells or cells[-1] != t:
                        cells.append(t)
                rows.append(cells)
            rows = [r for r in rows if any(r)]
            if len(rows) >= 2 and len(rows[0]) > 1:
                head = rows[0]
                for r in rows[1:]:
                    pairs = [f"{h}: {v}" if h else v for h, v in zip(head, r, strict=False) if v]
                    items.append(_Item("list", "; ".join(pairs)))
            else:
                items += [_Item("p", " · ".join(c for c in r if c)) for r in rows]
    if not items:
        raise ParseError("This Word file has no text.")
    title = clean(d.core_properties.title or "").strip()
    parsed = _assemble(items, title if len(title) > 3 else _title_from(filename))
    if parsed.sections == 0:
        parsed.warnings.append(
            "No headings found: add a few (## Heading) so answers cite the right part."
        )
    return parsed


# --- Text / Markdown ---------------------------------------------------------------


def parse_text(data: bytes, filename: str) -> Parsed:
    try:
        raw = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raw = data.decode("latin-1")
    raw = clean(raw.replace("\r\n", "\n").replace("\r", "\n"))
    if raw.startswith("---\n") and "\n---\n" in raw[4:]:  # drop front matter
        raw = raw.split("\n---\n", 1)[1]
    items: list[_Item] = []
    for para in re.split(r"\n\s*\n", raw):
        para = para.strip()
        if not para:
            continue
        m = re.match(r"^(#{1,6})\s+(.+)$", para.splitlines()[0])
        if m:
            level = len(m.group(1))
            kind = "title" if level == 1 and not items else ("h2" if level <= 2 else "h3")
            items.append(_Item(kind, m.group(2).strip()))
            rest = "\n".join(para.splitlines()[1:]).strip()
            if rest:
                items.append(_Item("p", rest))
        else:
            items.append(_Item("p", para))
    if not items:
        raise ParseError("This file is empty.")
    parsed = _assemble(items, _title_from(filename))
    if parsed.sections == 0 and parsed.words > 300:
        parsed.warnings.append(
            "No headings found: add a few (## Heading) so answers cite the right part."
        )
    return parsed


def parse(data: bytes, filename: str) -> Parsed:
    ext = PurePath(filename.lower()).suffix
    if ext not in SUPPORTED:
        raise ParseError("Upload a PDF, Word (.docx), text (.txt) or Markdown (.md) file.")
    if len(data) > MAX_MB * 1024 * 1024:
        raise ParseError(f"File too large (max {MAX_MB} MB).")
    if ext == ".pdf":
        parsed = parse_pdf(data, filename)
    elif ext == ".docx":
        parsed = parse_docx(data, filename)
    else:
        parsed = parse_text(data, filename)
    if parsed.words < 5:
        raise ParseError("Hardly any text was found in this file.")
    return parsed
