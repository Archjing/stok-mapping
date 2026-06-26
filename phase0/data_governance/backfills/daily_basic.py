from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from phase0.config import load_config
from phase0.data_governance.daily_basic import ensure_daily_basic_table, upsert_daily_basic_rows
from phase0.data_governance.sql import safe_identifier
from phase0.data_access.local_history import configure_local_history
from phase0.data_access.providers.tushare import fetch_tushare_trade_date, tushare_available, tushare_config


@dataclass
class DailyBasicBackfillResult:
    db_path: Path
    table_name: str
    start_date: str
    end_date: str
    target_dates: int
    fetched_dates: int
    inserted_rows: int
    skipped_existing_dates: int
    status: str
    warnings: list[str]


def _load_open_dates(conn: sqlite3.Connection, *, calendar_table: str, start_date: str, end_date: str) -> list[str]:
    table = safe_identifier(calendar_table)
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


def _existing_dates(conn: sqlite3.Connection, *, table_name: str, start_date: str, end_date: str) -> set[str]:
    table = safe_identifier(table_name)
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


def backfill_daily_basic_from_config(
    config_path: Path,
    *,
    start_date: str,
    end_date: str,
    limit_dates: int | None = None,
) -> DailyBasicBackfillResult:
    root = config_path.parent
    cfg = load_config(config_path)
    configure_local_history(cfg.get("local_history", {}), root)
    local_cfg = cfg.get("local_history", {})
    data_cfg = cfg.get("data_sources", {})
    tcfg = tushare_config(data_cfg.get("tushare", {}))
    db_path = Path(local_cfg.get("path", "data/manual_history/a_share_history.sqlite"))
    if not db_path.is_absolute():
        db_path = root / db_path
    table_name = str(local_cfg.get("daily_basic_table", "market_daily_basic"))
    calendar_table = str(local_cfg.get("calendar_table", "trading_calendar"))

    warnings: list[str] = []
    if not tushare_available(tcfg):
        return DailyBasicBackfillResult(
            db_path=db_path,
            table_name=table_name,
            start_date=start_date,
            end_date=end_date,
            target_dates=0,
            fetched_dates=0,
            inserted_rows=0,
            skipped_existing_dates=0,
            status="missing_tushare_token",
            warnings=[f"Tushare token env {tcfg.token_env} is not available."],
        )

    inserted_rows = 0
    fetched_dates = 0
    skipped_existing_dates = 0
    with sqlite3.connect(db_path) as conn:
        ensure_daily_basic_table(conn, table_name=table_name)
        open_dates = _load_open_dates(conn, calendar_table=calendar_table, start_date=start_date, end_date=end_date)
        existing = _existing_dates(conn, table_name=table_name, start_date=start_date, end_date=end_date)
        pending = [value for value in open_dates if value not in existing]
        if limit_dates is not None and limit_dates > 0:
            pending = pending[: int(limit_dates)]
        skipped_existing_dates = max(0, len(open_dates) - len(pending))

        for one_date in pending:
            try:
                _, meta_rows = fetch_tushare_trade_date(
                    pd.Timestamp(one_date).date(),
                    adjust_types=["qfq"],
                    cfg=tcfg,
                )
            except Exception as exc:
                warnings.append(f"{one_date}: {exc}")
                continue
            if meta_rows.empty:
                warnings.append(f"{one_date}: daily_basic returned empty")
                continue
            inserted_rows += upsert_daily_basic_rows(conn, table_name=table_name, rows=meta_rows)
            fetched_dates += 1
            conn.commit()

    status = "ok" if fetched_dates > 0 or skipped_existing_dates > 0 else "empty"
    return DailyBasicBackfillResult(
        db_path=db_path,
        table_name=table_name,
        start_date=start_date,
        end_date=end_date,
        target_dates=len(open_dates) if 'open_dates' in locals() else 0,
        fetched_dates=fetched_dates,
        inserted_rows=inserted_rows,
        skipped_existing_dates=skipped_existing_dates,
        status=status,
        warnings=warnings,
    )
