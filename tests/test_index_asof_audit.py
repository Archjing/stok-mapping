from __future__ import annotations

import sqlite3

import pandas as pd

from quant.data_governance.index_asof_audit import run_index_asof_audit


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
        conn.execute(
            """
            INSERT INTO market_index_bars
            VALUES ('CN', 'SH.000300', '2024-04-01', 'daily', 3500.0)
            """
        )
        conn.execute(
            """
            CREATE TABLE trading_calendar (
                exchange TEXT,
                date TEXT,
                is_open INTEGER
            )
            """
        )
        conn.execute("INSERT INTO trading_calendar VALUES ('SSE', '2024-04-01', 1)")


def test_index_asof_audit_marks_missing_constituent_and_weight_tables(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite"
    _create_base_db(db_path)
    folds_path = tmp_path / "folds.csv"
    pd.DataFrame(
        [
            {
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 4,
                "valid_start": "2024-04-01",
                "valid_end": "2025-03-31",
                "universe_as_of_date": "2024-03-29",
            }
        ]
    ).to_csv(folds_path, index=False)

    result = run_index_asof_audit(
        config={
            "benchmark_symbol": "SH.000300",
            "local_history": {"path": str(db_path), "index_table": "market_index_bars"},
        },
        root=tmp_path,
        candidate_folds_path=folds_path,
        output_dir=tmp_path / "audit",
    )

    assert result.constituent_status == "not_available"
    assert result.weight_status == "not_available"
    capability = pd.read_csv(result.capability_csv_path)
    assert capability.set_index("artifact").loc["benchmark_index_price", "status"] == "available"
    assert capability.set_index("artifact").loc["benchmark_open_day_coverage", "status"] == "available"
    assert capability.set_index("artifact").loc["benchmark_constituents", "status"] == "not_available"
    coverage = pd.read_csv(result.fold_coverage_csv_path)
    assert coverage.iloc[0]["coverage_status"] == "blocked_missing_asof_tables"
    assert "不能做成分或主动权重归因" in result.report_md_path.read_text(encoding="utf-8")


def test_index_asof_audit_detects_available_asof_tables(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite"
    _create_base_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE cn_index_constituents_asof (
                index_code TEXT,
                trade_date TEXT,
                symbol TEXT,
                effective_date TEXT,
                source TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE cn_index_weights_asof (
                index_code TEXT,
                trade_date TEXT,
                symbol TEXT,
                weight REAL,
                asof_time TEXT,
                source TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO cn_index_constituents_asof VALUES ('SH.000300', '2024-04-01', 'SH.600000', '2024-04-01', 'unit')"
        )
        conn.execute(
            "INSERT INTO cn_index_weights_asof VALUES ('SH.000300', '2024-04-01', 'SH.600000', 0.01, '2024-04-01T18:00:00', 'unit')"
        )

    result = run_index_asof_audit(
        config={
            "benchmark_symbol": "SH.000300",
            "local_history": {"path": str(db_path), "index_table": "market_index_bars"},
        },
        root=tmp_path,
        output_dir=tmp_path / "audit",
    )

    capability = pd.read_csv(result.capability_csv_path).set_index("artifact")
    assert result.constituent_status == "available"
    assert result.weight_status == "available"
    assert capability.loc["benchmark_constituents", "asof_status"] == "available"
    assert capability.loc["benchmark_weights", "asof_status"] == "available"
