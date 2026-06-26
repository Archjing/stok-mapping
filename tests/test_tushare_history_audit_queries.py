from __future__ import annotations

import sqlite3

from phase0.data_governance.backfills import tushare_history
from phase0.data_governance.backfills import tushare_history_audit_queries


def _create_history_audit_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE market_daily_bars (
            market TEXT,
            symbol TEXT,
            date TEXT,
            adjust_type TEXT
        );
        CREATE TABLE market_daily_basic (
            market TEXT,
            symbol TEXT,
            date TEXT,
            pe_ratio REAL,
            pb_ratio REAL,
            turnover_rate REAL
        );
        CREATE TABLE market_adj_factors (
            market TEXT,
            symbol TEXT,
            date TEXT,
            adj_factor REAL
        );
        CREATE TABLE market_dividends (
            market TEXT,
            symbol TEXT,
            ann_date TEXT,
            ex_date TEXT,
            record_date TEXT
        );
        CREATE TABLE market_financial_factors (
            market TEXT,
            symbol TEXT,
            report_date TEXT,
            announce_date TEXT,
            roe REAL,
            revenue_growth REAL,
            profit_growth REAL,
            operating_cash_flow_to_net_profit REAL,
            debt_to_asset REAL
        );
        """
    )
    conn.execute("INSERT INTO market_daily_bars VALUES ('CN', '000001.SZ', '2026-01-02', 'bfq')")
    conn.execute("INSERT INTO market_daily_bars VALUES ('CN', '000001.SZ', '2026-01-02', 'qfq')")
    conn.execute("INSERT INTO market_daily_basic VALUES ('CN', '000001.SZ', '2026-01-02', 10.0, NULL, 2.0)")
    conn.execute("INSERT INTO market_adj_factors VALUES ('CN', '000001.SZ', '2026-01-02', 1.0)")
    conn.execute("INSERT INTO market_dividends VALUES ('CN', '000001.SZ', '2026-01-02', NULL, NULL)")
    conn.execute(
        "INSERT INTO market_financial_factors VALUES ('CN', '000001.SZ', '2026-01-02', '2026-01-03', 0.1, 0.2, 0.3, 1.0, 0.4)"
    )


def _create_financial_backfill_audit_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE tushare_financial_backfill_tasks (
            period TEXT,
            symbol TEXT,
            status TEXT
        );
        CREATE TABLE market_financial_factors (
            market TEXT,
            symbol TEXT,
            report_date TEXT,
            announce_date TEXT,
            roe REAL,
            revenue_growth REAL,
            profit_growth REAL,
            operating_cash_flow_to_net_profit REAL,
            debt_to_asset REAL
        );
        """
    )
    conn.execute("INSERT INTO tushare_financial_backfill_tasks VALUES ('2026-03-31', '000001.SZ', 'fetched')")
    conn.execute("INSERT INTO tushare_financial_backfill_tasks VALUES ('2026-03-31', '000002.SZ', 'empty')")
    conn.execute("INSERT INTO tushare_financial_backfill_tasks VALUES ('2026-03-31', '000003.SZ', 'failed')")
    conn.execute("INSERT INTO tushare_financial_backfill_tasks VALUES ('2026-03-31', '000004.SZ', 'pending')")
    conn.execute(
        "INSERT INTO market_financial_factors VALUES ('CN', '000001.SZ', '2026-03-31', '2026-04-30', 0.1, 0.2, NULL, 1.0, 0.4)"
    )


def test_tushare_history_audit_query_helpers_are_import_compatible() -> None:
    assert tushare_history._coverage_audit is tushare_history_audit_queries.coverage_audit
    assert tushare_history._financial_backfill_audit is tushare_history_audit_queries.financial_backfill_audit


def test_coverage_audit_query_preserves_history_rows() -> None:
    with sqlite3.connect(":memory:") as conn:
        _create_history_audit_tables(conn)
        audit = tushare_history_audit_queries.coverage_audit(
            conn,
            local_cfg={},
            start_date="2026-01-02",
            end_date="2026-01-02",
        )

    rows = {(row["table"], row["field"]): row for row in audit.to_dict("records")}
    assert rows[("market_daily_bars", "bfq.ohlcv")]["rows"] == 1
    assert rows[("market_daily_bars", "qfq.ohlcv")]["rows"] == 1
    assert rows[("market_daily_basic", "pb_ratio")]["non_null_ratio"] == 0.0
    assert rows[("market_adj_factors", "adj_factor")]["non_null_ratio"] == 1.0
    assert rows[("market_dividends", "dividend_events")]["rows"] == 1


def test_financial_backfill_audit_query_preserves_task_and_factor_counts() -> None:
    with sqlite3.connect(":memory:") as conn:
        _create_financial_backfill_audit_tables(conn)
        audit = tushare_history_audit_queries.financial_backfill_audit(
            conn,
            task_table="tushare_financial_backfill_tasks",
            financial_table="market_financial_factors",
            periods=["2026-03-31"],
        )

    row = audit.iloc[0].to_dict()
    assert row["target_symbols"] == 4
    assert row["fetched_symbols"] == 1
    assert row["empty_symbols"] == 1
    assert row["failed_symbols"] == 1
    assert row["pending_symbols"] == 1
    assert row["factor_rows"] == 1
    assert row["profit_growth_coverage"] == 0.0
    assert row["debt_to_asset_coverage"] == 1.0
