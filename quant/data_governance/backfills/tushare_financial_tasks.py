from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

import pandas as pd

from quant.data_governance.backfills.tushare_financial_rows import financial_non_null_count
from quant.data_governance.sql import safe_identifier


FINANCIAL_FIELD_INTERFACES: dict[str, set[str]] = {
    "announce_date": {"income", "fina_indicator"},
    "roe": {"fina_indicator"},
    "revenue": {"income"},
    "revenue_growth": {"fina_indicator"},
    "net_profit": {"income"},
    "profit_growth": {"fina_indicator"},
    "operating_cash_flow": {"cashflow"},
    "operating_cash_flow_to_net_profit": {"income", "cashflow"},
    "debt_to_asset": {"balancesheet", "fina_indicator"},
    "total_assets": {"balancesheet"},
    "total_liabilities": {"balancesheet"},
    "total_equity": {"balancesheet"},
}


def load_symbols_for_period(conn: sqlite3.Connection, *, meta_table: str, markets: set[str], period: str) -> list[str]:
    table = safe_identifier(meta_table)
    df = pd.read_sql_query(
        f"""
        SELECT DISTINCT symbol
        FROM {table}
        WHERE market = 'CN'
          AND symbol IS NOT NULL
          AND (COALESCE(list_date, '') = '' OR list_date <= ?)
          AND (COALESCE(delist_date, '') = '' OR delist_date >= ?)
        ORDER BY symbol
        """,
        conn,
        params=(period, period),
    )
    symbols = [str(value) for value in df["symbol"].dropna().tolist()]
    if markets:
        symbols = [symbol for symbol in symbols if symbol.split(".")[0] in markets]
    return symbols


def ensure_financial_backfill_task_table(
    conn: sqlite3.Connection,
    *,
    table_name: str = "tushare_financial_backfill_tasks",
) -> None:
    table = safe_identifier(table_name)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            period TEXT NOT NULL,
            symbol TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            request_count INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            updated_at TEXT,
            PRIMARY KEY (period, symbol)
        )
        """
    )
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_status_period ON {table}(status, period)")


def ensure_financial_missing_field_task_table(
    conn: sqlite3.Connection,
    *,
    table_name: str = "tushare_financial_missing_field_tasks",
) -> None:
    table = safe_identifier(table_name)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            period TEXT NOT NULL,
            symbol TEXT NOT NULL,
            missing_fields TEXT NOT NULL,
            interfaces TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            request_count INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            updated_at TEXT,
            PRIMARY KEY (period, symbol)
        )
        """
    )
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_status_period ON {table}(status, period)")


def normalize_missing_fields(fields: list[str] | tuple[str, ...] | set[str] | None) -> list[str]:
    if not fields:
        return [
            "roe",
            "revenue_growth",
            "profit_growth",
            "operating_cash_flow_to_net_profit",
            "debt_to_asset",
        ]
    normalized: list[str] = []
    for field in fields:
        value = str(field).strip()
        if not value:
            continue
        if value not in FINANCIAL_FIELD_INTERFACES:
            raise ValueError(f"unsupported financial missing field: {value}")
        if value not in normalized:
            normalized.append(value)
    if not normalized:
        raise ValueError("missing field list is empty")
    return normalized


def interfaces_for_missing_fields(fields: list[str]) -> set[str]:
    interfaces: set[str] = set()
    for field in fields:
        interfaces.update(FINANCIAL_FIELD_INTERFACES[field])
    return interfaces


def has_existing_valid_financial_row(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    symbol: str,
    period: str,
) -> bool:
    table = safe_identifier(table_name)
    row = pd.read_sql_query(
        f"""
        SELECT
            announce_date,
            roe,
            revenue,
            revenue_growth,
            net_profit,
            profit_growth,
            operating_cash_flow,
            operating_cash_flow_to_net_profit,
            debt_to_asset,
            total_assets,
            total_liabilities,
            total_equity
        FROM {table}
        WHERE market = 'CN'
          AND symbol = ?
          AND report_date = ?
        """,
        conn,
        params=(symbol, period),
    )
    return bool(not row.empty and financial_non_null_count(row.iloc[0].to_dict()) > 0)


def initialize_financial_missing_field_tasks(
    conn: sqlite3.Connection,
    *,
    task_table: str,
    financial_table: str,
    periods: list[str],
    fields: list[str],
    limit_symbols: int | None,
) -> int:
    ensure_financial_missing_field_task_table(conn, table_name=task_table)
    task = safe_identifier(task_table)
    financial = safe_identifier(financial_table)
    field_expr = " OR ".join([f"{safe_identifier(field)} IS NULL" for field in fields])
    period_placeholders = ",".join(["?"] * len(periods))
    selected_fields = ", ".join([safe_identifier(field) for field in fields])
    query = f"""
        SELECT symbol, report_date AS period, {selected_fields}
        FROM {financial}
        WHERE market = 'CN'
          AND report_date IN ({period_placeholders})
          AND ({field_expr})
        ORDER BY report_date, symbol
    """
    rows = pd.read_sql_query(query, conn, params=periods)
    if limit_symbols is not None and limit_symbols > 0:
        rows = rows.groupby("period", group_keys=False).head(int(limit_symbols)).copy()
    inserted = 0
    now = datetime.now().isoformat(timespec="seconds")
    for row in rows.itertuples(index=False):
        row_dict = row._asdict()
        missing = [field for field in fields if pd.isna(row_dict.get(field))]
        if not missing:
            continue
        interfaces = sorted(interfaces_for_missing_fields(missing))
        cursor = conn.execute(
            f"""
            INSERT INTO {task} (period, symbol, missing_fields, interfaces, status, request_count, updated_at)
            VALUES (?, ?, ?, ?, 'pending', 0, ?)
            ON CONFLICT(period, symbol) DO UPDATE SET
                missing_fields = excluded.missing_fields,
                interfaces = excluded.interfaces,
                status = CASE WHEN {task}.status IN ('fetched', 'empty') THEN {task}.status ELSE 'pending' END,
                updated_at = excluded.updated_at
            """,
            (
                str(row_dict["period"]),
                str(row_dict["symbol"]),
                ",".join(missing),
                ",".join(interfaces),
                now,
            ),
        )
        inserted += int(cursor.rowcount or 0)
    return inserted


def initialize_financial_backfill_tasks(
    conn: sqlite3.Connection,
    *,
    task_table: str,
    financial_table: str,
    meta_table: str,
    periods: list[str],
    markets: set[str],
    replace_existing: bool,
    limit_symbols: int | None,
) -> int:
    ensure_financial_backfill_task_table(conn, table_name=task_table)
    table = safe_identifier(task_table)
    inserted = 0
    for period in periods:
        symbols = load_symbols_for_period(conn, meta_table=meta_table, markets=markets, period=period)
        if limit_symbols is not None and limit_symbols > 0:
            symbols = symbols[: int(limit_symbols)]
        for symbol in symbols:
            if not replace_existing and has_existing_valid_financial_row(
                conn,
                table_name=financial_table,
                symbol=symbol,
                period=period,
            ):
                continue
            cursor = conn.execute(
                f"""
                INSERT OR IGNORE INTO {table} (period, symbol, status, request_count, updated_at)
                VALUES (?, ?, 'pending', 0, ?)
                """,
                (period, symbol, datetime.now().isoformat(timespec="seconds")),
            )
            inserted += int(cursor.rowcount or 0)
    return inserted


def select_financial_missing_field_tasks(
    conn: sqlite3.Connection,
    *,
    task_table: str,
    periods: list[str],
    retry_failed: bool,
    shard_index: int,
    shard_count: int,
    limit_tasks: int | None = None,
) -> pd.DataFrame:
    table = safe_identifier(task_table)
    statuses = ["pending", "failed"] if retry_failed else ["pending"]
    placeholders = ",".join(["?"] * len(statuses))
    period_placeholders = ",".join(["?"] * len(periods))
    query = f"""
        SELECT period, symbol, missing_fields, interfaces, status, request_count
        FROM {table}
        WHERE status IN ({placeholders})
          AND period IN ({period_placeholders})
        ORDER BY period, symbol
    """
    tasks = pd.read_sql_query(query, conn, params=[*statuses, *periods])
    if tasks.empty:
        return tasks
    shard_count = max(1, int(shard_count))
    shard_index = max(0, int(shard_index)) % shard_count
    tasks = tasks.reset_index(drop=True)
    tasks = tasks[tasks.index % shard_count == shard_index].copy()
    if limit_tasks is not None:
        tasks = tasks.head(int(limit_tasks)).copy()
    return tasks


def select_financial_backfill_tasks(
    conn: sqlite3.Connection,
    *,
    task_table: str,
    periods: list[str],
    retry_failed: bool,
    shard_index: int,
    shard_count: int,
    limit_tasks: int | None = None,
) -> pd.DataFrame:
    table = safe_identifier(task_table)
    statuses = ["pending", "failed"] if retry_failed else ["pending"]
    placeholders = ",".join(["?"] * len(statuses))
    period_placeholders = ",".join(["?"] * len(periods))
    query = f"""
        SELECT period, symbol, status, request_count
        FROM {table}
        WHERE status IN ({placeholders})
          AND period IN ({period_placeholders})
        ORDER BY period, symbol
    """
    tasks = pd.read_sql_query(query, conn, params=[*statuses, *periods])
    if tasks.empty:
        return tasks
    shard_count = max(1, int(shard_count))
    shard_index = max(0, int(shard_index)) % shard_count
    tasks = tasks.reset_index(drop=True)
    tasks = tasks[tasks.index % shard_count == shard_index].copy()
    if limit_tasks is not None:
        tasks = tasks.head(int(limit_tasks)).copy()
    return tasks


def mark_financial_missing_field_task(
    conn: sqlite3.Connection,
    *,
    task_table: str,
    period: str,
    symbol: str,
    status: str,
    missing_fields: list[str] | None = None,
    error: str = "",
) -> None:
    table = safe_identifier(task_table)
    updates = [
        "status = ?",
        "request_count = request_count + 1",
        "last_error = ?",
        "updated_at = ?",
    ]
    params: list[Any] = [status, error[:1000], datetime.now().isoformat(timespec="seconds")]
    if missing_fields is not None:
        updates.append("missing_fields = ?")
        updates.append("interfaces = ?")
        params.append(",".join(missing_fields))
        params.append(",".join(sorted(interfaces_for_missing_fields(missing_fields))) if missing_fields else "")
    params.extend([period, symbol])
    conn.execute(
        f"""
        UPDATE {table}
        SET {", ".join(updates)}
        WHERE period = ?
          AND symbol = ?
        """,
        tuple(params),
    )


def mark_financial_task(
    conn: sqlite3.Connection,
    *,
    task_table: str,
    period: str,
    symbol: str,
    status: str,
    error: str = "",
) -> None:
    table = safe_identifier(task_table)
    conn.execute(
        f"""
        UPDATE {table}
        SET status = ?,
            request_count = request_count + 1,
            last_error = ?,
            updated_at = ?
        WHERE period = ?
          AND symbol = ?
        """,
        (status, error[:1000], datetime.now().isoformat(timespec="seconds"), period, symbol),
    )
