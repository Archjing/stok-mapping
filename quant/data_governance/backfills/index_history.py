from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from quant.config import load_config
from quant.data_governance.sql import safe_identifier
from quant.data_access.local_history import configure_local_history
from quant.data_access.providers.tushare import fetch_tushare_index_daily, tushare_available, tushare_config


@dataclass
class IndexHistoryBackfillResult:
    db_path: Path
    table_name: str
    start_date: str
    end_date: str
    target_symbols: int
    fetched_symbols: int
    empty_symbols: int
    failed_symbols: int
    inserted_rows: int
    status: str
    warnings: list[str]
    missing_symbols: list[str]


def index_ts_code(symbol: str) -> str:
    """Map a local index symbol to the Tushare ts_code.

    SH./SZ. prefixes map directly; CSI. entries live on the exchange their code
    space belongs to (399xxx on Shenzhen, everything else on Shanghai).
    """
    prefix, code = symbol.split(".", 1)
    if prefix == "SZ.":
        return f"{code}.SZ"
    if prefix == "SH.":
        return f"{code}.SH"
    return f"{code}.{'SZ' if code.startswith('399') else 'SH'}"


def _sleep_for_rate(last_request_at: float, max_requests_per_minute: int) -> float:
    min_interval = 60.0 / max(1, int(max_requests_per_minute))
    now = time.monotonic()
    sleep_for = min_interval - (now - last_request_at)
    if sleep_for > 0:
        time.sleep(sleep_for)
    return time.monotonic()


def backfill_index_history_from_config(
    config_path: Path,
    *,
    start_date: str,
    end_date: str,
    limit_symbols: int | None = None,
    max_requests_per_minute: int = 120,
) -> IndexHistoryBackfillResult:
    """Backfill market_index_bars for the configured window via Tushare index_daily.

    Each index is fetched once over the whole ``[start_date, end_date]`` window,
    which covers both the early-history gap and any stale tail.  Indexes that
    Tushare does not carry are reported in ``missing_symbols`` instead of being
    silently dropped.
    """
    root = config_path.parent
    cfg = load_config(config_path)
    configure_local_history(cfg.get("local_history", {}), root)
    local_cfg = cfg.get("local_history", {})
    data_cfg = cfg.get("data_sources", {})
    tcfg = tushare_config(data_cfg.get("tushare", {}))
    db_path = Path(local_cfg.get("path", "data/a_share_history.sqlite"))
    if not db_path.is_absolute():
        db_path = root / db_path
    table_name = str(local_cfg.get("index_table", "market_index_bars"))
    index_meta_table = str(local_cfg.get("index_meta_table", "market_indices"))

    warnings: list[str] = []
    if not tushare_available(tcfg):
        return IndexHistoryBackfillResult(
            db_path=db_path,
            table_name=table_name,
            start_date=start_date,
            end_date=end_date,
            target_symbols=0,
            fetched_symbols=0,
            empty_symbols=0,
            failed_symbols=0,
            inserted_rows=0,
            status="missing_tushare_token",
            warnings=[f"Tushare token env {tcfg.token_env} is not available."],
            missing_symbols=[],
        )

    with sqlite3.connect(db_path) as conn:
        symbols = [str(row[0]) for row in conn.execute(
            f"SELECT DISTINCT symbol FROM {safe_identifier(table_name)} WHERE market = 'CN' ORDER BY symbol"
        ).fetchall()]
        if limit_symbols is not None and limit_symbols > 0:
            symbols = symbols[: int(limit_symbols)]
        names: dict[str, str] = {}
        try:
            names = {
                str(row[0]): str(row[1] or "")
                for row in conn.execute(
                    f"SELECT symbol, name FROM {safe_identifier(index_meta_table)} WHERE market = 'CN'"
                ).fetchall()
            }
        except sqlite3.Error:
            names = {}

    inserted_rows = 0
    fetched_symbols = 0
    empty_symbols = 0
    failed_symbols = 0
    missing_symbols: list[str] = []
    last_request_at = 0.0
    with sqlite3.connect(db_path) as conn:
        table = safe_identifier(table_name)
        for symbol in symbols:
            last_request_at = _sleep_for_rate(last_request_at, max_requests_per_minute)
            try:
                frame = fetch_tushare_index_daily(
                    symbol,
                    ts_code=index_ts_code(symbol),
                    start_date=start_date,
                    end_date=end_date,
                    cfg=tcfg,
                    name=names.get(symbol, ""),
                )
            except Exception as exc:
                failed_symbols += 1
                warnings.append(f"{symbol}: {exc}")
                continue
            if frame.empty:
                empty_symbols += 1
                missing_symbols.append(symbol)
                continue
            conn.execute(
                f"DELETE FROM {table} WHERE market = 'CN' AND symbol = ? AND date >= ? AND date <= ?",
                (symbol, start_date, end_date),
            )
            frame.to_sql(table, conn, if_exists="append", index=False)
            inserted_rows += int(len(frame))
            fetched_symbols += 1
            conn.commit()

    status = "ok" if fetched_symbols > 0 else "empty"
    return IndexHistoryBackfillResult(
        db_path=db_path,
        table_name=table_name,
        start_date=start_date,
        end_date=end_date,
        target_symbols=len(symbols),
        fetched_symbols=fetched_symbols,
        empty_symbols=empty_symbols,
        failed_symbols=failed_symbols,
        inserted_rows=inserted_rows,
        status=status,
        warnings=warnings,
        missing_symbols=missing_symbols,
    )


def update_index_daily_tail_from_config(
    config_path: Path,
    *,
    end_date: str,
    max_requests_per_minute: int = 120,
) -> IndexHistoryBackfillResult:
    """Incrementally fill each index's missing tail up to ``end_date``.

    Daily post-close counterpart to ``backfill_index_history_from_config``:
    for every index symbol, the local ``MAX(date)`` is read and only dates in
    ``(local_max, end_date]`` are fetched (the first missing day is padded by
    one extra look-back day so the window is never empty).  Existing rows are
    left untouched, which keeps the daily job O(missing days) instead of
    re-pulling each index's full history.
    """
    from datetime import date as _date
    from datetime import timedelta as _timedelta

    root = config_path.parent
    cfg = load_config(config_path)
    configure_local_history(cfg.get("local_history", {}), root)
    local_cfg = cfg.get("local_history", {})
    data_cfg = cfg.get("data_sources", {})
    tcfg = tushare_config(data_cfg.get("tushare", {}))
    db_path = Path(local_cfg.get("path", "data/a_share_history.sqlite"))
    if not db_path.is_absolute():
        db_path = root / db_path
    table_name = str(local_cfg.get("index_table", "market_index_bars"))
    index_meta_table = str(local_cfg.get("index_meta_table", "market_indices"))
    table = safe_identifier(table_name)

    end_dt = _date.fromisoformat(end_date)
    warnings: list[str] = []
    if not tushare_available(tcfg):
        return IndexHistoryBackfillResult(
            db_path=db_path,
            table_name=table_name,
            start_date=end_date,
            end_date=end_date,
            target_symbols=0,
            fetched_symbols=0,
            empty_symbols=0,
            failed_symbols=0,
            inserted_rows=0,
            status="missing_tushare_token",
            warnings=[f"Tushare token env {tcfg.token_env} is not available."],
            missing_symbols=[],
        )

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT DISTINCT symbol, MAX(date) AS max_date FROM {table} WHERE market = 'CN' GROUP BY symbol ORDER BY symbol"
        ).fetchall()
        symbols: list[str] = []
        local_max: dict[str, _date] = {}
        for symbol, max_date in rows:
            symbols.append(str(symbol))
            if max_date:
                local_max[str(symbol)] = _date.fromisoformat(str(max_date)[:10])
        try:
            names = {
                str(row[0]): str(row[1] or "")
                for row in conn.execute(
                    f"SELECT symbol, name FROM {safe_identifier(index_meta_table)} WHERE market = 'CN'"
                ).fetchall()
            }
        except sqlite3.Error:
            names = {}

    inserted_rows = 0
    fetched_symbols = 0
    empty_symbols = 0
    failed_symbols = 0
    missing_symbols: list[str] = []
    skipped_up_to_date = 0
    last_request_at = 0.0
    with sqlite3.connect(db_path) as conn:
        for symbol in symbols:
            last_max = local_max.get(symbol)
            if last_max is not None and last_max >= end_dt:
                skipped_up_to_date += 1
                continue
            fetch_start = (last_max - _timedelta(days=1)).isoformat() if last_max else end_date
            last_request_at = _sleep_for_rate(last_request_at, max_requests_per_minute)
            try:
                frame = fetch_tushare_index_daily(
                    symbol,
                    ts_code=index_ts_code(symbol),
                    start_date=fetch_start,
                    end_date=end_date,
                    cfg=tcfg,
                    name=names.get(symbol, ""),
                )
            except Exception as exc:
                failed_symbols += 1
                warnings.append(f"{symbol}: {exc}")
                continue
            if frame.empty:
                empty_symbols += 1
                missing_symbols.append(symbol)
                continue
            # 只保留严格晚于本地最大日期的行，避免边界重复（to_sql append 无去重）。
            new = frame[frame["date"] > (last_max.isoformat() if last_max else "")]
            if new.empty:
                skipped_up_to_date += 1
                continue
            # 复用现有列结构；advances/declines 由 fetch 置 NULL。
            new.to_sql(table, conn, if_exists="append", index=False)
            inserted_rows += int(len(new))
            fetched_symbols += 1
            conn.commit()

    status = "ok" if fetched_symbols > 0 else ("up_to_date" if skipped_up_to_date > 0 else "empty")
    return IndexHistoryBackfillResult(
        db_path=db_path,
        table_name=table_name,
        start_date=end_date,
        end_date=end_date,
        target_symbols=len(symbols),
        fetched_symbols=fetched_symbols,
        empty_symbols=empty_symbols,
        failed_symbols=failed_symbols,
        inserted_rows=inserted_rows,
        status=status,
        warnings=warnings,
        missing_symbols=missing_symbols,
    )
