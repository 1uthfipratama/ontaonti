# Showcase script

About 25 minutes plus questions. Each part has **Do** (what you click), **Show**
(what to point at) and **Say** (talking points, in your own words).

Layout: two browser windows side by side. **Simulator** on the left (you play the
patient), **Kotak masuk** on the right (you play staff). Your phone ready for the
real-WhatsApp moments (optional, see "Using a real WhatsApp account" at the end).

---

## Before you start (10 minutes before)

1. Docker Desktop running, then in PowerShell, in the project folder:
   `.\scripts\showcase.ps1 on`
   This switches to clean demo data: 10 people, chats on three channels, two open
   cases, patients at every stage, two weeks of medication reminders, tasks. Your
   own test data is untouched.
2. Open http://localhost:3000 and sign in. Interface in **ID**, light mode for a projector.
3. Rehearsed already? `.\scripts\showcase.ps1 reset` gives fresh demo data
   (reminders go out once per person per day, so a rehearsal uses them up).
4. Silence laptop notifications.

---

## 1. What we built (2 min, talking only)

**Say:**
- The foundation runs its WhatsApp on Mekari Qontak: a general business inbox,
  paid monthly, with nothing made for TB.
- This is our own hub, **Onti Erlina**: one inbox for WhatsApp, Instagram and
  Messenger, plus a companion bot that answers questions about TB, plus tools built
  for a TB programme (patients, medication reminders, screening, kader tasks).
- It's a working prototype, not slides: everything you'll see runs for real.
  Built in about a week, with 144 automated checks behind it.
- It is **not** a diagnosis tool, and it doesn't hold real patient data yet.

**What we did, in order** (if asked):
1. The core: inbox, bot, safety checks, WhatsApp, Messenger and Instagram, broadcasts, dashboard, cost limits.
2. Tested with a real WhatsApp number and Claude (the AI): the bot answered correctly. Delivery is waiting on Meta account verification.
3. Redesign in the Mekari Talenta style, plus dark mode.
4. The pilot-ready batch:
   - Indonesian interface; inbox tools; photos, files and voice notes.
   - The Pengetahuan (knowledge) page; office hours; two-step login.
   - Patient journey, medication reminders, screening, tasks.
   - Programme reports, an installable app, daily backups.

---

## 2. A patient asks a question (3 min)

**Do:** Simulator → **ID pengguna** `rudi`, **Nama tampilan** `Rudi Hartono` →
type **Halo kak, berapa lama pengobatan TBC?** → send.
(Real phone: send the same text to the hub's WhatsApp number.)

**Show:**
- First, the privacy notice: messages are stored, this isn't a diagnosis, reply STOP to stop.
- Then one friendly answer in Indonesian: at least 6 months, two phases, free at the puskesmas.
- In the inbox, under the bot's bubble: which article it used, and the cost (about Rp 110).

**Do:** quick message **Pertanyaan bahasa Inggris**. **Show:** it answers in English.

**Say:**
- It only answers from the foundation's approved articles. It never diagnoses or
  gives doses, and says honestly when it doesn't know.
- Every answer shows its source, so staff can check it.

---

## 3. Safety (3 min)

**Do:** quick message **Darurat** ("Saya batuk darah banyak dan sesak napas berat").

**Show:**
- The bot's reply is a **fixed** text written by the foundation: go to the IGD or call 119, staff have been alerted.
- A red alert pops up and the **Kasus** badge counts it.
- In the inbox the chat switches from **Bot** to **Staf**; the bot goes quiet.

**Do:** Kasus → open the case → **Ambil** → add a note → **Selesai & kembali ke bot**.

**Say:**
- Risky messages never get an AI-written answer.
- The same goes for self-harm, serious side effects and someone stopping treatment.
- Keyword checks and an AI check both run, and the stricter one wins.
- The texts and keywords are the foundation's to edit.

---

## 4. Staff tools in the inbox (4 min)

**Do:** Kotak masuk → open **Dewi Lestari** (she wants to stop treatment; an agent is handling it).

**Show, one by one:**
- ✨ **Ringkasan AI** (sparkle icon): a briefing for whoever takes over. Never sent to Dewi.
- **Catatan** tab: write *Sudah ditelepon, minta kunjungan rumah* → it stays internal, shaded differently.
- **Balas** tab: type `/jadwal` → pick the saved reply → her name is filled in.
- **Saran AI**: the AI drafts a reply from the articles; staff edit before sending.
- 🏷 Tag icon: labels. The list on the left filters by label (**Semua label** dropdown).
- 📎 Paperclip: send a PDF or photo (e.g. a control schedule).

**Say:**
- What Qontak does, plus the AI drafting, in plain Indonesian.

---

## 5. Voice notes (1 min)

**Do:** Simulator → 🎤 mic → say *berapa lama pengobatan TBC?* → tap again to send.
(Or send a voice note from your phone.)

**Show:** in the inbox, a player plus the **Transkrip**, and the bot answering it like typed text.

**Say:** Many patients send voice notes. Qontak just stores them; we understand and answer them.

---

## 6. The TB programme (5 min)

**Pasien (Patients)**

**Do:** open **Pasien**.

**Show:**
- One column per stage: Terduga, Pemeriksaan, Pengobatan, Selesai, Putus berobat.
- Cards show the treatment month, puskesmas and kader, and the doses taken this week (red when some were missed).
- Drag **Andi P.** from Pemeriksaan to Pengobatan.

**Medication reminder, live**

**Do:**
1. Kotak masuk → open **Rudi Hartono** → contact panel → **Tahap: Pengobatan**.
2. Switch on **Pengingat obat**, and set its time to the current minute.
3. Within a minute the Simulator shows *"Halo Rudi 👋 Sudah minum obat TBC hari ini?"* with **Sudah ✅ / Belum**.
4. Tap **Sudah**.

**Show:**
- The thank-you reply; the dot for today turns green in the contact panel.
- Open **Siti Rahma** and **Budi Santoso** for two weeks of dots.

**Say:**
- Every day, at the time the patient picks.
- No answer: one gentle follow-up.
- Two missed days in a row: a case for staff, and a call task for the kader.
- Reminders cost no AI.

**Screening**

**Do:** Simulator → **ID pengguna** `nina`, **Nama tampilan** `Nina` → quick message
**Skrining TBC** → tap **Ya, Tidak, Ya, Tidak, Tidak**.

**Show:**
- The result: "disarankan periksa TBC", free at the puskesmas, not a diagnosis.
- On **Pasien**, Nina now sits under **Terduga**. On **Tugas**, there's a follow-up task.

**Tugas (Tasks)**

**Do:** **Tugas** → **Semua**.

**Show:** grouped into Terlambat, Hari ini and Tanpa tanggal; tasks made automatically (*otomatis*) next to staff ones.

**Do:** mark one **Selesai** with an outcome.

---

## 7. Pengetahuan (2 min)

**Do:** **Pengetahuan** → **Belum terjawab**.

**Show:** questions the bot couldn't answer (transport money, fasting during treatment), each linked to its chat.

**Do:** **Artikel** → open one; show the editor and **Terbitkan** (publish).

**Say:**
- Staff improve the bot themselves. Add the answer to an article and publish; the bot uses it within seconds.
- No developer needed.

(Optional live version: add a sentence to an article, publish, ask the bot about it,
then remove it again and republish.)

---

## 8. Contacts, consent, broadcasts (2 min)

**Do:** **Kontak** → **Siti Rahma**.

**Show:**
- One timeline across channels.
- In the panel, **Gabungkan kontak ganda** (merge duplicate contacts) → choose *siti.rahma (IG)* → **Gabungkan**: her WhatsApp and Instagram are now one person.

**Do:** Simulator (as Rudi) → **Berhenti (STOP)** → then type anything.

**Show:** one confirmation, then silence; staff can't message him either. **Mulai lagi (MULAI)** brings him back.

**Do:** **Broadcast** → template **pengingat_kontrol** → **Hitung biaya**.

**Show:** only people who agreed to broadcasts (and haven't sent STOP) are counted, with the cost and a preview. No need to send.

---

## 9. Dashboard (2 min)

**Do:** **Dasbor**.

**Show:**
- The summary strip: today's conversations, response times, contacts, open cases.
- **Program TBC:** adherence (86% in the demo data), screenings, patients per stage, risk flags per week.
- **Unduh CSV → Pasien** opens in Excel, ready for reporting.
- **Biaya bulan ini:** AI spend against the monthly cap.

---

## 10. Trust and control (2 min)

**Show, quickly:**
- **ID | EN** and the moon icon (dark mode).
- **Pengaturan → Bot, keamanan & biaya**, everything editable by the foundation:
  - the bot's instructions, the safety replies and keywords
  - office hours, reminder texts, the AI budget
- **Pengaturan → Staf:** roles. Agents work the inbox; reviewers only read and see the audit log.
- Click your name → **Akun saya** → **Verifikasi dua langkah** (a code from an authenticator app).
- **Log audit:** who opened, replied to, changed or downloaded what.
- On a phone: the hub installs like an app (Add to Home Screen).

---

## 11. Costs and next steps (2 min)

**Say:**

| Per month | Pilot | Full programme |
|---|---|---|
| Server (Jakarta) | ≈ Rp 140k | ≈ Rp 140k–790k |
| AI (≈ Rp 110 per answer) | ≈ Rp 33k | ≈ Rp 330k |
| WhatsApp (Meta) | ≈ Rp 440k | ≈ Rp 4–8M |

- Meta's fees are the same whichever platform sends the messages, Qontak included:
  - Rp 357 + VAT per message after the first 1,000 a month
  - charged since 1 October 2026
- So the real comparison is the Qontak subscription against our server.

**What we need to start a pilot:**
1. A WhatsApp number under the foundation's verified Meta account, with a payment method on file.
2. A small server, e.g. Biznet Gio Jakarta (setup is written up in `docs/HOSTING.md`).
3. Medical review of the articles, safety replies, screening questions and reminder texts.
4. A few staff and kader to try it for a month.
5. Later: move the current Qontak number over. The number, display name and templates
   move; old chat history stays in Qontak, so export it first.

---

## Questions you'll probably get

| Question | Short answer |
|---|---|
| Is it diagnosing people? | No. It never diagnoses or gives doses; it points to the puskesmas. Screening says "get tested", not "you have TB". |
| What if the bot is wrong? | It answers only from approved articles and shows its source. Risky topics get fixed texts. Staff can take over any chat, and unanswered questions are listed for fixing. |
| Where is the data? | On a server the foundation controls (Jakarta recommended). Daily backups, two-step login, an audit log, and files visible only to signed-in staff. |
| What happens to our Qontak number and history? | The number, name and templates can move to the foundation's own Meta account. History stays in Qontak, so we export it first. |
| Can kader use it on their phones? | Yes, it installs like an app, and tasks can be assigned to them. A simpler kader-only view is on the roadmap. |
| What if the AI budget runs out or the AI is down? | The bot sends a fixed "staff will contact you" reply and opens a case. Safety checks keep working. |
| English? Other channels? | English, yes. WhatsApp, Instagram and Messenger in one inbox. |

---

## If something goes wrong

- **Bot doesn't reply:** `docker compose logs worker` (usually the AI key or quota).
- **Real WhatsApp is silent:** Pengaturan → Kanal → **Tes token**. Has the tunnel URL changed?
- **Reminder doesn't come:** the person must be at stage *Pengobatan*, with the reminder switch on and the time set to now. Each person gets one reminder a day, so use a new simulator user or `.\scripts\showcase.ps1 reset`.
- **Start over:** `.\scripts\showcase.ps1 reset`.

**After the showcase:** `.\scripts\showcase.ps1 off` (back to your usual data).

---

## Using a real WhatsApp account

The live WhatsApp moments need these first (most are in Meta's settings, so only
you or the foundation's Meta admin can do them):

1. **Payment method** on the Meta business account (WhatsApp Manager → Payment
   settings). Since 1 October 2026, Meta doesn't deliver even normal replies without one.
2. **Business info and verification:**
   - Legal name, country and website, then business verification.
   - Settings → Kanal → **Tes token** lists exactly what Meta still wants.
   - Verification can take days. The foundation's already-verified account is the faster route.
3. **A permanent access token** (System User token, see `docs/SETUP.md` §5).
   Meta's test tokens last only 24 hours; the last one expired on 3 October.
4. **A public webhook address:**
   1. Start the tunnel: `docker compose --profile tunnel up -d tunnel`
   2. Get the address: `docker compose logs tunnel` (look for `https://…trycloudflare.com`).
   3. Paste `https://…/webhook/whatsapp` into Meta → WhatsApp → Configuration.
   4. The address changes every time the tunnel restarts.
5. **Phones that may receive messages:** with Meta's test number, add up to 5
   numbers under API Setup → "To". With a real number, anyone can message it.

Worth showing on the real phone if it's ready: a question and answer (part 2), a
voice note (part 5), and enrolling your own number for a reminder (part 6). Seeing
the buttons on a real phone lands well.
