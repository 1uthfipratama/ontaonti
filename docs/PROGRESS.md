# Where we left off — 2026-10-02

Handoff note for the Onti Erlani Hub build. Pick up from "Next steps" below.

## Status by phase

| Phase | State | Commit |
|---|---|---|
| 0 — Understand RAG | Done. `RAG PROT/rag` (thesis-rag) vendored into `rag/` with a multilingual embedder (`intfloat/multilingual-e5-small`), the E5 prefixes and Indonesian stopwords; see `rag/VENDORED.md`. TB knowledge base in `kb/` (DRAFT, needs medical review). | — |
| 1 — Core, simulator, inbox | Done | `e6fde6e` |
| 2 — Safety layer + cases | Done | `ce86a56` |
| 3 — WhatsApp + Messenger/IG, consent, contacts | Done | `6c552e1` |
| 4 — WhatsApp broadcasts | **Work in progress (committed as WIP, not finished)** | this commit |
| 5 — Dashboard, settings, cost controls | Not started | — |
| Quality / docs / finish | Not started | — |

Nothing has been pushed to GitHub yet (`origin` isn't set). Everything is local.

## Phase 4: what's done and what's broken

Done:
- Models + migration `0003`: `wa_templates`, `broadcasts`, `broadcast_recipients`
- `app/services/broadcasts.py`: template sync from the WABA, consent-filtered recipients,
  cost estimate (rate per category from settings), staggered queueing (rate limit),
  retries with backoff on 429/5xx, delivery/read via the webhook status hook, stats
- `app/routers/broadcasts.py`: `/templates`, `/templates/sync`, `/broadcasts/estimate`,
  `/broadcasts`, `/broadcasts/{id}/send|cancel`, `/broadcasts/{id}`
- `tests/test_broadcasts.py`: 11 tests, all pass when run on their own
- Web: `web/app/(app)/broadcasts/page.tsx` (templates, composer + estimate, campaign stats)

Broken (fix first):
1. **One flaky test.** `tests/test_broadcasts.py::test_send_broadcast_with_retry_and_delivery_statuses`
   passes alone but failed in the full run (80 passed, 1 failed). The traceback wasn't
   looked at yet. Check ordering or leftover state between tests: inline jobs, respx
   mocks, `_defer_by`.
   ```bash
   .venv/Scripts/python -m pytest -q   # reproduce
   ```
2. **ESLint error** in `web/app/(app)/broadcasts/page.tsx` (`react-hooks/set-state-in-effect`,
   in `Composer`'s `useEffect` that resets `vars`/`est` when the template changes). Fix: do
   the reset in the template `<select>` `onChange` handler and delete the effect.
   ```bash
   cd web && npm run lint
   ```
After both are fixed, re-run tests, lint and `npx tsc --noEmit`, then make the real
"Phase 4" commit.

## Next steps (remaining spec)

**Phase 5: dashboard, settings, cost controls**
- `GET /dashboard`: conversations by channel (today/month), open cases by severity,
  median first response time (bot vs human), AI spend vs monthly budget, WhatsApp template
  messages vs the free-tier setting.
- Editable settings page (`GET/PUT /settings`): persona, flag keywords (`flag_rules`), safety
  texts, models, monthly budget (IDR), daily cap. The defaults and the group layout already
  exist in `app/services/settings_service.py` (`DEFAULTS`, `GROUPS`, `coerce()`).
- Pipeline (`app/bot/pipeline.py`, after step 3): per-contact rate limit (20 msgs / 10 min,
  polite reply once per window), daily cap (30), budget at 80% → alert once a month
  (`budget.alert` event), at 100% → `budget_fallback_mode` (classifier model, or fixed
  reply + open case). Keyword flags already run before all of this.
- Tests: budget fallback, rate limit, daily cap.

**Quality / finish**
- `scripts/seed_demo.py`: demo staff (password from `DEMO_STAFF_PASSWORD`), contacts and
  conversations across channels, one flagged case, a few broadcast-consented contacts.
- Playwright e2e in `web/e2e/`: login → inbox → simulator message → bot reply.
- Docs: `docs/SETUP.md`, `docs/ARCHITECTURE.md` (diagram + data model), `docs/DEMO.md`.
- Final `pytest`, `docker compose up --build`, a browser check, then push to
  github.com/1uthfipratama/ontaonti (a public repo, so re-run the secret scan first).

## Things only you can do

1. **Anthropic key**: it isn't scoped to a workspace, so every call fails with
   "must include the anthropic-workspace-id header". Put the workspace ID
   (console.anthropic.com → Settings → Workspaces, `wrkspc_...`) in `.env` as
   `ANTHROPIC_WORKSPACE_ID`, or replace the key with a workspace-scoped one. Until then the
   bot sends the fixed "staf kami akan menghubungi" reply and opens a low `BOT_ERROR` case.
   For an offline demo: `LLM_PROVIDER=fake docker compose up`.
2. **WhatsApp**: fill `WA_PHONE_NUMBER_ID`, `WA_BUSINESS_ACCOUNT_ID` (Meta App Dashboard →
   WhatsApp → API Setup) and `WA_APP_SECRET` (App settings → Basic). `WA_ACCESS_TOKEN` is
   set, but it's the 24-hour temporary token, so it has probably expired.
3. **Rotate the secrets you pasted in chat** (Anthropic key, WhatsApp token). They're only
   in `.env` (gitignored), but they've been shared in a chat transcript.
4. Have the foundation's medical team review `kb/*.md` and the safety texts.

## Running it

- `.env` exists (gitignored) with a generated `SECRET_KEY`, DB password, verify token and
  admin password. Admin login: `ADMIN_EMAIL` / `ADMIN_PASSWORD` in `.env`.
- Docker stack (built from the Phase 2 code; rebuild to get Phase 3 and 4):
  ```bash
  docker compose up -d --build
  ```
  Admin UI http://localhost:3000, API http://localhost:8000 (`/health`).
  Stop with `docker compose down`; add `-v` to wipe data.
- Tests (local venv, SQLite, no network): `.venv/Scripts/python -m pytest -q`
- Rebuild the KB index after editing `kb/`: `python scripts/reindex_kb.py`
- Fake WhatsApp webhooks: `python scripts/simulate_whatsapp.py "Halo"` (needs `WA_APP_SECRET`)

## Notes and decisions so far

- Postgres isn't exposed on the host (port 5432 is already in use on this machine).
- In HUMAN mode the bot never replies, even to emergencies; keyword flags still open or
  raise a case and alert staff. The foundation should confirm this choice.
- Opted-out (STOP) contacts get no replies. Emergency keywords still alert staff.
- A classifier error counts as severity "low" (same as unreadable output).
- Meta's pricing changed (service conversations free since Nov 2024, per-message template
  pricing since Jul 2025). The "1,000 free" figure and the IDR rates are editable placeholder
  settings (`wa_free_tier_messages`, `wa_rate_*_idr`). Check Meta's current rate card.
- Next.js is 16.3 (Turbopack, `proxy` instead of `middleware`), and shadcn uses the Base UI
  "base-nova" style. The UI uses native `<select>` to avoid Base UI API surprises.
