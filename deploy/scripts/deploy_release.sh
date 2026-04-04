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
    --app-root) APP_ROOT="$2"; shift 2 ;;
    --release-id) RELEASE_ID="$2"; shift 2 ;;
    --artifact) ARTIFACT_PATH="$2"; shift 2 ;;
    --keep-releases) KEEP_RELEASES="$2"; shift 2 ;;
    --network-name) NETWORK_NAME="$2"; shift 2 ;;
    --compose-file) COMPOSE_FILE="$2"; shift 2 ;;
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

log "Validating inputs"

[[ -f "${ARTIFACT_PATH}" ]] || fail "Artifact not found at ${ARTIFACT_PATH}"

log "Preparing directories"

mkdir -p "${RELEASES_DIR}"
mkdir -p "${SHARED_DIR}/media" "${SHARED_DIR}/static" "${SHARED_DIR}/logs" "${SHARED_DIR}/run" "${SHARED_DIR}/tmp"
mkdir -p "${RELEASE_DIR}"

log "Extracting artifact"
tar -xzf "${ARTIFACT_PATH}" -C "${RELEASE_DIR}"

[[ -f "${RELEASE_DIR}/${COMPOSE_FILE}" ]] || fail "Compose file ${COMPOSE_FILE} not found in release directory"

log "Linking shared environment"

if [[ ! -f "${SHARED_DIR}/.env" ]]; then
  fail "Missing .env file at ${SHARED_DIR}/.env"
fi

ln -sfn "${SHARED_DIR}/.env" "${RELEASE_DIR}/.env"

# ── FIX 1: Ensure network exists BEFORE any compose operations ─────────────────
log "Ensuring Docker external network exists"

if ! docker network inspect "${NETWORK_NAME}" >/dev/null 2>&1; then
  echo "Creating network: ${NETWORK_NAME}"
  docker network create "${NETWORK_NAME}"
else
  echo "Network already exists: ${NETWORK_NAME}"
fi
# ──────────────────────────────────────────────────────────────────────────────

log "Updating current symlink for shared mount references"
ln -sfn "${RELEASE_DIR}" "${CURRENT_LINK}"

log "Starting Docker Compose deployment"

pushd "${RELEASE_DIR}" >/dev/null

echo "Using compose file: ${COMPOSE_FILE}"
docker compose -f "${COMPOSE_FILE}" config >/dev/null

echo "Stopping only this project's old containers..."
docker compose -f "${COMPOSE_FILE}" down --remove-orphans

# ── FIX 2: Re-ensure network after 'down' (down detaches all containers, ──────
#           making the network eligible for pruning if anything runs prune).
#           We removed the premature network prune that was here before.
if ! docker network inspect "${NETWORK_NAME}" >/dev/null 2>&1; then
  echo "Network was removed after compose down. Re-creating: ${NETWORK_NAME}"
  docker network create "${NETWORK_NAME}"
fi
# ──────────────────────────────────────────────────────────────────────────────

echo "Pulling latest images..."
docker compose -f "${COMPOSE_FILE}" pull

echo "Starting containers..."
docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans --force-recreate

# ── FIX 3: Prune unused networks AFTER containers are up ──────────────────────
#           aurora_network now has live containers attached, so it is safe
#           from pruning. Any truly orphaned networks will be cleaned up here.
echo "Pruning unused Docker networks..."
docker network prune -f || true
# ──────────────────────────────────────────────────────────────────────────────

echo "Current container status:"
docker compose -f "${COMPOSE_FILE}" ps

log "Running post-deployment health checks"

BACKEND_CONTAINER_ID="$(docker compose -f "${COMPOSE_FILE}" ps -q backend)"
[[ -n "${BACKEND_CONTAINER_ID}" ]] || fail "Backend container ID not found"

MAX_RETRIES=18
SLEEP_SECONDS=5
COUNT=0

while true; do
  HEALTH_STATUS="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "${BACKEND_CONTAINER_ID}" 2>/dev/null || echo "unknown")"

  if [[ "${HEALTH_STATUS}" == "healthy" ]]; then
    echo "Backend is healthy."
    break
  fi

  if [[ "${HEALTH_STATUS}" == "no-healthcheck" ]]; then
    echo "No Docker healthcheck found for backend. Falling back to process-running check."
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

log "Optional nginx verification"
NGINX_CONTAINER_ID="$(docker compose -f "${COMPOSE_FILE}" ps -q nginx_proxy || true)"
if [[ -n "${NGINX_CONTAINER_ID}" ]]; then
  NGINX_STATUS="$(docker inspect -f '{{.State.Status}}' "${NGINX_CONTAINER_ID}" 2>/dev/null || echo "unknown")"
  echo "nginx_proxy container status: ${NGINX_STATUS}"
fi

popd >/dev/null

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
echo "Current release: ${RELEASE_DIR}"
echo "Current symlink: ${CURRENT_LINK} -> $(readlink -f "${CURRENT_LINK}")"