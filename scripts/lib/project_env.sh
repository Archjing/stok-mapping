#!/usr/bin/env bash

stok_project_root() {
  local source_file="${BASH_SOURCE[0]}"
  local script_dir
  script_dir="$(cd "$(dirname "${source_file}")" && pwd)"
  cd "${script_dir}/../.." && pwd
}

stok_python_bin() {
  local root="$1"
  printf '%s\n' "${root}/.venv/bin/python"
}

stok_log_dir() {
  local root="$1"
  printf '%s\n' "${root}/logs"
}

stok_ensure_logs_dir() {
  local root="$1"
  mkdir -p "$(stok_log_dir "${root}")"
}

stok_load_dotenv() {
  local root="$1"
  if [[ -f "${root}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${root}/.env"
    set +a
  fi
}

stok_timestamp() {
  date '+%Y-%m-%d %H:%M:%S %z'
}
