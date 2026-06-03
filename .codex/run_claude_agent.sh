#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"

cd "${PROJECT_ROOT}"
exec "${PYTHON_BIN}" .codex/claude_agent.py \
  --config .codex/claude_analyst_agent_config.json \
  "$@"
