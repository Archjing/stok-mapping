#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/zj/workspace/stok-mapping"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"

cd "${PROJECT_ROOT}"
mkdir -p logs
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT_ROOT}/.env"
  set +a
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S %z')] manual history update started"
"${PYTHON_BIN}" -m phase0.cli update-history --config config.yaml
echo "[$(date '+%Y-%m-%d %H:%M:%S %z')] manual history update finished"
