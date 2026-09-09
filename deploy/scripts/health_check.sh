#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-full}"
WEB_BASE_URL="${WEB_BASE_URL:-http://127.0.0.1}"
API_BASE_URL="${API_BASE_URL:-http://127.0.0.1}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-12}"

check_url() {
  local method="$1"
  local url="$2"
  local expected_csv="$3"
  local data="${4:-}"

  local status
  if [[ -n "${data}" ]]; then
    status="$(curl -sS -o /dev/null -w "%{http_code}" --max-time "${TIMEOUT_SECONDS}" -X "${method}" -H "Content-Type: application/json" -d "${data}" "${url}" || true)"
  else
    status="$(curl -sS -o /dev/null -w "%{http_code}" --max-time "${TIMEOUT_SECONDS}" -X "${method}" "${url}" || true)"
  fi

  IFS=',' read -r -a expected_codes <<< "${expected_csv}"
  for code in "${expected_codes[@]}"; do
    if [[ "${status}" == "${code}" ]]; then
      echo "[PASS] ${method} ${url} -> ${status}"
      return 0
    fi
  done

  echo "[FAIL] ${method} ${url} -> ${status} (expected: ${expected_csv})"
  return 1
}

run_api_checks() {
  check_url GET "${API_BASE_URL}/health/server" "200"
  check_url GET "${API_BASE_URL}/health/db" "200"
  check_url GET "${API_BASE_URL}/health/cache" "200"
  check_url GET "${API_BASE_URL}/health/payment" "200"
  check_url GET "${API_BASE_URL}/api/v1/catalog/products/" "200"
  check_url POST "${API_BASE_URL}/api/v1/payments/initiate/" "400,401,403,405" "{}"
}

# The SSI bootstrap is invisible when it breaks: nginx drops the include
# silently (ssi_silent_errors on) and the SPA falls back to fetching the APIs,
# so the site looks perfectly healthy while LCP quietly regresses by seconds --
# the hero preload disappears and /features/public-settings/ lands back on the
# critical path. This asserts the fragment actually made it into the HTML.
#
# Non-fatal by design: a missing bootstrap is a performance regression, not an
# outage, and failing a deploy over it would be worse than serving the slower
# page. It prints loudly instead.
check_ssi_bootstrap() {
  local body
  body="$(curl -sS -L --max-time "${TIMEOUT_SECONDS}" "${WEB_BASE_URL}/" || true)"

  if grep -q '__BOOT__' <<< "${body}"; then
    echo "[PASS] SSI bootstrap present in ${WEB_BASE_URL}/"
    return 0
  fi

  echo "[WARN] SSI bootstrap MISSING from ${WEB_BASE_URL}/ -- window.__BOOT__ not found."
  if grep -q 'include virtual' <<< "${body}"; then
    echo "[WARN]   The include shipped unparsed: nginx served this HTML without 'ssi on'."
    echo "[WARN]   Check the 'location /' block in deploy/nginx/nginx.prod.conf is the"
    echo "[WARN]   config actually serving :443 (frontend.conf, baked into the frontend"
    echo "[WARN]   image, has no ssi directive)."
  else
    echo "[WARN]   The include was parsed but the fragment was empty: the subrequest to"
    echo "[WARN]   /api/v1/banners/bootstrap-fragment/ failed, timed out (2s) or returned"
    echo "[WARN]   nothing. Check the backend and Redis."
  fi
  return 0
}

run_full_checks() {
  check_url GET "${WEB_BASE_URL}/" "200,301,302"
  check_url GET "${API_BASE_URL}/admin/login/" "200,301,302"
  check_url GET "${API_BASE_URL}/api/v1/banners/bootstrap-fragment/?uri=/" "200"
  check_ssi_bootstrap
  run_api_checks
}

if [[ "${MODE}" == "api-only" ]]; then
  run_api_checks
else
  run_full_checks
fi

echo "Health checks completed successfully."