#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CRON_START="# stok-mapping project scheduler start"
CRON_END="# stok-mapping project scheduler end"
LEGACY_CRON_START="# stok-mapping manual history update start"
LEGACY_CRON_END="# stok-mapping manual history update end"
SCHEDULER_CRON_LINE="* * * * * bash ${PROJECT_ROOT}/scripts/run_project_scheduler.sh >> ${PROJECT_ROOT}/logs/project_scheduler.log 2>&1"

mkdir -p "${PROJECT_ROOT}/logs"

tmp_file="$(mktemp)"
trap 'rm -f "${tmp_file}"' EXIT

crontab -l 2>/dev/null \
  | sed "/${CRON_START}/,/${CRON_END}/d" \
  | sed "/${LEGACY_CRON_START}/,/${LEGACY_CRON_END}/d" > "${tmp_file}" || true
{
  echo "${CRON_START}"
  echo "${SCHEDULER_CRON_LINE}"
  echo "${CRON_END}"
} >> "${tmp_file}"

crontab "${tmp_file}"
crontab -l | sed -n "/${CRON_START}/,/${CRON_END}/p"
