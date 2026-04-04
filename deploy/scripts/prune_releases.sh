#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/srv/aurora}"          # ✅ was /srv/aurorablings
KEEP_RELEASES="${KEEP_RELEASES:-3}"
RELEASES_DIR="${APP_ROOT}/releases"
CURRENT_TARGET="$(readlink -f "${APP_ROOT}/current" 2>/dev/null || true)"

if [[ ! -d "${RELEASES_DIR}" ]]; then
  exit 0
fi

mapfile -t releases < <(ls -1dt "${RELEASES_DIR}"/* 2>/dev/null || true)

count=0
for release in "${releases[@]}"; do
  count=$((count + 1))
  if (( count <= KEEP_RELEASES )); then
    continue
  fi

  # Never delete the currently active release
  if [[ -n "${CURRENT_TARGET}" && "$(readlink -f "${release}")" == "${CURRENT_TARGET}" ]]; then
    echo "Skipping active release: ${release}"
    continue
  fi

  echo "Pruning old release: ${release}"
  rm -rf "${release}"
done

echo "Pruning complete. Kept last ${KEEP_RELEASES} releases."