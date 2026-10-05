# Setup (Windows 11)

Prerequisites: Docker Desktop (WSL 2 backend), Git, `cloudflared`. Python 3.13 and
Node 24 are only needed to run tests or scripts outside Docker.

## 1. Configure

```powershell
Copy-Item .env.example .env
notepad .env
```

Every variable is explained in `.env.example`. The minimum for a local run:

| Variable | What to put |
|---|---|
| `SECRET_KEY` | long random string: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `POSTGRES_PASSWORD` | any password (used by the `db` container) |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | your first admin login (created on API start) |
| `LLM_PROVIDER`, `LLM_API_KEY` | `groq` or `anthropic` + key. `fake` runs offline with canned answers |
| `ANTHROPIC_WORKSPACE_ID` | only if your Anthropic key isn't scoped to a workspace |

WhatsApp variables can wait until step 4.

## 2. Start

```powershell
docker compose up --build
```

The first build downloads the multilingual embedding model (~470 MB) into the image.
On start, the API container runs the migrations (`alembic upgrade head`), builds the
knowledge-base index if needed, and creates the admin from `ADMIN_EMAIL` /
`ADMIN_PASSWORD`.

- Admin UI: http://localhost:3000 (log in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`)
- API health: http://localhost:8000/health
- Offline demo without an LLM key: `$env:LLM_PROVIDER="fake"; docker compose up --build`

Optional demo data (staff `agent@demo.local` / `reviewer@demo.local` with
`DEMO_STAFF_PASSWORD`, seven contacts across channels, two cases, a template):

```powershell
docker compose exec api python scripts/seed_demo.py
```

To re-run migrations by hand: `docker compose exec api alembic upgrade head`.

## 3. Try it without Meta

Open **Simulator** in the admin UI and chat as a fake WhatsApp, Messenger or
Instagram user. Everything (safety checks, cases, bot answers, broadcasts to
simulated contacts) works without Meta. See [DEMO.md](DEMO.md) for a full script.

## 4. Connect the real WhatsApp test number

1. In the [Meta App Dashboard](https://developers.facebook.com/apps) → your app →
   **WhatsApp → API Setup**, copy into `.env`:
   - `WA_ACCESS_TOKEN`: the temporary access token (valid 24 h, see step 6)
   - `WA_PHONE_NUMBER_ID`: the test number's *Phone number ID*
   - `WA_BUSINESS_ACCOUNT_ID`: the *WhatsApp Business Account ID*
2. **App settings → Basic → App secret** → `WA_APP_SECRET`. Every webhook is
   checked against it (`X-Hub-Signature-256`). Wrong secret = every webhook gets 403.
3. Invent a `WA_VERIFY_TOKEN` (any random string).
4. On the API Setup page, add your own phone number to the test number's
   **To** list. The test number can only message up to 5 verified numbers.
5. Recreate the backend so it reads the new env:
   `docker compose up -d --force-recreate api worker`
6. Start a public HTTPS tunnel to the API. Easiest: the optional compose
   service, which keeps running in the background with the stack:
   ```powershell
   docker compose --profile tunnel up -d tunnel
   docker compose logs tunnel    # look for https://<random>.trycloudflare.com
   ```
   (Or run `cloudflared tunnel --url http://localhost:8000` in a terminal and
   leave it open.) Optionally put the URL in `.env` as `API_BASE_URL` so the
   Settings page shows the full webhook URL.
7. Meta App Dashboard → **WhatsApp → Configuration → Webhook → Edit**:
   - Callback URL: `https://<random>.trycloudflare.com/webhook/whatsapp`
   - Verify token: your `WA_VERIFY_TOKEN`
   - **Verify and save**, then under **Webhook fields** subscribe to **messages**.
8. From your phone, send "Halo" to the test number. You should get the privacy
   notice and an answer, and see the conversation in the inbox.

**The quick-tunnel URL changes every time the tunnel restarts** (including after
a reboot or a Docker Desktop restart). Get the new one with
`docker compose logs tunnel` and update the Callback URL in Meta (or use a named
Cloudflare tunnel with a fixed hostname). In Meta's "Production setup" checklist
you can skip *Register your WhatsApp phone number* and *Add payment*: the test
number needs neither.

Admin → **Settings → Channels** shows what is configured, when the last webhook
arrived, and a **Test token** button that calls the Graph API.

## 5. Replace the 24-hour token with a System User token

The temporary token expires after 24 h. For anything longer:

1. [Business Settings](https://business.facebook.com/settings) → **Users → System users**
   → **Add** (role *Admin*).
2. **Assign assets**: your app (full control) and your WhatsApp account (full control).
3. **Generate new token** → choose the app → permissions `whatsapp_business_messaging`
   and `whatsapp_business_management` → expiry **Never**.
4. Put it in `WA_ACCESS_TOKEN` and run `docker compose up -d --force-recreate api worker`.

## Messenger and Instagram (optional, off by default)

Set `ENABLE_MESSENGER=true` / `ENABLE_INSTAGRAM=true`, `META_PAGE_ID`,
`META_PAGE_ACCESS_TOKEN` (and `META_IG_ACCOUNT_ID`). Use the webhook URLs
`/webhook/messenger` and `/webhook/instagram` with the same verify token, and
subscribe to `messages`, `message_deliveries` and `message_reads`. Staff replies
after 24 h use the `HUMAN_AGENT` tag, which needs Meta's Human Agent permission.

## Voice notes, reminders, backups

- **Voice notes** are transcribed on the worker's CPU by default
  (`TRANSCRIBE_PROVIDER=local`, Whisper `small`). The first voice note downloads the
  model (~460 MB) into the Docker volume. Use `base` on a small server, `groq` (with
  `TRANSCRIBE_API_KEY`) for fast, low-cost hosted transcription, or an
  empty value to switch it off.
- **Medication reminders** are off until you switch them on in Settings → Bot,
  keamanan & biaya → Pengingat obat, and per patient in the contact panel (stage
  "Pengobatan"). For patients who haven't chatted in 24 hours WhatsApp only allows an
  approved template: create one in WhatsApp Manager with two quick-reply buttons
  (Sudah / Belum) and one variable for the first name, then put its name in
  "Template WhatsApp".
- **Backups** run automatically (the `backup` service) into `./backups`. Restore
  steps and hosting on a real server: [HOSTING.md](HOSTING.md).

## Tests

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest -q              # backend, SQLite, no network, no cost
cd web; npm ci; npx playwright install chromium
npm run e2e                                     # needs the stack running
```

`scripts/simulate_whatsapp.py "Halo"` posts a signed fake WhatsApp webhook to
localhost. It needs `WA_APP_SECRET` in `.env`.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Meta: "The callback URL or verify token couldn't be validated" | tunnel not running, wrong URL path, or `WA_VERIFY_TOKEN` mismatch |
| Webhooks arrive but the API logs `bad or missing signature` (403) | `WA_APP_SECRET` is wrong (it's the *app* secret, not the token) |
| Inbox shows "Not delivered: … not in allowed list" | add the number to the test number's To list |
| Bot always replies "Staf kami akan menghubungi…" and opens BOT_ERROR cases | the LLM call fails: check the worker log (`docker compose logs worker`) for the reason (key, workspace ID, quota) |
| "Outside WhatsApp's 24-hour window" on staff reply | the user hasn't written for 24 h; only templates (Broadcasts) can be sent |
| Settings → Test token fails with code 190 | the access token expired: see step 5 |
