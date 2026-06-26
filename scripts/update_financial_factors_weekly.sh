#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/project_env.sh
source "${SCRIPT_DIR}/lib/project_env.sh"
PROJECT_ROOT="$(stok_project_root)"
PYTHON_BIN="$(stok_python_bin "${PROJECT_ROOT}")"
LOG_DIR="$(stok_log_dir "${PROJECT_ROOT}")"
LOCK_FILE="${LOG_DIR}/financial_factors_weekly.lock"
UPDATE_CMD=("${PYTHON_BIN}" -m phase0.cli update-financials --config config.yaml)

cd "${PROJECT_ROOT}"
stok_ensure_logs_dir "${PROJECT_ROOT}"

exec 9>"${LOCK_FILE}"
if command -v flock >/dev/null 2>&1; then
  if ! flock -n 9; then
    echo "[$(stok_timestamp)] financial factor update skipped: another run is active"
    exit 0
  fi
fi

echo "[$(stok_timestamp)] financial factor update started"
if command -v timeout >/dev/null 2>&1; then
  UPDATE_CMD=(timeout 120m "${UPDATE_CMD[@]}")
fi
if command -v ionice >/dev/null 2>&1; then
  ionice -c2 -n7 nice -n 10 "${UPDATE_CMD[@]}"
else
  nice -n 10 "${UPDATE_CMD[@]}"
fi
echo "[$(stok_timestamp)] financial factor update finished"
