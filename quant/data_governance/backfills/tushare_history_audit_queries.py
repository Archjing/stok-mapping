from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd

from quant.data_governance.sql import safe_identifier


def coverage_audit(
    conn: sqlite3.Connection,
    *,
    local_cfg: dict[str, Any],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    daily_table = safe_identifier(str(local_cfg.get("daily_table", "market_daily_bars")))
    daily_basic_table = safe_identifier(str(local_cfg.get("daily_basic_table", "market_daily_basic")))
    adj_factor_table = safe_identifier(str(local_cfg.get("adj_factor_table", "market_adj_factors")))
    dividend_table = safe_identifier(str(local_cfg.get("dividend_table", "market_dividends")))
    financial_table = safe_identifier(str(local_cfg.get("financial_table", "market_financial_factors")))
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
                "non_null_ratio": 1.0 if total else 0.0,
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


def financial_backfill_audit(
    conn: sqlite3.Connection,
    *,
    task_table: str,
    financial_table: str,
    periods: list[str],
) -> pd.DataFrame:
    task = safe_identifier(task_table)
    financial = safe_identifier(financial_table)
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
