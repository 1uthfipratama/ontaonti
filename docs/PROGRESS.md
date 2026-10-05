# Progress — updated 2026-10-05

## Where things stand

The prototype from the original spec (phases 0–5) is done, and on 2026-10-05 the
"pilot-ready" batch was added on top. Full list: [FEATURES.md](FEATURES.md).

| Batch | What | State |
|---|---|---|
| Spec phases 0–5 | Inbox, simulator, RAG bot, safety + cases, WhatsApp/Messenger/IG, consent, broadcasts, dashboard, settings, cost controls | Done |
| Rename + look | "Onti Erlina", Talenta-style UI, dark mode | Done |
| Indonesian UI + inbox tools | ID default with EN switch; notes, saved replies, AI suggestion, labels | Done |
| Office hours | Away message once per closed period when staff have the chat | Done |
| Media | Photos/files/voice in and out; voice notes transcribed and answered | Done |
| Knowledge page | Edit/publish articles; unanswered questions list | Done |
| Security | Two-step verification, password change | Done |
| TB programme | Patient journey + board, medication reminders, tasks | Done |
| Screening | "SKRINING" symptom screening over chat | Done |
| Reports + ops | Programme card, CSV exports, installable app, daily backups, HTTPS setup | Done |

## Verified

- `pytest`: 144 passed (SQLite, fake LLM, mocked Meta: no network, no cost).
- Playwright: 4 passed against the Docker stack, including saved reply, note, label
  and sending a file.
- On the Docker stack with real services:
  - A voice note recorded in the simulator was transcribed by Whisper in the worker
    (1.4 s) and answered by Claude.
  - A test article published from the Knowledge page was re-indexed in 2 s and cited
    by Claude in its answer. The article was then deleted and republished.
  - A question outside the knowledge base was flagged as unanswered by Claude.
  - A reminder was sent by the worker's cron, then answered with the Sudah button.
  - A screening was run with the buttons, and the result appeared on the board.
  - 2FA was set up and used to sign in, with a throwaway staff account (now deactivated).
  - Chrome reports the app installable, with no errors.
  - Backups were written to `./backups`, and the dump lists all tables.

## Not done / next

1. **Meta / WhatsApp** (unchanged from 2026-10-03): the personal Meta portfolio needs
   business info, verification and a payment method before the test number can
   deliver. The plan is still a pilot WABA + spare number under the foundation's
   verified portfolio, then a later migration of the Qontak number.
2. **A server** ([HOSTING.md](HOSTING.md)) with a fixed webhook URL, instead of a PC
   and a quick tunnel.
3. **Medical review** of the knowledge base, safety replies, screening questions and
   reminder texts. An **approved WhatsApp template** for reminders to patients who
   haven't chatted in 24 hours (Settings → Pengingat obat).
4. Qontak parity still missing: routing/teams, tickets with SLA, CSAT, broadcast
   scheduling and segments, CSV contact import, template editor, web chat widget,
   multiple numbers, push notifications ([ROADMAP.md](ROADMAP.md)).

## Housekeeping

- Local demo data: the medication reminder master switch is **on** in this database,
  and a simulated patient "Siti Rahma" gets a reminder at 18:55 every day. Turn it off
  in Settings → Bot, keamanan & biaya → Pengingat obat if it's in the way.
- The first voice note after a fresh volume downloads the Whisper model (~460 MB).
- `WA_ACCESS_TOKEN` is a 24 h token; replace it with a System User token (SETUP §5).
- Rotate the secrets that were pasted in chat (Anthropic key, WhatsApp token, app
  secret) once the real setup exists.
