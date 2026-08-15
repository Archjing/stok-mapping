#!/usr/bin/env bash
# 一键发布 A股指数走势单文件页到远端站点 share.spidermanread.men。
#
# 流程：npm run extract（重新抽取 sqlite 数据）→ npm run build（单文件 dist/index.html）
#       → rsync 到远端 /var/www/share/index-chart/index.html
#
# 用法：./scripts/deploy.sh
# 环境变量覆盖：QUANT_SITE_SYNC_REMOTE（远端 user@host）、QUANT_INDEX_CHART_REMOTE_DIR（远端目录）
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${APP_DIR}/../.." && pwd)"
cd "${APP_DIR}"

# ---- 1. 数据 + 构建 ----
npm run extract
npm run build

# ---- 2. 远端目标 ----
REMOTE="${QUANT_SITE_SYNC_REMOTE:-linuxuser@108.61.182.91}"
REMOTE_DIR="${QUANT_INDEX_CHART_REMOTE_DIR:-/var/www/share/index-chart}"

# ---- 3. 读取 .env 中的同步密码（不打印）----
PASSWORD="$(grep -E '^QUANT_SITE_SYNC_PASSWORD=' "${REPO_ROOT}/.env" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)"
if [ -z "${PASSWORD:-}" ]; then
  echo "[deploy] 缺少 QUANT_SITE_SYNC_PASSWORD（${REPO_ROOT}/.env）" >&2
  exit 1
fi
export QUANT_SITE_SYNC_PASSWORD="${PASSWORD}"

ASKPASS="$(mktemp)"
trap 'rm -f "${ASKPASS}"' EXIT
printf '#!/bin/sh\nprintf "%%s\\n" "$QUANT_SITE_SYNC_PASSWORD"\n' > "${ASKPASS}"
chmod 700 "${ASKPASS}"

SSH_OPTS=(
  -o BatchMode=no
  -o PasswordAuthentication=yes
  -o PreferredAuthentications=password,keyboard-interactive
  -o NumberOfPasswordPrompts=1
  -o StrictHostKeyChecking=accept-new
)

echo "==> 同步 dist/index.html -> ${REMOTE}:${REMOTE_DIR}/index.html"
SSH_ASKPASS="${ASKPASS}" SSH_ASKPASS_REQUIRE=force \
  rsync -az \
  --rsync-path "mkdir -p ${REMOTE_DIR} && rsync" \
  -e "ssh ${SSH_OPTS[*]}" \
  dist/index.html "${REMOTE}:${REMOTE_DIR}/index.html"

echo "==> 完成：https://share.spidermanread.men/index-chart/"
