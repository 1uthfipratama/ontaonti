# Onti Erlina Hub

Feasibility prototype of an omnichannel inbox, a TB companion chatbot ("Onti
Erlina") and an admin dashboard for a TB health foundation, as a possible
replacement for Mekari Qontak. **Prototype — test data only.**

- **Channels**: WhatsApp Cloud API, Messenger, Instagram (feature-flagged) and a
  built-in simulator.
- **Bot**: RAG answers from a TB knowledge base, in Bahasa Indonesia or English;
  never diagnoses, never gives doses; one WhatsApp message ≤ 900 chars.
- **Safety**: keyword rules plus an LLM classifier. Risky messages get a fixed
  safety reply (IGD / 119), a case for staff, and a human takeover.
- **Inbox**: live 3-panel inbox, Bot/Human toggle, cases, AI summary, contacts
  with merged identities, consent (STOP / MULAI / LANGGANAN), audit log.
- **Broadcasts**: WhatsApp templates to consented contacts, with cost estimate,
  rate limit, retries and delivery/read stats.
- **Cost controls**: monthly AI budget with alert and fallback, per-contact rate
  limit and daily cap, token and cost logging per call.
- **TB programme**: patient journey board, daily medication reminders with
  Sudah / Belum buttons and missed-dose follow-up, symptom screening over chat
  ("SKRINING"), kader tasks, programme reports and CSV exports.
- **Staff tools**: Bahasa Indonesia UI (English switch), saved replies, notes,
  labels, AI-suggested replies, photos/files/voice notes (transcribed), knowledge
  editor with an unanswered-questions list, office hours, two-step verification,
  installable app, daily backups.

Stack: FastAPI · SQLAlchemy 2 + Alembic · PostgreSQL · Redis + arq · SSE ·
Next.js 16 + Tailwind + shadcn/ui · Groq or Anthropic · fastembed
(multilingual-e5-small) + SQLite FTS5/sqlite-vec.

```powershell
Copy-Item .env.example .env   # fill it in (see docs/SETUP.md)
docker compose up --build     # http://localhost:3000
```

- [docs/SETUP.md](docs/SETUP.md): Windows setup, WhatsApp test number,
  cloudflared, long-lived token
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): diagram, pipeline, data model
- [docs/DEMO.md](docs/DEMO.md): step-by-step demo script
- [docs/FEATURES.md](docs/FEATURES.md): everything the app does today
- [docs/ROADMAP.md](docs/ROADMAP.md): Mekari Qontak parity plan, and where we go further
- [docs/HOSTING.md](docs/HOSTING.md): running it on a real server, HTTPS, backups, restore
- [docs/PROGRESS.md](docs/PROGRESS.md): where things stand and what's next
- [kb/README.md](kb/README.md): the knowledge base (**draft, needs medical review**)
- [rag/VENDORED.md](rag/VENDORED.md): what was reused from thesis-rag

Tests: `python -m pytest -q` (backend, no network) and `cd web; npm run e2e`
(Playwright, against the running stack).
