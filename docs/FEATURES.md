# What Onti Erlina Hub does today

Inventory as of 2026-10-05: **built and tested**. What's still missing compared with
Mekari Qontak is in [ROADMAP.md](ROADMAP.md).

## 1. Channels

| Channel | State |
|---|---|
| **WhatsApp (Cloud API)** | Signed webhooks, queued processing, duplicates dropped. Text, photos, documents, voice notes and video in and out; reply buttons; delivery/read/failed status; mark-as-read; 24-hour window; templates outside it. Tested end to end with the Meta test number (delivery blocked only by the personal Meta account's verification). |
| **Messenger / Instagram** | Built behind feature flags: text, quick replies, files (Messenger), receipts, staff replies after 24 h with the `HUMAN_AGENT` tag. Not yet tried against a real Page. |
| **Simulator** | Chat as a fake user on any channel through the real pipeline. Quick messages, attach a file, **record a voice note in the browser**, tap reply buttons. |

## 2. Staff interface

- **Bahasa Indonesia by default**, English with the ID | EN switch (per browser).
- Light and dark mode, Mekari Pixel / Talenta-style look, Plus Jakarta Sans + DM Mono.
- **Installable app** (PWA) on phones and desktops.

## 3. Inbox

- Three panels, live updates (SSE). Filters: channel, status, flag, bot/staff, **label**, search.
- **Reply / Note** tabs: internal notes stay in the thread and never reach the patient.
- **Saved replies**: type `/` in the reply box; `{nama}` becomes the contact's name.
- **AI suggestion**: a draft reply from the knowledge base that staff edit before sending.
- **Labels** from the tag icon; **attach files** (photo, PDF, Office, audio, video).
- Photos shown inline, players for voice notes and video, links for documents.
- Bot ⇄ Staff switch, assign, resolve/reopen, AI summary for takeover, per-message
  sources, tokens and cost.

## 4. The bot (Onti Erlina)

- Answers only from the TB knowledge base (multilingual keyword + semantic search),
  Indonesian or English, never diagnoses or doses, points to the puskesmas.
- **Voice notes are transcribed** (Whisper on the server, or Groq) and answered like
  typed messages; staff see the player and the transcript.
- Questions the knowledge base doesn't cover are logged for staff (§8).
- Claude Sonnet 5.5 answers (≈Rp 110 per question with the safety check), Haiku 4.5
  classifier; Groq or an offline demo mode also work.

## 5. Safety

- Keyword rules + AI classifier on every message; the higher level wins.
- High/emergency: a **fixed** safety reply (IGD / 119), a case, staff take over, live
  alert and email. Editable rules and texts.
- **Office hours**: outside them, a contact whose chat is with staff gets one away
  message per closed period saying when staff are back (the bot still answers 24/7).

## 6. TB programme

- **Patient journey** per contact: presumptive → testing → on treatment → completed /
  lost to follow-up, treatment start and length ("month 3 of 6"), puskesmas, kader.
- **Patients board**: drag cards between stages; cards show the treatment month,
  this week's doses and open tasks.
- **Medication reminders** (opt-in per patient): "Sudah minum obat hari ini?" with
  Sudah / Belum buttons at the patient's time. Unanswered → one follow-up; missed N
  days in a row → an adherence case and a call task for the kader. 14-day dose dots
  in the contact panel.
- **TB symptom screening** over chat: "SKRINING" → five Ya / Tidak questions → result.
  "Should get tested" marks the person presumptive and creates a follow-up task.
  Questions and rule in `config/screening.yaml`.
- **Tasks**: calls, home visits, other follow-ups with due dates and an assignee;
  overdue / today / upcoming; outcome on completion; sidebar badge.

## 7. Cases, contacts, consent

- Case queue by severity, claim, notes, resolve back to bot or keep staff mode.
- Contacts with several channel identities, merge, cross-channel timeline, notes.
- Consent log: privacy notice, STOP/BERHENTI, MULAI, LANGGANAN, staff-recorded consent.

## 8. Knowledge page

- Edit the bot's articles in the browser; hide/show, add, delete.
- **Publish** rebuilds the search index in the background (a few seconds); the bot
  uses it straight away.
- **Unanswered**: questions the bot couldn't answer, with a link to the conversation;
  mark done once an article covers them.

## 9. Broadcasts (WhatsApp)

Templates (synced or registered), consent-only audience, `{{name}}` variables, cost
estimate and preview, rate-limited sending with retries, per-recipient status.

## 10. Dashboard and reports

- Conversations by channel, open cases, first response time (bot vs staff), AI spend
  vs budget, WhatsApp template use, contacts.
- **TB programme**: adherence %, screenings and how many should get tested, patients
  per stage, risk flags per week (8 weeks).
- **CSV exports** (admin and reviewer, logged): patients, doses, screenings, cases.

## 11. Settings and security

- Tabs: Bot, safety & costs (one group at a time; Indonesian/English versions of a
  text in one field), Saved replies, Labels, Channels, Staff.
- Editable: persona, models, safety/consent texts, keyword rules, budget and limits,
  office hours, reminders, WhatsApp pricing, voice transcription on/off.
- Roles: admin, agent, reviewer. **Two-step verification** (authenticator app) and
  password change under **My account**; admins can reset a lost 2FA.
- Audit log of sign-ins, views, replies, changes, exports.

## 12. Cost controls

Monthly AI budget (alert at 80%, fallback at 100%), per-contact rate limit and daily
cap, every AI call logged with tokens and cost.

## 13. Operations

`docker compose up` for everything; migrations on start; **daily backups** of the
database and media (14 days kept); optional HTTPS with Caddy for a real server
([HOSTING.md](HOSTING.md)); Cloudflare quick tunnel for testing webhooks; demo seed
data; 144 backend tests and 4 browser tests.
