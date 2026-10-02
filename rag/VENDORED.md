# rag/ — vendored from thesis-rag

Copied from `RAG PROT/rag` (github.com/1uthfipratama/thesis-rag, commit `25df011`)
and reused as a module. Only the retrieval/indexing core came over; the PDF parsers,
uploads, evaluation and the thesis chat prompt were left behind.

| file | used by the hub for | changed? |
|---|---|---|
| `config.py` | settings (`EMBED_MODEL`, `TOP_K`, `DATA_DIR`, ...) | defaults: multilingual embedder, E5 prefixes, `top_k` 4, data dir `data/kb` |
| `embed.py` | query/passage embeddings | registers `intfloat/multilingual-e5-small` as a custom fastembed model; adds the passage prefix |
| `tokens.py` | chunk sizing in the embedder's tokens | gets the tokenizer through `embed.model()`; reserves 8 tokens for the prefix |
| `index.py` | `build()`, `connect()`, `check_meta()` | `check_meta` also compares the query/passage prefixes |
| `retrieve.py` | `search()` (BM25 + dense + RRF), `neighbours()` | Indonesian stopwords added |
| `generate.py` | `build_passages()`, `validate_citations()`, `strip_markers()`, `history_messages()` | unchanged (its thesis prompt and Anthropic call are not used) |
| `chunk.py`, `schemas.py`, `manifest.py` | turning KB Markdown into chunks | unchanged |
| `parse/sections.py` | `heading_level()` for the chunker | trimmed to the heading helpers (no PyMuPDF) |

Generation is the hub's own (`app/bot/answer.py`): a different persona, Groq or
Anthropic, WhatsApp formatting and a 900-character limit.

Changing the embedder (`EMBED_MODEL`, `QUERY_INSTRUCTION`, `PASSAGE_PREFIX`) needs a
re-index: `python scripts/reindex_kb.py`. `check_meta()` refuses a stale index.
