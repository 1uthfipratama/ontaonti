#!/bin/sh
# Backups for the "backup" compose service: the database (pg_dump, custom format)
# and the media files (photos, voice notes, documents). Runs once at start, then
# every BACKUP_INTERVAL_HOURS. Files land in ./backups on the host; anything older
# than BACKUP_KEEP_DAYS is deleted. Restore steps: docs/HOSTING.md.
set -eu
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
INTERVAL_HOURS="${BACKUP_INTERVAL_HOURS:-24}"

backup() {
  stamp=$(date -u +%Y%m%d-%H%M)
  db="${PGDATABASE:-onti}"
  pg_dump -h db -U onti -d "$db" -Fc -f "/backups/db-$stamp.dump.part"
  mv "/backups/db-$stamp.dump.part" "/backups/db-$stamp.dump"
  if [ -d /data/media ]; then
    tar -czf "/backups/media-$stamp.tar.gz" -C /data media
  fi
  find /backups -maxdepth 1 \( -name 'db-*.dump' -o -name 'media-*.tar.gz' \) -mtime +"$KEEP_DAYS" -delete
  echo "backup $stamp done: $(ls /backups | wc -l) files kept"
}

while true; do
  backup || echo "backup failed (will retry next round)"
  sleep $((INTERVAL_HOURS * 3600))
done
