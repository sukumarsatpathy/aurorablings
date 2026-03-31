#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/srv/aurora}"          # ✅ match docker-compose.prod.yml
SHARED_DIR="${APP_ROOT}/shared"
RELEASES_DIR="${APP_ROOT}/releases"

sudo mkdir -p "${RELEASES_DIR}" \
    "${SHARED_DIR}"/{media,static,logs,logs/nginx,run,tmp}

# ✅ Fix ownership so django user (uid 1000) inside container can write
sudo chown -R 1000:1000 "${SHARED_DIR}/logs"

if [[ ! -f "${SHARED_DIR}/.env" ]]; then
  sudo touch "${SHARED_DIR}/.env"
  sudo chmod 600 "${SHARED_DIR}/.env"
fi

if [[ ! -d "${SHARED_DIR}/venv" ]]; then
  python3 -m venv "${SHARED_DIR}/venv"
fi

"${SHARED_DIR}/venv/bin/pip" install --upgrade pip wheel setuptools

echo "Bootstrap complete."
echo "1) Copy project release tarball to server"
echo "2) Populate ${SHARED_DIR}/.env"
echo "3) Install systemd unit files from deploy/systemd"
echo "4) Install nginx config from deploy/nginx"