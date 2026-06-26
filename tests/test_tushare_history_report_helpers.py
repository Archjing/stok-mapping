from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from phase0.data_governance.backfills import tushare_history
from phase0.data_governance.backfills import tushare_history_reports


def test_tushare_history_report_helpers_are_import_compatible() -> None:
    assert tushare_history.HISTORY_BACKFILL_SUMMARY_COLUMNS is tushare_history_reports.HISTORY_BACKFILL_SUMMARY_COLUMNS
    assert tushare_history.FINANCIAL_BACKFILL_DETAIL_COLUMNS is tushare_history_reports.FINANCIAL_BACKFILL_DETAIL_COLUMNS
    assert tushare_history.FINANCIAL_BACKFILL_SUMMARY_COLUMNS is tushare_history_reports.FINANCIAL_BACKFILL_SUMMARY_COLUMNS
    assert tushare_history._history_audit_paths is tushare_history_reports.history_audit_paths
    assert tushare_history._financial_audit_paths is tushare_history_reports.financial_audit_paths
    assert tushare_history._write_history_detail_audit is tushare_history_reports.write_history_detail_audit
    assert tushare_history._write_financial_backfill_audit is tushare_history_reports.write_financial_backfill_audit
    assert tushare_history._append_summary_row is tushare_history_reports.append_summary_row
    assert tushare_history._history_summary_row is tushare_history_reports.history_summary_row
    assert tushare_history._financial_summary_row is tushare_history_reports.financial_summary_row


def test_tushare_history_report_helpers_write_summary_and_detail_files(tmp_path: Path) -> None:
    audit = pd.DataFrame(
        [
            {
                "table": "market_daily_basic",
                "field": "pe_ttm",
                "start_date": "2026-01-02",
                "end_date": "2026-01-03",
                "rows": 2,
                "non_null_ratio": 0.5,
            }
        ]
    )
    detail_csv = tmp_path / "detail.csv"
    detail_md = tmp_path / "detail.md"
    summary_csv = tmp_path / "summary.csv"
    summary_md = tmp_path / "summary.md"

    tushare_history_reports.write_history_detail_audit(
        audit=audit,
        output_csv=detail_csv,
        output_md=detail_md,
        warnings=["sample warning"],
    )
    row = tushare_history_reports.history_summary_row(
        status="ok",
        start_date="2026-01-02",
        end_date="2026-01-03",
        limit_dates=None,
        limit_periods=None,
        skip_existing=True,
        include_daily_basic=True,
        include_adj_factor=False,
        include_dividends=False,
        include_financial=False,
        max_requests_per_minute=180,
        daily_basic_target_dates=2,
        daily_basic_fetched_dates=2,
        daily_basic_inserted_rows=20,
        adj_factor_target_dates=0,
        adj_factor_fetched_dates=0,
        adj_factor_inserted_rows=0,
        dividend_inserted_rows=0,
        financial_target_periods=0,
        financial_fetched_periods=0,
        financial_inserted_rows=0,
        warnings=["sample warning"],
        detail_csv=detail_csv,
        detail_md=detail_md,
        run_started_at="2026-01-02T00:00:00",
    )
    tushare_history_reports.append_summary_row(
        summary_csv=summary_csv,
        summary_md=summary_md,
        columns=tushare_history_reports.HISTORY_BACKFILL_SUMMARY_COLUMNS,
        row=row,
        title="# Summary",
        warnings=["sample warning"],
    )

    assert pd.read_csv(detail_csv).iloc[0]["field"] == "pe_ttm"
    assert "sample warning" in detail_md.read_text(encoding="utf-8")
    assert pd.read_csv(summary_csv).iloc[0]["status"] == "ok"
    assert "daily_basic 2/2" in summary_md.read_text(encoding="utf-8")


def test_tushare_history_missing_token_path_writes_reports(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TUSHARE_TEST_TOKEN", raising=False)
    db_path = tmp_path / "history.sqlite"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
phase0:
  local_history:
    path: "{db_path}"
    daily_table: "market_daily_bars"
    daily_basic_table: "market_daily_basic"
    adj_factor_table: "market_adj_factors"
    dividend_table: "market_dividends"
    financial_table: "market_financial_factors"
  data_sources:
    tushare:
      enabled: true
      token_env: "TUSHARE_TEST_TOKEN"
""",
        encoding="utf-8",
    )
    with sqlite3.connect(db_path) as conn:
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
        conn.execute("INSERT INTO market_daily_basic VALUES ('CN', '000001.SZ', '2026-01-02', 10.0, 1.0, 2.0)")
        conn.execute("INSERT INTO market_adj_factors VALUES ('CN', '000001.SZ', '2026-01-02', 1.0)")
        conn.execute("INSERT INTO market_dividends VALUES ('CN', '000001.SZ', '2026-01-02', NULL, NULL)")
        conn.execute("INSERT INTO market_financial_factors VALUES ('CN', '000001.SZ', '2026-01-02', 0.1, 0.2, 0.3, 1.0, 0.4)")

    result = tushare_history.backfill_tushare_history_from_config(
        config_path,
        start_date="2026-01-02",
        end_date="2026-01-02",
    )

    assert result.status == "missing_tushare_token"
    assert result.audit_csv.exists()
    assert result.audit_md.exists()
    assert "TUSHARE_TEST_TOKEN" in result.audit_md.read_text(encoding="utf-8")
    summary_csv = tmp_path / "reports" / "database_health" / "tushare_history_backfill_audit_summary.csv"
    assert pd.read_csv(summary_csv).iloc[-1]["status"] == "missing_tushare_token"
