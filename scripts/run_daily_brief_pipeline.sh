#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/project_env.sh
source "${SCRIPT_DIR}/lib/project_env.sh"
PROJECT_ROOT="$(stok_project_root)"
PYTHON_BIN="$(stok_python_bin "${PROJECT_ROOT}")"

cd "${PROJECT_ROOT}"
stok_ensure_logs_dir "${PROJECT_ROOT}"
stok_load_dotenv "${PROJECT_ROOT}"

echo "[$(stok_timestamp)] watchlist pipeline started"
"${PYTHON_BIN}" -m phase0.cli brief watchlist --config config.yaml
echo "[$(stok_timestamp)] watchlist pipeline finished"
