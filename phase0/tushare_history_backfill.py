from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from phase0.adjustment import ensure_adj_factor_table, upsert_adj_factors
from phase0.adjustment_backfill import ensure_dividend_table, upsert_dividends
from phase0.config import load_config
from phase0.financial_factors import ensure_financial_factor_table
from phase0.tushare_source import (
    fetch_tushare_adj_factor_trade_date,
    fetch_tushare_daily_basic_trade_date,
    fetch_tushare_dividend,
    fetch_tushare_financial_period,
    tushare_available,
    tushare_config,
)
from phase0.update_history import _ensure_daily_basic_table, _safe_identifier, _upsert_daily_basic_rows


@dataclass(frozen=True)
class TushareHistoryBackfillResult:
    db_path: Path
    start_date: str
    end_date: str
    status: str
    daily_basic_target_dates: int
    daily_basic_fetched_dates: int
    daily_basic_inserted_rows: int
    adj_factor_target_dates: int
    adj_factor_fetched_dates: int
    adj_factor_inserted_rows: int
    dividend_inserted_rows: int
    financial_target_periods: int
    financial_fetched_periods: int
    financial_inserted_rows: int
    audit_csv: Path
    audit_md: Path
    warnings: list[str]


@dataclass(frozen=True)
class TushareFinancialBackfillResult:
    db_path: Path
    start_period: str
    end_period: str
    status: str
    target_tasks: int
    processed_tasks: int
    fetched_tasks: int
    empty_tasks: int
    failed_tasks: int
    inserted_rows: int
    audit_csv: Path
    audit_md: Path
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


def _existing_dates(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    start_date: str,
    end_date: str,
    date_column: str = "date",
) -> set[str]:
    table = _safe_identifier(table_name)
    column = _safe_identifier(date_column)
    df = pd.read_sql_query(
        f"""
        SELECT DISTINCT {column} AS date
        FROM {table}
        WHERE market = 'CN'
          AND {column} >= ?
          AND {column} <= ?
        """,
        conn,
        params=(start_date, end_date),
    )
    return {str(value)[:10] for value in df["date"].dropna().tolist()}


def _quarter_periods(start_date: str, end_date: str) -> list[str]:
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    periods: list[str] = []
    for year in range(start.year, end.year + 1):
        for month_day in ["03-31", "06-30", "09-30", "12-31"]:
            period = pd.Timestamp(f"{year}-{month_day}")
            if start <= period <= end:
                periods.append(period.date().isoformat())
    return periods


def _load_symbols(conn: sqlite3.Connection, *, meta_table: str, markets: set[str]) -> list[str]:
    table = _safe_identifier(meta_table)
    df = pd.read_sql_query(
        f"""
        SELECT DISTINCT symbol
        FROM {table}
        WHERE market = 'CN'
          AND symbol IS NOT NULL
        ORDER BY symbol
        """,
        conn,
    )
    symbols = [str(value) for value in df["symbol"].dropna().tolist()]
    if markets:
        symbols = [symbol for symbol in symbols if symbol.split(".")[0] in markets]
    return symbols


def _load_symbols_for_period(conn: sqlite3.Connection, *, meta_table: str, markets: set[str], period: str) -> list[str]:
    table = _safe_identifier(meta_table)
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


def _sleep_for_rate(last_request_at: float, max_requests_per_minute: int) -> float:
    min_interval = 60.0 / max(1, int(max_requests_per_minute))
    now = time.monotonic()
    sleep_for = min_interval - (now - last_request_at)
    if sleep_for > 0:
        time.sleep(sleep_for)
    return time.monotonic()


def _replace_financial_rows(conn: sqlite3.Connection, *, table_name: str, rows: pd.DataFrame) -> int:
    if rows.empty:
        return 0
    table = _safe_identifier(table_name)
    ensure_financial_factor_table(conn, table=table)
    out = rows.copy()
    keep = [
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
    for col in keep:
        if col not in out.columns:
            out[col] = None
    out = out[keep].where(pd.notna(out), None)
    for market, report_date in out[["market", "report_date"]].dropna().drop_duplicates().itertuples(index=False):
        conn.execute(f"DELETE FROM {table} WHERE market = ? AND report_date = ?", (str(market), str(report_date)))
    out.to_sql(table, conn, if_exists="append", index=False)
    return int(len(out))


def _financial_non_null_count(row: pd.Series | dict[str, Any]) -> int:
    fields = [
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
    return sum(1 for field in fields if pd.notna(row.get(field)))


def _upsert_financial_row_preserving_valid(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    row: pd.Series,
    replace_existing: bool,
) -> int:
    if _financial_non_null_count(row) == 0:
        return 0
    table = _safe_identifier(table_name)
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
        if _financial_non_null_count(existing.iloc[0].to_dict()) >= _financial_non_null_count(row):
            return 0
    keep = [
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
    values = {col: row.get(col) for col in keep}
    values["market"] = market
    values["symbol"] = symbol
    values["report_date"] = report_date
    placeholders = ", ".join(["?"] * len(keep))
    updates = ", ".join([f"{col}=excluded.{col}" for col in keep if col not in {"market", "symbol", "report_date"}])
    conn.execute(
        f"""
        INSERT INTO {table} ({", ".join(keep)})
        VALUES ({placeholders})
        ON CONFLICT(market, symbol, report_date) DO UPDATE SET {updates}
        """,
        tuple(None if pd.isna(values[col]) else values[col] for col in keep),
    )
    return 1


def _ensure_financial_backfill_task_table(conn: sqlite3.Connection, *, table_name: str = "tushare_financial_backfill_tasks") -> None:
    table = _safe_identifier(table_name)
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


def _has_existing_valid_financial_row(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    symbol: str,
    period: str,
) -> bool:
    table = _safe_identifier(table_name)
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
    return bool(not row.empty and _financial_non_null_count(row.iloc[0].to_dict()) > 0)


def _initialize_financial_backfill_tasks(
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
    _ensure_financial_backfill_task_table(conn, table_name=task_table)
    table = _safe_identifier(task_table)
    inserted = 0
    for period in periods:
        symbols = _load_symbols_for_period(conn, meta_table=meta_table, markets=markets, period=period)
        if limit_symbols is not None and limit_symbols > 0:
            symbols = symbols[: int(limit_symbols)]
        for symbol in symbols:
            if not replace_existing and _has_existing_valid_financial_row(
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


def _select_financial_backfill_tasks(
    conn: sqlite3.Connection,
    *,
    task_table: str,
    periods: list[str],
    retry_failed: bool,
    shard_index: int,
    shard_count: int,
    limit_tasks: int | None = None,
) -> pd.DataFrame:
    table = _safe_identifier(task_table)
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


def _mark_financial_task(
    conn: sqlite3.Connection,
    *,
    task_table: str,
    period: str,
    symbol: str,
    status: str,
    error: str = "",
) -> None:
    table = _safe_identifier(task_table)
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


def _coverage_audit(
    conn: sqlite3.Connection,
    *,
    local_cfg: dict[str, Any],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    daily_table = _safe_identifier(str(local_cfg.get("daily_table", "market_daily_bars")))
    daily_basic_table = _safe_identifier(str(local_cfg.get("daily_basic_table", "market_daily_basic")))
    adj_factor_table = _safe_identifier(str(local_cfg.get("adj_factor_table", "market_adj_factors")))
    dividend_table = _safe_identifier(str(local_cfg.get("dividend_table", "market_dividends")))
    financial_table = _safe_identifier(str(local_cfg.get("financial_table", "market_financial_factors")))
    rows: list[dict[str, Any]] = []

    def scalar(query: str, params: tuple[Any, ...] = ()) -> Any:
        return pd.read_sql_query(query, conn, params=params).iloc[0, 0]

    for adjust_type in ["bfq", "qfq"]:
        total = int(
            scalar(
                f"SELECT COUNT(*) FROM {daily_table} WHERE market='CN' AND adjust_type=? AND date>=? AND date<=?",
                (adjust_type, start_date, end_date),
            )
            or 0
        )
        rows.append(
            {
                "table": daily_table,
                "field": f"{adjust_type}.ohlcv",
                "start_date": scalar(
                    f"SELECT MIN(date) FROM {daily_table} WHERE market='CN' AND adjust_type=? AND date>=? AND date<=?",
                    (adjust_type, start_date, end_date),
                ),
                "end_date": scalar(
                    f"SELECT MAX(date) FROM {daily_table} WHERE market='CN' AND adjust_type=? AND date>=? AND date<=?",
                    (adjust_type, start_date, end_date),
                ),
                "rows": total,
                "non_null_ratio": 1.0
                if total
                else 0.0,
            }
        )

    audit_specs = [
        (daily_basic_table, "pe_ratio", "date"),
        (daily_basic_table, "pb_ratio", "date"),
        (daily_basic_table, "turnover_rate", "date"),
        (adj_factor_table, "adj_factor", "date"),
        (financial_table, "roe", "report_date"),
        (financial_table, "revenue_growth", "report_date"),
        (financial_table, "profit_growth", "report_date"),
        (financial_table, "operating_cash_flow_to_net_profit", "report_date"),
        (financial_table, "debt_to_asset", "report_date"),
    ]
    for table, field, date_col in audit_specs:
        total = int(
            scalar(
                f"SELECT COUNT(*) FROM {table} WHERE market='CN' AND {date_col}>=? AND {date_col}<=?",
                (start_date, end_date),
            )
            or 0
        )
        non_null = int(
            scalar(
                f"SELECT COUNT(*) FROM {table} WHERE market='CN' AND {date_col}>=? AND {date_col}<=? AND {field} IS NOT NULL",
                (start_date, end_date),
            )
            or 0
        )
        rows.append(
            {
                "table": table,
                "field": field,
                "start_date": scalar(
                    f"SELECT MIN({date_col}) FROM {table} WHERE market='CN' AND {date_col}>=? AND {date_col}<=?",
                    (start_date, end_date),
                ),
                "end_date": scalar(
                    f"SELECT MAX({date_col}) FROM {table} WHERE market='CN' AND {date_col}>=? AND {date_col}<=?",
                    (start_date, end_date),
                ),
                "rows": total,
                "non_null_ratio": non_null / total if total else 0.0,
            }
        )

    dividend_rows = int(
        scalar(
            f"SELECT COUNT(*) FROM {dividend_table} WHERE market='CN' AND COALESCE(ann_date, ex_date, record_date)>=? AND COALESCE(ann_date, ex_date, record_date)<=?",
            (start_date, end_date),
        )
        or 0
    )
    rows.append(
        {
            "table": dividend_table,
            "field": "dividend_events",
            "start_date": scalar(
                f"SELECT MIN(COALESCE(ann_date, ex_date, record_date)) FROM {dividend_table} WHERE market='CN'"
            ),
            "end_date": scalar(
                f"SELECT MAX(COALESCE(ann_date, ex_date, record_date)) FROM {dividend_table} WHERE market='CN'"
            ),
            "rows": dividend_rows,
            "non_null_ratio": 1.0 if dividend_rows else 0.0,
        }
    )
    return pd.DataFrame(rows)


def _write_audit_report(*, audit: pd.DataFrame, output_csv: Path, output_md: Path, warnings: list[str]) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output_csv, index=False)
    lines = [
        "# Tushare 历史数据补全验收报告",
        "",
        "## 覆盖率汇总",
        "",
        "| table | field | start_date | end_date | rows | non_null_ratio |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for _, row in audit.iterrows():
        lines.append(
            f"| {row['table']} | {row['field']} | {row.get('start_date') or ''} | {row.get('end_date') or ''} | "
            f"{int(row.get('rows') or 0)} | {float(row.get('non_null_ratio') or 0.0):.4f} |"
        )
    lines.extend(["", "## Warnings", ""])
    if warnings:
        lines.extend([f"- {item}" for item in warnings])
    else:
        lines.append("- 无。")
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _financial_backfill_audit(
    conn: sqlite3.Connection,
    *,
    task_table: str,
    financial_table: str,
    periods: list[str],
) -> pd.DataFrame:
    task = _safe_identifier(task_table)
    financial = _safe_identifier(financial_table)
    rows: list[dict[str, Any]] = []
    for period in periods:
        task_row = pd.read_sql_query(
            f"""
            SELECT
                COUNT(*) AS target_symbols,
                SUM(CASE WHEN status = 'fetched' THEN 1 ELSE 0 END) AS fetched_symbols,
                SUM(CASE WHEN status = 'empty' THEN 1 ELSE 0 END) AS empty_symbols,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_symbols,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending_symbols
            FROM {task}
            WHERE period = ?
            """,
            conn,
            params=(period,),
        ).iloc[0]
        factor_row = pd.read_sql_query(
            f"""
            SELECT
                COUNT(*) AS rows,
                SUM(CASE WHEN announce_date IS NOT NULL THEN 1 ELSE 0 END) AS announce_date,
                SUM(CASE WHEN roe IS NOT NULL THEN 1 ELSE 0 END) AS roe,
                SUM(CASE WHEN revenue_growth IS NOT NULL THEN 1 ELSE 0 END) AS revenue_growth,
                SUM(CASE WHEN profit_growth IS NOT NULL THEN 1 ELSE 0 END) AS profit_growth,
                SUM(CASE WHEN operating_cash_flow_to_net_profit IS NOT NULL THEN 1 ELSE 0 END) AS cash_flow_quality,
                SUM(CASE WHEN debt_to_asset IS NOT NULL THEN 1 ELSE 0 END) AS debt_to_asset
            FROM {financial}
            WHERE market = 'CN'
              AND report_date = ?
            """,
            conn,
            params=(period,),
        ).iloc[0]
        factor_rows = int(factor_row.get("rows") or 0)
        rows.append(
            {
                "period": period,
                "target_symbols": int(task_row.get("target_symbols") or 0),
                "fetched_symbols": int(task_row.get("fetched_symbols") or 0),
                "empty_symbols": int(task_row.get("empty_symbols") or 0),
                "failed_symbols": int(task_row.get("failed_symbols") or 0),
                "pending_symbols": int(task_row.get("pending_symbols") or 0),
                "factor_rows": factor_rows,
                "announce_date_coverage": int(factor_row.get("announce_date") or 0) / factor_rows if factor_rows else 0.0,
                "roe_coverage": int(factor_row.get("roe") or 0) / factor_rows if factor_rows else 0.0,
                "revenue_growth_coverage": int(factor_row.get("revenue_growth") or 0) / factor_rows if factor_rows else 0.0,
                "profit_growth_coverage": int(factor_row.get("profit_growth") or 0) / factor_rows if factor_rows else 0.0,
                "cash_flow_quality_coverage": int(factor_row.get("cash_flow_quality") or 0) / factor_rows if factor_rows else 0.0,
                "debt_to_asset_coverage": int(factor_row.get("debt_to_asset") or 0) / factor_rows if factor_rows else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _write_financial_backfill_audit(
    *,
    audit: pd.DataFrame,
    output_csv: Path,
    output_md: Path,
    warnings: list[str],
) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output_csv, index=False)
    columns = [
        "period",
        "target_symbols",
        "fetched_symbols",
        "empty_symbols",
        "failed_symbols",
        "pending_symbols",
        "factor_rows",
        "announce_date_coverage",
        "roe_coverage",
        "revenue_growth_coverage",
        "profit_growth_coverage",
        "cash_flow_quality_coverage",
        "debt_to_asset_coverage",
    ]
    lines = [
        "# Tushare 财务因子逐股票回填验收报告",
        "",
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in audit.iterrows():
        values = []
        for col in columns:
            value = row.get(col)
            if isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value if pd.notna(value) else ""))
        lines.append("| " + " | ".join(values) + " |")
    lines.extend(["", "## Warnings", ""])
    if warnings:
        lines.extend([f"- {warning}" for warning in warnings])
    else:
        lines.append("- 无。")
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def backfill_tushare_financials_from_config(
    config_path: Path,
    *,
    start_period: str = "2016-03-31",
    end_period: str = "2018-03-31",
    period: str | None = None,
    max_requests_per_minute: int = 120,
    max_runtime_minutes: int | None = None,
    limit_symbols: int | None = None,
    limit_tasks: int | None = None,
    retry_failed: bool = False,
    replace_existing: bool = False,
    shard_index: int = 0,
    shard_count: int = 1,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    progress_interval_seconds: float = 30.0,
) -> TushareFinancialBackfillResult:
    root = config_path.parent
    cfg = load_config(config_path)
    local_cfg = cfg.get("local_history", {})
    data_cfg = cfg.get("data_sources", {})
    tcfg = tushare_config(data_cfg.get("tushare", {}))
    db_path = Path(local_cfg.get("path", "data/manual_history/a_share_history.sqlite"))
    if not db_path.is_absolute():
        db_path = root / db_path
    meta_table = str(local_cfg.get("meta_table", "market_stocks"))
    financial_table = str(local_cfg.get("financial_table", "market_financial_factors"))
    task_table = "tushare_financial_backfill_tasks"
    output_csv = root / "reports" / "tushare_financial_backfill_audit.csv"
    output_md = root / "reports" / "tushare_financial_backfill_audit.md"
    warnings: list[str] = []
    periods = [period] if period else _quarter_periods(start_period, end_period)
    if not periods:
        periods = [start_period]
    markets = {str(item) for item in cfg.get("universe", {}).get("markets", ["SH", "SZ"])}

    if not tushare_available(tcfg):
        warnings.append(f"Tushare token env {tcfg.token_env} is not available.")
        with sqlite3.connect(db_path) as conn:
            _ensure_financial_backfill_task_table(conn, table_name=task_table)
            ensure_financial_factor_table(conn, table=financial_table)
            audit = _financial_backfill_audit(conn, task_table=task_table, financial_table=financial_table, periods=periods)
        _write_financial_backfill_audit(audit=audit, output_csv=output_csv, output_md=output_md, warnings=warnings)
        return TushareFinancialBackfillResult(
            db_path=db_path,
            start_period=start_period,
            end_period=end_period,
            status="missing_tushare_token",
            target_tasks=0,
            processed_tasks=0,
            fetched_tasks=0,
            empty_tasks=0,
            failed_tasks=0,
            inserted_rows=0,
            audit_csv=output_csv,
            audit_md=output_md,
            warnings=warnings,
        )

    processed = 0
    fetched = 0
    empty = 0
    failed = 0
    inserted_rows = 0
    last_request_at = 0.0
    start_time = time.monotonic()
    last_progress_at = start_time
    max_runtime_seconds = None if max_runtime_minutes is None or max_runtime_minutes <= 0 else float(max_runtime_minutes) * 60.0

    def emit_progress(event: str, target_tasks: int, *, force: bool = False) -> None:
        nonlocal last_progress_at
        if progress_callback is None:
            return
        now = time.monotonic()
        if not force and progress_interval_seconds > 0 and now - last_progress_at < progress_interval_seconds:
            return
        progress_callback(
            {
                "event": event,
                "target_tasks": target_tasks,
                "processed_tasks": processed,
                "fetched_tasks": fetched,
                "empty_tasks": empty,
                "failed_tasks": failed,
                "inserted_rows": inserted_rows,
                "elapsed_seconds": now - start_time,
            }
        )
        last_progress_at = now

    with sqlite3.connect(db_path) as conn:
        _ensure_financial_backfill_task_table(conn, table_name=task_table)
        ensure_financial_factor_table(conn, table=financial_table)
        _initialize_financial_backfill_tasks(
            conn,
            task_table=task_table,
            financial_table=financial_table,
            meta_table=meta_table,
            periods=periods,
            markets=markets,
            replace_existing=replace_existing,
            limit_symbols=limit_symbols,
        )
        conn.commit()
        tasks = _select_financial_backfill_tasks(
            conn,
            task_table=task_table,
            periods=periods,
            retry_failed=retry_failed,
            shard_index=shard_index,
            shard_count=shard_count,
            limit_tasks=limit_tasks,
        )
        target_tasks = int(len(tasks))
        emit_progress("start", target_tasks, force=True)
        for task in tasks.itertuples(index=False):
            if max_runtime_seconds is not None and time.monotonic() - start_time >= max_runtime_seconds:
                warnings.append(f"max runtime reached after {processed} tasks")
                break
            task_period = str(task.period)
            symbol = str(task.symbol)
            try:
                last_request_at = _sleep_for_rate(last_request_at, max_requests_per_minute)
                rows = fetch_tushare_financial_period(pd.Timestamp(task_period).date(), cfg=tcfg, ts_code=symbol)
            except Exception as exc:
                failed += 1
                processed += 1
                _mark_financial_task(
                    conn,
                    task_table=task_table,
                    period=task_period,
                    symbol=symbol,
                    status="failed",
                    error=str(exc),
                )
                conn.commit()
                emit_progress("progress", target_tasks, force=processed >= target_tasks)
                continue
            processed += 1
            if rows.empty or rows.apply(_financial_non_null_count, axis=1).max() == 0:
                empty += 1
                _mark_financial_task(conn, task_table=task_table, period=task_period, symbol=symbol, status="empty")
                conn.commit()
                emit_progress("progress", target_tasks, force=processed >= target_tasks)
                continue
            row = rows.iloc[0]
            inserted_rows += _upsert_financial_row_preserving_valid(
                conn,
                table_name=financial_table,
                row=row,
                replace_existing=replace_existing,
            )
            fetched += 1
            _mark_financial_task(conn, task_table=task_table, period=task_period, symbol=symbol, status="fetched")
            conn.commit()
            emit_progress("progress", target_tasks, force=processed >= target_tasks)
        audit = _financial_backfill_audit(conn, task_table=task_table, financial_table=financial_table, periods=periods)

    _write_financial_backfill_audit(audit=audit, output_csv=output_csv, output_md=output_md, warnings=warnings)
    status = "ok" if not warnings and failed == 0 else "ok_with_warnings"
    return TushareFinancialBackfillResult(
        db_path=db_path,
        start_period=start_period,
        end_period=end_period,
        status=status,
        target_tasks=target_tasks if "target_tasks" in locals() else 0,
        processed_tasks=processed,
        fetched_tasks=fetched,
        empty_tasks=empty,
        failed_tasks=failed,
        inserted_rows=inserted_rows,
        audit_csv=output_csv,
        audit_md=output_md,
        warnings=warnings,
    )


def backfill_tushare_history_from_config(
    config_path: Path,
    *,
    start_date: str,
    end_date: str,
    max_requests_per_minute: int = 180,
    limit_dates: int | None = None,
    limit_periods: int | None = None,
    skip_existing: bool = True,
    include_daily_basic: bool = True,
    include_adj_factor: bool = True,
    include_dividends: bool = True,
    include_financial: bool = True,
) -> TushareHistoryBackfillResult:
    root = config_path.parent
    cfg = load_config(config_path)
    local_cfg = cfg.get("local_history", {})
    data_cfg = cfg.get("data_sources", {})
    tcfg = tushare_config(data_cfg.get("tushare", {}))
    db_path = Path(local_cfg.get("path", "data/manual_history/a_share_history.sqlite"))
    if not db_path.is_absolute():
        db_path = root / db_path
    calendar_table = str(local_cfg.get("calendar_table", "trading_calendar"))
    daily_basic_table = str(local_cfg.get("daily_basic_table", "market_daily_basic"))
    meta_table = str(local_cfg.get("meta_table", "market_stocks"))
    adj_factor_table = str(local_cfg.get("adj_factor_table", "market_adj_factors"))
    dividend_table = str(local_cfg.get("dividend_table", "market_dividends"))
    financial_table = str(local_cfg.get("financial_table", "market_financial_factors"))
    warnings: list[str] = []

    output_csv = root / "reports" / "tushare_history_backfill_audit.csv"
    output_md = root / "reports" / "tushare_history_backfill_audit.md"
    if not tushare_available(tcfg):
        warnings.append(f"Tushare token env {tcfg.token_env} is not available.")
        with sqlite3.connect(db_path) as conn:
            audit = _coverage_audit(conn, local_cfg=local_cfg, start_date=start_date, end_date=end_date)
        _write_audit_report(audit=audit, output_csv=output_csv, output_md=output_md, warnings=warnings)
        return TushareHistoryBackfillResult(
            db_path=db_path,
            start_date=start_date,
            end_date=end_date,
            status="missing_tushare_token",
            daily_basic_target_dates=0,
            daily_basic_fetched_dates=0,
            daily_basic_inserted_rows=0,
            adj_factor_target_dates=0,
            adj_factor_fetched_dates=0,
            adj_factor_inserted_rows=0,
            dividend_inserted_rows=0,
            financial_target_periods=0,
            financial_fetched_periods=0,
            financial_inserted_rows=0,
            audit_csv=output_csv,
            audit_md=output_md,
            warnings=warnings,
        )

    daily_basic_fetched = 0
    daily_basic_inserted = 0
    adj_factor_fetched = 0
    adj_factor_inserted = 0
    dividend_inserted = 0
    financial_fetched = 0
    financial_inserted = 0
    last_request_at = 0.0

    with sqlite3.connect(db_path) as conn:
        _ensure_daily_basic_table(conn, table_name=daily_basic_table)
        ensure_adj_factor_table(conn, adj_factor_table)
        ensure_dividend_table(conn, table_name=dividend_table)
        ensure_financial_factor_table(conn, table=financial_table)
        open_dates = _load_open_dates(conn, calendar_table=calendar_table, start_date=start_date, end_date=end_date)
        existing_basic = _existing_dates(conn, table_name=daily_basic_table, start_date=start_date, end_date=end_date)
        existing_adj = _existing_dates(conn, table_name=adj_factor_table, start_date=start_date, end_date=end_date)
        pending_basic = [value for value in open_dates if include_daily_basic and (not skip_existing or value not in existing_basic)]
        pending_adj = [value for value in open_dates if include_adj_factor and (not skip_existing or value not in existing_adj)]
        if limit_dates is not None and limit_dates > 0:
            pending_basic = pending_basic[: int(limit_dates)]
            pending_adj = pending_adj[: int(limit_dates)]

        for one_date in pending_basic:
            try:
                last_request_at = _sleep_for_rate(last_request_at, max_requests_per_minute)
                rows = fetch_tushare_daily_basic_trade_date(pd.Timestamp(one_date).date(), cfg=tcfg)
            except Exception as exc:
                warnings.append(f"{one_date}: daily_basic failed: {exc}")
                continue
            if rows.empty:
                warnings.append(f"{one_date}: daily_basic returned empty")
                continue
            daily_basic_inserted += _upsert_daily_basic_rows(conn, table_name=daily_basic_table, rows=rows)
            daily_basic_fetched += 1
            conn.commit()

        for one_date in pending_adj:
            try:
                last_request_at = _sleep_for_rate(last_request_at, max_requests_per_minute)
                rows = fetch_tushare_adj_factor_trade_date(pd.Timestamp(one_date).date(), cfg=tcfg)
            except Exception as exc:
                warnings.append(f"{one_date}: adj_factor failed: {exc}")
                continue
            if rows.empty:
                warnings.append(f"{one_date}: adj_factor returned empty")
                continue
            adj_factor_inserted += upsert_adj_factors(conn, rows, table=adj_factor_table, source="tushare.adj_factor")
            adj_factor_fetched += 1
            conn.commit()

        if include_dividends:
            try:
                last_request_at = _sleep_for_rate(last_request_at, max_requests_per_minute)
                dividends = fetch_tushare_dividend(start_date=start_date, end_date=end_date, cfg=tcfg)
                dividend_inserted = upsert_dividends(conn, dividends, table_name=dividend_table)
                conn.commit()
            except Exception as exc:
                warnings.append(f"dividend failed: {exc}")

        periods = _quarter_periods(start_date, end_date)
        markets = {str(item) for item in cfg.get("universe", {}).get("markets", ["SH", "SZ"])}
        symbols = _load_symbols(conn, meta_table=meta_table, markets=markets)
        existing_periods = _existing_dates(
            conn,
            table_name=financial_table,
            start_date=start_date,
            end_date=end_date,
            date_column="report_date",
        )
        pending_periods = [value for value in periods if include_financial and (not skip_existing or value not in existing_periods)]
        if limit_periods is not None and limit_periods > 0:
            pending_periods = pending_periods[: int(limit_periods)]
        for period in pending_periods:
            period_frames: list[pd.DataFrame] = []
            failed_symbols = 0
            for symbol in symbols:
                try:
                    last_request_at = _sleep_for_rate(last_request_at, max_requests_per_minute)
                    one_symbol = fetch_tushare_financial_period(pd.Timestamp(period).date(), cfg=tcfg, ts_code=symbol)
                except Exception as exc:
                    failed_symbols += 1
                    if failed_symbols <= 5:
                        warnings.append(f"{period} {symbol}: financial factors failed: {exc}")
                    continue
                if not one_symbol.empty:
                    period_frames.append(one_symbol)
            if not period_frames:
                warnings.append(f"{period}: financial factors returned empty for {len(symbols)} symbols")
                continue
            rows = pd.concat(period_frames, ignore_index=True)
            financial_inserted += _replace_financial_rows(conn, table_name=financial_table, rows=rows)
            financial_fetched += 1
            conn.commit()

        audit = _coverage_audit(conn, local_cfg=local_cfg, start_date=start_date, end_date=end_date)

    _write_audit_report(audit=audit, output_csv=output_csv, output_md=output_md, warnings=warnings)
    status = "ok" if not warnings else "ok_with_warnings"
    return TushareHistoryBackfillResult(
        db_path=db_path,
        start_date=start_date,
        end_date=end_date,
        status=status,
        daily_basic_target_dates=len(open_dates) if "open_dates" in locals() else 0,
        daily_basic_fetched_dates=daily_basic_fetched,
        daily_basic_inserted_rows=daily_basic_inserted,
        adj_factor_target_dates=len(open_dates) if "open_dates" in locals() else 0,
        adj_factor_fetched_dates=adj_factor_fetched,
        adj_factor_inserted_rows=adj_factor_inserted,
        dividend_inserted_rows=dividend_inserted,
        financial_target_periods=len(periods) if "periods" in locals() else 0,
        financial_fetched_periods=financial_fetched,
        financial_inserted_rows=financial_inserted,
        audit_csv=output_csv,
        audit_md=output_md,
        warnings=warnings,
    )
