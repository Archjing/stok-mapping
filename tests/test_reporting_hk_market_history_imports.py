from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import scripts.export_hk_market_history_report as legacy_hk_market_history
from phase0.reporting import hk_market_history
from phase0.reporting.hk_market_history import build_report


def test_hk_market_history_report_new_imports_are_available() -> None:
    assert callable(build_report)


def test_legacy_hk_market_history_report_script_aliases_reporting_module() -> None:
    assert legacy_hk_market_history is hk_market_history
    assert legacy_hk_market_history.build_report is build_report


def test_legacy_hk_market_history_report_script_help_runs_directly() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/export_hk_market_history_report.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--output" in result.stdout


def test_hk_market_history_report_builds_from_local_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "hk.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE hk_daily_bars (
                symbol TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                adjusted_close REAL,
                volume REAL,
                source TEXT,
                hk TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO hk_daily_bars (
                symbol, date, open, high, low, close, adjusted_close, volume, source, hk
            )
            VALUES ('HK.00700', '2026-06-25', 100, 101, 99, 100.5, 100.5, 123456, 'test', 'HK')
            """
        )
        conn.execute(
            """
            CREATE TABLE hk_data_source_runs (
                id INTEGER PRIMARY KEY,
                fetched_at TEXT,
                source TEXT,
                latest_trade_date TEXT,
                coverage REAL,
                fetched_rows INTEGER,
                inserted_rows INTEGER,
                updated_rows INTEGER,
                status TEXT,
                message TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO hk_data_source_runs (
                fetched_at, source, latest_trade_date, coverage, fetched_rows, inserted_rows, updated_rows, status, message
            )
            VALUES ('2026-06-26T08:00:00', 'test', '2026-06-25', 1.0, 1, 1, 0, 'updated', '')
            """
        )

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
phase0:
  hk_market_history:
    path: {db_path}
    daily_table: hk_daily_bars
    source_audit_table: hk_data_source_runs
    provider: test
    symbols:
      - HK.00700
    max_staleness_days: 3650
""",
        encoding="utf-8",
    )
    output_path = tmp_path / "report.md"

    result = build_report(config_path, output_path)

    assert result == output_path
    content = output_path.read_text(encoding="utf-8")
    assert "HK Market History Batch Load Report" in content
    assert "腾讯控股" in content
    assert "Coverage: 1.0000" in content
