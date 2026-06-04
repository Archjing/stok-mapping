from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from phase0.adjustment import ensure_adj_factor_table, upsert_adj_factors
from phase0.config import load_config
from phase0.tushare_source import (
    fetch_tushare_adj_factor_trade_date,
    fetch_tushare_dividend,
    tushare_available,
    tushare_config,
)
from phase0.update_history import _safe_identifier


@dataclass(frozen=True)
class AdjustmentBackfillResult:
    db_path: Path
    start_date: str
    end_date: str
    target_dates: int
    fetched_dates: int
    inserted_adj_factor_rows: int
    inserted_dividend_rows: int
    skipped_existing_dates: int
    status: str
    warnings: list[str]


def _load_open_dates(conn: sqlite3.Connection, *, calendar_table: str, start_date: str, end_date: str) -> list[str]:
    table = _safe_identifier(calendar_table)
    df = pd.read_sql_query(
        f"""
        SELECT date
        FROM {table}
        WHERE is_open = 1
          AND date >= ?
          AND date <= ?
        ORDER BY date
        """,
        conn,
        params=(start_date, end_date),
    )
    return [str(value) for value in df["date"].dropna().tolist()]


def _existing_adj_factor_dates(conn: sqlite3.Connection, *, table_name: str, start_date: str, end_date: str) -> set[str]:
    table = _safe_identifier(table_name)
    df = pd.read_sql_query(
        f"""
        SELECT DISTINCT date
        FROM {table}
        WHERE market = 'CN'
          AND date >= ?
          AND date <= ?
        """,
        conn,
        params=(start_date, end_date),
    )
    return {str(value) for value in df["date"].dropna().tolist()}


def ensure_dividend_table(conn: sqlite3.Connection, *, table_name: str = "market_dividends") -> None:
    table = _safe_identifier(table_name)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            market TEXT NOT NULL,
            symbol TEXT NOT NULL,
            ann_date TEXT,
            div_proc TEXT,
            stk_div REAL,
            stk_bo_rate REAL,
            stk_co_rate REAL,
            cash_div REAL,
            cash_div_tax REAL,
            record_date TEXT,
            ex_date TEXT,
            pay_date TEXT,
            div_listdate TEXT,
            imp_ann_date TEXT,
            base_date TEXT,
            base_share REAL,
            source TEXT,
            updated_at TEXT,
            PRIMARY KEY (market, symbol, ann_date, ex_date, record_date, div_proc)
        )
        """
    )
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_symbol_ex_date ON {table}(market, symbol, ex_date)")


def upsert_dividends(conn: sqlite3.Connection, rows: pd.DataFrame, *, table_name: str = "market_dividends") -> int:
    if rows.empty:
        return 0
    ensure_dividend_table(conn, table_name=table_name)
    table = _safe_identifier(table_name)
    out = rows.copy()
    out["source"] = "tushare.dividend"
    out["updated_at"] = datetime.now().isoformat(timespec="seconds")
    keep = [
        "market",
        "symbol",
        "ann_date",
        "div_proc",
        "stk_div",
        "stk_bo_rate",
        "stk_co_rate",
        "cash_div",
        "cash_div_tax",
        "record_date",
        "ex_date",
        "pay_date",
        "div_listdate",
        "imp_ann_date",
        "base_date",
        "base_share",
        "source",
        "updated_at",
    ]
    for col in keep:
        if col not in out.columns:
            out[col] = None
    out = out[keep].drop_duplicates(["market", "symbol", "ann_date", "ex_date", "record_date", "div_proc"])
    conn.executemany(
        f"""
        INSERT INTO {table} (
            market, symbol, ann_date, div_proc, stk_div, stk_bo_rate, stk_co_rate,
            cash_div, cash_div_tax, record_date, ex_date, pay_date, div_listdate,
            imp_ann_date, base_date, base_share, source, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(market, symbol, ann_date, ex_date, record_date, div_proc) DO UPDATE SET
            stk_div = excluded.stk_div,
            stk_bo_rate = excluded.stk_bo_rate,
            stk_co_rate = excluded.stk_co_rate,
            cash_div = excluded.cash_div,
            cash_div_tax = excluded.cash_div_tax,
            pay_date = excluded.pay_date,
            div_listdate = excluded.div_listdate,
            imp_ann_date = excluded.imp_ann_date,
            base_date = excluded.base_date,
            base_share = excluded.base_share,
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        list(out.itertuples(index=False, name=None)),
    )
    return int(len(out))


def backfill_adjustment_factors_from_config(
    config_path: Path,
    *,
    start_date: str,
    end_date: str,
    limit_dates: int | None = None,
    skip_existing: bool = True,
    include_dividends: bool = True,
    max_requests_per_minute: int = 180,
) -> AdjustmentBackfillResult:
    root = config_path.parent
    cfg = load_config(config_path)
    local_cfg = cfg.get("local_history", {})
    data_cfg = cfg.get("data_sources", {})
    tcfg = tushare_config(data_cfg.get("tushare", {}))
    db_path = Path(local_cfg.get("path", "data/manual_history/a_share_history.sqlite"))
    if not db_path.is_absolute():
        db_path = root / db_path
    calendar_table = str(local_cfg.get("calendar_table", "trading_calendar"))
    adj_factor_table = str(local_cfg.get("adj_factor_table", "market_adj_factors"))
    dividend_table = str(local_cfg.get("dividend_table", "market_dividends"))
    warnings: list[str] = []

    if not tushare_available(tcfg):
        return AdjustmentBackfillResult(
            db_path=db_path,
            start_date=start_date,
            end_date=end_date,
            target_dates=0,
            fetched_dates=0,
            inserted_adj_factor_rows=0,
            inserted_dividend_rows=0,
            skipped_existing_dates=0,
            status="missing_tushare_token",
            warnings=[f"Tushare token env {tcfg.token_env} is not available."],
        )

    inserted_factors = 0
    inserted_dividends = 0
    fetched_dates = 0
    skipped_existing = 0
    min_interval = 60.0 / max(1, int(max_requests_per_minute))
    last_request_at = 0.0

    def throttle() -> None:
        nonlocal last_request_at
        now = time.monotonic()
        sleep_for = min_interval - (now - last_request_at)
        if sleep_for > 0:
            time.sleep(sleep_for)
        last_request_at = time.monotonic()

    with sqlite3.connect(db_path) as conn:
        ensure_adj_factor_table(conn, adj_factor_table)
        ensure_dividend_table(conn, table_name=dividend_table)
        open_dates = _load_open_dates(conn, calendar_table=calendar_table, start_date=start_date, end_date=end_date)
        existing = _existing_adj_factor_dates(conn, table_name=adj_factor_table, start_date=start_date, end_date=end_date)
        pending = [value for value in open_dates if not skip_existing or value not in existing]
        if limit_dates is not None and limit_dates > 0:
            pending = pending[: int(limit_dates)]
        skipped_existing = max(0, len(open_dates) - len(pending))

        for one_date in pending:
            try:
                throttle()
                factors = fetch_tushare_adj_factor_trade_date(pd.Timestamp(one_date).date(), cfg=tcfg)
            except Exception as exc:
                warnings.append(f"{one_date}: adj_factor failed: {exc}")
                continue
            if factors.empty:
                warnings.append(f"{one_date}: adj_factor returned empty")
                continue
            inserted_factors += upsert_adj_factors(conn, factors, table=adj_factor_table, source="tushare.adj_factor")
            fetched_dates += 1
            conn.commit()

        if include_dividends:
            try:
                throttle()
                dividends = fetch_tushare_dividend(start_date=start_date, end_date=end_date, cfg=tcfg)
                inserted_dividends = upsert_dividends(conn, dividends, table_name=dividend_table)
                conn.commit()
            except Exception as exc:
                warnings.append(f"dividend backfill failed: {exc}")

    status = "ok" if fetched_dates > 0 or skipped_existing > 0 or inserted_dividends > 0 else "empty"
    return AdjustmentBackfillResult(
        db_path=db_path,
        start_date=start_date,
        end_date=end_date,
        target_dates=len(open_dates) if "open_dates" in locals() else 0,
        fetched_dates=fetched_dates,
        inserted_adj_factor_rows=inserted_factors,
        inserted_dividend_rows=inserted_dividends,
        skipped_existing_dates=skipped_existing,
        status=status,
        warnings=warnings,
    )
