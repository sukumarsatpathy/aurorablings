#!/usr/bin/env bash
#
# Run this ON YOUR LAPTOP, from the repo root.
# Restores a production dump into the local Docker Postgres, unpacks media,
# then scrubs customer PII.
#
# Usage:  bash scripts/restore_local.sh <db-dump.sql.gz> [media.tar.gz]
#
set -euo pipefail

DB_DUMP="${1:-}"
MEDIA_ARCHIVE="${2:-}"
COMPOSE="docker compose -f docker-compose.dev.yml"

if [ -z "$DB_DUMP" ] || [ ! -f "$DB_DUMP" ]; then
  echo "Usage: bash scripts/restore_local.sh <db-dump.sql.gz> [media.tar.gz]" >&2
  exit 1
fi

# Guard: this script drops the local database. Make sure that's understood.
echo "This will DROP and recreate the local 'aurora_db' database in Docker."
read -r -p "Continue? [y/N] " reply
[ "$reply" = "y" ] || [ "$reply" = "Y" ] || { echo "Aborted."; exit 1; }

echo "==> Starting db service"
$COMPOSE up -d db
echo "==> Waiting for Postgres to accept connections"
until $COMPOSE exec -T db pg_isready -U aurora_user -d aurora_db >/dev/null 2>&1; do
  sleep 1
done

echo "==> Recreating database"
$COMPOSE exec -T db psql -U aurora_user -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS aurora_db;" \
  -c "CREATE DATABASE aurora_db OWNER aurora_user;"

echo "==> Restoring dump (this can take a while)"
gunzip -c "$DB_DUMP" | $COMPOSE exec -T db psql -U aurora_user -d aurora_db -q

echo "==> Applying any migrations newer than the dump"
$COMPOSE up -d backend
$COMPOSE exec -T backend python manage.py migrate --noinput

echo "==> Scrubbing customer PII"
$COMPOSE exec -T backend python manage.py anonymize_local --yes

if [ -n "$MEDIA_ARCHIVE" ] && [ -f "$MEDIA_ARCHIVE" ]; then
  echo "==> Restoring media into the backend container"
  tar -xzf "$MEDIA_ARCHIVE" -C /tmp
  docker cp /tmp/media/. "$($COMPOSE ps -q backend)":/app/media/
  rm -rf /tmp/media

  # docker cp preserves the HOST uid/gid (501:20 on macOS), so the restored
  # tree ends up unwritable by the container's django user (uid 101). The app
  # only notices when it first tries to create a new subdirectory --
  # upload_to="products/%Y/%m/" means that happens the next time the month
  # rolls over, which makes it look like an unrelated bug months later.
  echo "==> Fixing media ownership for the container user"
  $COMPOSE exec -T -u root backend chown -R django:django /app/media
fi

echo
echo "Done. Local database restored and anonymized."
echo "Every customer login is now: <something>@example.invalid / password 'localdev123'"
