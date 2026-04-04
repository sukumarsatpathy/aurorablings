#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/srv/aurora}"          # ✅ was /srv/aurorablings
TARGET_RELEASE="${1:-}"
RELEASES_DIR="${APP_ROOT}/releases"
NETWORK_NAME="${NETWORK_NAME:-aurora_network}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

if [[ ! -d "${RELEASES_DIR}" ]]; then
  echo "Missing releases directory: ${RELEASES_DIR}" >&2
  exit 1
fi

# Pick previous release if none specified
if [[ -z "${TARGET_RELEASE}" ]]; then
  mapfile -t releases < <(ls -1dt "${RELEASES_DIR}"/*)
  if (( ${#releases[@]} < 2 )); then
    echo "No previous release found for rollback." >&2
    exit 1
  fi
  TARGET_RELEASE="$(basename "${releases[1]}")"
fi

TARGET_PATH="${RELEASES_DIR}/${TARGET_RELEASE}"
if [[ ! -d "${TARGET_PATH}" ]]; then
  echo "Release not found: ${TARGET_PATH}" >&2
  exit 1
fi

echo "Rolling back to: ${TARGET_RELEASE}"

# Point current symlink to the target release
ln -sfn "${TARGET_PATH}" "${APP_ROOT}/current"

# Re-ensure network exists before starting containers
if ! docker network inspect "${NETWORK_NAME}" >/dev/null 2>&1; then
  echo "Re-creating Docker network: ${NETWORK_NAME}"
  docker network create "${NETWORK_NAME}"
fi

# Restart Docker Compose stack from the target release
pushd "${TARGET_PATH}" >/dev/null
docker compose -f "${COMPOSE_FILE}" down --remove-orphans
docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans --force-recreate
popd >/dev/null

echo "Rolled back to ${TARGET_RELEASE} successfully."