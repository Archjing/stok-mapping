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
CONFIG_PATH = ROOT / "config.yaml"
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
    from quant.config import load_config
    from quant.reporting.paths import slug

    cfg = load_config(CONFIG_PATH)
    metas = []
    for account in q["load_accounts"](cfg, ROOT):
        frames = q["read_frames"](account)
        meta = q["meta_for_account"](account, frames)
        meta["slug"] = slug(str(account.account_id))
        meta["strategy_id"] = str(getattr(account, "strategy_id", "") or "")
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
    from quant.config import load_config

    q = _quant()
    from quant.reporting.paths import slug

    cfg = load_config(CONFIG_PATH)
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
    from quant.config import load_config

    cfg = load_config(CONFIG_PATH)
    account = next(
        (a for a in q["load_accounts"](cfg, ROOT) if str(a.account_id) == account_id or slug_of(a) == account_id),
        None,
    )
    # 单 ETF 日内账户：观察池 = 市场快照 + 研究上下文 + 美股新闻（site build 同源）
    if account is not None and str(getattr(account, "execution_model", "")) == "single_etf_intraday":
        from quant.reporting.semiconductor_timing_watchlist import (
            _load_market_snapshot,
            _load_research_market_context,
            _load_us_market_news,
        )

        snapshot, market_error = _load_market_snapshot(ROOT, cfg)
        research, research_error = _load_research_market_context(ROOT, cfg)
        news, ingested_at, news_error = _load_us_market_news(ROOT, cfg)
        return {
            "account_id": account_id,
            "kind": "market_snapshot",
            "snapshot": snapshot,
            "market_error": market_error,
            "research_rows": research,
            "research_error": research_error,
            "news": news,
            "news_ingested_at": ingested_at,
            "news_error": news_error,
        }
    try:
        result = q["export_watchlist"](config_path=CONFIG_PATH, account_id=account_id)
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
        "kind": "stock_watchlist",
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


def slug_of(account: Any) -> str:
    from quant.reporting.paths import slug

    return slug(str(getattr(account, "account_id", "")))


def _account_by_slug(account_id: str) -> Any | None:
    from quant.config import load_config

    q = _quant()
    cfg = load_config(CONFIG_PATH)
    for account in q["load_accounts"](cfg, ROOT):
        if str(getattr(account, "account_id", "")) == account_id or slug_of(account) == account_id:
            return account
    return None


def _bill_tables(account: Any, frames: dict[str, Any]) -> dict[str, Any]:
    """最新账单日账单：账户总览 / 每日资产 / 交易明细 / 持仓明细（列与格式化同 account_bill.py）。"""
    import pandas as pd

    from quant.reporting.account_bill import format_money, format_num, format_pct

    assets, trades, positions = frames["assets"], frames["trades"], frames["positions"]
    if assets.empty:
        return {"bill_date": "", "tables": []}
    bill_date = str(assets.iloc[0]["brief_date"])
    day_assets = assets[assets["brief_date"] == bill_date] if "brief_date" in assets.columns else assets
    day_trades = trades[trades["brief_date"] == bill_date] if not trades.empty and "brief_date" in trades.columns else trades
    day_positions = (
        positions[positions["brief_date"] == bill_date] if not positions.empty and "brief_date" in positions.columns else positions
    )

    money_cols = {"total_asset", "stock_asset", "cash_asset", "daily_pnl", "estimated_trade_amount", "price", "amount", "cost", "close", "market_value", "initial_cash"}
    pct_cols = {"daily_return", "target_exposure", "target_weight", "weight_before", "weight_after", "weight_change", "max_participation_rate"}
    num_cols = {"shares", "lots", "raw_shares", "estimated_volume", "lot_size", "unfilled_orders"}

    def fmt(frame: Any, cols: list[tuple[str, str]]) -> list[dict[str, str]]:
        out = []
        for _, row in frame.iterrows():
            item = {}
            for key, label in cols:
                if key not in frame.columns:
                    item[key] = ""
                    continue
                value = row[key]
                if key in money_cols:
                    item[key] = format_money(value)
                elif key in pct_cols:
                    item[key] = format_pct(value)
                elif key in num_cols:
                    item[key] = format_num(value, 2)
                else:
                    item[key] = "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)
            out.append(item)
        return out

    account_summary = [["账户 ID", str(getattr(account, "account_id", ""))], ["账户名称", str(getattr(account, "name", ""))]]
    if not assets.empty and "initial_cash" in assets.columns:
        account_summary.append(["初始资产", format_money(assets.iloc[0].get("initial_cash"))])
    tables = [
        {"title": "账户总览", "columns": [("key", "项目"), ("value", "值")], "rows": [{"key": k, "value": v} for k, v in account_summary]},
        {
            "title": "每日资产",
            "columns": [
                ("brief_date", "账户日期"), ("total_asset", "总资产"), ("stock_asset", "股票资产"),
                ("cash_asset", "现金资产"), ("daily_pnl", "收益额"), ("daily_return", "收益率"),
                ("target_exposure", "实际股票暴露"), ("estimated_trade_amount", "成交金额"),
            ],
            "rows": fmt(day_assets, [("brief_date", "账户日期"), ("total_asset", "总资产"), ("stock_asset", "股票资产"), ("cash_asset", "现金资产"), ("daily_pnl", "收益额"), ("daily_return", "收益率"), ("target_exposure", "实际股票暴露"), ("estimated_trade_amount", "成交金额")]),
        },
        {
            "title": "交易明细",
            "columns": [
                ("symbol", "股票代码"), ("name", "股票名称"), ("side", "方向"), ("signal_date", "信号日期"),
                ("trade_time", "交易时间"), ("price", "价格"), ("amount", "金额"), ("cost", "交易成本"),
                ("shares", "股数"), ("lots", "手数"), ("trade_status", "成交状态"),
            ],
            "rows": fmt(day_trades, [("symbol", "股票代码"), ("name", "股票名称"), ("side", "方向"), ("signal_date", "信号日期"), ("trade_time", "交易时间"), ("price", "价格"), ("amount", "金额"), ("cost", "交易成本"), ("shares", "股数"), ("lots", "手数"), ("trade_status", "成交状态")]),
        },
        {
            "title": "持仓明细",
            "columns": [
                ("symbol", "股票代码"), ("name", "股票名称"), ("close", "收盘价"), ("target_weight", "权重"),
                ("market_value", "市值"), ("shares", "股数"), ("lots", "手数"),
            ],
            "rows": fmt(day_positions, [("symbol", "股票代码"), ("name", "股票名称"), ("close", "收盘价"), ("target_weight", "权重"), ("market_value", "市值"), ("shares", "股数"), ("lots", "手数")]),
        },
    ]
    return {"bill_date": bill_date, "tables": tables}


@app.get("/api/accounts/{account_id}/bill")
def api_account_bill(account_id: str) -> dict[str, Any]:
    account = _account_by_slug(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"未找到账户 {account_id}")
    frames = _quant()["read_frames"](account)
    return {"account_id": account_id, "name": str(account.name), **_bill_tables(account, frames)}


@app.get("/api/accounts/{account_id}/ledger")
def api_account_ledger(account_id: str) -> dict[str, Any]:
    account = _account_by_slug(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"未找到账户 {account_id}")
    q = _quant()
    frames = q["read_frames"](account)
    import pandas as pd

    from quant.reporting.account_bill import format_money, format_num, format_pct

    money_cols = {"total_asset", "stock_asset", "cash_asset", "daily_pnl", "estimated_trade_amount", "price", "amount", "cost", "close", "market_value"}
    pct_cols = {"daily_return", "target_exposure", "target_weight", "weight_before", "weight_after", "weight_change"}
    num_cols = {"shares", "lots", "estimated_volume", "unfilled_orders", "requested_shares", "filled_shares"}

    def rows_for(frame: Any, cols: list[tuple[str, str]]) -> list[dict[str, str]]:
        out = []
        for _, row in frame.iterrows():
            item = {}
            for key, _label in cols:
                if key not in frame.columns:
                    item[key] = ""
                    continue
                value = row[key]
                if key in money_cols:
                    item[key] = format_money(value)
                elif key in pct_cols:
                    item[key] = format_pct(value)
                elif key in num_cols:
                    item[key] = format_num(value, 2)
                else:
                    item[key] = "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)
            out.append(item)
        return out

    assets = frames["assets"]
    trades = frames["trades"]
    positions = frames["positions"]
    order_events = frames["order_events"]
    recent_dates = sorted({str(v)[:10] for frame in (positions, order_events) for v in frame["brief_date"].dropna().astype(str)})[-3:] if not positions.empty else []
    recent_positions = positions[positions["brief_date"].astype(str).str[:10].isin(recent_dates)] if not positions.empty else positions
    recent_events = order_events[order_events["brief_date"].astype(str).str[:10].isin(recent_dates)] if not order_events.empty else order_events

    sections = [
        {
            "title": "每日资产（全部账单日）",
            "columns": [
                ("brief_date", "账单日"), ("total_asset", "总资产"), ("stock_asset", "股票资产"), ("cash_asset", "现金资产"),
                ("daily_pnl", "当日收益"), ("daily_return", "当日收益率"), ("target_exposure", "仓位"),
                ("estimated_trade_amount", "成交金额"), ("unfilled_orders", "未成交数"), ("block_reason_counts", "拦截原因"),
            ],
            "rows": rows_for(assets, [("brief_date", "账单日"), ("total_asset", "总资产"), ("stock_asset", "股票资产"), ("cash_asset", "现金资产"), ("daily_pnl", "当日收益"), ("daily_return", "当日收益率"), ("target_exposure", "仓位"), ("estimated_trade_amount", "成交金额"), ("unfilled_orders", "未成交数"), ("block_reason_counts", "拦截原因")]),
        },
        {
            "title": "成交明细（全部历史成交）",
            "columns": [
                ("brief_date", "账单日"), ("symbol", "股票代码"), ("name", "股票名称"), ("side", "方向"),
                ("trade_time", "成交时间"), ("price", "价格"), ("amount", "金额"), ("shares", "股数"),
                ("lots", "手数"), ("trade_status", "成交状态"), ("block_reasons", "说明"),
            ],
            "rows": rows_for(trades, [("brief_date", "账单日"), ("symbol", "股票代码"), ("name", "股票名称"), ("side", "方向"), ("trade_time", "成交时间"), ("price", "价格"), ("amount", "金额"), ("shares", "股数"), ("lots", "手数"), ("trade_status", "成交状态"), ("block_reasons", "说明")]),
        },
        {
            "title": "持仓快照（最近3个账单日）",
            "columns": [
                ("brief_date", "账单日"), ("symbol", "股票代码"), ("name", "股票名称"), ("close", "收盘价"),
                ("target_weight", "权重"), ("market_value", "市值"), ("shares", "股数"), ("lots", "手数"),
            ],
            "rows": rows_for(recent_positions, [("brief_date", "账单日"), ("symbol", "股票代码"), ("name", "股票名称"), ("close", "收盘价"), ("target_weight", "权重"), ("market_value", "市值"), ("shares", "股数"), ("lots", "手数")]),
        },
        {
            "title": "执行事件（最近3个账单日）",
            "columns": [
                ("brief_date", "账单日"), ("symbol", "股票代码"), ("name", "股票名称"), ("side", "方向"),
                ("event_type", "事件类型"), ("target_weight", "目标权重"), ("requested_shares", "计划股数"),
                ("filled_shares", "成交股数"), ("trade_status", "状态"), ("block_reasons", "原因"),
            ],
            "rows": rows_for(recent_events, [("brief_date", "账单日"), ("symbol", "股票代码"), ("name", "股票名称"), ("side", "方向"), ("event_type", "事件类型"), ("target_weight", "目标权重"), ("requested_shares", "计划股数"), ("filled_shares", "成交股数"), ("trade_status", "状态"), ("block_reasons", "原因")]),
        },
    ]
    return {"account_id": account_id, "name": str(account.name), "sections": sections}


# ═══════════ 研究域：对照图 + WIKI（补全原静态站 research/ 与 wiki/） ═══════════
# 原静态站遗漏内容：research/vix-vs-512480、research/sox-vs-512480、每账户 mapping charts、wiki 全景图。
# 对照图复用 market_comparison_chart.build_comparison_chart_data（与 site build 同源）。
VIX_512480_COMPARISON_CONFIG: Any = None


def _vix_comparison_config() -> Any:
    """延迟构造 VIX 对照图配置（避免模块顶层依赖 quant.reporting 类型）。"""
    from datetime import date

    from quant.reporting.market_comparison_chart import ComparisonChartConfig, ComparisonSeriesConfig

    return ComparisonChartConfig(
        slug="vix-vs-512480",
        title="^VIX 与半导体 ETF（512480）对照图",
        source=ComparisonSeriesConfig(
            symbol="^VIX",
            label="^VIX（恐慌指数）",
            storage="us_daily_bars",
        ),
        target=ComparisonSeriesConfig(
            symbol="SH.512480",
            label="SH.512480 前复权收盘价（实际交易标的）",
            storage="etf_qfq",
        ),
        start_date=date(2025, 11, 3),
        observation_band=None,
        daily_mapping_pct=0.5,
        consecutive_days=3,
        consecutive_daily_change_pct=0.0,
    )


@app.get("/api/research/comparison/{slug}")
def api_research_comparison(slug: str) -> dict[str, Any]:
    from quant.reporting.market_comparison_chart import build_comparison_chart_data
    from quant.reporting.quant_static_site import SOX_512480_COMPARISON_CONFIG

    configs = {
        "sox-vs-512480": SOX_512480_COMPARISON_CONFIG,
        "vix-vs-512480": _vix_comparison_config(),
    }
    config = configs.get(slug)
    if config is None:
        raise HTTPException(status_code=404, detail=f"未知对照图 {slug}")
    data = build_comparison_chart_data(root=ROOT, config=config)
    if data is None:
        raise HTTPException(status_code=404, detail=f"对照图 {slug} 数据不足（本地历史缺失）")
    return data


@app.get("/api/accounts/{account_id}/charts")
def api_account_charts(account_id: str) -> dict[str, Any]:
    account = _account_by_slug(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"未找到账户 {account_id}")
    from quant.config import load_config
    from quant.reporting.market_comparison_chart import build_comparison_chart_data
    from quant.strategies import get_strategy

    cfg = load_config(CONFIG_PATH)
    strategy_id = str(getattr(account, "strategy_id", "") or "")
    try:
        strategy = get_strategy(strategy_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 未注册") from None
    global_strategy_cfg = dict(cfg.get("walk_forward", {}).get("strategy_v2", {}) or {})
    charts = []
    try:
        items = strategy.account_mapping_charts(global_strategy_cfg, dict(getattr(account, "strategy_params", {}) or {}))
    except Exception:  # noqa: BLE001 — 策略未实现映射图时跳过
        items = []
    for item in items:
        data = build_comparison_chart_data(root=ROOT, config=item.chart)
        charts.append(
            {
                "slug": item.chart.slug,
                "title": item.chart.title,
                "button_label": item.button_label,
                "button_kicker": item.button_kicker,
                "data": data,
            }
        )
    return {"account_id": account_id, "charts": charts}


@app.get("/api/research/wiki")
def api_research_wiki():
    """A股影响因子全景图（marklogseq 静态导出，自包含 HTML，前端 iframe 嵌入）。"""
    from quant.config import load_config
    from quant.reporting.quant_static_site import _wiki_index_source

    cfg = load_config(CONFIG_PATH)
    source = _wiki_index_source(cfg)
    if source is None or not source.is_file():
        raise HTTPException(status_code=404, detail="wiki_index_source 未配置或文件缺失")
    from fastapi.responses import Response

    html_text = source.read_text(encoding="utf-8")
    # 与 site build 相同的默认页与折叠调整
    html_text = html_text.replace(
        'window.MARKLOGSEQ_DEFAULT_PAGE="cn_gdp"', 'window.MARKLOGSEQ_DEFAULT_PAGE="a_share_factor_overview"'
    )
    return Response(html_text, media_type="text/html; charset=utf-8")


@app.get("/api/accounts/{account_id}/strategy")
def api_account_strategy(account_id: str) -> dict[str, Any]:
    """该账户执行的量化策略详细解释（原静态站账户主页"这套策略怎么交易"区，结构化输出）。"""
    account = _account_by_slug(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"未找到账户 {account_id}")
    from quant.config import load_config

    cfg = load_config(CONFIG_PATH)
    strategy_id = str(getattr(account, "strategy_id", "") or "")
    if strategy_id == "cross_market_semiconductor_timing_etf_v1":
        base = dict(
            (cfg.get("walk_forward", {}).get("strategy_v2", {}).get("cross_market_semiconductor_timing", {}) or {})
        )
        base.update(dict(getattr(account, "strategy_params", {}) or {}))
        target = str(base.get("target_symbol", "SH.512480"))
        is_scheduled_close = target == "SH.588200"
        vix = 20 if is_scheduled_close else 19
        target_name = "科创芯片ETF（588200）" if is_scheduled_close else "国联安半导体ETF（512480）"
        exit_rule = "不设盘中追踪止损，在 T+1 日 14:55 清仓。" if is_scheduled_close else "从日内高点回落 2% 时卖出；未触发则 14:55 清仓。"
        discount = float(base.get("limit_order_discount", 0.012))
        if is_scheduled_close:
            period = "2022-10-26 至 2026-08-07"
            example_rows = [
                ["策略：SOX + VIX 映射择时", "+53.1%", "+12.4%", "0.77", "-14.8%", "26.0%", "+204.2%"],
                ["SH.588200 买入持有", "+256.6%", "+40.4%", "1.00", "-48.1%", "100.0%", "+256.6%"],
                ["沪深 300 买入持有", "+28.4%", "+7.1%", "0.48", "-24.8%", "100.0%", "+28.4%"],
            ]
        else:
            period = "2021-05-13 至 2026-08-07"
            example_rows = [
                ["策略：SOX + VIX 映射择时", "+67.5%", "+10.8%", "0.87", "-13.6%", "23.0%", "+293.6%"],
                ["SH.512480 买入持有", "+129.0%", "+17.5%", "0.62", "-62.5%", "100.0%", "+129.0%"],
                ["沪深 300 买入持有", "-6.0%", "-1.2%", "0.02", "-40.9%", "100.0%", "-6.0%"],
            ]
        return {
            "strategy_id": strategy_id,
            "name": "跨市场半导体择时（^SOX + ^VIX → A股半导体ETF）",
            "target_symbol": target,
            "target_name": target_name,
            "sections": [
                {
                    "heading": "这套策略怎么交易",
                    "paragraphs": [
                        f"它用上一交易日美股费城半导体指数（^SOX）的涨跌和恐慌指数（^VIX）筛选次日 A 股的 {target_name}（{target}）。美股收盘后，信号在下一次 A 股开盘时才可执行。",
                        f"开仓条件：r_SOX = SOX收盘(D) / SOX收盘(D−1) − 1；当 r_SOX > 0.5% 且 VIX < {vix} 时才考虑买入。SOX 涨幅超过 1% 是强信号，按开盘价买入，目标仓位 60%；0.5% 至 1% 是弱信号，按 开盘价 × (1 − {discount:.1%}) 挂限价单，目标仓位 50%。",
                        "弱信号未成交：当天价格没有触及限价就撤单，不追价；因此不会使用当天未来价格来决定成交。",
                        f"卖出规则：{exit_rule} 买入后遵守 ETF 的 T+1 规则，不留隔夜仓位。",
                        "交易口径：使用 5 分钟 K 线判断限价成交和盘中止损；按 100 份整手、账户佣金、最低佣金与滑点计算。回测和模拟账户采用同一套撮合规则。",
                        "跨市场映射风险：SOX 上涨不等于 A 股半导体 ETF 必然上涨。汇率、国内政策、行业供需、开盘跳空和流动性都可能使映射失效；策略结果不构成收益承诺或投资建议。",
                    ],
                }
            ],
            "research_example": {
                "period": period,
                "headers": ["对象", "总收益", "年化收益率", "夏普比率", "最大回撤", "平均资金占用", "已投入资本回报率"],
                "rows": example_rows,
                "terms": (
                    "总收益和年化收益率均以账户总资产为分母。平均资金占用是每日目标仓位的平均值，也可理解为资金利用率；"
                    "已投入资本回报率 = 总收益 ÷ 平均资金占用。夏普比率衡量单位波动对应的历史收益；最大回撤是历史峰值至谷底的最大跌幅。"
                    "历史研究结果不代表当前模拟账户业绩，也不构成未来收益承诺。"
                ),
            },
        }
    return {
        "strategy_id": strategy_id,
        "name": str(getattr(account, "name", "")),
        "note": "该策略暂无原站详细说明；账户口径见账单与台账。",
        "sections": [],
        "research_example": None,
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
