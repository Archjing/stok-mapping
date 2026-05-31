#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CRON_START="# stok-mapping manual history update start"
CRON_END="# stok-mapping manual history update end"
DAILY_CRON_LINE="30 16 * * 1-5 bash ${PROJECT_ROOT}/scripts/update_manual_history_daily.sh >> ${PROJECT_ROOT}/logs/manual_history_update.log 2>&1"
WEEKLY_FINANCIAL_CRON_LINE="30 3 * * 1 bash ${PROJECT_ROOT}/scripts/update_financial_factors_weekly.sh >> ${PROJECT_ROOT}/logs/financial_factors_update.log 2>&1"

mkdir -p "${PROJECT_ROOT}/logs"

tmp_file="$(mktemp)"
trap 'rm -f "${tmp_file}"' EXIT

crontab -l 2>/dev/null | sed "/${CRON_START}/,/${CRON_END}/d" > "${tmp_file}" || true
{
  echo "${CRON_START}"
  echo "${DAILY_CRON_LINE}"
  echo "${WEEKLY_FINANCIAL_CRON_LINE}"
  echo "${CRON_END}"
} >> "${tmp_file}"

crontab "${tmp_file}"
crontab -l | sed -n "/${CRON_START}/,/${CRON_END}/p"
