from __future__ import annotations

import sqlite3

import pandas as pd

from quant.data_governance.sql import safe_identifier, to_sql_value


def ensure_daily_basic_table(conn: sqlite3.Connection, *, table_name: str) -> None:
    table = safe_identifier(table_name)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            market TEXT NOT NULL,
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            market_cap REAL,
            circ_mv REAL,
            pe_ratio REAL,
            pb_ratio REAL,
            turnover_rate REAL,
            PRIMARY KEY (market, symbol, date)
        )
        """
    )
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_date ON {table}(date)")


def upsert_daily_basic_rows(conn: sqlite3.Connection, *, table_name: str, rows: pd.DataFrame) -> int:
    if rows.empty:
        return 0
    table = safe_identifier(table_name)
    ensure_daily_basic_table(conn, table_name=table)
    params = [
        (
            str(row.get("market") or "CN"),
            str(row.get("symbol") or ""),
            str(row.get("date") or ""),
            to_sql_value(row.get("market_cap")),
            to_sql_value(row.get("circ_mv")),
            to_sql_value(row.get("pe_ratio")),
            to_sql_value(row.get("pb_ratio")),
            to_sql_value(row.get("turnover_rate")),
        )
        for _, row in rows.iterrows()
        if str(row.get("symbol") or "") and str(row.get("date") or "")
    ]
    if not params:
        return 0
    cursor = conn.executemany(
        f"""
        INSERT OR REPLACE INTO {table} (
            market, symbol, date, market_cap, circ_mv, pe_ratio, pb_ratio, turnover_rate
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        params,
    )
    return int(cursor.rowcount or 0)
