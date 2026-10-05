# Hosting, backups and updates

How to run the hub on a real server instead of a laptop with a quick tunnel.
Do this before any real patient data goes in.

## 1. Server

- A VPS in **Jakarta or Singapore** (health data should stay close; check what the
  foundation's UU PDP review says). 2 vCPU / 4 GB RAM / 40 GB disk is enough for a
  pilot; 8 GB if voice notes are transcribed on the server (`TRANSCRIBE_PROVIDER=local`).
- Ubuntu 24.04 with Docker Engine and the compose plugin:
  `curl -fsSL https://get.docker.com | sh`
- Firewall: allow 22 (SSH), 80 and 443 only. Postgres, Redis and the app ports stay
  inside Docker.

## 2. Domains

Two DNS **A records** pointing at the server, for example:

| Name | Serves |
|---|---|
| `hub.yayasan.org` | the staff app (Next.js) |
| `api.yayasan.org` | the API and the Meta webhooks |

## 3. Configure

```bash
git clone https://github.com/1uthfipratama/ontaonti.git && cd ontaonti
cp .env.example .env
```

In `.env`, besides the keys from [SETUP.md](SETUP.md):

```ini
APP_ENV=prod
SECRET_KEY=<64 random characters>        # python -c "import secrets; print(secrets.token_hex(32))"
POSTGRES_PASSWORD=<random>
COOKIE_SECURE=true
API_BASE_URL=https://api.yayasan.org
WEB_BASE_URL=https://hub.yayasan.org
PUBLIC_API_URL=https://api.yayasan.org   # baked into the web build
WEB_DOMAIN=hub.yayasan.org
API_DOMAIN=api.yayasan.org
```

The admin's browser talks to `api.` directly, with cookies. Both subdomains share the
parent domain, so the session cookie works as a same-site cookie.

## 4. Start with HTTPS

```bash
docker compose --profile https up -d --build
```

Caddy (`deploy/Caddyfile`) gets Let's Encrypt certificates for both domains and
renews them. The `backup` service starts with everything else (see §6).

Then in the Meta App Dashboard → WhatsApp → Configuration, set the webhook to
`https://api.yayasan.org/webhook/whatsapp`. This URL is permanent, unlike the
quick tunnel's.

## 5. Check

- `https://api.yayasan.org/health` → `{"ok": true, "db": "ok", "redis": "ok", "kb_index": "ok"}`
- Sign in at `https://hub.yayasan.org`, then turn on two-step verification under
  **Akun saya** (click your name in the sidebar). Ask every staff member to do the same.
- Settings → Kanal → **Tes token** shows whether Meta lets the number send.
- Uptime: point any free monitor (UptimeRobot, Better Stack) at `/health`.

## 6. Backups

The `backup` service dumps the database and the media files (photos, voice notes,
documents) once at start and then every 24 hours into `./backups`, keeping 14 days
(`BACKUP_KEEP_DAYS`, `BACKUP_INTERVAL_HOURS`).

`./backups` is on the same server. **Copy it somewhere else every day**: another
server, object storage (`rclone sync ./backups remote:onti-backups`) or the
foundation's Google Drive. A backup on the same disk doesn't survive losing the server.

The knowledge-base index and Whisper models aren't backed up: both are rebuilt
automatically. Knowledge-base articles live in the database, so they are in the dump.

### Restore

```bash
docker compose stop api worker
docker compose exec -T db pg_restore -U onti -d onti --clean --if-exists < backups/db-YYYYMMDD-HHMM.dump
docker run --rm -v onti-hub_kbdata:/data -v "$PWD/backups:/backups" alpine \
  tar -xzf /backups/media-YYYYMMDD-HHMM.tar.gz -C /data
docker compose start api worker
```

Test a restore on a spare machine at least once before relying on it.

## 7. Updates

```bash
git pull
docker compose --profile https up -d --build
```

Database migrations run automatically when the api starts. Take a manual backup first
for big updates: `docker compose restart backup` runs one straight away.

## 8. Phones (installable app)

The staff app can be installed like an app: in Chrome on Android, open the hub and
choose **Install app** (or "Add to home screen"); on iPhone, Safari → Share → **Add to
Home Screen**. It opens full screen with the Onti Erlina icon. Push notifications
are not built yet; the sidebar badges update live while the app is open.

## 9. Before real patients

- Medical review of the knowledge base, the safety replies, the screening questions
  (`config/screening.yaml`) and the reminder texts.
- UU PDP 27/2022: a data-processing record, retention rules, who can see what (roles),
  and how to answer a patient's request to see or delete their data.
- A WhatsApp number under the foundation's verified Meta Business account
  ([PROGRESS.md](PROGRESS.md)), with a System User token instead of the 24-hour token.
- Rotate every secret that was ever pasted into a chat or committed by mistake.
