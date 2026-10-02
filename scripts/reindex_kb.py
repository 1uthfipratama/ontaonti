"""Rebuild the knowledge-base index (kb/*.md -> data/kb/index.sqlite).

    python scripts/reindex_kb.py              # always rebuild
    python scripts/reindex_kb.py --if-needed  # only if missing, stale, or the embedder changed

Run after editing kb/ or changing EMBED_MODEL / QUERY_INSTRUCTION / PASSAGE_PREFIX.
In Docker: docker compose exec api python scripts/reindex_kb.py && docker compose restart worker
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.bot.kb import build_index, index_status  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--if-needed", action="store_true")
    args = ap.parse_args()
    if args.if_needed:
        ok, reason = index_status()
        if ok:
            print("knowledge-base index is up to date")
            return
        print(f"rebuilding knowledge-base index: {reason}")
    t0 = time.perf_counter()
    meta = build_index()
    print(
        f"indexed {meta['n_docs']} documents, {meta['n_chunks']} chunks with "
        f"{meta['embed_model']} in {time.perf_counter() - t0:.1f}s"
    )


if __name__ == "__main__":
    main()
