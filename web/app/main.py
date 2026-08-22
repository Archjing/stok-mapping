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
from starlette.exceptions import HTTPException as StarletteHTTPException

ROOT = Path(__file__).resolve().parents[2]  # worktree 仓库根（web/app/main.py -> web -> 根）

DEFAULT_DB = ROOT / "data" / "a_share_history.sqlite"
US_DB = ROOT / "data" / "us_market_history.sqlite"
OPTIONS_DB = ROOT / "data" / "china_options.sqlite"

# 美股已知名称（us_daily_bars 无名称表；搜索/展示用）
US_SYMBOL_NAMES: dict[str, str] = {
    "^IXIC": "纳斯达克",
    "^NYA": "纽约",
    "^VIX": "VIX恐慌",
    "^SOX": "^SOX",
    "^NDX": "纳斯达克100",
    "^TNX": "10年美债",
    "^FVX": "5年美债",
    "^IRX": "3月美债",
    "AAPL": "苹果",
    "MSFT": "微软",
    "GOOGL": "谷歌",
    "AMZN": "亚马逊",
    "META": "Meta",
    "NVDA": "英伟达",
    "AMD": "超威半导体",
    "TSM": "台积电",
    "ASML": "阿斯麦",
    "AMAT": "应用材料",
    "LRCX": "泛林",
    "INTC": "英特尔",
    "SMH": "半导体ETF",
    "KWEB": "中概互联ETF",
    "BABA": "阿里巴巴",
    "JD": "京东",
    "CNY=X": "离岸人民币",
    "HYG": "高收益债ETF",
    "LQD": "投资级债ETF",
    "GC=F": "COMEX黄金",
}


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


def _us_connect() -> sqlite3.Connection:
    if not US_DB.exists():
        raise HTTPException(status_code=503, detail=f"数据库不存在：{US_DB}")
    return sqlite3.connect(f"file:{US_DB}?mode=ro", uri=True)


def _options_connect() -> sqlite3.Connection:
    if not OPTIONS_DB.exists():
        raise HTTPException(status_code=503, detail=f"数据库不存在：{OPTIONS_DB}")
    return sqlite3.connect(f"file:{OPTIONS_DB}?mode=ro", uri=True)


def get_us_bars(
    symbol: str,
    *,
    start: str | None,
    end: str | None,
    recent: str | None,
) -> list[dict[str, Any]]:
    conn = _us_connect()
    try:
        sql = (
            "SELECT date AS d, open AS o, high AS h, low AS l, close AS c "
            "FROM us_daily_bars WHERE symbol = ? AND close IS NOT NULL"
        )
        params: list[Any] = [symbol]
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
        return _rows(conn, sql, tuple(params))
    finally:
        conn.close()


def get_cn_panic_bars(
    *,
    start: str | None,
    end: str | None,
    recent: str | None,
) -> list[dict[str, Any]]:
    """CN_PANIC_HO30 是收盘值序列（无 OHLC），合成 o=h=l=c=value 供 K 线渲染。"""
    conn = _options_connect()
    try:
        sql = (
            "SELECT trade_date AS d, value AS c "
            "FROM china_option_index_values WHERE index_id = 'CN_PANIC_HO30' AND value IS NOT NULL"
        )
        params: list[Any] = []
        if start:
            sql += " AND trade_date >= ?"
            params.append(start)
        if end:
            sql += " AND trade_date <= ?"
            params.append(end)
        if recent == "1y":
            sql += " AND trade_date >= ?"
            params.append((date.today() - timedelta(days=365)).isoformat())
        sql += " ORDER BY trade_date ASC"
        rows = _rows(conn, sql, tuple(params))
        return [{"d": r["d"], "o": r["c"], "h": r["c"], "l": r["c"], "c": r["c"]} for r in rows]
    finally:
        conn.close()


def search_us_instruments(q: str) -> list[dict[str, Any]]:
    """美股搜索：DB 中实际存在的 symbol 前缀匹配 + 内置名称表匹配。"""
    conn = _us_connect()
    try:
        like = f"%{q.upper()}%"
        rows = _rows(
            conn,
            "SELECT DISTINCT symbol FROM us_daily_bars WHERE UPPER(symbol) LIKE ? ORDER BY symbol LIMIT 30",
            (like,),
        )
    finally:
        conn.close()
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        sym = r["symbol"]
        seen.add(sym)
        out.append(
            {
                "symbol": sym,
                "name": US_SYMBOL_NAMES.get(sym, sym),
                "kind": "index" if sym.startswith("^") else "stock",
            }
        )
    for sym, name in US_SYMBOL_NAMES.items():
        if q.lower() in name.lower() and sym not in seen:
            seen.add(sym)
            out.append(
                {"symbol": sym, "name": name, "kind": "index" if sym.startswith("^") else "stock"}
            )
    return out[:30]


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
    market: str = Query(default="cn"),
) -> dict[str, Any]:
    if market == "us":
        items = get_us_bars(symbol, start=start, end=end, recent=recent)
    elif symbol == "CN_PANIC_HO30":
        items = get_cn_panic_bars(start=start, end=end, recent=recent)
    else:
        items = get_bars(symbol, start=start, end=end, adjust=adjust, recent=recent)
    if not items:
        raise HTTPException(status_code=404, detail=f"未找到 {symbol} 的行情数据")
    return {"symbol": symbol, "items": items}


@app.get("/api/market/search")
def search(
    q: str = Query(min_length=1),
    kind: str | None = Query(default=None),
    market: str = Query(default="cn"),
) -> dict[str, Any]:
    if market == "us":
        return {"items": search_us_instruments(q)}
    return {"items": search_instruments(q, kind)}


# ═══════════ 账户域（P2：复用 quant.reporting 只读，口径与 CLI 一致） ═══════════
# 数据链路与 `quant site build` / `daily-brief` 完全相同：
#   accounts = load_simulated_accounts(config) → SQLite 帧 → _meta_for_account
#   watchlist = export_premarket_watchlist(account_id=...)（复用 panel 缓存）
WATCHLIST_HEADERS = [
    "动作", "信号动作", "股票代码", "股票名称", "收盘价", "当前权重", "目标权重",
    "权重变化", "持仓天数", "动量分数", "当日排名", "信号持有天数", "成交价口径",
    "最大成交参与率", "执行风险提示", "账户说明", "观察理由",
]


def _quant() -> dict[str, Any]:
    """延迟导入 quant.*（依赖仓库根路径与全量依赖，避免 web 独立运行被拖累）。"""
    from quant.execution.accounts import load_simulated_accounts
    from quant.reporting.premarket_watchlist import (
        _cell_title,
        _display_cell,
        _watchlist_cell_class,
        export_premarket_watchlist,
    )
    from quant.reporting.quant_static_site import _meta_for_account, _read_account_frames

    return {
        "load_accounts": load_simulated_accounts,
        "export_watchlist": export_premarket_watchlist,
        "display_cell": _display_cell,
        "cell_title": _cell_title,
        "cell_class": _watchlist_cell_class,
        "meta_for_account": _meta_for_account,
        "read_frames": _read_account_frames,
    }


def _accounts_metas(q: dict[str, Any]) -> list[dict[str, Any]]:
    import yaml

    from quant.reporting.paths import slug

    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8")) or {}
    metas = []
    for account in q["load_accounts"](cfg, ROOT):
        frames = q["read_frames"](account)
        meta = q["meta_for_account"](account, frames)
        meta["slug"] = slug(str(account.account_id))
        metas.append(meta)
    return metas


@app.get("/api/accounts")
def api_accounts() -> dict[str, Any]:
    return {"accounts": _accounts_metas(_quant())}


@app.get("/api/accounts/brief")
def api_accounts_brief() -> dict[str, Any]:
    metas = _accounts_metas(_quant())
    latest_dates = sorted(m.get("latest_bill_date") for m in metas if m.get("latest_bill_date"))
    return {
        "accounts": metas,
        "account_count": len(metas),
        "ready_accounts": sum(1 for m in metas if m.get("latest_bill_date")),
        "latest_bill_date": latest_dates[-1] if latest_dates else "暂无",
    }


@app.get("/api/accounts/{account_id}")
def api_account_detail(account_id: str) -> dict[str, Any]:
    import yaml

    q = _quant()
    from quant.reporting.paths import slug

    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8")) or {}
    for account in q["load_accounts"](cfg, ROOT):
        if slug(str(account.account_id)) != account_id:
            continue
        frames = q["read_frames"](account)
        meta = q["meta_for_account"](account, frames)
        meta.update(
            {
                "slug": account_id,
                "strategy_id": str(getattr(account, "strategy_id", "") or ""),
                "simulation_start_date": str(getattr(account, "simulation_start_date", "") or ""),
                "initial_cash": getattr(account, "initial_cash", None),
                "price_mode": str(getattr(account, "price_mode", "") or ""),
                "name": str(account.name),
            }
        )
        return meta
    raise HTTPException(status_code=404, detail=f"未找到账户 {account_id}")


@app.get("/api/accounts/{account_id}/watchlist")
def api_account_watchlist(account_id: str) -> dict[str, Any]:
    q = _quant()
    try:
        result = q["export_watchlist"](config_path=ROOT / "config.yaml", account_id=account_id)
    except Exception as exc:  # noqa: BLE001 — 面板/数据缺失统一转 404
        raise HTTPException(status_code=404, detail=f"观察池生成失败：{exc}") from exc

    import pandas as pd

    watchlist = pd.read_csv(result["watchlist"], encoding="utf-8-sig")
    rows = []
    for _, row in watchlist.iterrows():
        action = str(row.get("动作", ""))
        cls = ""
        if "买" in action or "加仓" in action:
            cls = "buy"
        elif "卖" in action or "减仓" in action:
            cls = "sell"
        elif "持有" in action:
            cls = "hold"
        cells = []
        for header in WATCHLIST_HEADERS:
            if header not in watchlist.columns:
                cells.append({"value": "", "title": "", "cls": ""})
                continue
            raw = row[header]
            display = q["display_cell"](header, raw)
            cells.append(
                {"value": display, "title": q["cell_title"](header, raw, display), "cls": q["cell_class"](header)}
            )
        rows.append({"class": cls, "cells": cells})
    return {
        "account_id": account_id,
        "headers": WATCHLIST_HEADERS,
        "rows": rows,
        "overview_cards": [
            {"label": "当前策略", "value": str(result.get("strategy_display_name", "") or "")},
            {"label": "信号日期", "value": str(result.get("signal_date", "") or "")},
            {"label": "盘前检查时间", "value": str(result.get("check_time", "") or "")},
            {"label": "观察池行数", "value": str(result.get("rows", 0))},
        ],
        "account_summary_cards": result.get("account_summary_cards") or [],
    }


# 生产托管前端构建产物（web/ui/dist 存在时）
class SPAStaticFiles(StaticFiles):
    """SPA history 模式回退：静态文件未命中（如刷新 /market/cn 深链）时返回 index.html。
    注意：Starlette 1.x 对未命中路径是抛出 HTTPException(404)，而非返回 404 Response，故需捕获。
    """

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as ex:
            if ex.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


_ui_dist = ROOT / "web" / "ui" / "dist"
if _ui_dist.is_dir():
    app.mount("/", SPAStaticFiles(directory=_ui_dist, html=True), name="ui")
