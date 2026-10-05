# What Onti Erlina Hub does today

A complete inventory of the prototype as of 2026-10-05: **what's built and tested**.
What's missing compared with Mekari Qontak is in [ROADMAP.md](ROADMAP.md).

## 1. Channels

| Channel | State |
|---|---|
| **WhatsApp (Cloud API)** | Live webhook: verification handshake, signed requests only (`X-Hub-Signature-256`), 200 at once, queued processing, duplicate deliveries dropped. Text in/out, delivery/read/failed status, mark-as-read, 24-hour window, polite reply to photos/voice notes/stickers, phone and account IDs learned from the first webhook. Tested end to end with the Meta test number (delivery blocked only by the personal Meta account's verification status). |
| **Messenger** | Built, behind a feature flag: webhook, signature check, text in/out, delivery and read receipts, staff replies after 24 h with the `HUMAN_AGENT` tag (up to 7 days). Not yet tried against a real Page. |
| **Instagram DM** | Same as Messenger, behind its own flag. |
| **Simulator** | Admin page to chat as a fake WhatsApp/Messenger/Instagram user. Same pipeline as the real channels, nothing sent to Meta. Quick buttons for normal, risky and consent messages. |

## 2. Inbox

- Three panels: conversation list, thread, contact panel. Live updates without refresh (SSE).
- Filters: channel, open/resolved, flag level, bot/staff mode, search by name or text.
- Unread counts, severity dot on flagged conversations.
- **Bot ⇄ Staff switch** per conversation; a staff reply hands the chat to staff automatically.
- Staff replies respect each channel's rules (24 h on WhatsApp, 7 days with tag on Messenger/IG) and are blocked for opted-out contacts.
- Assign to me, Resolve / Reopen, system notes in the thread (mode changes, handovers).
- **AI summary** for a staff member taking over (never sent to the patient).
- Per message: sources used by the bot, tokens and cost in Rupiah, delivery status, failure reason.

## 3. The bot (Onti Erlina)

- Answers **only from the TB knowledge base** (`kb/`, 10 draft articles) using the reused thesis-rag retrieval: keyword + semantic search with a multilingual model, so Indonesian and English questions both work.
- Persona: warm TB companion, Bahasa Indonesia by default (English if the user writes English), never diagnoses, never gives or changes medication, points to the puskesmas, says so when the material doesn't cover a question.
- One WhatsApp-formatted message, aiming for 400–700 characters (hard cap 900); a reply cut off by the length limit is trimmed to its last full sentence.
- Context: last 6 messages; fixed number of passages; input capped at 500 characters.
- LLM provider switchable: Anthropic (Claude Sonnet 5.5 answers, Haiku 4.5 classifier), Groq (Llama), or an offline demo mode.

## 4. Safety

- **Keyword rules** (Indonesian + English) for Emergency, Self-harm, Medicine side effects, Stopping/missing treatment. Tolerant of case, accents, punctuation, suffixes (-nya, -ku) and words in between. Always run, even over budget, in staff mode, or for opted-out contacts.
- **AI classifier** on every message; the final level is whichever is higher. An unreadable classifier answer counts as "low".
- High/emergency → a **fixed** safety reply written by the foundation (IGD / 119 / staff alerted), never AI-generated, in the user's language; a case is opened; the conversation goes to staff; staff get a live alert and an email (if SMTP is set).
- All rules and texts are editable in Settings.

## 5. Cases

- Queue sorted by severity (emergency first), with the message that raised it.
- Claim / unclaim, notes, "Resolve & return to bot" or "Resolve, keep staff mode".
- Case badge in the sidebar; cases listed in the conversation's contact panel.

## 6. Contacts and consent

- One contact can have several channel identities; **merge** duplicates (opt-out always wins).
- Cross-channel timeline of every message with that person; notes.
- Consent log: privacy notice on first contact, **STOP/BERHENTI** (one confirmation, then silence), **MULAI** to come back, **LANGGANAN** to subscribe to broadcasts, staff-recorded consent.

## 7. Broadcasts (WhatsApp)

- Templates synced from Meta or registered by hand.
- Composer with variables (`{{name}}` = contact name), **consent-only audience**, cost estimate (per-category rate) and preview.
- Sending through a queue with a rate limit and automatic retries; consent re-checked at send time.
- Campaign page: sent / delivered / read / failed per recipient.

## 8. Dashboard

Conversations by channel (today / month), open cases by severity, median first response time (bot vs staff), AI spend against the monthly budget, WhatsApp template messages against the free-tier setting, contacts subscribed / opted out. Table view for the charts.

## 9. Cost controls

Monthly AI budget (alert at 80%, at 100% switch to the cheaper model or to a fixed "staff will contact you" reply), per-contact rate limit (20 messages / 10 minutes) and daily cap (30), every AI call logged with tokens and cost.

## 10. Settings and administration

- Editable: persona, models, safety and consent texts, keyword rules, budget and limits, WhatsApp pricing.
- Channel status: webhook URLs, what's configured, last webhook, live token + Meta health check (shows why sending is blocked).
- Staff accounts with three roles: **admin** (everything), **agent** (inbox, cases, contacts, simulator), **reviewer** (read-only + audit log).
- **Audit log** of sign-ins, conversation views, replies, mode changes, case actions, setting changes, merges, broadcasts.

## 11. Look and feel

Mekari Pixel tokens / Talenta-style layout, Plus Jakarta Sans + DM Mono, light and **dark mode** (follows the system until switched), collapsible sidebar on small screens.

## 12. Under the hood

FastAPI + PostgreSQL + Redis + background worker, Next.js admin, `docker compose up` for everything, database migrations, optional Cloudflare tunnel for webhooks, demo seed data, 100 backend tests + 3 browser tests, setup/architecture/demo docs.

**Not built yet** (all in the roadmap): Bahasa Indonesia staff UI, canned replies, labels, sending images/files, web chat widget, routing rules, SLAs, CSAT, scheduling, a knowledge-base editor in the UI, hosting/backups.
