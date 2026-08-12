#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=scripts/lib/project_env.sh
source "${SCRIPT_DIR}/lib/project_env.sh"

PROJECT_ROOT="$(stok_project_root)"
PYTHON_BIN="$(stok_python_bin "${PROJECT_ROOT}")"
CONFIG_PATH="${PROJECT_ROOT}/config.yaml"

cd "${PROJECT_ROOT}"
stok_ensure_logs_dir "${PROJECT_ROOT}"
stok_load_dotenv "${PROJECT_ROOT}"

# Warm the maintenance state DB schema before the real tick so older local
# SQLite files get migrated instead of crashing inside `maintain tick`.
"${PYTHON_BIN}" -m quant.cli maintain status --config "${CONFIG_PATH}" >/dev/null

exec "${PYTHON_BIN}" -m quant.cli maintain tick --config "${CONFIG_PATH}"
