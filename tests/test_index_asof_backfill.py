from __future__ import annotations

import sqlite3

import pandas as pd

from phase0.data_governance.index_asof_audit import run_index_asof_audit
from phase0.data_governance.index_asof_backfill import normalize_index_weight_rows, upsert_index_asof_rows


def _create_base_db(path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE market_index_bars (
                market TEXT,
                symbol TEXT,
                date TEXT,
                frequency TEXT,
                close REAL
            )
            """
        )
        conn.execute("INSERT INTO market_index_bars VALUES ('CN', 'SH.000300', '2024-01-31', 'daily', 3215.0)")
        conn.execute(
            """
            CREATE TABLE trading_calendar (
                exchange TEXT,
                date TEXT,
                is_open INTEGER
            )
            """
        )
        conn.execute("INSERT INTO trading_calendar VALUES ('SSE', '2024-01-31', 1)")


def test_index_weight_rows_normalize_to_project_symbol_and_asof_fields() -> None:
    raw = pd.DataFrame(
        [
            {"index_code": "000300.SH", "con_code": "600519.SH", "trade_date": "20240131", "weight": "6.191"},
            {"index_code": "000300.SH", "con_code": "300750.SZ", "trade_date": "20240131", "weight": "2.457"},
        ]
    )

    rows = normalize_index_weight_rows(raw, default_index_code="SH.000300", source="unit")

    assert rows["index_code"].tolist() == ["SH.000300", "SH.000300"]
    assert rows["symbol"].tolist() == ["SH.600519", "SZ.300750"]
    assert rows["trade_date"].tolist() == ["2024-01-31", "2024-01-31"]
    assert rows["effective_date"].tolist() == ["2024-01-31", "2024-01-31"]
    assert rows["asof_time"].tolist() == ["2024-01-31T18:00:00", "2024-01-31T18:00:00"]


def test_upsert_index_asof_rows_satisfies_existing_audit(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite"
    _create_base_db(db_path)
    rows = normalize_index_weight_rows(
        pd.DataFrame(
            [
                {"index_code": "000300.SH", "con_code": "600519.SH", "trade_date": "20240131", "weight": 6.191},
                {"index_code": "000300.SH", "con_code": "601318.SH", "trade_date": "20240131", "weight": 2.678},
            ]
        ),
        default_index_code="SH.000300",
        source="unit",
    )

    with sqlite3.connect(db_path) as conn:
        weight_rows, constituent_rows = upsert_index_asof_rows(conn, rows)

    assert weight_rows == 2
    assert constituent_rows == 2

    result = run_index_asof_audit(
        config={
            "benchmark_symbol": "SH.000300",
            "local_history": {"path": str(db_path), "index_table": "market_index_bars"},
        },
        root=tmp_path,
        output_dir=tmp_path / "audit",
    )

    assert result.constituent_status == "available"
    assert result.weight_status == "available"
