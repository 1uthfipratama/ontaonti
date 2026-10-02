"""Heading levels and canonical section labels.

Vendored subset of thesis-rag rag/parse/sections.py: only what rag.chunk needs.
The PDF-specific heading detection (and its PyMuPDF dependency) is left out."""

import re

HEADING_MAX_WORDS = 12
HEADING_SIZE_RATIO = 1.1
PROMINENT_RATIO = 1.15  # size-only headings need a clearer jump than bold ones

NUMBERED = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+[A-Z]")
ROMAN = re.compile(r"^([IVX]+)\.\s+\S")

# First match wins, in this order (plan section 2.5), with two changes:
# - backmatter is checked early: its phrases are specific, and otherwise "data"
#   claims "Availability of data and materials" (p08);
# - "frontmatter" is added: keyword and article-info boxes before the abstract.
# Matched on word starts, so "data" doesn't fire inside "update".
LABEL_KEYWORDS: list[tuple[str, list[str]]] = [
    ("abstract", ["abstract"]),
    (
        "backmatter",
        [
            "acknowledg",
            "author contribution",
            "funding",
            "conflict",
            "data availability",
            "availability of data",
            "appendix",
            "publisher",
            "competing interest",
            "institutional review",
            "informed consent",
            "declaration",
            "abbreviations",
            "supporting information",
            "authors’ information",
            "author details",
            "ethics",
            "credit authorship",  # Elsevier CRediT statement (p10)
            "orcid",
        ],
    ),
    (
        "frontmatter",
        [
            "keywords",
            "index terms",
            "article info",
            "jel",
            "ccs concepts",
            "acm reference",
            "highlights",
        ],
    ),
    ("introduction", ["introduction"]),
    ("literature_review", ["literature", "related work", "review"]),
    ("data", ["data", "sample", "dataset"]),
    (
        "methodology",
        [
            "method",
            "methodology",
            "model",
            "approach",
            "algorithm",
            "framework",
            "solution",
            "numerical",
        ],
    ),
    ("results", ["result", "simulation", "empirical", "experiment", "forecast", "fit", "analysis"]),
    ("discussion", ["discussion"]),
    ("conclusion", ["conclusion", "concluding"]),
    ("references", ["references", "bibliography", "daftar pustaka"]),
]
_KEYWORD_RES = [
    (label, re.compile(r"\b(" + "|".join(re.escape(k) for k in kws) + r")", re.I))
    for label, kws in LABEL_KEYWORDS
]
# An unnumbered, non-caps heading is only accepted if it starts with one of these,
# e.g. "Introduction", "Results and discussion". Otherwise every bold phrase
# would become a section.
KNOWN_START = re.compile(
    r"^(abstract|introduction|background|literature|related work|data|methods?|methodology|"
    r"materials|model|results?|discussion|conclusions?|concluding|references|bibliography|"
    r"acknowledg|appendix|funding|author contributions?|conflicts? of interest|"
    r"data availability|availability of data|competing interests|declarations?|"
    r"keywords|abbreviations|empirical|findings|summary|limitations)\b",
    re.I,
)
MONTH = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|"
    r"December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\b"
)
STRUCTURAL_LABEL = re.compile(
    r"^(abstract|article info|keywords|references|bibliography|acknowledge?ments?|"
    r"data availability( statement)?|conflicts? of interest|funding)\s*:?$",
    re.I,
)
ABSTRACT_PREFIX = re.compile(r"^\s*(Abstract|ABSTRACT)\s*[.:—–-]?\s*")
CAPTION = re.compile(r"^\s*(Table|TABLE|Fig\.?|Figure|FIGURE)\s*[\dIVX]+")


def despace(text: str) -> str:
    """'A B S T R A C T' -> 'ABSTRACT' (Elsevier p10, IJRBS p19)."""
    parts = re.split(r"\s{2,}", text.strip())
    out = []
    for part in parts:
        if re.fullmatch(r"(?:[A-Z] )+[A-Z]", part):
            part = part.replace(" ", "")
        out.append(part)
    return " ".join(out)


def label_for(heading: str) -> str:
    h = re.sub(r"^(\d+(\.\d+)*\.?|[IVX]+\.)\s*", "", despace(heading))
    # Deviation from the plan's order: an explicit "result(s)" wins, otherwise
    # "Numerical Results" (p03) lands in methodology via "numerical".
    if re.search(r"\bresults?\b", h, re.I) and not dict(_KEYWORD_RES)["backmatter"].search(h):
        return "results"
    for label, rx in _KEYWORD_RES:
        if rx.search(h):
            return label
    return "other"


def heading_level(text: str, bold: bool = True) -> int:
    """ "2.1 Euler method" -> 2. Unnumbered: bold or caps is top level, plain/italic
    (p17 "The Heston Model") is a subsection."""
    m = NUMBERED.match(text)
    if m:
        return m.group(1).count(".") + 1
    if ROMAN.match(text) or bold or text.isupper() or STRUCTURAL_LABEL.match(text):
        return 1
    return 2
