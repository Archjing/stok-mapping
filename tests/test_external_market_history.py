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


def test_settings_flattens_configured_instrument_groups(tmp_path: Path) -> None:
    settings = external_market_history._build_settings(
        {
            "instrument_groups": {
                "core_signal": {"symbols": ["^SOX", "^VIX"], "critical": True},
                "rates": {"symbols": ["^TNX", "^SOX"]},
            }
        },
        root=tmp_path,
        defaults=_settings(tmp_path / "data/us.sqlite"),
        default_symbols=[],
    )

    assert settings.symbols == ["^SOX", "^VIX", "^TNX"]
    assert settings.symbol_groups["core_signal"].critical is True
    assert settings.symbol_groups["rates"].asset_types["^TNX"] == "index"


def test_invalid_ohlc_does_not_replace_existing_valid_bar_and_is_audited(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path / "data" / "us.sqlite")
    settings.symbol_groups = {
        "core_signal": external_market_history.MarketInstrumentGroup(
            name="core_signal", symbols=("^SOX", "^VIX"), critical=True
        )
    }
    settings.symbols = ["^SOX", "^VIX"]
    settings.path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(settings.path) as conn:
        external_market_history._ensure_tables(conn, settings)
        conn.execute(
            """
            INSERT INTO us_daily_bars
            (market, symbol, date, open, high, low, close, adjusted_close, volume, source, fetched_at, hk)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("US_INDEX", "^SOX", "2026-08-10", 10, 11, 9, 10, 10, 0, "seed", "2026-08-10T00:00:00", None),
        )

    def fake_fetch(symbol: str, supplied_settings: external_market_history.MarketHistorySettings) -> pd.DataFrame:
        if symbol == "^SOX":
            return pd.DataFrame(
                [{"date": "2026-08-10", "open": 10, "high": 9, "low": 11, "close": 10, "volume": 0}]
            )
        return pd.DataFrame(
            [{"date": "2026-08-10", "open": 20, "high": 21, "low": 19, "close": 20, "volume": 0}]
        )

    monkeypatch.setattr(external_market_history, "fetch_external_market_daily", fake_fetch)
    result = external_market_history._update_market_history(settings, check_only=False)

    assert result.status == "critical_failed"
    with sqlite3.connect(settings.path) as conn:
        db_close = conn.execute("SELECT close FROM us_daily_bars WHERE symbol = ? AND date = ?", ("^SOX", "2026-08-10")).fetchone()[0]
        audit_status = conn.execute(
            "SELECT status FROM us_data_source_symbol_runs WHERE symbol = ? ORDER BY id DESC LIMIT 1", ("^SOX",)
        ).fetchone()[0]
    assert db_close == 10.0
    assert audit_status == "invalid_data"


def test_noncritical_symbol_fetch_failure_is_audited_as_partial(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path / "data" / "us.sqlite")
    settings.symbol_groups = {
        "core_signal": external_market_history.MarketInstrumentGroup(
            name="core_signal", symbols=("^SOX", "^VIX"), critical=True
        ),
        "rates": external_market_history.MarketInstrumentGroup(name="rates", symbols=("^TNX",)),
    }
    settings.symbols = ["^SOX", "^VIX", "^TNX"]

    def fake_fetch(symbol: str, supplied_settings: external_market_history.MarketHistorySettings) -> pd.DataFrame:
        if symbol == "^TNX":
            raise RuntimeError("provider timeout")
        return pd.DataFrame(
            [{"date": "2026-08-10", "open": 20, "high": 21, "low": 19, "close": 20, "volume": 0}]
        )

    monkeypatch.setattr(external_market_history, "fetch_external_market_daily", fake_fetch)
    result = external_market_history._update_market_history(settings, check_only=False)

    assert result.status == "partial"
    assert result.ok
    with sqlite3.connect(settings.path) as conn:
        rows = conn.execute(
            "SELECT group_name, symbol, status FROM us_data_source_symbol_runs ORDER BY id"
        ).fetchall()
    assert ("rates", "^TNX", "failed") in rows


def test_check_only_does_not_create_missing_database(tmp_path: Path) -> None:
    settings = _settings(tmp_path / "data" / "missing.sqlite")

    result = external_market_history._update_market_history(settings, check_only=True)

    assert result.status == "stale"
    assert not settings.path.exists()
