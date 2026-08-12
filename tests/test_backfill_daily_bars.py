from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

from quant.data_access import local_history
from quant.data_governance.backfills import daily_bars


@pytest.fixture(autouse=True)
def restore_local_history_configuration() -> Iterator[None]:
    original_config = vars(local_history._settings).copy()
    try:
        yield
    finally:
        local_history.configure_local_history(original_config)


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "history.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE trading_calendar (
                exchange TEXT, date TEXT, is_open INTEGER, previous_trade_date TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO trading_calendar VALUES ('SSE', ?, 1, ?)",
            [("2016-01-04", ""), ("2016-01-05", "2016-01-04"), ("2016-01-06", "2016-01-05")],
        )
        conn.execute(
            """
            CREATE TABLE market_daily_bars (
                market TEXT NOT NULL,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                adjust_type TEXT NOT NULL,
                open REAL, high REAL, low REAL, close REAL,
                volume REAL, amount REAL, adjusted_close REAL,
                change_pct REAL, change_amount REAL, amplitude REAL, turnover_rate REAL
            )
            """
        )
        # One pre-existing day (2016-01-05) that must not be refetched.
        conn.execute(
            "INSERT INTO market_daily_bars VALUES ('CN','SH.600000','2016-01-05','bfq',1,2,0.5,1.5,100,1000,1.5,1,0.5,100,1)",
        )
        conn.execute(
            """
            CREATE TABLE market_daily_basic (
                market TEXT, symbol TEXT, date TEXT,
                market_cap REAL, circ_mv REAL, pe_ratio REAL, pb_ratio REAL, turnover_rate REAL
            )
            """
        )
    return db_path


def _write_config(tmp_path: Path, db_path: Path) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
quant:
  local_history:
    path: "{db_path}"
  data_sources:
    tushare:
      enabled: true
      token_env: "TUSHARE_TOKEN"
"""
    )
    return config_path


def test_backfill_daily_bars_fills_missing_dates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)
    config_path = _write_config(tmp_path, db_path)
    monkeypatch.setenv("TUSHARE_TOKEN", "fake-token")

    def fake_fetch(trade_date, *, adjust_types, cfg):
        date_text = pd.Timestamp(trade_date).strftime("%Y-%m-%d")
        rows = pd.DataFrame(
            [
                {
                    "market": "CN",
                    "symbol": "SH.600000",
                    "date": date_text,
                    "adjust_type": adjust_type,
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.5,
                    "close": 10.5,
                    "volume": 1000.0,
                    "amount": 1_000_000.0,
                    "adjusted_close": 10.5,
                    "change_pct": 1.0,
                    "change_amount": 0.1,
                    "amplitude": 14.3,
                    "turnover_rate": 0.5,
                }
                for adjust_type in adjust_types
            ]
        )
        meta = pd.DataFrame(
            [
                {
                    "market": "CN",
                    "symbol": "SH.600000",
                    "date": date_text,
                    "market_cap": 1e10,
                    "circ_mv": 8e9,
                    "pe_ratio": 10.0,
                    "pb_ratio": 1.0,
                    "turnover_rate": 0.5,
                }
            ]
        )
        return rows, meta

    monkeypatch.setattr(daily_bars, "fetch_tushare_trade_date", fake_fetch)
    result = daily_bars.backfill_daily_bars_from_config(
        config_path, start_date="2016-01-01", end_date="2016-01-31"
    )

    assert result.status == "ok"
    assert result.target_dates == 3
    assert result.fetched_dates == 2  # 2016-01-05 already exists (bfq present)
    assert result.skipped_existing_dates == 1
    # 2 missing days x 2 adjust types
    assert result.inserted_rows == 4
    assert result.daily_basic_inserted_rows == 2

    with sqlite3.connect(db_path) as conn:
        bars = conn.execute(
            "SELECT date, adjust_type, close FROM market_daily_bars ORDER BY date, adjust_type"
        ).fetchall()
        assert bars == [
            ("2016-01-04", "bfq", 10.5),
            ("2016-01-04", "qfq", 10.5),
            ("2016-01-05", "bfq", 1.5),  # pre-existing row untouched
            ("2016-01-06", "bfq", 10.5),
            ("2016-01-06", "qfq", 10.5),
        ]
        basics = conn.execute(
            "SELECT symbol, date, pe_ratio FROM market_daily_basic ORDER BY date"
        ).fetchall()
        assert basics == [
            ("SH.600000", "2016-01-04", 10.0),
            ("SH.600000", "2016-01-06", 10.0),
        ]


def test_backfill_daily_bars_requires_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)
    config_path = _write_config(tmp_path, db_path)
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    result = daily_bars.backfill_daily_bars_from_config(
        config_path, start_date="2016-01-01", end_date="2016-01-31"
    )
    assert result.status == "missing_tushare_token"
    assert result.fetched_dates == 0


def test_backfill_daily_bars_records_fetch_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)
    config_path = _write_config(tmp_path, db_path)
    monkeypatch.setenv("TUSHARE_TOKEN", "fake-token")

    def failing_fetch(trade_date, *, adjust_types, cfg):
        raise RuntimeError("boom")

    monkeypatch.setattr(daily_bars, "fetch_tushare_trade_date", failing_fetch)
    result = daily_bars.backfill_daily_bars_from_config(
        config_path, start_date="2016-01-01", end_date="2016-01-31"
    )
    assert result.status == "ok"  # existing 2016-01-05 row was skipped, so run is not empty
    assert result.fetched_dates == 0
    assert any("boom" in warning for warning in result.warnings)
