from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd

from quant.data_governance import external_market_history


def _daily_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2026-08-07", "2026-08-10"],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "adjusted_close": [101.0, 102.0],
            "volume": [1000, 1100],
        }
    )


def test_europe_history_uses_explicit_eodhd_index_universe(monkeypatch, tmp_path: Path) -> None:
    requested: list[str] = []

    def fake_fetch(symbol: str, settings) -> pd.DataFrame:
        requested.append(symbol)
        assert settings.provider == "eodhd"
        assert settings.api_token_env == "EODHD_API_TOKEN"
        assert settings.source_symbols["^GDAXI"] == "GDAXI.INDX"
        return _daily_frame()

    monkeypatch.setattr(external_market_history, "fetch_external_market_daily", fake_fetch)
    cfg = {
        "europe_market_history": {
            "path": "data/euro_market_history.sqlite",
            "provider": "eodhd",
            "api_token_env": "EODHD_API_TOKEN",
            "symbols": ["^FTSE", "^GDAXI"],
            "source_symbols": {"^FTSE": "FTSE.INDX", "^GDAXI": "GDAXI.INDX"},
            "years": 5,
            "max_staleness_days": 5,
            "min_symbol_coverage": 1.0,
        }
    }

    result = external_market_history.update_europe_market_history_from_config(cfg, tmp_path)

    assert result.status == "updated"
    assert result.covered_symbols == 2
    assert requested == ["^FTSE", "^GDAXI"]
    with sqlite3.connect(result.db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT market, symbol, source FROM market_daily_bars ORDER BY symbol"
        ).fetchall()
        audit = conn.execute(
            "SELECT source, status, fetched_rows FROM market_data_source_runs"
        ).fetchone()
    assert rows == [("EU_INDEX", "^FTSE", "eodhd"), ("EU_INDEX", "^GDAXI", "eodhd")]
    assert audit == ("eodhd", "updated", 4)


def test_europe_history_reader_uses_configured_database(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(external_market_history, "fetch_external_market_daily", lambda symbol, settings: _daily_frame())
    cfg = {
        "europe_market_history": {
            "path": "data/euro_market_history.sqlite",
            "symbols": ["^STOXX50E"],
            "max_staleness_days": 5,
        }
    }
    external_market_history.update_europe_market_history_from_config(cfg, tmp_path)

    result = external_market_history.load_europe_daily_from_history(
        ["^STOXX50E"],
        date(2026, 8, 8),
        date(2026, 8, 10),
    )

    assert result[["date", "symbol", "close"]].to_dict("records") == [
        {"date": pd.Timestamp("2026-08-10"), "symbol": "^STOXX50E", "close": 102.0}
    ]
