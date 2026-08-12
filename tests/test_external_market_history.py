from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd

from phase0.data_governance import external_market_history


def _settings(db_path: Path) -> external_market_history.MarketHistorySettings:
    return external_market_history.MarketHistorySettings(
        path=db_path,
        daily_table="us_daily_bars",
        source_audit_table="us_data_source_runs",
        provider="yfinance",
        symbols=["^SOX", "^VIX"],
        years=5,
        max_staleness_days=3,
        min_symbol_coverage=1.0,
        market_name="us_market",
    )


def test_market_history_marks_all_empty_provider_fetches_as_source_failed(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path / "data" / "us.sqlite")

    monkeypatch.setattr(external_market_history, "fetch_external_market_daily", lambda symbol, settings: pd.DataFrame())

    result = external_market_history._update_market_history(settings, check_only=False)

    assert result.status == "source_failed"
    assert not result.ok
    assert result.fetched_rows == 0
    assert len(result.warnings) == 2


def test_market_history_uses_incremental_fetch_window_after_initial_load(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path / "data" / "us.sqlite")
    settings.years = 5
    calls: list[tuple[str, int, date | None]] = []
    settings.path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(settings.path) as conn:
        external_market_history._ensure_tables(conn, settings)
        for symbol in settings.symbols:
            conn.execute(
                """
                INSERT INTO us_daily_bars
                (market, symbol, date, open, high, low, close, adjusted_close, volume, source, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("US", symbol, "2026-08-10", 1, 1, 1, 1, 1, 0, "test", "2026-08-11T08:00:00"),
            )

    def fake_fetch(symbol: str, supplied_settings: external_market_history.MarketHistorySettings) -> pd.DataFrame:
        calls.append((symbol, supplied_settings.years, supplied_settings.fetch_start_date))
        return pd.DataFrame()

    monkeypatch.setattr(external_market_history, "fetch_external_market_daily", fake_fetch)

    external_market_history._update_market_history(settings, check_only=False)

    assert calls == [
        ("^SOX", 1, date(2026, 8, 3)),
        ("^VIX", 1, date(2026, 8, 3)),
    ]
