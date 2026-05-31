#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
LOCK_FILE="${PROJECT_ROOT}/logs/financial_factors_weekly.lock"
UPDATE_CMD=("${PYTHON_BIN}" -m phase0.cli update-financials --config config.yaml)

cd "${PROJECT_ROOT}"
mkdir -p logs

exec 9>"${LOCK_FILE}"
if command -v flock >/dev/null 2>&1; then
  if ! flock -n 9; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S %z')] financial factor update skipped: another run is active"
    exit 0
  fi
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S %z')] financial factor update started"
if command -v timeout >/dev/null 2>&1; then
  UPDATE_CMD=(timeout 120m "${UPDATE_CMD[@]}")
fi
if command -v ionice >/dev/null 2>&1; then
  ionice -c2 -n7 nice -n 10 "${UPDATE_CMD[@]}"
else
  nice -n 10 "${UPDATE_CMD[@]}"
fi
echo "[$(date '+%Y-%m-%d %H:%M:%S %z')] financial factor update finished"
