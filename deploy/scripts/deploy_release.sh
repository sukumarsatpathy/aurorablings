#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/srv/aurora}"
RELEASE_ID="${RELEASE_ID:-}"
ARTIFACT_PATH="${ARTIFACT_PATH:-}"
KEEP_RELEASES="${KEEP_RELEASES:-3}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --app-root) APP_ROOT="$2"; shift 2 ;;
    --release-id) RELEASE_ID="$2"; shift 2 ;;
    --artifact) ARTIFACT_PATH="$2"; shift 2 ;;
    --keep-releases) KEEP_RELEASES="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "${RELEASE_ID}" || -z "${ARTIFACT_PATH}" ]]; then
  echo "Usage: deploy_release.sh --release-id <id> --artifact <path> [--app-root /srv/aurora]" >&2
  exit 1
fi

SHARED_DIR="${APP_ROOT}/shared"
RELEASES_DIR="${APP_ROOT}/releases"
RELEASE_DIR="${RELEASES_DIR}/${RELEASE_ID}"
CURRENT_LINK="${APP_ROOT}/current"

# 1. Prepare Release Directory
echo "Preparing release: ${RELEASE_ID}..."
mkdir -p "${RELEASES_DIR}" "${SHARED_DIR}"/{media,static,logs,run,tmp}
mkdir -p "${RELEASE_DIR}"
tar -xzf "${ARTIFACT_PATH}" -C "${RELEASE_DIR}"

# 2. Link Shared Environment
if [[ ! -f "${SHARED_DIR}/.env" ]]; then
  echo "CRITICAL: Missing .env file in ${SHARED_DIR}/.env" >&2
  exit 1
fi
ln -sfn "${SHARED_DIR}/.env" "${RELEASE_DIR}/.env"

# 3. Docker Compose Deployment
echo "Starting Docker Compose deployment..."
pushd "${RELEASE_DIR}" >/dev/null

# ✅ ADD THIS LINE: Ensure the 'current' link exists for Docker mounts
ln -sfn "${RELEASE_DIR}" "${CURRENT_LINK}"

# Pull/Build images
docker compose -f docker-compose.prod.yml build --pull

# Start new containers (replaces existing ones)
docker compose -f docker-compose.prod.yml up -d --remove-orphans

# 4. Post-Deployment Checks
echo "Verifying deployment health..."
# Wait for backend to be healthy
MAX_RETRIES=10
COUNT=0
until [[ $(docker inspect -f '{{.State.Health.Status}}' $(docker compose -f docker-compose.prod.yml ps -q backend)) == "healthy" ]]; do
    if [ $COUNT -ge $MAX_RETRIES ]; then
        echo "ERROR: Backend health check failed!" >&2
        docker compose -f docker-compose.prod.yml logs backend
        exit 1
    fi
    echo "Waiting for backend health... ($((COUNT+1))/$MAX_RETRIES)"
    sleep 5
    COUNT=$((COUNT+1))
done

echo "Backend is healthy!"
popd >/dev/null

# 5. Update Symlink
echo "Updating current release symlink..."
ln -sfn "${RELEASE_DIR}" "${CURRENT_LINK}"

# 6. Cleanup
echo "Cleaning up old releases..."
# Prune old images to save space on Vultr
docker image prune -f --filter "until=168h" 

# Keep only N recent releases in the file system
ls -dt "${RELEASES_DIR}"/* | tail -n +"$((KEEP_RELEASES + 1))" | xargs -r rm -rf

echo "Deployment ${RELEASE_ID} successful!"
