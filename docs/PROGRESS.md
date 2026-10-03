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

## Status on 2026-10-03

- **Bot on real Claude: working.** Sonnet 5.5 answers from the KB, about Rp 110 per
  question including the safety classifier.
- **WhatsApp test number: wired end to end, delivery blocked by Meta.** Webhooks
  arrive (the `ontaonti` app is now subscribed to WABA 944254002089833), the bot
  answers, and Meta refuses delivery (131031). Meta's health check (Settings →
  Channels → Test token) says the *personal* business portfolio needs:
  - Legal name, Country and Website in its business info
  - business verification
  - a payment method (for business-initiated messages)
- The admin UI was redesigned after Mekari Pixel / Talenta.

## Next steps (weekdays)

1. With the foundation's Meta admin: check business.facebook.com → Settings →
   Accounts → WhatsApp accounts. Is the current (Qontak) number's WABA owned by the
   foundation with Mekari as a partner? Is the business verified?
2. **Pilot:** a new WABA + a spare number under the foundation's verified portfolio.
   Qontak stays untouched. Connect the app with a System User token (SETUP §5).
3. **Later cutover:** migrate the live number to the foundation-owned WABA. Number,
   display name, quality rating, limits and approved templates move; chat history
   and Qontak flows don't. Export the history first and agree the timing with Mekari.
4. Before real patient data: proper hosting (not a PC + quick tunnel), backups,
   UU PDP 27/2022 review (health data), medical review of `kb/` and the safety texts.

## Housekeeping

- Docker Desktop must be running for the app and the tunnel. The quick-tunnel URL
  changes on every restart: `docker compose logs tunnel`, then update Meta.
- `WA_ACCESS_TOKEN` is a 24 h token. Replace it with a System User token (SETUP §5).
- Rotate the secrets that were pasted in chat (Anthropic key, WhatsApp token,
  app secret) once the real setup exists.
