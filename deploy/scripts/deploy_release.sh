#!/usr/bin/env bash
set -Eeuo pipefail

APP_ROOT="${APP_ROOT:-/srv/aurora}"
RELEASE_ID="${RELEASE_ID:-}"
ARTIFACT_PATH="${ARTIFACT_PATH:-}"
KEEP_RELEASES="${KEEP_RELEASES:-3}"
NETWORK_NAME="${NETWORK_NAME:-aurora_network}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --app-root)      APP_ROOT="$2";      shift 2 ;;
    --release-id)    RELEASE_ID="$2";    shift 2 ;;
    --artifact)      ARTIFACT_PATH="$2"; shift 2 ;;
    --keep-releases) KEEP_RELEASES="$2"; shift 2 ;;
    --network-name)  NETWORK_NAME="$2";  shift 2 ;;
    --compose-file)  COMPOSE_FILE="$2";  shift 2 ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "${RELEASE_ID}" || -z "${ARTIFACT_PATH}" ]]; then
  echo "Usage: deploy_release.sh --release-id <id> --artifact <path> [--app-root /srv/aurora] [--keep-releases 3] [--network-name aurora_network] [--compose-file docker-compose.prod.yml]" >&2
  exit 1
fi

SHARED_DIR="${APP_ROOT}/shared"
RELEASES_DIR="${APP_ROOT}/releases"
RELEASE_DIR="${RELEASES_DIR}/${RELEASE_ID}"
CURRENT_LINK="${APP_ROOT}/current"

log() {
  echo
  echo "=================================================="
  echo "$1"
  echo "=================================================="
}

fail() {
  echo "ERROR: $1" >&2
  exit 1
}

cleanup_on_error() {
  echo
  echo "Deployment failed. Showing compose status and recent logs..."
  if [[ -d "${RELEASE_DIR}" && -f "${RELEASE_DIR}/${COMPOSE_FILE}" ]]; then
    (
      cd "${RELEASE_DIR}" || exit 0
      docker compose -f "${COMPOSE_FILE}" ps || true
      docker compose -f "${COMPOSE_FILE}" logs --tail=200 backend nginx_proxy frontend celery_worker celery_beat db redis || true
    )
  fi
}
trap cleanup_on_error ERR

# ── Step 1: Validate ──────────────────────────────────────────────────────────
log "Validating inputs"
[[ -f "${ARTIFACT_PATH}" ]] || fail "Artifact not found at ${ARTIFACT_PATH}"

# ── Step 2: Prepare directories ───────────────────────────────────────────────
log "Preparing directories"
mkdir -p "${RELEASES_DIR}"
mkdir -p "${SHARED_DIR}/media" "${SHARED_DIR}/static" "${SHARED_DIR}/logs" \
         "${SHARED_DIR}/logs/nginx" "${SHARED_DIR}/run" "${SHARED_DIR}/tmp"
mkdir -p "${RELEASE_DIR}"

# ── Step 3: Extract artifact ──────────────────────────────────────────────────
log "Extracting artifact"
tar -xzf "${ARTIFACT_PATH}" -C "${RELEASE_DIR}"
[[ -f "${RELEASE_DIR}/${COMPOSE_FILE}" ]] || fail "Compose file ${COMPOSE_FILE} not found in release directory"

# ── Step 4: Link shared .env ──────────────────────────────────────────────────
log "Linking shared environment"
[[ -f "${SHARED_DIR}/.env" ]] || fail "Missing .env file at ${SHARED_DIR}/.env"
ln -sfn "${SHARED_DIR}/.env" "${RELEASE_DIR}/.env"

# ── Step 5: Ensure Docker network exists (FIX 1) ──────────────────────────────
log "Ensuring Docker external network exists"
if ! docker network inspect "${NETWORK_NAME}" >/dev/null 2>&1; then
  echo "Creating network: ${NETWORK_NAME}"
  docker network create "${NETWORK_NAME}"
else
  echo "Network already exists: ${NETWORK_NAME}"
fi

# ── Step 6: Update current symlink ───────────────────────────────────────────
log "Updating current symlink for shared mount references"
ln -sfn "${RELEASE_DIR}" "${CURRENT_LINK}"

# ── Step 7: Deploy ───────────────────────────────────────────────────────────
log "Starting Docker Compose deployment"
pushd "${RELEASE_DIR}" >/dev/null

echo "Validating compose file..."
docker compose -f "${COMPOSE_FILE}" config >/dev/null

echo "Stopping old containers..."
docker compose -f "${COMPOSE_FILE}" down --remove-orphans

# Re-ensure network after 'down' detaches all containers (FIX 2)
if ! docker network inspect "${NETWORK_NAME}" >/dev/null 2>&1; then
  echo "Re-creating network after compose down: ${NETWORK_NAME}"
  docker network create "${NETWORK_NAME}"
fi

# ── FIX 4: Kill any stale containers holding ports 80 or 443 ─────────────────
# Timestamp-based project names mean 'compose down' only stops the CURRENT
# project. A previously failed deploy may still own port 80/443.
echo "Releasing ports 80 and 443 from any stale containers..."
for PORT in 80 443; do
  STALE="$(docker ps -q --filter "publish=${PORT}" || true)"
  if [[ -n "${STALE}" ]]; then
    echo "  Port ${PORT} held by container(s): ${STALE} — stopping..."
    docker stop ${STALE} || true
    docker rm   ${STALE} || true
  fi
done
# ──────────────────────────────────────────────────────────────────────────────

echo "Pulling latest images..."
docker compose -f "${COMPOSE_FILE}" pull

echo "Starting containers..."
docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans --force-recreate

# Prune AFTER containers are up so aurora_network is protected (FIX 3)
echo "Pruning unused Docker networks..."
docker network prune -f || true

echo "Current container status:"
docker compose -f "${COMPOSE_FILE}" ps

# ── Step 8: Backend health check ─────────────────────────────────────────────
log "Running post-deployment health checks"

BACKEND_CONTAINER_ID="$(docker compose -f "${COMPOSE_FILE}" ps -q backend)"
[[ -n "${BACKEND_CONTAINER_ID}" ]] || fail "Backend container ID not found"

MAX_RETRIES=24   # 24 × 10s = 4 minutes (covers migrate + collectstatic time)
SLEEP_SECONDS=10
COUNT=0

while true; do
  HEALTH_STATUS="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "${BACKEND_CONTAINER_ID}" 2>/dev/null || echo "unknown")"

  if [[ "${HEALTH_STATUS}" == "healthy" ]]; then
    echo "Backend is healthy."
    break
  fi

  if [[ "${HEALTH_STATUS}" == "no-healthcheck" ]]; then
    echo "No Docker healthcheck found for backend. Falling back to process check."
    RUNNING_STATUS="$(docker inspect -f '{{.State.Status}}' "${BACKEND_CONTAINER_ID}" 2>/dev/null || echo "unknown")"
    [[ "${RUNNING_STATUS}" == "running" ]] || fail "Backend container is not running"
    echo "Backend container is running."
    break
  fi

  if [[ "${COUNT}" -ge "${MAX_RETRIES}" ]]; then
    echo "Backend health status: ${HEALTH_STATUS}"
    docker compose -f "${COMPOSE_FILE}" logs --tail=200 backend
    fail "Backend health check failed after ${MAX_RETRIES} attempts"
  fi

  COUNT=$((COUNT + 1))
  echo "Waiting for backend health... attempt ${COUNT}/${MAX_RETRIES} (status: ${HEALTH_STATUS})"
  sleep "${SLEEP_SECONDS}"
done

# ── Step 9: Nginx verification ────────────────────────────────────────────────
log "Optional nginx verification"
NGINX_CONTAINER_ID="$(docker compose -f "${COMPOSE_FILE}" ps -q nginx_proxy || true)"
if [[ -n "${NGINX_CONTAINER_ID}" ]]; then
  NGINX_STATUS="$(docker inspect -f '{{.State.Status}}' "${NGINX_CONTAINER_ID}" 2>/dev/null || echo "unknown")"
  echo "nginx_proxy container status: ${NGINX_STATUS}"
fi

popd >/dev/null

# ── Step 10: Cleanup ──────────────────────────────────────────────────────────
log "Cleaning up old Docker images"
docker image prune -f --filter "until=168h" || true

log "Cleaning up old releases"
if [[ -d "${RELEASES_DIR}" ]]; then
  mapfile -t OLD_RELEASES < <(ls -dt "${RELEASES_DIR}"/* 2>/dev/null | tail -n +"$((KEEP_RELEASES + 1))" || true)
  if [[ "${#OLD_RELEASES[@]}" -gt 0 ]]; then
    printf '%s\n' "${OLD_RELEASES[@]}" | xargs -r rm -rf
  fi
fi

log "Deployment ${RELEASE_ID} completed successfully"
echo "Current release : ${RELEASE_DIR}"
echo "Current symlink : ${CURRENT_LINK} -> $(readlink -f "${CURRENT_LINK}")"