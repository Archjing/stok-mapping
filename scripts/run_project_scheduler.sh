#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
STATE_DIR="${PROJECT_ROOT}/logs/scheduler"
LOCK_DIR="${STATE_DIR}/locks"
CONFIG_PATH="${PROJECT_ROOT}/config.yaml"

cd "${PROJECT_ROOT}"
mkdir -p "${STATE_DIR}" "${LOCK_DIR}" logs

if [[ -f "${PROJECT_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT_ROOT}/.env"
  set +a
fi

now_time="$(date '+%H:%M')"
today="$(date '+%Y-%m-%d')"
weekday="$(date '+%u')"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S %z')] $*"
}

should_run_weekdays() {
  [[ "${weekday}" -ge 1 && "${weekday}" -le 5 ]]
}

should_run_monday() {
  [[ "${weekday}" == "1" ]]
}

run_once_per_day() {
  local task_name="$1"
  local run_time="$2"
  local log_file="$3"
  shift 3

  local stamp_file="${STATE_DIR}/${task_name}.last"
  local lock_dir="${LOCK_DIR}/${task_name}.lock"
  local last_run=""
  last_run="$(cat "${stamp_file}" 2>/dev/null || true)"

  if [[ "${now_time}" != "${run_time}" || "${last_run}" == "${today}" ]]; then
    return 0
  fi

  if ! mkdir "${lock_dir}" 2>/dev/null; then
    log "skip ${task_name}: already running" >> "${log_file}"
    return 0
  fi

  log "start ${task_name}" >> "${log_file}"
  if "$@" >> "${log_file}" 2>&1; then
    echo "${today}" > "${stamp_file}"
    log "finish ${task_name}" >> "${log_file}"
  else
    log "fail ${task_name}" >> "${log_file}"
    rm -rf "${lock_dir}"
    return 0
  fi

  rm -rf "${lock_dir}"
}

run_daily_brief() {
  should_run_weekdays || return 0
  run_once_per_day \
    "daily_brief" \
    "${DAILY_BRIEF_TIME:-07:20}" \
    "${PROJECT_ROOT}/logs/daily_brief_pipeline.log" \
    "${PYTHON_BIN}" -m phase0.cli daily-brief --config "${CONFIG_PATH}"
}

run_hk_market_update() {
  should_run_weekdays || return 0
  run_once_per_day \
    "hk_market_history" \
    "${HK_MARKET_HISTORY_TIME:-16:20}" \
    "${PROJECT_ROOT}/logs/hk_market_history_update.log" \
    "${PYTHON_BIN}" -m phase0.cli update-hk-market-history --config "${CONFIG_PATH}"
}

run_a_share_update() {
  should_run_weekdays || return 0
  run_once_per_day \
    "a_share_history" \
    "${A_SHARE_HISTORY_TIME:-16:30}" \
    "${PROJECT_ROOT}/logs/manual_history_update.log" \
    "${PYTHON_BIN}" -m phase0.cli update-history --config "${CONFIG_PATH}"
}

run_us_market_update() {
  should_run_weekdays || return 0
  run_once_per_day \
    "us_market_history" \
    "${US_MARKET_HISTORY_TIME:-17:10}" \
    "${PROJECT_ROOT}/logs/us_market_history_update.log" \
    "${PYTHON_BIN}" -m phase0.cli update-us-market-history --config "${CONFIG_PATH}"
}

run_financial_update() {
  should_run_monday || return 0
  run_once_per_day \
    "financial_factors" \
    "${FINANCIAL_FACTORS_TIME:-03:30}" \
    "${PROJECT_ROOT}/logs/financial_factors_update.log" \
    "${PYTHON_BIN}" -m phase0.cli update-financials --config "${CONFIG_PATH}"
}

run_financial_update || true
run_daily_brief || true
run_hk_market_update || true
run_a_share_update || true
run_us_market_update || true
