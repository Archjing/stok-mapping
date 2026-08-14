from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from quant.data_governance.sqlite_index_governance import (
    SQLiteBenchmarkQuery,
    run_index_removal_benchmark,
)


def _build_source_database(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE market_adj_factors (
                market TEXT NOT NULL,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                adj_factor REAL NOT NULL,
                PRIMARY KEY (market, symbol, date)
            );
            CREATE INDEX idx_market_adj_factors_symbol_date
            ON market_adj_factors(market, symbol, date);
            """
        )
        conn.executemany(
            "INSERT INTO market_adj_factors(market, symbol, date, adj_factor) VALUES (?, ?, ?, ?)",
            [
                ("CN", "000001.SZ", "2026-08-12", 1.00),
                ("CN", "000001.SZ", "2026-08-13", 1.05),
                ("CN", "000001.SZ", "2026-08-14", 1.10),
            ],
        )


def test_index_removal_benchmark_uses_a_copy_and_preserves_query_results(tmp_path: Path) -> None:
    source_path = tmp_path / "source.sqlite"
    copy_path = tmp_path / "working" / "source-copy.sqlite"
    _build_source_database(source_path)

    result = run_index_removal_benchmark(
        source_path=source_path,
        copy_path=copy_path,
        index_name="idx_market_adj_factors_symbol_date",
        queries=(
            SQLiteBenchmarkQuery(
                name="symbol_range",
                sql=(
                    "SELECT date, adj_factor FROM market_adj_factors "
                    "WHERE market = ? AND symbol = ? AND date BETWEEN ? AND ? ORDER BY date"
                ),
                parameters=("CN", "000001.SZ", "2026-08-12", "2026-08-14"),
            ),
        ),
    )

    assert source_path.exists()
    assert copy_path.exists()
    assert result.source_path == source_path.resolve()
    assert result.copy_path == copy_path.resolve()
    assert result.removed_index_bytes > 0
    assert result.before[0].row_count == 3
    assert result.before[0].result_sha256 == result.after_drop[0].result_sha256
    assert result.after_drop[0].result_sha256 == result.after_optimize[0].result_sha256
    assert result.after_drop[0].query_plan
    assert "idx_market_adj_factors_symbol_date" not in "\n".join(result.after_drop[0].query_plan)
    assert result.after_optimize[0].query_plan

    with sqlite3.connect(source_path) as source_conn:
        assert source_conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
            ("idx_market_adj_factors_symbol_date",),
        ).fetchone()
    with sqlite3.connect(copy_path) as copy_conn:
        assert not copy_conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
            ("idx_market_adj_factors_symbol_date",),
        ).fetchone()


def test_index_removal_benchmark_rejects_a_copy_path_that_is_the_source(tmp_path: Path) -> None:
    source_path = tmp_path / "source.sqlite"
    _build_source_database(source_path)

    with pytest.raises(ValueError, match="copy_path must differ from source_path"):
        run_index_removal_benchmark(
            source_path=source_path,
            copy_path=source_path,
            index_name="idx_market_adj_factors_symbol_date",
            queries=(),
        )
