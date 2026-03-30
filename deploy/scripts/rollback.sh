#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/srv/aurorablings}"
TARGET_RELEASE="${1:-}"
RELEASES_DIR="${APP_ROOT}/releases"

if [[ ! -d "${RELEASES_DIR}" ]]; then
  echo "Missing releases directory: ${RELEASES_DIR}" >&2
  exit 1
fi

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

ln -sfn "${TARGET_PATH}" "${APP_ROOT}/current"
sudo systemctl restart aurorablings-gunicorn.service
sudo systemctl restart aurorablings-celery-worker.service
sudo systemctl restart aurorablings-celery-beat.service
sudo systemctl reload nginx

echo "Rolled back to ${TARGET_RELEASE}."