#!/usr/bin/env bash
# 发布 web 控制台到 https://share.spidermanread.men/quant-dashboard/
#
# 架构（已核实 2026-08-22）：
#   远端 /quant-dashboard/ 是 nginx proxy_pass -> frpc TCP 隧道 -> 本机 8010 (uvicorn + web/ui/dist)
#   —— 动态反代，非静态托管。因此"发布"= 构建 dist + 确保 8010 运行，远端实时跟随。
# 注意：nginx 配置见远端 /etc/nginx/conf.d/share.spidermanread.men.conf（location /quant-dashboard/）。
set -uo pipefail
ROOT=/Users/aj/workspace/stok-mapping
UI=$ROOT/web/ui
URL_BASE="https://share.spidermanread.men/quant-dashboard"

echo "===== [1] 构建 dist ====="
cd "$UI" || exit 1
npm run build 2>&1 | tail -4 || { echo "!! 构建失败"; exit 1; }

echo
echo "===== [2] 确保本机 8010 运行 ====="
if curl -s -m 2 http://127.0.0.1:8010/health >/dev/null 2>&1; then
  echo "8010 已在运行（保持，无需重启；dist 由 StaticFiles 实时读取）"
else
  echo "8010 未运行，后台启动……"
  cd "$ROOT"
  nohup .venv/bin/uvicorn web.app.main:app --port 8010 --host 127.0.0.1 > /tmp/web8010.log 2>&1 &
  sleep 3
fi
curl -s -m 3 http://127.0.0.1:8010/health && echo " <- 本机 OK"

echo
echo "===== [3] 验证远端（frpc 隧道）====="
BUNDLE=$(curl -s -m 10 "$URL_BASE/" | grep -o 'index-[^"]*\.js' | head -1)
LOCAL=$(ls "$UI/dist/assets/" | grep '\.js$' | head -1)
echo "远端 bundle: ${BUNDLE:-（无响应）}"
echo "本地 bundle: $LOCAL"
if [ -n "$BUNDLE" ] && [ "$BUNDLE" = "$LOCAL" ]; then
  echo "✓ 远端已与最新构建一致"
elif [ -n "$BUNDLE" ]; then
  echo "⚠ 远端与本地不一致——检查 frpc 隧道是否在跑、本机 8010 是否最新"
else
  echo "⚠ 远端无响应——检查 frpc / nginx"
fi

echo
echo "===== [4] 完成 ====="
echo "$URL_BASE/"
