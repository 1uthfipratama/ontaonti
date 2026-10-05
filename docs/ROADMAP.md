# Roadmap: Mekari Qontak parity, then better

Goal: replace Mekari Qontak for the foundation, matching what the foundation actually
uses and doing better where a TB programme needs it. (Mekari **Talenta** is Mekari's
HR/payroll product; it shaped our *look*. **Qontak** is the product we replace.)

Qontak's feature set below is from its public pages and partner listings
(qontak.com, mekari.com/product/qontak, Capterra). First step before building: list
which Qontak features the foundation **actually uses today**. Parity with unused
features is wasted effort.

Legend: ✅ have · 🟡 partial · ❌ missing · ➖ skip (doesn't fit a TB foundation)
Status updated 2026-10-05 after the "pilot-ready" batch (see the bottom).
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
| Quick replies / canned responses | ✅ | Saved replies with `/`, plus **AI-suggested reply** drafted from the KB. Next: per-team replies. | — |
| Labels / tags | ✅ conversations | Next: contact tags, auto-tag by the classifier's category. | S |
| Internal notes in a chat | ✅ | Next: @mentions with a notification. | S |
| Transfer / assignment | 🟡 (assign to me) | Assign to anyone or a team; transfer with a note. | S |
| Auto-routing (round robin, by team) | ❌ | Routing rules by channel, tag or severity; emergencies to the on-duty person first. | M |
| Office hours / away message | ✅ | Next: page the on-call staff for emergencies outside hours. | S |
| Send and view media (images, documents, voice notes) | ✅ + voice notes transcribed and answered | — | — |
| Supervisor live monitoring | 🟡 (everyone sees inbox) | Live agent status, workload, queue view. | M |
| Mobile app | 🟡 installable PWA | Push notifications for cases and tasks. | M |

## 3. Chatbot and AI (Qontak: Mekari Airene + flow builder)

| Qontak | Us | Plan / better | Size |
|---|---|---|---|
| AI chatbot | ✅ grounded answers | Already better for health: answers only from approved material, cites sources, **clinical safety layer** (fixed replies, cases, handover), cost cap per month. | — |
| Knowledge base for the AI | ✅ editor, publish, unanswered questions | Next: draft → review → approve workflow for medical sign-off. | S |
| No-code flow builder (menus, buttons, forms) | 🟡 screening flow (YAML) | Generalise the screening engine into flows editable in the UI (appointments, data collection). | L |
| Interactive buttons / lists | ✅ buttons (reminders, screening) | Next: list messages, buttons on templates. | S |
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

**Better than Qontak: treatment reminders.** ✅ Built: opt-in daily reminders with
Sudah / Belum buttons, follow-up when unanswered, adherence case and kader task after
missed days. Needs clinical sign-off of the texts and an approved WhatsApp template for
patients outside the 24-hour window.

## 6. CRM, adapted to a TB programme

Qontak's sales CRM (deals pipeline, GPS field sales, quotas) doesn't fit as-is. The
same ideas, adapted:

| Qontak | Our version | Size |
|---|---|---|
| Sales pipeline (Kanban) | ✅ **Patients board**: presumptive → testing → on treatment (month n of N) → completed / lost | — |
| Tasks and reminders | ✅ tasks for staff and **kader** (calls, home visits), automatic ones from missed doses and screenings | — |
| GPS field visit tracking | Home-visit log for kader (optional location); kader-only mobile view | M |
| Custom contact fields | 🟡 puskesmas, treatment start/length, kader. Next: TB type, regimen, free custom fields | S |
| Companies | Organisations: puskesmas, hospitals, partner NGOs | S |
| Integrations (Sheets, Talenta, Jurnal, API) | Export to Sheets; public API + webhooks; explore **SITB / SATUSEHAT** (Indonesia's TB and health record systems) if official access is possible | M / L |

## 7. Reports

| Qontak | Us | Plan / better | Size |
|---|---|---|---|
| Dashboards (volume, agents, SLA, CSAT, campaigns) | 🟡 core dashboard + CSV exports | Date ranges, agent and SLA reports, scheduled email reports. | M |
| — | ✅ **Programme metrics**: adherence, screenings, patients per stage, risk flags per week | Next: reasons for stopping treatment, per-puskesmas breakdown, donor report template. | S |

## 8. Platform, security, compliance

| Item | Us | Plan | Size |
|---|---|---|---|
| Bahasa Indonesia staff UI | ✅ default, with English switch | — | — |
| Roles and permissions | 🟡 (3 fixed roles) | Teams/divisions, custom roles. | M |
| 2-factor login, SSO | ✅ 2FA (TOTP) | Next: require 2FA for admins; Google sign-in optional. | S |
| Hosting, backups, monitoring | 🟡 daily backups + HTTPS setup ([HOSTING.md](HOSTING.md)) | Actually rent the server, off-site backup copy, uptime alerts. | S |
| Data protection (UU PDP 27/2022) | 🟡 (consent, audit) | Retention rules, patient data export/delete on request, data processing records, access reviews. | M |
| Multiple WhatsApp numbers / programmes | ❌ | Several numbers, one inbox. | M |

## Suggested order

1. **Pilot-ready.** ✅ Built on 2026-10-05: Indonesian UI, 2FA, saved replies, labels,
   internal notes, office hours, media send/receive, voice-note transcription, KB editor,
   backups and HTTPS setup. Plus, from step 3: treatment reminders, screening flow,
   patients board, tasks, programme reports, AI-suggested replies, installable app.
   **Still needed for a pilot:** a server ([HOSTING.md](HOSTING.md)), a WhatsApp number
   under the foundation's verified Meta account, and medical review of the content.
2. **Replace Qontak day-to-day (≈5–7 weeks):** routing and teams, tickets + SLA, CSAT,
   broadcast scheduling/segments/CSV import, template editor, web chat widget, agent
   reports, multiple numbers, push notifications. Then migrate the real number (see
   PROGRESS.md).
3. **Better than Qontak (ongoing):** flow builder in the UI, kader mobile view with
   home-visit log, SITB/SATUSEHAT exploration, per-puskesmas reports.

Estimates assume one developer working with an AI assistant. Clinical features
(reminders, screening) need the foundation's medical team to sign off the content.
