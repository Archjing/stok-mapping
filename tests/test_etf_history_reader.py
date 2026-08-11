from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from phase0.data_access.etf_history import ETFAdjustmentCoverageError, ETFHistoryReader
from phase0.data_governance.etf_store import (
    ensure_etf_schema,
    upsert_etf_adj_factors,
    upsert_etf_daily_bars,
)


def _database(tmp_path: Path, *, missing_factor_date: str | None = None) -> Path:
    db_path = tmp_path / "etf.sqlite"
    bars = pd.DataFrame([
        {"symbol": "SH.510300", "date": "2026-01-05", "open": 4.00, "high": 4.10, "low": 3.90, "close": 4.05, "pre_close": 3.95, "change_amount": 0.10, "change_pct": 2.53, "volume": 100.0, "amount": 1000.0, "source": "fixture"},
        {"symbol": "SH.510300", "date": "2026-01-06", "open": 4.10, "high": 4.25, "low": 4.05, "close": 4.20, "pre_close": 4.05, "change_amount": 0.15, "change_pct": 3.70, "volume": 110.0, "amount": 1100.0, "source": "fixture"},
        {"symbol": "SH.510300", "date": "2026-01-07", "open": 4.25, "high": 4.45, "low": 4.20, "close": 4.40, "pre_close": 4.20, "change_amount": 0.20, "change_pct": 4.76, "volume": 120.0, "amount": 1200.0, "source": "fixture"},
        {"symbol": "SH.512480", "date": "2026-01-05", "open": 1.00, "high": 1.10, "low": 0.95, "close": 1.05, "pre_close": 1.00, "change_amount": 0.05, "change_pct": 5.00, "volume": 200.0, "amount": 2000.0, "source": "fixture"},
        {"symbol": "SZ.159915", "date": "2026-01-05", "open": 2.00, "high": 2.10, "low": 1.95, "close": 2.05, "pre_close": 2.00, "change_amount": 0.05, "change_pct": 2.50, "volume": 300.0, "amount": 3000.0, "source": "fixture"},
    ])
    factors = pd.DataFrame([
        {"symbol": "SH.510300", "date": "2026-01-05", "adj_factor": 1.0, "source": "fixture"},
        {"symbol": "SH.510300", "date": "2026-01-06", "adj_factor": 1.1, "source": "fixture"},
        {"symbol": "SH.510300", "date": "2026-01-07", "adj_factor": 99.0, "source": "future-poison"},
        {"symbol": "SH.512480", "date": "2026-01-05", "adj_factor": 1.0, "source": "fixture"},
        {"symbol": "SZ.159915", "date": "2026-01-05", "adj_factor": 1.0, "source": "fixture"},
    ])
    if missing_factor_date is not None:
        factors = factors[factors["date"] != missing_factor_date]
    with sqlite3.connect(db_path) as conn:
        ensure_etf_schema(conn)
        upsert_etf_daily_bars(conn, bars, fetched_at="2026-08-11T00:00:00")
        upsert_etf_adj_factors(conn, factors, fetched_at="2026-08-11T00:00:00")
    return db_path


def test_raw_reader_returns_unadjusted_exchange_prices(tmp_path):
    reader = ETFHistoryReader(_database(tmp_path))
    frame = reader.load_raw("510300.SH", date(2026, 1, 5), date(2026, 1, 5))
    assert frame.loc[0, "close"] == 4.05
    assert frame.loc[0, "price_mode"] == "raw"


@pytest.mark.parametrize(
    ("requested", "expected"),
    [("510300.SH", "SH.510300"), ("SH.512480", "SH.512480"), ("159915.SZ", "SZ.159915")],
)
def test_reader_normalizes_supported_exchange_qualified_symbols(tmp_path, requested, expected):
    reader = ETFHistoryReader(_database(tmp_path))
    frame = reader.load_raw(requested, date(2026, 1, 5), date(2026, 1, 5))
    assert frame.loc[0, "symbol"] == expected


@pytest.mark.parametrize("symbol", ["510300", "CSI.931865", "931865.CSI", "not-a-symbol"])
def test_invalid_etf_symbol_is_rejected_before_sqlite_access(tmp_path, symbol):
    reader = ETFHistoryReader(tmp_path / "missing" / "etf.sqlite")
    with pytest.raises(ValueError):
        reader.load_raw(symbol, date(2026, 1, 5), date(2026, 1, 6))


def test_qfq_asof_never_queries_or_uses_future_factor(tmp_path):
    reader = ETFHistoryReader(_database(tmp_path))
    frame = reader.load_qfq_asof(
        "SH.510300",
        date(2026, 1, 5),
        date(2026, 1, 7),
        date(2026, 1, 6),
    )
    assert frame["date"].max().date() == date(2026, 1, 6)
    assert frame.loc[frame["date"] == pd.Timestamp("2026-01-05"), "close"].iloc[0] == pytest.approx(4.05 / 1.1)


def test_qfq_asof_formula_uses_factor_at_or_before_asof(tmp_path):
    reader = ETFHistoryReader(_database(tmp_path))
    frame = reader.load_qfq_asof(
        "SH.510300",
        date(2026, 1, 5),
        date(2026, 1, 6),
        date(2026, 1, 6),
    )
    assert frame.loc[0, "close"] == pytest.approx(4.05 * 1.0 / 1.1)
    assert frame.loc[0, "price_mode"] == "qfq_asof"


def test_missing_factor_for_an_actual_bar_fails_closed(tmp_path):
    reader = ETFHistoryReader(_database(tmp_path, missing_factor_date="2026-01-05"))
    with pytest.raises(ETFAdjustmentCoverageError, match="missing factor"):
        reader.load_qfq_asof(
            "SH.510300",
            date(2026, 1, 5),
            date(2026, 1, 6),
            date(2026, 1, 6),
        )


def test_no_factor_at_or_before_asof_fails_closed(tmp_path):
    db_path = _database(tmp_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM market_etf_adj_factors WHERE symbol='SH.510300' AND date<='2026-01-06'")
    reader = ETFHistoryReader(db_path)
    with pytest.raises(ETFAdjustmentCoverageError, match="as-of factor"):
        reader.load_qfq_asof(
            "SH.510300",
            date(2026, 1, 5),
            date(2026, 1, 6),
            date(2026, 1, 6),
        )


def test_end_date_after_asof_is_truncated(tmp_path):
    reader = ETFHistoryReader(_database(tmp_path))
    as_of_date = date(2026, 1, 6)
    frame = reader.load_qfq_asof(
        "SH.510300",
        date(2026, 1, 5),
        date(2026, 1, 7),
        as_of_date,
    )
    assert frame["date"].max().date() == as_of_date
