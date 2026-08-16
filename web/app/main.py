"""stok-mapping 网站后端 — FastAPI 薄 API（P0 骨架）。

只读端点，直查本地 SQLite（`data/a_share_history.sqlite`），不放业务逻辑；
图表计算（K线聚合/归一化）仍在前端 `web/ui/src/lib`。
认证（计划书 D6）默认只作用于写端点，本期只读端点不设 token。
"""
from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[2]  # worktree 仓库根（web/app/main.py -> web -> 根）

DEFAULT_DB = ROOT / "data" / "a_share_history.sqlite"


def db_path() -> Path:
    """数据源路径：DATA_SQLITE 环境变量 > config.yaml local_history.path > 默认。"""
    env = os.environ.get("DATA_SQLITE")
    if env:
        return Path(env)
    try:
        import yaml

        cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8")) or {}
        p = cfg.get("local_history", {}).get("path")
        if p:
            path = Path(p)
            return path if path.is_absolute() else ROOT / path
    except Exception:
        pass
    return DEFAULT_DB


def _connect() -> sqlite3.Connection:
    path = db_path()
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"数据库不存在：{path}")
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _dedupe_by_date(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """指数表 D/daily 两种频率按日期去重（区间不重叠，稳妥起见保留首条）。"""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        if r["d"] in seen:
            continue
        seen.add(r["d"])
        out.append(r)
    return out


def list_indices() -> list[dict[str, Any]]:
    conn = _connect()
    try:
        rows = _rows(
            conn,
            """SELECT i.symbol, i.name, MIN(b.date) AS start, MAX(b.date) AS end, COUNT(*) AS count
                 FROM market_indices i
                 JOIN market_index_bars b ON b.symbol = i.symbol
                WHERE b.open IS NOT NULL AND b.close IS NOT NULL
                GROUP BY i.symbol, i.name
                ORDER BY i.symbol""",
        )
        return [{**r, "kind": "index"} for r in rows]
    finally:
        conn.close()


def get_bars(
    symbol: str,
    *,
    start: str | None,
    end: str | None,
    adjust: str,
    recent: str | None,
) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        is_index = bool(_rows(conn, "SELECT 1 FROM market_index_bars WHERE symbol = ? LIMIT 1", (symbol,)))
        if is_index:
            sql = (
                "SELECT date AS d, open AS o, high AS h, low AS l, close AS c "
                "FROM market_index_bars WHERE symbol = ? AND open IS NOT NULL AND close IS NOT NULL"
            )
            params: list[Any] = [symbol]
        else:
            adj = adjust if adjust in ("qfq", "bfq") else "qfq"
            sql = (
                "SELECT date AS d, open AS o, high AS h, low AS l, close AS c "
                "FROM market_daily_bars WHERE symbol = ? AND adjust_type = ? AND close IS NOT NULL"
            )
            params = [symbol, adj]

        if start:
            sql += " AND date >= ?"
            params.append(start)
        if end:
            sql += " AND date <= ?"
            params.append(end)
        if recent == "1y":
            sql += " AND date >= ?"
            params.append((date.today() - timedelta(days=365)).isoformat())
        sql += " ORDER BY date ASC"

        rows = _rows(conn, sql, tuple(params))
        return _dedupe_by_date(rows) if is_index else rows
    finally:
        conn.close()


def search_instruments(q: str, kind: str | None) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        like = f"%{q}%"
        out: list[dict[str, Any]] = []
        if kind in (None, "index"):
            rows = _rows(
                conn,
                "SELECT symbol, name FROM market_indices WHERE symbol LIKE ? OR name LIKE ? ORDER BY symbol LIMIT 20",
                (like, like),
            )
            out += [{"symbol": r["symbol"], "name": r["name"], "kind": "index"} for r in rows]
        if kind in (None, "stock"):
            rows = _rows(
                conn,
                "SELECT symbol, name FROM market_stocks "
                "WHERE (symbol LIKE ? OR name LIKE ?) AND (symbol LIKE 'SH.%' OR symbol LIKE 'SZ.%') "
                "ORDER BY symbol LIMIT 20",
                (like, like),
            )
            out += [{"symbol": r["symbol"], "name": r["name"], "kind": "stock"} for r in rows]
        return out
    finally:
        conn.close()


app = FastAPI(title="stok-mapping web", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "db": str(db_path())}


@app.get("/api/market/instruments")
def instruments() -> dict[str, Any]:
    return {"items": list_indices()}


@app.get("/api/market/bars/{symbol}")
def bars(
    symbol: str,
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    adjust: str = Query(default="qfq"),
    recent: str | None = Query(default=None),
) -> dict[str, Any]:
    items = get_bars(symbol, start=start, end=end, adjust=adjust, recent=recent)
    if not items:
        raise HTTPException(status_code=404, detail=f"未找到 {symbol} 的行情数据")
    return {"symbol": symbol, "items": items}


@app.get("/api/market/search")
def search(q: str = Query(min_length=1), kind: str | None = Query(default=None)) -> dict[str, Any]:
    return {"items": search_instruments(q, kind)}


# 生产托管前端构建产物（web/ui/dist 存在时）
_ui_dist = ROOT / "web" / "ui" / "dist"
if _ui_dist.is_dir():
    app.mount("/", StaticFiles(directory=_ui_dist, html=True), name="ui")
