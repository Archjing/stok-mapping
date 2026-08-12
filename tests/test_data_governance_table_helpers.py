from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

import quant.data_governance.update_history as governance_update_history
from quant.data_governance.daily_basic import ensure_daily_basic_table, upsert_daily_basic_rows
from quant.data_governance.sql import safe_identifier, to_sql_value


def test_safe_identifier_accepts_simple_sql_identifiers() -> None:
    assert safe_identifier("market_daily_basic") == "market_daily_basic"
    assert safe_identifier("_tmp1") == "_tmp1"


def test_safe_identifier_rejects_unsafe_values() -> None:
    for value in ["", "1table", "market-daily", "market daily", "market;drop"]:
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            safe_identifier(value)


def test_to_sql_value_converts_pandas_missing_values() -> None:
    assert to_sql_value(pd.NA) is None
    assert to_sql_value(float("nan")) is None
    assert to_sql_value(3.5) == 3.5
    assert to_sql_value("x") == "x"


def test_daily_basic_table_helper_creates_and_upserts_rows() -> None:
    rows = pd.DataFrame(
        [
            {
                "market": "CN",
                "symbol": "SH.600000",
                "date": "2026-06-25",
                "market_cap": 100.0,
                "circ_mv": 80.0,
                "pe_ratio": 12.5,
                "pb_ratio": 1.2,
                "turnover_rate": 0.8,
            },
            {
                "market": "CN",
                "symbol": "SZ.000001",
                "date": "2026-06-25",
                "market_cap": pd.NA,
                "circ_mv": 90.0,
                "pe_ratio": 9.0,
                "pb_ratio": 0.9,
                "turnover_rate": 1.1,
            },
        ]
    )
    with sqlite3.connect(":memory:") as conn:
        ensure_daily_basic_table(conn, table_name="market_daily_basic")
        inserted = upsert_daily_basic_rows(conn, table_name="market_daily_basic", rows=rows)
        fetched = pd.read_sql_query(
            "SELECT symbol, date, market_cap, circ_mv, pe_ratio, pb_ratio, turnover_rate "
            "FROM market_daily_basic ORDER BY symbol",
            conn,
        )

    assert inserted == 2
    records = fetched.to_dict("records")
    assert records[0] == {
        "symbol": "SH.600000",
        "date": "2026-06-25",
        "market_cap": 100.0,
        "circ_mv": 80.0,
        "pe_ratio": 12.5,
        "pb_ratio": 1.2,
        "turnover_rate": 0.8,
    }
    assert records[1]["symbol"] == "SZ.000001"
    assert records[1]["date"] == "2026-06-25"
    assert pd.isna(records[1]["market_cap"])
    assert {
        key: records[1][key]
        for key in ["circ_mv", "pe_ratio", "pb_ratio", "turnover_rate"]
    } == {
        "circ_mv": 90.0,
        "pe_ratio": 9.0,
        "pb_ratio": 0.9,
        "turnover_rate": 1.1,
    }


def test_update_history_uses_shared_table_helpers() -> None:
    assert governance_update_history._safe_identifier is safe_identifier
    assert governance_update_history._to_sql_value is to_sql_value
    assert governance_update_history._ensure_daily_basic_table is ensure_daily_basic_table
    assert governance_update_history._upsert_daily_basic_rows is upsert_daily_basic_rows
