from __future__ import annotations

import sqlite3

import pandas as pd

from quant.data_governance.backfills import tushare_financial_rows
from quant.data_governance.backfills import tushare_history


def test_tushare_financial_row_helpers_are_import_compatible() -> None:
    assert tushare_history._replace_financial_rows is tushare_financial_rows.replace_financial_rows
    assert tushare_history._financial_non_null_count is tushare_financial_rows.financial_non_null_count
    assert tushare_history._upsert_financial_row_preserving_valid is tushare_financial_rows.upsert_financial_row_preserving_valid
    assert tushare_history._merge_financial_missing_fields is tushare_financial_rows.merge_financial_missing_fields


def test_replace_financial_rows_replaces_existing_period_rows() -> None:
    rows = pd.DataFrame(
        [
            {
                "market": "CN",
                "symbol": "000001.SZ",
                "report_date": "2026-03-31",
                "roe": 0.1,
                "source": "new",
            },
            {
                "market": "CN",
                "symbol": "000002.SZ",
                "report_date": "2026-03-31",
                "roe": 0.2,
                "source": "new",
            },
        ]
    )
    with sqlite3.connect(":memory:") as conn:
        tushare_financial_rows.upsert_financial_row_preserving_valid(
            conn,
            table_name="market_financial_factors",
            row=pd.Series({"market": "CN", "symbol": "000009.SZ", "report_date": "2026-03-31", "roe": 0.9}),
            replace_existing=True,
        )
        inserted = tushare_financial_rows.replace_financial_rows(conn, table_name="market_financial_factors", rows=rows)
        stored = pd.read_sql_query(
            "SELECT symbol, roe, source FROM market_financial_factors WHERE report_date='2026-03-31' ORDER BY symbol",
            conn,
        )

    assert inserted == 2
    assert stored.to_dict("records") == [
        {"symbol": "000001.SZ", "roe": 0.1, "source": "new"},
        {"symbol": "000002.SZ", "roe": 0.2, "source": "new"},
    ]


def test_upsert_financial_row_preserves_more_complete_existing_row() -> None:
    with sqlite3.connect(":memory:") as conn:
        first = tushare_financial_rows.upsert_financial_row_preserving_valid(
            conn,
            table_name="market_financial_factors",
            row=pd.Series(
                {
                    "market": "CN",
                    "symbol": "000001.SZ",
                    "report_date": "2026-03-31",
                    "roe": 0.1,
                    "revenue": 100.0,
                    "source": "first",
                }
            ),
            replace_existing=True,
        )
        second = tushare_financial_rows.upsert_financial_row_preserving_valid(
            conn,
            table_name="market_financial_factors",
            row=pd.Series(
                {
                    "market": "CN",
                    "symbol": "000001.SZ",
                    "report_date": "2026-03-31",
                    "roe": 0.2,
                    "source": "less_complete",
                }
            ),
            replace_existing=False,
        )
        stored = pd.read_sql_query("SELECT roe, revenue, source FROM market_financial_factors", conn).iloc[0].to_dict()

    assert first == 1
    assert second == 0
    assert stored == {"roe": 0.1, "revenue": 100.0, "source": "first"}


def test_merge_financial_missing_fields_only_fills_empty_requested_fields() -> None:
    with sqlite3.connect(":memory:") as conn:
        tushare_financial_rows.upsert_financial_row_preserving_valid(
            conn,
            table_name="market_financial_factors",
            row=pd.Series(
                {
                    "market": "CN",
                    "symbol": "000001.SZ",
                    "report_date": "2026-03-31",
                    "roe": 0.1,
                    "revenue_growth": None,
                    "source": "existing",
                }
            ),
            replace_existing=True,
        )
        changed = tushare_financial_rows.merge_financial_missing_fields(
            conn,
            table_name="market_financial_factors",
            row=pd.Series(
                {
                    "market": "CN",
                    "symbol": "000001.SZ",
                    "report_date": "2026-03-31",
                    "roe": 0.9,
                    "revenue_growth": 0.25,
                    "source": "patch",
                    "updated_at": "2026-04-30T15:00:00",
                }
            ),
            fields=["roe", "revenue_growth"],
        )
        stored = pd.read_sql_query(
            "SELECT roe, revenue_growth, source, updated_at FROM market_financial_factors",
            conn,
        ).iloc[0].to_dict()

    assert changed == 1
    assert stored == {
        "roe": 0.1,
        "revenue_growth": 0.25,
        "source": "existing",
        "updated_at": "2026-04-30T15:00:00",
    }
