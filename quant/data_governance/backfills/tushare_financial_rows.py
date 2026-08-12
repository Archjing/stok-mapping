from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd

from quant.data_governance.financial_factors import ensure_financial_factor_table
from quant.data_governance.sql import safe_identifier


FINANCIAL_FACTOR_VALUE_FIELDS = [
    "announce_date",
    "roe",
    "revenue",
    "revenue_growth",
    "net_profit",
    "profit_growth",
    "operating_cash_flow",
    "operating_cash_flow_to_net_profit",
    "debt_to_asset",
    "total_assets",
    "total_liabilities",
    "total_equity",
]

FINANCIAL_FACTOR_ROW_COLUMNS = [
    "market",
    "symbol",
    "report_date",
    "fiscal_year",
    "fiscal_quarter",
    "announce_date",
    "name",
    "industry",
    "roe",
    "revenue",
    "revenue_growth",
    "net_profit",
    "profit_growth",
    "operating_cash_flow",
    "operating_cash_flow_to_net_profit",
    "debt_to_asset",
    "total_assets",
    "total_liabilities",
    "total_equity",
    "source",
    "updated_at",
]


def replace_financial_rows(conn: sqlite3.Connection, *, table_name: str, rows: pd.DataFrame) -> int:
    if rows.empty:
        return 0
    table = safe_identifier(table_name)
    ensure_financial_factor_table(conn, table=table)
    out = rows.copy()
    for col in FINANCIAL_FACTOR_ROW_COLUMNS:
        if col not in out.columns:
            out[col] = None
    out = out[FINANCIAL_FACTOR_ROW_COLUMNS].where(pd.notna(out), None)
    for market, report_date in out[["market", "report_date"]].dropna().drop_duplicates().itertuples(index=False):
        conn.execute(f"DELETE FROM {table} WHERE market = ? AND report_date = ?", (str(market), str(report_date)))
    out.to_sql(table, conn, if_exists="append", index=False)
    return int(len(out))


def financial_non_null_count(row: pd.Series | dict[str, Any]) -> int:
    return sum(1 for field in FINANCIAL_FACTOR_VALUE_FIELDS if pd.notna(row.get(field)))


def upsert_financial_row_preserving_valid(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    row: pd.Series,
    replace_existing: bool,
) -> int:
    if financial_non_null_count(row) == 0:
        return 0
    table = safe_identifier(table_name)
    ensure_financial_factor_table(conn, table=table)
    market = str(row.get("market") or "CN")
    symbol = str(row.get("symbol") or "")
    report_date = str(row.get("report_date") or "")
    if not symbol or not report_date:
        return 0
    existing = pd.read_sql_query(
        f"SELECT * FROM {table} WHERE market = ? AND symbol = ? AND report_date = ?",
        conn,
        params=(market, symbol, report_date),
    )
    if not existing.empty and not replace_existing:
        if financial_non_null_count(existing.iloc[0].to_dict()) >= financial_non_null_count(row):
            return 0
    values = {col: row.get(col) for col in FINANCIAL_FACTOR_ROW_COLUMNS}
    values["market"] = market
    values["symbol"] = symbol
    values["report_date"] = report_date
    placeholders = ", ".join(["?"] * len(FINANCIAL_FACTOR_ROW_COLUMNS))
    updates = ", ".join(
        [f"{col}=excluded.{col}" for col in FINANCIAL_FACTOR_ROW_COLUMNS if col not in {"market", "symbol", "report_date"}]
    )
    conn.execute(
        f"""
        INSERT INTO {table} ({", ".join(FINANCIAL_FACTOR_ROW_COLUMNS)})
        VALUES ({placeholders})
        ON CONFLICT(market, symbol, report_date) DO UPDATE SET {updates}
        """,
        tuple(None if pd.isna(values[col]) else values[col] for col in FINANCIAL_FACTOR_ROW_COLUMNS),
    )
    return 1


def merge_financial_missing_fields(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    row: pd.Series,
    fields: list[str],
) -> int:
    table = safe_identifier(table_name)
    market = str(row.get("market") or "CN")
    symbol = str(row.get("symbol") or "")
    report_date = str(row.get("report_date") or "")
    if not symbol or not report_date:
        return 0
    existing = pd.read_sql_query(
        f"SELECT * FROM {table} WHERE market = ? AND symbol = ? AND report_date = ?",
        conn,
        params=(market, symbol, report_date),
    )
    if existing.empty:
        return upsert_financial_row_preserving_valid(conn, table_name=table_name, row=row, replace_existing=False)

    updates: dict[str, Any] = {}
    existing_row = existing.iloc[0].to_dict()
    for field in fields:
        value = row.get(field)
        if pd.notna(value) and pd.isna(existing_row.get(field)):
            updates[field] = value
    if not updates:
        return 0
    for field in ["announce_date", "source", "updated_at"]:
        value = row.get(field)
        if pd.notna(value) and (field == "updated_at" or pd.isna(existing_row.get(field))):
            updates[field] = value
    assignments = ", ".join([f"{safe_identifier(field)} = ?" for field in updates])
    conn.execute(
        f"""
        UPDATE {table}
        SET {assignments}
        WHERE market = ?
          AND symbol = ?
          AND report_date = ?
        """,
        tuple(None if pd.isna(value) else value for value in updates.values()) + (market, symbol, report_date),
    )
    return 1
