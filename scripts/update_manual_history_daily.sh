#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/zj/workspace/stok-mapping"
PYTHON_BIN="/home/zj/workspace/stok-quant/.venv/bin/python"

cd "${PROJECT_ROOT}"
mkdir -p logs

echo "[$(date '+%Y-%m-%d %H:%M:%S %z')] manual history update started"
"${PYTHON_BIN}" -m phase0.cli update-history --config config.yaml
echo "[$(date '+%Y-%m-%d %H:%M:%S %z')] manual history update finished"
