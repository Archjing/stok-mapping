from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

from phase0.data_access import local_history
from phase0.data_access.daily_basic_history import (
    load_daily_basic_factor_frame,
    merge_point_in_time_daily_basic,
)
from phase0.data_access.local_history import configure_local_history


@pytest.fixture(autouse=True)
def restore_local_history_configuration() -> Iterator[None]:
    original_config = vars(local_history._settings).copy()
    try:
        yield
    finally:
        configure_local_history(original_config)


@pytest.fixture
def daily_basic_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "history.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE market_daily_basic (
                market TEXT,
                symbol TEXT,
                date TEXT,
                market_cap REAL,
                circ_mv REAL,
                pe_ratio REAL,
                pb_ratio REAL,
                turnover_rate REAL
            )
            """
        )
        conn.executemany(
            "INSERT INTO market_daily_basic VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("CN", "AAA", "2024-01-02", 100, 80, 10, 1.0, 0.5),
                ("CN", "AAA", "2024-01-03", 110, 90, 11, 1.1, 0.6),
                ("CN", "AAA", "2024-02-01", 999, 999, 99, 9.9, 9.9),
            ],
        )
    configure_local_history({"path": str(db_path)})
    return db_path


def test_load_daily_basic_factor_frame_respects_as_of_date(daily_basic_db: Path) -> None:
    frame = load_daily_basic_factor_frame(
        symbols=["AAA"],
        start_date="2024-01-01",
        end_date="2024-01-31",
        as_of_date="2024-01-03",
    )

    assert frame["date"].max() == pd.Timestamp("2024-01-03")
    assert frame.sort_values("date").iloc[-1]["market_cap"] == 110
    assert 999 not in frame["market_cap"].tolist()


def test_load_daily_basic_factor_frame_returns_empty_when_table_is_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "history.sqlite"
    with sqlite3.connect(db_path):
        pass
    configure_local_history({"path": str(db_path)})

    frame = load_daily_basic_factor_frame(
        symbols=["AAA"],
        start_date="2024-01-01",
        end_date="2024-01-31",
    )

    assert frame.empty


def test_load_daily_basic_factor_frame_drops_invalid_symbols(daily_basic_db: Path) -> None:
    with sqlite3.connect(daily_basic_db) as conn:
        conn.executemany(
            "INSERT INTO market_daily_basic VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("CN", "", "2024-01-02", 1, 1, 1, 1, 1),
                ("CN", "   ", "2024-01-02", 2, 2, 2, 2, 2),
                ("CN", None, "2024-01-02", 3, 3, 3, 3, 3),
            ],
        )

    frame = load_daily_basic_factor_frame(
        symbols=[" AAA ", "", "   ", None],
        start_date="2024-01-02",
        end_date="2024-01-02",
    )

    assert frame["symbol"].tolist() == ["AAA"]


def test_merge_point_in_time_daily_basic_matches_exact_date_only(daily_basic_db: Path) -> None:
    panel = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "AAA"],
            "date": ["2024-01-02", "2024-01-03", "2024-01-04"],
        }
    )

    merged = merge_point_in_time_daily_basic(panel, as_of_date="2024-01-04")

    assert merged.loc[merged["date"] == pd.Timestamp("2024-01-02"), "pe_ttm"].item() == 10
    assert merged.loc[merged["date"] == pd.Timestamp("2024-01-03"), "pb"].item() == 1.1
    assert pd.isna(merged.loc[merged["date"] == pd.Timestamp("2024-01-04"), "market_cap"].item())


def test_merge_point_in_time_daily_basic_normalizes_panel_symbol_without_mutating_input(
    daily_basic_db: Path,
) -> None:
    panel = pd.DataFrame({"symbol": [" AAA "], "date": ["2024-01-02"]})
    original = panel.copy(deep=True)

    merged = merge_point_in_time_daily_basic(panel, as_of_date="2024-01-02")

    assert merged["market_cap"].item() == 100
    assert merged["pe_ttm"].item() == 10
    pd.testing.assert_frame_equal(panel, original)
