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

run_full_checks() {
  check_url GET "${WEB_BASE_URL}/" "200,301,302"
  check_url GET "${API_BASE_URL}/admin/login/" "200,301,302"
  run_api_checks
}

if [[ "${MODE}" == "api-only" ]]; then
  run_api_checks
else
  run_full_checks
fi

echo "Health checks completed successfully."