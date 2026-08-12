from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from quant.data_governance.us_market_features import (
    load_common_market_daily_features,
    load_completed_market_snapshot,
)


def _seed(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE us_daily_bars (date TEXT, symbol TEXT, open REAL, high REAL, low REAL, close REAL, adjusted_close REAL, volume REAL, source TEXT, PRIMARY KEY(symbol, date))")
        conn.executemany(
            "INSERT INTO us_daily_bars VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-08-09", "^SOX", 100, 101, 99, 100, 100, 1, "test"),
                ("2026-08-10", "^SOX", 101, 102, 100, 101, 101, 1, "test"),
                ("2026-08-11", "^SOX", 102, 103, 101, 102, 102, 1, "test"),
                ("2026-08-09", "^VIX", 20, 21, 19, 20, 20, 1, "test"),
                ("2026-08-10", "^VIX", 19, 20, 18, 19, 19, 1, "test"),
            ],
        )


def test_snapshot_uses_latest_common_completed_session(tmp_path: Path) -> None:
    db_path = tmp_path / "us.sqlite"
    _seed(db_path)

    snapshot = load_completed_market_snapshot(db_path, "us_daily_bars", ["^SOX", "^VIX"])

    assert snapshot is not None
    assert snapshot.as_of_date == "2026-08-10"
    assert snapshot.bars["symbol"].tolist() == ["^SOX", "^VIX"]


def test_common_features_do_not_forward_fill_missing_sessions(tmp_path: Path) -> None:
    db_path = tmp_path / "us.sqlite"
    _seed(db_path)

    features = load_common_market_daily_features(
        db_path, "us_daily_bars", ["^SOX", "^VIX"], start=date(2026, 8, 9), end=date(2026, 8, 11)
    )

    assert features["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-08-09", "2026-08-10"]
    assert features.loc[1, "^SOX_return"] == pytest.approx(0.01)


def test_return_uses_each_symbol_previous_session_before_common_date_filter(tmp_path: Path) -> None:
    db_path = tmp_path / "us.sqlite"
    _seed(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO us_daily_bars VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("2026-08-11", "^VIX", 18, 19, 17, 18, 18, 1, "test"),
        )

    features = load_common_market_daily_features(
        db_path, "us_daily_bars", ["^SOX", "^VIX"], start=date(2026, 8, 9), end=date(2026, 8, 11)
    )

    assert features.loc[2, "^SOX_return"] == pytest.approx(102 / 101 - 1)
