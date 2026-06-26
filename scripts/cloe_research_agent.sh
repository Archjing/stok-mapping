#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${ROOT_DIR}/scripts/lib/acpx_agent.sh"

SESSION_NAME="$(stok_acpx_env_value RESEARCH SESSION "cloe-research")"
TIMEOUT_SECONDS="$(stok_acpx_env_value RESEARCH TIMEOUT "600")"
OUTPUT_FORMAT="$(stok_acpx_env_value RESEARCH FORMAT "text")"

if [[ $# -eq 0 ]]; then
  cat <<USAGE
Usage:
  scripts/cloe_research_agent.sh "任务内容"

Environment:
  CLOE_RESEARCH_ACPX_SESSION      默认 cloe-research
  CLOE_RESEARCH_ACPX_TIMEOUT      默认 600 秒
  CLOE_RESEARCH_ACPX_FORMAT       默认 text，可设为 json

Fallback:
  CLOE_ACPX_SESSION / CLOE_ACPX_TIMEOUT / CLOE_ACPX_FORMAT
  OPENCLAW_ACPX_SESSION / OPENCLAW_ACPX_TIMEOUT / OPENCLAW_ACPX_FORMAT

This script first ensures the acpx Cloe session exists, then sends the task.
USAGE
  exit 2
fi

TASK="$*"

stok_acpx_run_openclaw_task "$ROOT_DIR" "$SESSION_NAME" "$TIMEOUT_SECONDS" "$OUTPUT_FORMAT" "" "$TASK"
