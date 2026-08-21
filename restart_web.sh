#!/usr/bin/env bash
# 一键诊断 + 重启 web 服务（8010），用于排查"改了代码还是 404"
# 只影响 8010 端口进程和 worktree 的 .venv，不碰代码和数据。
set -uo pipefail
ROOT=/Users/aj/workspace/stok-mapping
WT=$ROOT/.worktrees/website-design-dev-20260816

echo "===== [1] 谁占用 8010 ====="
lsof -i :8010 || echo "(8010 当前无监听)"
echo
echo "===== [2] 所有 uvicorn / web.app 进程 ====="
ps aux | grep -E "uvicorn|web\.app" | grep -v grep || echo "(无 uvicorn 进程)"
echo
echo "===== [3] 8010 当前提供的 bundle（应是 index-Cd7oCEgF.js）====="
curl -s -m 3 http://127.0.0.1:8010/ | grep -o 'assets/index-[^"]*\.js' || echo "(8010 无响应)"
echo
echo "===== [4] 杀掉 8010 上的旧进程 ====="
lsof -ti :8010 | xargs kill -9 2>/dev/null
sleep 1
if lsof -i :8010 >/dev/null 2>&1; then echo "!! 端口仍被占用（有进程杀不掉）"; else echo "8010 已空闲"; fi
echo
echo "===== [5] 重建 worktree .venv 并后台启动 ====="
cd "$WT"
rm -rf .venv
uv sync 2>&1 | tail -3
nohup uv run uvicorn web.app.main:app --port 8010 > /tmp/web8010.log 2>&1 &
sleep 6
echo
echo "===== [6] 验证 ====="
echo -n "bundle  : "; curl -s -m 3 http://127.0.0.1:8010/ | grep -o 'assets/index-[^"]*\.js' || echo "(无响应)"
echo -n "恐慌指数: "; curl -s -m 5 "http://127.0.0.1:8010/api/market/bars/CN_PANIC_HO30?recent=1y" | head -c 120; echo
echo -n "美股纳指: "; curl -s -m 5 "http://127.0.0.1:8010/api/market/bars/%5EIXIC?recent=1y&market=us" | head -c 120; echo
echo
echo "===== 服务日志尾 ====="
tail -8 /tmp/web8010.log
echo
echo "===== 完成：把上面全部输出发我 ====="
