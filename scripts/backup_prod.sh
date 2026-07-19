#!/usr/bin/env bash
#
# Run this ON THE PRODUCTION SERVER.
# Dumps the Postgres database and archives the media directory.
# Read-only with respect to production: nothing is modified.
#
# Usage:  bash backup_prod.sh [output_dir]
#
set -euo pipefail

OUT_DIR="${1:-$HOME/aurora-backups}"
MEDIA_DIR="${MEDIA_DIR:-/srv/aurora/shared/media}"
STAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$OUT_DIR"

# ── Locate the running Postgres container ────────────────────────────────
# This deploy is release-based (/srv/aurora/current -> releases/<stamp>), so the
# Compose project name is the release timestamp, not the directory we run from.
# Addressing the container directly sidesteps that entirely.
DB_CONTAINER="${DB_CONTAINER:-$(docker ps --filter 'name=db-1' --format '{{.Names}}' | head -n1)}"

if [ -z "$DB_CONTAINER" ]; then
  echo "ERROR: could not find a running Postgres container." >&2
  echo "       Set it explicitly:  DB_CONTAINER=<name> bash $0" >&2
  docker ps --format '  {{.Names}}\t{{.Image}}' >&2
  exit 1
fi
echo "==> Using database container: ${DB_CONTAINER}"

# ── Read credentials from the container's own environment ────────────────
# More reliable than guessing where .env lives across releases.
POSTGRES_USER="$(docker exec "$DB_CONTAINER" printenv POSTGRES_USER 2>/dev/null || true)"
POSTGRES_DB="$(docker exec "$DB_CONTAINER" printenv POSTGRES_DB 2>/dev/null || true)"

if [ -z "$POSTGRES_USER" ] || [ -z "$POSTGRES_DB" ]; then
  echo "ERROR: could not read POSTGRES_USER / POSTGRES_DB from ${DB_CONTAINER}." >&2
  exit 1
fi

DB_FILE="${OUT_DIR}/aurora-db-${STAMP}.sql.gz"
MEDIA_FILE="${OUT_DIR}/aurora-media-${STAMP}.tar.gz"

echo "==> Dumping database '${POSTGRES_DB}' as '${POSTGRES_USER}'"
# --no-owner / --no-acl so the dump restores cleanly under a different local role.
docker exec "$DB_CONTAINER" \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl \
  | gzip > "$DB_FILE"

echo "==> Archiving media from ${MEDIA_DIR}"
if [ -d "$MEDIA_DIR" ]; then
  tar -czf "$MEDIA_FILE" -C "$(dirname "$MEDIA_DIR")" "$(basename "$MEDIA_DIR")"
else
  echo "WARNING: ${MEDIA_DIR} not found; skipping media archive" >&2
  MEDIA_FILE="(skipped)"
fi

echo
echo "Done."
echo "  database : ${DB_FILE}"
echo "  media    : ${MEDIA_FILE}"
echo
echo "These contain live customer data. Pull them down, then delete them"
echo "from the server when you're finished:"
echo "  rm -f ${DB_FILE} ${MEDIA_FILE}"
