#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${ROOT_DIR}/scripts/lib/acpx_agent.sh"

SESSION_NAME="$(stok_acpx_env_value PREMARKET SESSION "cloe-premarket")"
TIMEOUT_SECONDS="$(stok_acpx_env_value PREMARKET TIMEOUT "600")"
TTL_SECONDS="$(stok_acpx_env_value PREMARKET TTL "1800")"
OUTPUT_FORMAT="$(stok_acpx_env_value PREMARKET FORMAT "text")"

if [[ $# -eq 0 ]]; then
  cat <<USAGE
Usage:
  scripts/cloe_premarket_agent.sh "任务内容"

Environment:
  CLOE_PREMARKET_ACPX_SESSION      默认 cloe-premarket
  CLOE_PREMARKET_ACPX_TIMEOUT      默认 600 秒
  CLOE_PREMARKET_ACPX_TTL          默认 1800 秒（会话空闲存活）
  CLOE_PREMARKET_ACPX_FORMAT       默认 text，可设为 json

Fallback:
  CLOE_ACPX_SESSION / CLOE_ACPX_TIMEOUT / CLOE_ACPX_TTL / CLOE_ACPX_FORMAT
  OPENCLAW_ACPX_SESSION / OPENCLAW_ACPX_TIMEOUT / OPENCLAW_ACPX_TTL / OPENCLAW_ACPX_FORMAT

This script first ensures the acpx Cloe session exists, then sends the task.
USAGE
  exit 2
fi

TASK="$*"

stok_acpx_run_openclaw_task "$ROOT_DIR" "$SESSION_NAME" "$TIMEOUT_SECONDS" "$OUTPUT_FORMAT" "$TTL_SECONDS" "$TASK"
