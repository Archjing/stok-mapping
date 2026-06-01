#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION_NAME="${CLOE_RESEARCH_ACPX_SESSION:-${CLOE_ACPX_SESSION:-${OPENCLAW_ACPX_SESSION:-cloe-research}}}"
TIMEOUT_SECONDS="${CLOE_RESEARCH_ACPX_TIMEOUT:-${CLOE_ACPX_TIMEOUT:-${OPENCLAW_ACPX_TIMEOUT:-600}}}"
OUTPUT_FORMAT="${CLOE_RESEARCH_ACPX_FORMAT:-${CLOE_ACPX_FORMAT:-${OPENCLAW_ACPX_FORMAT:-text}}}"

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

acpx --cwd "$ROOT_DIR" openclaw sessions ensure --name "$SESSION_NAME" >/dev/null
acpx --cwd "$ROOT_DIR" \
  --format "$OUTPUT_FORMAT" \
  --timeout "$TIMEOUT_SECONDS" \
  openclaw -s "$SESSION_NAME" "$TASK"
