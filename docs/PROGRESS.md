# Progress — updated 2026-10-02 (evening)

All phases of the spec are built and committed.

| Phase | State |
|---|---|
| 0 — Understand RAG | Done. thesis-rag's retrieval core is vendored in `rag/` (multilingual embedder); the KB is in `kb/` (draft) |
| 1 — Core, simulator, inbox | Done |
| 2 — Safety layer + cases | Done |
| 3 — WhatsApp + Messenger/IG, consent, contacts | Done |
| 4 — WhatsApp broadcasts | Done (the flaky test was the in-memory SQLite harness; tests now use a temp file DB) |
| 5 — Dashboard, settings, cost controls | Done |
| Quality / docs | Done: 92 backend tests, 3 Playwright e2e tests, `seed_demo.py`, `simulate_whatsapp.py`, SETUP / ARCHITECTURE / DEMO |

## Verified

- `pytest`: 92 passed (SQLite, fake LLM, mocked Meta: no network, no cost).
- Playwright: 3 passed against the Docker stack (login → inbox → simulator → bot
  reply; emergency → fixed reply → case).
- `docker compose up --build`: db, redis, api, worker, web all start. Migrations
  `0001..0003` apply on Postgres and the KB index builds in the container.
- Clicked through in a browser: inbox, simulator (consent notice + KB answer live
  over SSE), emergency flow, dashboard, settings.

## Still needs you

1. **Anthropic key**: add `ANTHROPIC_WORKSPACE_ID` to `.env` (or use a
   workspace-scoped key). Until then every answer falls back to the fixed
   "staf kami akan menghubungi" reply plus a BOT_ERROR case. Then run
   `docker compose up -d --force-recreate api worker`.
2. **WhatsApp**: `WA_PHONE_NUMBER_ID`, `WA_BUSINESS_ACCOUNT_ID`, `WA_APP_SECRET`,
   and a fresh token (the one in `.env` is a 24 h token). Steps are in `docs/SETUP.md` §4–5.
3. **Rotate** the Anthropic key and the WhatsApp token you pasted in chat.
4. **Medical review** of `kb/*.md` and the fixed safety texts (Settings → Safety).
5. Optional: strip the old `Co-Authored-By` lines from the first 4 commits
   (commands were given in chat). Newer commits don't have them.

## Open decisions for the foundation

- HUMAN mode: the bot never replies, even to an emergency. Keywords still open a
  case and alert staff. Is that the right call at night with no staff online?
- The "1,000 free messages" figure and the IDR rates are editable placeholders.
  Meta's pricing changed in 2024–2025, so check the current rate card.
