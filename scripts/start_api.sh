#!/bin/sh
# API container entrypoint: migrate, make sure the KB index exists, serve.
set -e
alembic upgrade head
python scripts/reindex_kb.py --if-needed
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
