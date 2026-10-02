"""Post signed, fake WhatsApp Cloud API webhooks to the local API.

Exercises the real webhook path (signature check, queue, dedupe, worker) without
Meta. The bot's replies are then sent through the Graph API with your
WA_ACCESS_TOKEN: to a made-up number they simply fail (shown as "not delivered"
in the inbox). Don't use a real person's number unless they agreed to it.

    python scripts/simulate_whatsapp.py "Berapa lama pengobatan TBC?"
    python scripts/simulate_whatsapp.py "saya batuk darah banyak" --from 6280000000002 --name Rina
    python scripts/simulate_whatsapp.py --image
    python scripts/simulate_whatsapp.py --status wamid.XXXX --state read
    python scripts/simulate_whatsapp.py "Halo" --duplicate     # same payload twice: processed once
    python scripts/simulate_whatsapp.py "Halo" --bad-signature # expect 403
"""

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent


def load_env() -> dict[str, str]:
    env = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"')
    env.update({k: v for k, v in os.environ.items() if k.startswith("WA_")})
    return env


def envelope(value: dict, phone_number_id: str) -> dict:
    value = {
        "messaging_product": "whatsapp",
        "metadata": {"display_phone_number": "15550000000", "phone_number_id": phone_number_id},
        **value,
    }
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "0", "changes": [{"field": "messages", "value": value}]}],
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("text", nargs="?", default="Halo, saya mau tanya tentang TBC")
    ap.add_argument(
        "--from", dest="wa_id", default="6280000000001", help="sender wa_id (fake by default)"
    )
    ap.add_argument("--name", default="Pengguna Simulasi")
    ap.add_argument("--url", default="http://localhost:8000/webhook/whatsapp")
    ap.add_argument("--image", action="store_true", help="send an image message instead of text")
    ap.add_argument("--status", help="send a status callback for this outbound wamid")
    ap.add_argument("--state", default="delivered", choices=["sent", "delivered", "read", "failed"])
    ap.add_argument("--duplicate", action="store_true", help="post the same payload twice")
    ap.add_argument("--bad-signature", action="store_true")
    args = ap.parse_args()

    env = load_env()
    secret = env.get("WA_APP_SECRET", "")
    if not secret and not args.bad_signature:
        sys.exit("WA_APP_SECRET is empty in .env: the API would reject every webhook (403).")
    phone_id = env.get("WA_PHONE_NUMBER_ID") or "0"
    now = str(int(time.time()))

    if args.status:
        value = {"statuses": [{"id": args.status, "status": args.state, "timestamp": now,
                               "recipient_id": args.wa_id}]}  # fmt: skip
    else:
        msg: dict = {
            "from": args.wa_id,
            "id": f"wamid.SIM{uuid.uuid4().hex[:24]}",
            "timestamp": now,
        }
        if args.image:
            msg |= {"type": "image", "image": {"id": "SIMMEDIA", "mime_type": "image/jpeg"}}
        else:
            msg |= {"type": "text", "text": {"body": args.text}}
        value = {
            "contacts": [{"profile": {"name": args.name}, "wa_id": args.wa_id}],
            "messages": [msg],
        }
    body = json.dumps(envelope(value, phone_id)).encode()
    signature = "sha256=" + (
        "0" * 64
        if args.bad_signature
        else hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    )
    headers = {"Content-Type": "application/json", "X-Hub-Signature-256": signature}
    for attempt in range(2 if args.duplicate else 1):
        r = httpx.post(args.url, content=body, headers=headers, timeout=15)
        print(f"POST #{attempt + 1} -> {r.status_code} {r.text[:200]}")
    print("Open the admin inbox to see the conversation and the bot's reply.")


if __name__ == "__main__":
    main()
