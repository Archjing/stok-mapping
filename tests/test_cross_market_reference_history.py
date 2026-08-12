from __future__ import annotations

import importlib
import importlib.util
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from quant import walk_forward
from quant.cli_commands import data_update as data_update_cli
from quant.cli_commands import pipeline_run
from quant.data_governance.cross_market_reference_history import CrossMarketReferenceHistoryUpdateResult


def test_reference_history_configuration_does_not_leak_previous_defaults(tmp_path: Path) -> None:
    reference_history = importlib.import_module("quant.data_governance.cross_market_reference_history")

    reference_history.configure_cross_market_reference_history({"path": "custom.sqlite", "years": 3}, tmp_path)
    reference_history.configure_cross_market_reference_history({}, tmp_path)

    assert reference_history._settings.path == tmp_path / "data/cross_market_reference_history.sqlite"
    assert reference_history._settings.years == 7


def test_phase0_blocks_enabled_cross_market_overlay_when_reference_history_is_stale() -> None:
    cfg = {
        "cross_market_reference_history": {"enabled": True},
        "walk_forward": {"strategy_v2": {"cross_market": {"enabled": True}}},
    }
    result = CrossMarketReferenceHistoryUpdateResult(
        db_path=Path("data/cross_market_reference_history.sqlite"),
        status="stale",
        latest_date="2026-07-20",
        symbol_count=2,
        covered_symbols=0,
        coverage=0.0,
        fetched_rows=0,
        inserted_rows=0,
        updated_rows=0,
        warnings=["fred ^NDX failed"],
    )

    with pytest.raises(RuntimeError, match="cross_market_reference_history_gate_failed:status=stale"):
        pipeline_run.require_fresh_cross_market_reference(cfg, result)


def test_reference_history_respects_disabled_fred_source(monkeypatch, tmp_path: Path) -> None:
    reference_history = importlib.import_module("quant.data_governance.cross_market_reference_history")
    monkeypatch.setattr(
        reference_history,
        "fetch_fred_series",
        lambda *args, **kwargs: pytest.fail("FRED must not be fetched while disabled"),
    )
    cfg = {
        "cross_market_reference_history": {
            "enabled": True,
            "path": "data/cross_market_reference_history.sqlite",
            "series": {"^NDX": {"provider": "fred", "source_series_id": "NASDAQ100"}},
        },
        "data_sources": {"fred": {"enabled": False}},
    }

    result = reference_history.update_cross_market_reference_history_from_config(cfg, tmp_path)

    assert result.status == "stale"
    assert result.warnings == ["^NDX source_disabled:fred"]


def test_fred_reference_history_persists_close_only_series_and_audits_source(monkeypatch, tmp_path: Path) -> None:
    module_name = "quant.data_governance.cross_market_reference_history"
    assert importlib.util.find_spec(module_name) is not None
    reference_history = importlib.import_module(module_name)

    calls: list[tuple[str, int]] = []

    def fake_fetch_fred_series(series_id: str, *, years: int, **kwargs) -> pd.DataFrame:
        calls.append((series_id, years))
        return pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-07-30", "2026-07-31"]),
                "value": [100.0 if series_id == "NASDAQ100" else 200.0, 101.0 if series_id == "NASDAQ100" else 201.0],
            }
        )

    monkeypatch.setattr(reference_history, "fetch_fred_series", fake_fetch_fred_series)
    cfg = {
        "cross_market_reference_history": {
            "enabled": True,
            "path": "data/cross_market_reference_history.sqlite",
            "daily_table": "cross_market_reference_daily",
            "source_audit_table": "cross_market_reference_source_runs",
            "years": 7,
            "max_staleness_days": 7,
            "min_symbol_coverage": 1.0,
            "series": {
                "^NDX": {"provider": "fred", "source_series_id": "NASDAQ100"},
                "^SOX": {"provider": "fred", "source_series_id": "NASDAQSOX"},
            },
        },
        "data_sources": {"fred": {"api_key_env": "FRED_API_KEY", "cache": {"enabled": False}}},
    }

    result = reference_history.update_cross_market_reference_history_from_config(
        cfg,
        tmp_path,
        as_of_date=date(2026, 8, 7),
    )

    assert result.ok
    assert result.status == "updated"
    assert result.coverage == 1.0
    assert calls == [("NASDAQ100", 7), ("NASDAQSOX", 7)]

    loaded = reference_history.load_cross_market_reference_from_history(
        ["^NDX", "^SOX"],
        date(2026, 7, 30),
        date(2026, 7, 31),
    )
    assert loaded[["symbol", "date", "close", "source", "source_series_id"]].to_dict("records") == [
        {"symbol": "^NDX", "date": pd.Timestamp("2026-07-30"), "close": 100.0, "source": "fred", "source_series_id": "NASDAQ100"},
        {"symbol": "^NDX", "date": pd.Timestamp("2026-07-31"), "close": 101.0, "source": "fred", "source_series_id": "NASDAQ100"},
        {"symbol": "^SOX", "date": pd.Timestamp("2026-07-30"), "close": 200.0, "source": "fred", "source_series_id": "NASDAQSOX"},
        {"symbol": "^SOX", "date": pd.Timestamp("2026-07-31"), "close": 201.0, "source": "fred", "source_series_id": "NASDAQSOX"},
    ]
    with sqlite3.connect(tmp_path / "data/cross_market_reference_history.sqlite") as conn:
        audit = conn.execute(
            "SELECT symbol, source, source_series_id, status FROM cross_market_reference_source_runs ORDER BY symbol"
        ).fetchall()
    assert audit == [("^NDX", "fred", "NASDAQ100", "updated"), ("^SOX", "fred", "NASDAQSOX", "updated")]


def test_cross_market_features_prioritize_reference_close_series(monkeypatch) -> None:
    dates = pd.to_datetime(["2026-07-29", "2026-07-30", "2026-07-31"])
    history = pd.concat(
        [
            pd.DataFrame({"date": dates, "symbol": ticker, "close": [100.0, 100.0, 100.0]})
            for ticker in walk_forward.MARKET_TICKERS
        ],
        ignore_index=True,
    )
    reference = pd.DataFrame({"date": dates, "symbol": "^NDX", "close": [100.0, 110.0, 121.0]})
    calls: list[tuple[list[str], date, date]] = []

    monkeypatch.setattr(walk_forward, "load_us_daily_from_history", lambda *args: history)
    monkeypatch.setattr(walk_forward, "us_market_history_runtime_fallback_enabled", lambda: False)

    def fake_load_reference(symbols: list[str], start: date, end: date) -> pd.DataFrame:
        calls.append((symbols, start, end))
        return reference

    monkeypatch.setattr(walk_forward, "load_cross_market_reference_from_history", fake_load_reference, raising=False)

    out = walk_forward._load_cross_market_features(1, {})

    assert calls and calls[0][0] == walk_forward.MARKET_TICKERS
    assert out.loc[out["date"] == pd.Timestamp("2026-07-31"), "xmarket_score"].iloc[0] == 0.3


def test_data_update_registers_cross_market_reference_command() -> None:
    assert "update-cross-market-reference-history" in data_update_cli.DATA_UPDATE_COMMANDS
