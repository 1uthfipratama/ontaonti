"""Runtime settings. Every value can be overridden by an env var or `.env`."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    # Paths. DATA_DIR is overridable (the hub's containers use /app/data/kb).
    # Onti Erlina Hub: the knowledge-base index and its generated manifest live here.
    data_dir: Path = ROOT / "data" / "kb"
    # Point tests/chunking at another backend's output, e.g. data/parsed_alt/mineru
    parsed_dir_override: Path | None = None

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def parsed_dir(self) -> Path:
        return self.parsed_dir_override or self.data_dir / "parsed"

    @property
    def chunks_path(self) -> Path:
        return self.data_dir / "chunks" / "chunks.jsonl"

    @property
    def index_path(self) -> Path:
        return self.data_dir / "index.sqlite"

    @property
    def usage_db_path(self) -> Path:
        return self.data_dir / "usage.sqlite"

    @property
    def manifest_path(self) -> Path:
        return self.data_dir / "manifest.yaml"

    # Parser backend for the core corpus: pymupdf | mineru | hybrid (rag/parse/backends.py)
    # mineru won the parse-level bake-off (eval/results/parsers_20260924_1635.md).
    # User uploads must not use it: ~8 s/page on CPU is too slow for the free Space.
    parse_backend: str = "mineru"

    # Models
    # Onti Erlina Hub: users write Bahasa Indonesia, so the default embedder is
    # multilingual (registered as a custom fastembed model in rag/embed.py).
    # Set EMBED_MODEL=BAAI/bge-small-en-v1.5 plus QUERY_INSTRUCTION="Represent this
    # sentence for searching relevant passages: " and PASSAGE_PREFIX="" for the old
    # English setup. Changing any of the three needs `python scripts/reindex_kb.py`.
    embed_model: str = "intfloat/multilingual-e5-small"
    # Plan default is Haiku 4.5 for cost; Phase 8 compares claude-sonnet-5.
    # Undated IDs are the current form (the plan's "-20251001" suffix is legacy).
    llm_model: str = "claude-haiku-4-5"
    llm_thinking: str = "off"  # "adaptive" enables thinking on models that support it
    # Answers are < 200 words, but list answers (q50) run longer; the plan's 600
    # risked truncation. Raised to 8000 automatically when thinking is on.
    answer_max_tokens: int = 1024
    # Neighbouring chunks (same section) added around each hit: small-to-big context.
    context_neighbours: int = 1
    # Prepended to queries / passages before embedding (rag/embed.py). E5 models are
    # trained with "query: " and "passage: "; BGE uses a query instruction only.
    query_instruction: str = "query: "
    passage_prefix: str = "passage: "
    anthropic_api_key: str = ""

    # Retrieval: fuse 30 BM25 + 30 dense candidates, return top_k.
    # Onti Erlina Hub: a fixed k=4 bounds the prompt (and cost) of every answer.
    top_k: int = 4
    bm25_k: int = 30
    dense_k: int = 30
    rrf_k: int = 60  # standard RRF constant; damps the influence of rank-1 outliers
    # Diversity cap (rag/retrieve.per_paper_cap): max chunks per paper in top_k.
    # "adaptive" tightens to 2 only for list-style questions; see eval/results.
    max_per_paper: int = 3
    # Top-g of each retriever always reach the final top_k (rag/retrieve.search).
    guaranteed_per_retriever: int = 2
    # Tables a retrieved passage refers to ("Table 5 shows...") are attached from the
    # same paper; bounded so context (and cost) can't balloon (rag/generate).
    attach_tables: bool = True
    max_attached_tables: int = 3
    cap_mode: str = "adaptive"  # eval/results/retrieval_*_1735: best coverage/depth trade-off

    # API guards (PLAN.md Phase 9, PLAN_ADDENDUM 14.1)
    max_question_chars: int = 500
    max_history_chars: int = 4000  # per turn sent back by the browser
    rate_limit: str = "10/minute"  # per access code (or per IP when no code is set)
    upload_rate_limit: str = "5/hour"  # PLAN_ADDENDUM 13.5
    # Spend guard: ~$0.006/question on Haiku, so 100/day caps a public demo at ~$0.60/day.
    daily_question_cap: int = 100
    # Shared passphrase for asking, uploading and deleting. Empty = open (local dev only).
    access_code: str = ""
    # Demo/UI-development mode: no Claude calls, canned answers from real passages.
    fake_llm: bool = False

    # HF Space (PLAN_ADDENDUM 11.4): the index holds text from papers that aren't open
    # access, so it lives in a private dataset repo and is downloaded on boot.
    hf_token: str = ""
    hf_dataset_repo: str = ""  # e.g. "<user>/thesis-rag-data"; empty = use the local index


settings = Settings()
