#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"

cd "${PROJECT_ROOT}"
mkdir -p logs
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT_ROOT}/.env"
  set +a
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S %z')] daily brief pipeline started"
"${PYTHON_BIN}" -m phase0.cli daily-brief --config config.yaml
echo "[$(date '+%Y-%m-%d %H:%M:%S %z')] daily brief pipeline finished"
