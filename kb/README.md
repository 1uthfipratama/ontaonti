# Knowledge base (KB) — DRAFT, needs medical review

These Markdown files are the only source the bot answers from. They were written
for the feasibility prototype from general, public TB information (WHO / Kemenkes
TOSS TBC messaging). **They are not reviewed by a clinician.** Before any real
patient sees an answer, the foundation's medical team must review, correct and
replace them with the foundation's official materials.

Rules for editing:

- One topic per file, `NN-slug.md`, with front matter: `id` (`p01`..`p99`, unique),
  `title`, `short_cite`.
- `##` headings split a file into sections; the chunker keeps each section together.
- No medication doses or schedules: the bot must never give them.
- No phone numbers or addresses that aren't verified.

After editing, rebuild the index:

```bash
docker compose exec api python scripts/reindex_kb.py
docker compose restart worker
```
