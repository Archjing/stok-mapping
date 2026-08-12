from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from quant.data_governance.financial_factors import ensure_financial_factor_table
from quant.data_governance.backfills import tushare_financial_tasks
from quant.data_governance.backfills import tushare_history


def test_tushare_financial_task_helpers_are_import_compatible() -> None:
    assert tushare_history.FINANCIAL_FIELD_INTERFACES is tushare_financial_tasks.FINANCIAL_FIELD_INTERFACES
    assert tushare_history._load_symbols_for_period is tushare_financial_tasks.load_symbols_for_period
    assert tushare_history._ensure_financial_backfill_task_table is tushare_financial_tasks.ensure_financial_backfill_task_table
    assert (
        tushare_history._ensure_financial_missing_field_task_table
        is tushare_financial_tasks.ensure_financial_missing_field_task_table
    )
    assert tushare_history._normalize_missing_fields is tushare_financial_tasks.normalize_missing_fields
    assert tushare_history._interfaces_for_missing_fields is tushare_financial_tasks.interfaces_for_missing_fields
    assert tushare_history._has_existing_valid_financial_row is tushare_financial_tasks.has_existing_valid_financial_row
    assert (
        tushare_history._initialize_financial_missing_field_tasks
        is tushare_financial_tasks.initialize_financial_missing_field_tasks
    )
    assert tushare_history._initialize_financial_backfill_tasks is tushare_financial_tasks.initialize_financial_backfill_tasks
    assert tushare_history._select_financial_missing_field_tasks is tushare_financial_tasks.select_financial_missing_field_tasks
    assert tushare_history._select_financial_backfill_tasks is tushare_financial_tasks.select_financial_backfill_tasks
    assert tushare_history._mark_financial_missing_field_task is tushare_financial_tasks.mark_financial_missing_field_task
    assert tushare_history._mark_financial_task is tushare_financial_tasks.mark_financial_task


def test_normalize_missing_fields_deduplicates_defaults_and_validates_names() -> None:
    assert tushare_financial_tasks.normalize_missing_fields(None) == [
        "roe",
        "revenue_growth",
        "profit_growth",
        "operating_cash_flow_to_net_profit",
        "debt_to_asset",
    ]
    assert tushare_financial_tasks.normalize_missing_fields(["roe", "roe", "debt_to_asset", ""]) == [
        "roe",
        "debt_to_asset",
    ]
    assert tushare_financial_tasks.interfaces_for_missing_fields(["debt_to_asset"]) == {"balancesheet", "fina_indicator"}

    with pytest.raises(ValueError, match="unsupported financial missing field"):
        tushare_financial_tasks.normalize_missing_fields(["not_a_factor"])


def test_initialize_backfill_tasks_respects_listing_period_and_existing_valid_rows() -> None:
    with sqlite3.connect(":memory:") as conn:
        conn.execute(
            """
            CREATE TABLE market_stocks (
                market TEXT,
                symbol TEXT,
                list_date TEXT,
                delist_date TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO market_stocks (market, symbol, list_date, delist_date) VALUES (?, ?, ?, ?)",
            [
                ("CN", "SH.600000", "1999-01-01", ""),
                ("CN", "SZ.000001", "1991-01-01", ""),
                ("CN", "BJ.430001", "2020-01-01", ""),
                ("CN", "SH.688001", "2026-04-01", ""),
                ("CN", "SZ.000002", "1991-01-01", "2025-12-31"),
            ],
        )
        ensure_financial_factor_table(conn, table="market_financial_factors")
        conn.execute(
            """
            INSERT INTO market_financial_factors (market, symbol, report_date, roe)
            VALUES ('CN', 'SH.600000', '2026-03-31', 0.12)
            """
        )

        inserted = tushare_financial_tasks.initialize_financial_backfill_tasks(
            conn,
            task_table="tushare_financial_backfill_tasks",
            financial_table="market_financial_factors",
            meta_table="market_stocks",
            periods=["2026-03-31"],
            markets={"SH", "SZ"},
            replace_existing=False,
            limit_symbols=None,
        )
        tasks = pd.read_sql_query(
            """
            SELECT period, symbol, status, request_count
            FROM tushare_financial_backfill_tasks
            ORDER BY symbol
            """,
            conn,
        )

    assert inserted == 1
    assert tasks.to_dict("records") == [
        {"period": "2026-03-31", "symbol": "SZ.000001", "status": "pending", "request_count": 0}
    ]


def test_select_and_mark_backfill_tasks_support_retry_shards_and_error_truncation() -> None:
    with sqlite3.connect(":memory:") as conn:
        tushare_financial_tasks.ensure_financial_backfill_task_table(conn, table_name="tushare_financial_backfill_tasks")
        conn.executemany(
            """
            INSERT INTO tushare_financial_backfill_tasks (period, symbol, status, request_count)
            VALUES (?, ?, ?, ?)
            """,
            [
                ("2026-03-31", "SH.600000", "pending", 0),
                ("2026-03-31", "SZ.000001", "failed", 2),
                ("2026-03-31", "SZ.000002", "fetched", 1),
                ("2026-03-31", "SZ.000003", "pending", 0),
            ],
        )

        selected = tushare_financial_tasks.select_financial_backfill_tasks(
            conn,
            task_table="tushare_financial_backfill_tasks",
            periods=["2026-03-31"],
            retry_failed=True,
            shard_index=1,
            shard_count=2,
            limit_tasks=None,
        )
        tushare_financial_tasks.mark_financial_task(
            conn,
            task_table="tushare_financial_backfill_tasks",
            period="2026-03-31",
            symbol="SZ.000001",
            status="failed",
            error="x" * 1200,
        )
        stored = pd.read_sql_query(
            """
            SELECT symbol, status, request_count, LENGTH(last_error) AS error_length
            FROM tushare_financial_backfill_tasks
            WHERE symbol = 'SZ.000001'
            """,
            conn,
        ).iloc[0].to_dict()

    assert selected["symbol"].tolist() == ["SZ.000001"]
    assert stored == {"symbol": "SZ.000001", "status": "failed", "request_count": 3, "error_length": 1000}


def test_missing_field_tasks_capture_remaining_fields_and_interfaces() -> None:
    with sqlite3.connect(":memory:") as conn:
        ensure_financial_factor_table(conn, table="market_financial_factors")
        conn.execute(
            """
            INSERT INTO market_financial_factors (
                market,
                symbol,
                report_date,
                roe,
                revenue_growth,
                debt_to_asset
            )
            VALUES ('CN', 'SH.600000', '2026-03-31', NULL, 0.1, NULL)
            """
        )

        inserted = tushare_financial_tasks.initialize_financial_missing_field_tasks(
            conn,
            task_table="tushare_financial_missing_field_tasks",
            financial_table="market_financial_factors",
            periods=["2026-03-31"],
            fields=["roe", "revenue_growth", "debt_to_asset"],
            limit_symbols=None,
        )
        selected = tushare_financial_tasks.select_financial_missing_field_tasks(
            conn,
            task_table="tushare_financial_missing_field_tasks",
            periods=["2026-03-31"],
            retry_failed=False,
            shard_index=0,
            shard_count=1,
        )
        tushare_financial_tasks.mark_financial_missing_field_task(
            conn,
            task_table="tushare_financial_missing_field_tasks",
            period="2026-03-31",
            symbol="SH.600000",
            status="pending",
            missing_fields=["debt_to_asset"],
        )
        stored = pd.read_sql_query(
            """
            SELECT missing_fields, interfaces, status, request_count
            FROM tushare_financial_missing_field_tasks
            WHERE symbol = 'SH.600000'
            """,
            conn,
        ).iloc[0].to_dict()

    assert inserted == 1
    assert selected[["symbol", "missing_fields", "interfaces"]].to_dict("records") == [
        {
            "symbol": "SH.600000",
            "missing_fields": "roe,debt_to_asset",
            "interfaces": "balancesheet,fina_indicator",
        }
    ]
    assert stored == {
        "missing_fields": "debt_to_asset",
        "interfaces": "balancesheet,fina_indicator",
        "status": "pending",
        "request_count": 1,
    }
