from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from phase0.data_governance.db_health import _check_cn_market_data
from phase0.data_governance.db_health import _connect as db_connect
from phase0.update_history import _latest_stats


def _seed_history_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE market_daily_bars (
                market TEXT,
                symbol TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                adjust_type TEXT
            );
            CREATE TABLE market_stocks (
                market TEXT,
                symbol TEXT,
                name TEXT,
                exchange TEXT,
                board TEXT,
                sector TEXT,
                industry TEXT,
                area TEXT,
                country TEXT,
                currency TEXT,
                list_status TEXT,
                list_date TEXT,
                delist_date TEXT,
                is_hs_connect TEXT,
                controller TEXT,
                controller_type TEXT,
                market_cap REAL,
                pe_ratio REAL,
                pb_ratio REAL,
                turnover_rate REAL
            );
            CREATE TABLE market_daily_basic (
                market TEXT,
                symbol TEXT,
                date TEXT,
                market_cap REAL,
                circ_mv REAL,
                pe_ratio REAL,
                pb_ratio REAL,
                turnover_rate REAL
            );
            CREATE TABLE market_adj_factors (
                market TEXT,
                symbol TEXT,
                date TEXT,
                adj_factor REAL,
                source TEXT
            );
            CREATE TABLE trading_calendar (
                date TEXT,
                is_open INTEGER
            );
            """
        )
        conn.executemany(
            "INSERT INTO market_stocks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("CN", "SH.600001", "A", "", "", "", "", "", "", "", "上市", "2020-01-01", "", "", "", "", None, None, None, None),
                ("CN", "SH.600002", "B", "", "", "", "", "", "", "", "上市", "2020-01-01", "", "", "", "", None, None, None, None),
                ("CN", "SH.600003", "C", "", "", "", "", "", "", "", "上市", "2026-06-13", "", "", "", "", None, None, None, None),
                ("CN", "SH.600004", "D", "", "", "", "", "", "", "", "退市", "2020-01-01", "2026-06-11", "", "", "", None, None, None, None),
            ],
        )
        conn.executemany(
            "INSERT INTO market_daily_bars VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("CN", "SH.600001", "2026-06-12", 1, 1, 1, 1, 1, 1, "qfq"),
                ("CN", "SH.600002", "2026-06-12", 1, 1, 1, 1, 1, 1, "qfq"),
                ("CN", "SH.600004", "2026-06-10", 1, 1, 1, 1, 1, 1, "qfq"),
            ],
        )
        conn.executemany(
            "INSERT INTO trading_calendar VALUES (?, ?)",
            [
                ("2026-06-10", 1),
                ("2026-06-11", 1),
                ("2026-06-12", 1),
            ],
        )
        conn.commit()


def test_latest_stats_uses_eligible_symbol_denominator(tmp_path: Path) -> None:
    db_path = tmp_path / "history.sqlite"
    _seed_history_db(db_path)

    with sqlite3.connect(db_path) as conn:
        latest, coverage, latest_symbols, total_symbols = _latest_stats(
            conn,
            daily_table="market_daily_bars",
            meta_table="market_stocks",
            market="CN",
            adjust_type="qfq",
        )

    assert str(latest) == "2026-06-12"
    assert latest_symbols == 2
    assert total_symbols == 2
    assert coverage == 1.0


def test_db_health_latest_coverage_uses_eligible_symbol_denominator(tmp_path: Path) -> None:
    db_path = tmp_path / "history.sqlite"
    _seed_history_db(db_path)

    config = {
        "local_history": {
            "path": str(db_path),
            "market": "CN",
            "adjust_type": "qfq",
            "daily_table": "market_daily_bars",
            "meta_table": "market_stocks",
            "daily_basic_table": "market_daily_basic",
            "adj_factor_table": "market_adj_factors",
            "calendar_table": "trading_calendar",
            "min_snapshot_coverage": 0.80,
            "max_snapshot_staleness_days": 1,
        },
        "manual_history_update": {
            "min_latest_coverage": 0.80,
            "max_staleness_days": 1,
        },
    }

    with db_connect(db_path) as conn:
        summary: list = []
        findings: list = []
        _check_cn_market_data(conn=conn, config=config, as_of=date(2026, 6, 12), summary=summary, findings=findings)

    coverage_row = next(row for row in summary if row.check_id == "cn.daily.latest_coverage")
    assert coverage_row.value == "2/2 (100.00%)"
    assert coverage_row.status == "pass"
