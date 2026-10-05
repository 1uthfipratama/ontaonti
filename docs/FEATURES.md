# Onti Erlina Hub: every feature

Everything the hub can do as of 2026-10-05, checked against the code. Menu names
are in Indonesian as staff see them, with English in brackets. What's still
missing compared with Mekari Qontak is in [ROADMAP.md](ROADMAP.md).

## 1. Channels

**WhatsApp (Cloud API)**
- Receives text, photos, documents, voice notes, video, stickers, locations and button taps.
- Sends text, reply buttons, photos, documents, audio, video and approved templates.
- Webhook verification handshake, and only signed webhooks are accepted (`X-Hub-Signature-256`).
- Duplicate webhook deliveries are ignored.
- Marks incoming messages as read.
- Tracks delivered, read and failed status per message, with Meta's failure reason.
- Enforces the 24-hour reply window; only templates can be sent outside it.
- Learns the phone number ID and WhatsApp account ID from the first webhook.

**Messenger and Instagram** (built, switched off by default, not yet tried on a real Page)
- Receive text, attachments and quick-reply taps.
- Send text and quick-reply buttons; Messenger can also send files.
- Delivery and read receipts.
- Staff can reply up to 7 days after the last message, using Meta's `HUMAN_AGENT` tag.

**Simulator (Simulator)**
- Chat as a test user on WhatsApp, Messenger or Instagram. Nothing goes to Meta.
- Messages go through exactly the same pipeline as real ones.
- Quick messages: normal question, English question, mild and serious side effects,
  emergency, self-harm, stopping treatment, TB screening, LANGGANAN, STOP, MULAI.
- Attach a photo, audio file or PDF.
- Record a voice note in the browser.
- Tap the bot's reply buttons.
- "Hand back to bot" when staff have taken over, and a link to open the chat in the inbox.

## 2. Inbox (Kotak masuk)

- Three panels: conversation list, thread, contact panel.
- Live updates without refreshing, plus pop-up alerts for new cases.
- **Filters:** channel, open/resolved, flag level, bot/staff, label. **Search** by name or last message.
- Unread counts and a coloured dot on flagged conversations.
- **Bot ⇄ Staf switch** per conversation. A staff reply or file takes the chat over automatically.
- **Ambil** (assign to me), **Selesaikan / Buka lagi** (resolve / reopen).
- **Balas** tab: reply on the patient's channel.
- **Catatan** tab: internal note shown in the thread, never sent to the patient.
- **Saved replies:** type `/` in the reply box and pick one; `{nama}` becomes the contact's name.
- **Saran AI** (AI suggestion): drafts a reply from the knowledge base; staff edit it before sending.
- **Ringkasan AI** (AI summary): summary of the chat for staff taking over; never sent.
- **Labels:** tag icon to add, remove or create labels.
- **Attach a file** with a caption: JPG, PNG, PDF, Word, Excel, text, MP3/OGG/M4A/AAC, MP4. Photos up to 5 MB, others up to 16 MB.
- Photos shown in the bubble, players for voice notes and video, links for documents.
- Voice notes show their **transcript**.
- Reply buttons the bot sent are shown under its message.
- Per message: delivery status and failure reason, which flag raised it, the knowledge sources the bot used, tokens and cost in rupiah.
- System notes in the thread: who took over, handed back, replied, and why the bot stopped.
- Replies are blocked for contacts who sent STOP, and outside the channel's reply window.
- **Contact panel:** contact details, patient journey (§5), latest screening result, open tasks with quick add, channels, cases.

## 3. The bot, Onti Erlina

- Answers only from the TB knowledge base, with hybrid keyword + meaning search that works in Indonesian and English.
- Replies in Bahasa Indonesia by default, in English when the person writes English.
- Never diagnoses, never gives or changes medicines or doses, points to the puskesmas, and says honestly when it doesn't know.
- One WhatsApp-formatted message: 400–700 characters, never over 900. A reply cut off by the length limit is trimmed to its last full sentence.
- Reads the last 6 messages for context and 4 knowledge passages per answer (both editable).
- **Voice notes are transcribed** (Whisper on the server, or Groq) and answered like typed text.
- Photos and stickers get a polite "I can only read text" reply; staff still see them.
- **Privacy notice** on a person's first message.
- Questions the knowledge base doesn't cover are recorded for staff (§7).
- AI models: Claude Sonnet 5.5 for answers and Claude Haiku 4.5 for risk classification. Groq (Llama) or an offline demo mode also work, and models can be changed in Settings.

## 4. Safety

- **Keyword rules** in four categories: emergency, self-harm, serious medicine side effects, stopping or missing treatment. Each category has an editable severity.
- Matching ignores case, accents and punctuation, and tolerates suffixes (-nya, -ku) and up to 2 words in between.
- Keyword rules always run: over budget, in staff mode, and for people who sent STOP.
- **AI risk classifier** on every message; the higher of the keyword and AI levels wins. Can be switched off.
- **High or emergency:**
  - The bot sends a **fixed** reply written by the foundation (IGD / 119 / staff alerted), never AI-written, in the person's language.
  - A **case** opens and the chat goes to staff.
  - Staff get a live alert, plus an **email** if email is set up.
- **Office hours (Jam layanan):**
  - Pick days and opening/closing times.
  - Outside them, a person whose chat is with staff gets one away message per closed period saying when staff are back.
  - The bot keeps answering 24/7.

## 5. TB programme

**Patient journey (Perjalanan pasien)**, in every contact panel:
- Stage: Terduga (presumptive), Pemeriksaan (testing), Pengobatan (on treatment), Selesai (completed), Putus berobat (lost to follow-up).
- Treatment start date and length; shows "Bulan ke-3 dari 6" (month 3 of 6).
- Puskesmas and assigned kader.

**Patients board (Pasien)**:
- One column per stage; drag a card to change the stage.
- Each card shows the treatment month, puskesmas, kader, reminder on/off, doses taken this week, and open tasks.

**Medication reminders (Pengingat obat)**:
- Switched on per patient (only for patients on treatment), with each patient's own time.
- Master switch in Settings.
- Daily "Sudah minum obat hari ini?" with **Sudah ✅ / Belum** buttons.
- Answers are understood whether tapped or typed ("sudah", "udah minum obat", "belum", "lupa"…); the bot replies with thanks or encouragement.
- No answer after 3 hours (editable): counted as missed, plus one gentle follow-up.
- Missed 2 days in a row (editable): an **adherence case** and a **call task** for the kader.
- For patients who haven't chatted in 24 hours, an approved WhatsApp template is used if set; otherwise that day is skipped.
- 14-day dose dots in the contact panel (taken / missed / no data).

**TB symptom screening (Skrining)**:
- A person types **SKRINING** (or "screening", "cek tbc", "tes tbc").
- Five Ya / Tidak questions with buttons: cough of 2 weeks or more, fever, night sweats, weight loss, close contact with TB.
- The result either suggests testing at the puskesmas (free, not a diagnosis) or says there are no main symptoms.
- "Should get tested" marks the person Terduga and creates a follow-up task.
- Any other reply ends the screening and the bot answers it normally. Not run while staff have the chat.
- Questions, wording and the rule are in `config/screening.yaml`.

**Tasks (Tugas)**:
- Calls, home visits and other follow-ups, with a due date, assignee and optional contact.
- Views: **Tugas saya** (mine), **Semua** (all), **Selesai** (done). Open tasks are grouped Terlambat (overdue), Hari ini (today), Mendatang (upcoming), Tanpa tanggal (no date).
- Mark done with an outcome note; reopen.
- Created automatically from missed doses and from screenings.
- Sidebar badge with how many of your tasks are due.

## 6. Cases (Kasus)

- Queue sorted by severity (emergency first), filtered by open/claimed/resolved.
- Each case shows the message that raised it, the reason, contact, channel, who has it, and the chat mode.
- **Ambil / Lepas** (claim / unclaim) and case notes.
- **Selesai & kembali ke bot** (resolve and hand back to the bot) or **Selesai, tetap staf** (resolve but keep staff handling).
- Case types: emergency, self-harm, side effects, stopping treatment (from keywords, AI or missed doses), AI budget used up, bot error.
- Sidebar badge with the number of open cases (red when there's an emergency).

## 7. Knowledge (Pengetahuan)

- Read, edit, add, hide and delete the bot's articles in the browser (editing is admin only).
- **Terbitkan** (publish) rebuilds the bot's search index in the background in a few seconds; the bot uses it straight away. Shows status, last publish date, and errors.
- **Belum terjawab** (unanswered): questions the bot couldn't answer from the articles, with a link to the chat. Mark done or ignore. Count shown on the tab.
- The 10 starter articles are drafts and need medical review.

## 8. Contacts and consent (Kontak)

- One contact can have several channel identities (WhatsApp, Messenger, Instagram).
- Search by name, phone or ID.
- Timeline of every message with that person across channels.
- Edit name, phone and notes.
- **Merge** duplicate contacts; channels, chats, cases and consents move over, and a STOP always wins.
- Consent log with time and source. Staff can record or revoke broadcast consent.
- **Keywords** (the whole message):
  - **STOP / BERHENTI** ("unsubscribe", "stop semua"…): one confirmation, then silence. Emergency keywords still alert staff.
  - **MULAI** ("start", "lanjut", "mulai lagi"): back in.
  - **LANGGANAN** ("subscribe", "berlangganan"): agrees to broadcasts.

## 9. Broadcasts (Broadcast, admin only)

- WhatsApp templates: **sync from WhatsApp** or register by hand.
- Composer: choose an approved template and fill variables (`{{name}}` = the contact's name).
- **Hitung biaya** (estimate): number of recipients, estimated cost per template category, this month's template count, and a preview for the first recipient.
- Goes only to contacts who agreed to broadcasts and haven't sent STOP; consent is checked again at send time.
- Sent through a queue with a rate limit and automatic retries.
- Campaign page: sent, delivered, read and failed per recipient, with error reasons.
- A campaign can be cancelled through the API (no button yet).

## 10. Dashboard (Dasbor)

- **Summary strip:** conversations today with 14 daily bars; this month's total; median first response for the bot and for staff; contacts with a subscribed / STOP bar; open cases split by severity (click through to cases).
- **Program TBC:** medication adherence (30 days), screenings and how many should get tested, patients per stage, risk flags per week over 8 weeks by severity.
- **CSV downloads** (admin and reviewer): patients, doses, screenings, cases. Excel-ready, and every download is logged.
- **Costs this month:** AI spend against the budget with a warning line, and WhatsApp template messages against the free allowance.
- **Active conversations per channel**, today and this month, as bars or a table.
- Refreshes every 30 seconds.

## 11. Settings (Pengaturan, admin only)

**Bot, keamanan & biaya** (bot, safety and costs), one group at a time; texts with Indonesian and English versions are one field with an ID | EN switch:
- **Bot:** persona instructions, answer and classifier models, chat history length, passages per answer, input/output limits, voice transcription on/off.
- **Keamanan** (safety): AI classifier on/off; fixed replies for emergency, self-harm, side effects, stopping treatment, and other high risk.
- **Persetujuan & kata kunci** (consent and keywords): privacy notice, STOP / MULAI / LANGGANAN confirmations, reply to photos and stickers.
- **Batas & anggaran** (limits and budget): monthly AI budget, alert level, what happens at 100% (cheaper model, or fixed reply + case), daily cap per contact, burst rate limit and their replies.
- **Jam layanan** (office hours): on/off, days, opening and closing times, away message.
- **Pengingat obat** (medication reminders): master switch, default time, reminder text, template name, thank-you and not-yet replies, follow-up delay and text, missed days before escalation.
- **Tarif WhatsApp** (WhatsApp pricing): marketing and utility rates, free monthly allowance (used for estimates).
- **Kata kunci keamanan** (safety keywords): edit each category's words and severity.
- Any field can be reset to its default.

**Other tabs:**
- **Balasan tersimpan** (saved replies): add, edit, delete.
- **Label**: add and delete.
- **Kanal** (channels): webhook URLs; what's configured or missing; IDs learned from webhooks; last webhook time; **Tes token** (Meta's own check of whether the number can send, and why not); which AI models and email alerts are active.
- **Staf** (staff): add staff, change roles, deactivate/activate, see who has two-step verification and reset it.

## 12. Accounts and security

- Sign in with email and password. Repeated failures are blocked for 15 minutes.
- **Akun saya** (my account, click your name in the sidebar):
  - **Two-step verification** with any authenticator app (QR code or key).
  - **Change password**, which signs out your other sessions.
- **Roles:**
  - **Admin:** everything.
  - **Agent:** inbox, cases, contacts, patients, tasks, simulator, knowledge (read only).
  - **Reviewer:** read only, plus the audit log and CSV downloads.
- **Log audit** (audit log): sign-ins, chats opened, replies, notes, files sent, mode and status changes, case actions, label and saved-reply changes, setting changes, contact merges, consent changes, broadcasts, knowledge edits and publishes, task changes, CSV downloads. Filter by action.
- Files are only visible to signed-in staff. Secrets stay in `.env` and are masked in logs.

## 13. Costs and limits

- Monthly AI budget (default Rp 300,000): email alert at 80%, at 100% switch to a cheaper model or to a fixed reply + case.
- Per contact: at most 20 messages per 10 minutes and 30 bot replies per day, with a polite notice once.
- Every AI call is logged with tokens, cost in rupiah, speed and errors.
- Medication reminders and screening use no AI.

## 14. Interface

- **Bahasa Indonesia** by default, English with the **ID | EN** switch (remembered per browser).
- Light and **dark mode** (follows the device until switched).
- **Installable app** on phones and computers ("Install app" / "Add to Home Screen"), with the Onti Erlina icon.
- Clean Mekari Talenta-style look, Plus Jakarta Sans font, sidebar that shrinks to icons on small screens.

## 15. Running it

- Everything starts with `docker compose up --build`: database, Redis, API, worker, web app.
- Database migrations run automatically on start.
- **Daily backups** of the database and files into `./backups`, 14 days kept.
- Optional **HTTPS** with automatic certificates for a real server; see [HOSTING.md](HOSTING.md).
- Optional Cloudflare quick tunnel to receive Meta webhooks while testing.
- `/health` endpoint for uptime monitors.
- Scripts: `seed_demo.py` (demo data), `simulate_whatsapp.py` (send a fake signed WhatsApp message or photo), `reindex_kb.py` (rebuild the search index).
- Tests: 144 backend tests (no network, no cost) and 4 browser tests.
