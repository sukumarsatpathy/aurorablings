#!/usr/bin/env bash
#
# Compress already-uploaded images on the production Docker deployment.
#
# RUN THIS ONLY AFTER the deploy that ships backfill_banner_variants. The
# command does not exist in older backend images.
#
# What it does NOT do: nothing here touches the database schema or restarts a
# service. It re-encodes files under /srv/aurora/shared/media in place.
#
# ── Why not `docker compose exec` from /srv/aurora/current ───────────────────
# deploy_release.sh runs compose from ${APP_ROOT}/releases/<RELEASE_ID>, so the
# Compose project name is the timestamped release directory. Running
# `docker compose exec` from anywhere else (including the `current` symlink,
# whose basename is "current") resolves to a DIFFERENT project with no running
# containers, and exits without doing anything. So we locate the live container
# by image instead, which is stable across releases.
#
set -euo pipefail

APP_ROOT="${APP_ROOT:-/srv/aurora}"
MEDIA_DIR="${APP_ROOT}/shared/media"
BACKEND_IMAGE="ghcr.io/sukumarsatpathy/aurorablings/backend"

log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# ── 1. Locate the running backend container ─────────────────────────────────
log "Locating backend container"
BACKEND="$(docker ps --filter "ancestor=${BACKEND_IMAGE}:latest" --format '{{.ID}}' | head -n1)"
if [[ -z "${BACKEND}" ]]; then
  # Fall back to name matching if the image tag was pinned to a release.
  BACKEND="$(docker ps --format '{{.ID}} {{.Image}} {{.Names}}' \
             | grep -E "${BACKEND_IMAGE}|backend" | awk '{print $1}' | head -n1)"
fi
[[ -n "${BACKEND}" ]] || die "No running backend container found. Is the stack up?"
echo "Using container ${BACKEND}"

dexec() { docker exec -i "${BACKEND}" "$@"; }

# ── 2. Preflight: encoders and disk ─────────────────────────────────────────
log "Checking image encoders inside the container"
dexec python -c "
import PIL
from PIL import features
print('Pillow', PIL.__version__)
print('webp:', features.check('webp'))
print('avif:', features.check('avif'), '(needs Pillow >= 11.3; False means WebP-only output)')
" || die "Could not inspect Pillow. Wrong container?"

log "Disk space on the media volume"
df -h "${MEDIA_DIR}"
echo
echo "Re-encoding writes new files before the old ones are removed, and the"
echo "backup below duplicates the tree. Make sure there is headroom."

# ── 3. Back up media. --apply DELETES original masters. ─────────────────────
BACKUP="${APP_ROOT}/backups/media-$(date +%Y%m%d-%H%M%S).tar.gz"
log "Backing up ${MEDIA_DIR} -> ${BACKUP}"
mkdir -p "$(dirname "${BACKUP}")"
tar -czf "${BACKUP}" -C "$(dirname "${MEDIA_DIR}")" "$(basename "${MEDIA_DIR}")"
echo "Backup size: $(du -h "${BACKUP}" | cut -f1)"
echo
echo "This is the only way back. compress_image() re-encodes the master under a"
echo "new name and the pre_save signal deletes the previous file. Re-encoding an"
echo "already-lossy JPEG is lossy again and cannot be undone from the app."

# ── 4. Dry run: see what would change, change nothing ───────────────────────
log "DRY RUN — promo banners"
dexec python manage.py backfill_banner_variants

log "DRY RUN — product media"
dexec python manage.py backfill_media_variants

cat <<'PROMPT'

────────────────────────────────────────────────────────────────────────────
Nothing has been modified yet. Review the dry-run output above.

Next, run a single-record trial and LOOK AT IT in the browser before
committing to the full pass:

    docker exec -i <CONTAINER> python manage.py backfill_banner_variants --apply --limit 1
    docker exec -i <CONTAINER> python manage.py backfill_media_variants  --apply --limit 5

Then load the homepage and confirm the banner still looks right. Quality
settings are WebP q74 / q72 and AVIF q50; if the trial looks soft, tune
AVIF_QUALITY_DEFAULT in core/image_optimization.py and redeploy BEFORE
processing the rest.

Once satisfied:

    docker exec -i <CONTAINER> python manage.py backfill_banner_variants --apply
    docker exec -i <CONTAINER> python manage.py backfill_media_variants  --apply

Banner saves fire invalidate_promo_banner_cache via Celery, so the API cache
clears itself. If you have a CDN in front of /media, purge it afterwards --
filenames change, so stale URLs will 404 rather than serve old bytes.
────────────────────────────────────────────────────────────────────────────

PROMPT

echo "Backend container: ${BACKEND}"
echo "Backup:            ${BACKUP}"
