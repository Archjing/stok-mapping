"""Tests for the China/US macro data source module."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from quant.data_governance.macro_history import (
    MACRO_SERIES,
    ensure_macro_tables,
    upsert_macro_series,
    load_macro_series,
)


def test_macro_series_has_china_and_us_rates() -> None:
    symbols = {s.symbol for s in MACRO_SERIES}
    # China: 10y yield, M2, CPI, social finance
    assert "CN_10Y_YIELD" in symbols
    assert "CN_M2_YOY" in symbols
    assert "CN_CPI_YOY" in symbols
    # US: 10y treasury, fed funds
    assert "US_10Y_YIELD" in symbols
    assert "US_FED_FUNDS" in symbols


def test_ensure_and_upsert_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "macro.sqlite"
    with sqlite3.connect(db) as conn:
        ensure_macro_tables(conn)
    rows = pd.DataFrame({
        "symbol": ["CN_10Y_YIELD", "CN_10Y_YIELD"],
        "date": ["2020-01-02", "2020-01-03"],
        "value": [3.15, 3.14],
    })
    n = upsert_macro_series(db, rows, source="akshare.bond_china_yield")
    assert n >= 2
    # idempotent upsert: same rows again → no duplicate
    upsert_macro_series(db, rows, source="akshare.bond_china_yield")
    out = load_macro_series(db, symbol="CN_10Y_YIELD")
    assert len(out) == 2
    assert out.iloc[0]["value"] == 3.15


def test_load_macro_series_filters_by_date(tmp_path: Path) -> None:
    db = tmp_path / "macro.sqlite"
    with sqlite3.connect(db) as conn:
        ensure_macro_tables(conn)
    upsert_macro_series(
        db,
        pd.DataFrame({
            "symbol": ["CN_10Y_YIELD", "CN_10Y_YIELD"],
            "date": ["2020-01-02", "2021-06-01"],
            "value": [3.0, 2.8],
        }),
        source="test",
    )
    out = load_macro_series(db, symbol="CN_10Y_YIELD", start="2021-01-01")
    assert len(out) == 1
    assert out.iloc[0]["date"] == "2021-06-01"


def test_load_macro_series_unknown_symbol_empty(tmp_path: Path) -> None:
    db = tmp_path / "macro.sqlite"
    with sqlite3.connect(db) as conn:
        ensure_macro_tables(conn)
    out = load_macro_series(db, symbol="NONEXISTENT")
    assert out.empty
