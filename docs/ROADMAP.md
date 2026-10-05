# Roadmap: Mekari Qontak parity, then better

Goal: replace Mekari Qontak for the foundation, matching what the foundation actually
uses and doing better where a TB programme needs it. (Mekari **Talenta** is Mekari's
HR/payroll product; it shaped our *look*. **Qontak** is the product we replace.)

Qontak's feature set below is from its public pages and partner listings
(qontak.com, mekari.com/product/qontak, Capterra). First step before building: list
which Qontak features the foundation **actually uses today**. Parity with unused
features is wasted effort.

Legend: ✅ have · 🟡 partial · ❌ missing · ➖ skip (doesn't fit a TB foundation)
Size: S ≈ days, M ≈ 1–2 weeks, L ≈ 3+ weeks.

## 1. Channels

| Qontak | Us | Plan / how we do better | Size |
|---|---|---|---|
| WhatsApp Business API (official BSP) | ✅ | Cloud API directly: no BSP markup. Add **multiple numbers** per account. | S |
| Instagram DM, Messenger | 🟡 built, untested live | Test with the foundation's Page; staff "human agent" tag already handled. | S |
| Web chat widget | ❌ | Embeddable widget for the foundation website, same inbox and bot. | M |
| Telegram, LINE | ❌ | Telegram is cheap to add (free API) if patients use it; LINE is rare in Indonesia, skip unless asked. | S / ➖ |
| Email | ❌ | For partners and puskesmas, not patients. Lower priority. | M |
| Voice / WhatsApp calling | ❌ | Click-to-call from a case (WhatsApp calling API). Useful for emergencies. | L |
| X (Twitter), Tokopedia, Shopee | ➖ | Commerce/social channels, not relevant. | — |
| Click-to-WhatsApp ads | ➖ | Only if the foundation runs Meta ads. | — |

## 2. Inbox productivity (what agents use all day)

| Qontak | Us | Plan / better | Size |
|---|---|---|---|
| Quick replies / canned responses | ❌ | Saved replies with `/` shortcut, plus **AI-suggested reply** drafted from the KB that the agent edits before sending. | S + M |
| Labels / tags | ❌ | Tags on conversations and contacts; filters; auto-tag by the classifier's category. | S |
| Internal notes in a chat | 🟡 (system notes only) | Staff notes and @mentions inside the thread. | S |
| Transfer / assignment | 🟡 (assign to me) | Assign to anyone or a team; transfer with a note. | S |
| Auto-routing (round robin, by team) | ❌ | Routing rules by channel, tag or severity; emergencies to the on-duty person first. | M |
| Office hours / away message | ❌ | Opening hours; outside them the bot covers, safety cases page the on-call staff. | S |
| Send and view media (images, documents, voice notes) | ❌ (receive label only) | Download, display and send media; **transcribe voice notes** so the bot and safety checks can read them (many patients send voice). | M |
| Supervisor live monitoring | 🟡 (everyone sees inbox) | Live agent status, workload, queue view. | M |
| Mobile app | ❌ | Installable web app (PWA) with push notifications for cases. | M |

## 3. Chatbot and AI (Qontak: Mekari Airene + flow builder)

| Qontak | Us | Plan / better | Size |
|---|---|---|---|
| AI chatbot | ✅ grounded answers | Already better for health: answers only from approved material, cites sources, **clinical safety layer** (fixed replies, cases, handover), cost cap per month. | — |
| Knowledge base for the AI | 🟡 (Markdown files + re-index) | **KB editor in the admin**: write/approve articles, review status, re-index with one click, see which questions the KB couldn't answer. | M |
| No-code flow builder (menus, buttons, forms) | ❌ | Flows for **TB symptom screening**, appointment questions and data collection, using WhatsApp buttons/lists, with AI as fallback. | L |
| Interactive buttons / lists | ❌ | Buttons in bot replies and templates. | S |
| AI summary for agents | ✅ | Add sentiment, auto-tags and "next best action". | S |

## 4. Service and ticketing

| Qontak | Us | Plan / better | Size |
|---|---|---|---|
| Tickets with SLA and escalation | 🟡 (risk cases only) | General tickets (any request), categories, **SLA by severity** (e.g. emergency 15 min), escalation when breached. | M |
| CSAT / NPS surveys | ❌ | One-tap rating after a resolved chat; results per agent. | S |
| Agent scorecards | ❌ | Response time, resolution time, CSAT and volume per agent. | M |
| Agent knowledge base | ❌ | The same KB, searchable by agents, plus internal SOPs. | S |

## 5. Broadcasts and campaigns

| Qontak | Us | Plan / better | Size |
|---|---|---|---|
| Template broadcasts | ✅ with consent filter, cost estimate, retries, stats | — | — |
| Scheduling | ❌ | Send later; recurring sends. | S |
| Audience segments | ❌ (all consented) | Segments by tag, channel, last active, treatment stage. | M |
| Contact import (CSV) | ❌ | Import with consent proof required per row. | S |
| Create/submit templates to Meta | ❌ (sync/register only) | Template editor that submits to Meta and tracks approval. | M |
| Media and button templates | ❌ | Header image/doc, quick-reply buttons. | S |
| Campaign analytics | 🟡 | Add replies, opt-outs and cost per campaign. | S |

**Better than Qontak: treatment reminders.** Opt-in daily medication reminders and
follow-up when a patient reports a missed dose. This is the biggest
patient-outcome feature and Qontak has nothing TB-specific. (M–L, needs clinical sign-off.)

## 6. CRM, adapted to a TB programme

Qontak's sales CRM (deals pipeline, GPS field sales, quotas) doesn't fit as-is. The
same ideas, adapted:

| Qontak | Our version | Size |
|---|---|---|
| Sales pipeline (Kanban) | **Patient journey board**: screening → diagnosed → treatment month 1–6 → completed / lost to follow-up | M |
| Tasks and reminders | Follow-up tasks for staff and **kader** (community health workers) | S |
| GPS field visit tracking | Home-visit log for kader (optional location) | M |
| Custom contact fields | Custom fields (puskesmas, treatment start date, TB type…) | S |
| Companies | Organisations: puskesmas, hospitals, partner NGOs | S |
| Integrations (Sheets, Talenta, Jurnal, API) | Export to Sheets; public API + webhooks; explore **SITB / SATUSEHAT** (Indonesia's TB and health record systems) if official access is possible | M / L |

## 7. Reports

| Qontak | Us | Plan / better | Size |
|---|---|---|---|
| Dashboards (volume, agents, SLA, CSAT, campaigns) | 🟡 core dashboard | Date ranges, CSV export, agent and SLA reports, scheduled email reports. | M |
| — | — | **Programme metrics**: risk flags over time by category, adherence risk, reasons for stopping treatment. Reports a donor or the health office would want. | M |

## 8. Platform, security, compliance

| Item | Us | Plan | Size |
|---|---|---|---|
| Bahasa Indonesia staff UI | ❌ (English) | Full Indonesian UI with an English switch. **Needed before staff use it.** | M |
| Roles and permissions | 🟡 (3 fixed roles) | Teams/divisions, custom roles. | M |
| 2-factor login, SSO | ❌ | 2FA for all staff; Google sign-in optional. | S |
| Hosting, backups, monitoring | ❌ (laptop + tunnel) | Managed hosting in Indonesia or Singapore, nightly backups, uptime alerts, fixed webhook domain. | M |
| Data protection (UU PDP 27/2022) | 🟡 (consent, audit) | Retention rules, patient data export/delete on request, data processing records, access reviews. | M |
| Multiple WhatsApp numbers / programmes | ❌ | Several numbers, one inbox. | M |

## Suggested order

1. **Pilot-ready (≈3–4 weeks):** Indonesian UI, hosting + backups + 2FA, canned replies,
   labels, internal notes, office hours, media send/receive, KB editor, a new WhatsApp
   number under the foundation's verified Meta account.
2. **Replace Qontak day-to-day (≈6–8 weeks):** routing and teams, tickets + SLA, CSAT,
   broadcast scheduling/segments/CSV import, template editor, web chat widget, agent
   reports + exports, multiple numbers. Then migrate the real number (see PROGRESS.md).
3. **Better than Qontak (ongoing):** treatment reminders and adherence follow-up,
   AI-suggested replies, voice-note transcription, screening flows, patient journey
   board, kader tasks/visits, programme reports, SITB/SATUSEHAT exploration, mobile PWA.

Estimates assume one developer working with an AI assistant. Clinical features
(reminders, screening) need the foundation's medical team to sign off the content.
