from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from phase0.data_access import local_history
import phase0.walk_forward as wf


class DummyStrategy:
    panel_scope = "portfolio"
    candidate_name = "dummy"

    def __init__(self) -> None:
        self.calls = 0

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict) -> pd.DataFrame:
        self.calls += 1
        return panel.assign(prepared_call=self.calls)


def _panel() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "symbol": ["SH.600000", "SH.600001"],
            "close": [10.0, 11.0],
        }
    )


def test_prepared_panel_cache_reuses_same_strategy_input(tmp_path: Path) -> None:
    strategy = DummyStrategy()
    runtime = wf.WalkForwardRuntime(root=tmp_path)
    token = wf._WALK_FORWARD_RUNTIME.set(runtime)
    try:
        first = wf._prepare_strategy_panel_cached(
            strategy_name="dummy_a",
            strategy=strategy,
            panel=_panel(),
            strategy_cfg={"mode": "portfolio"},
        )
        second = wf._prepare_strategy_panel_cached(
            strategy_name="dummy_a",
            strategy=strategy,
            panel=_panel(),
            strategy_cfg={"mode": "portfolio"},
        )
    finally:
        wf._WALK_FORWARD_RUNTIME.reset(token)

    assert strategy.calls == 1
    assert first["prepared_call"].tolist() == [1, 1]
    assert second["prepared_call"].tolist() == [1, 1]
    assert runtime.cache_stats["prepared_panel_memory_hits"] == 1
    assert runtime.cache_stats["prepared_panel_misses"] == 1


def test_prepared_panel_cache_does_not_cross_strategy_names(tmp_path: Path) -> None:
    strategy = DummyStrategy()
    runtime = wf.WalkForwardRuntime(root=tmp_path)
    token = wf._WALK_FORWARD_RUNTIME.set(runtime)
    try:
        first = wf._prepare_strategy_panel_cached(
            strategy_name="dummy_a",
            strategy=strategy,
            panel=_panel(),
            strategy_cfg={"mode": "portfolio"},
        )
        second = wf._prepare_strategy_panel_cached(
            strategy_name="dummy_b",
            strategy=strategy,
            panel=_panel(),
            strategy_cfg={"mode": "portfolio"},
        )
    finally:
        wf._WALK_FORWARD_RUNTIME.reset(token)

    assert strategy.calls == 2
    assert first["prepared_call"].tolist() == [1, 1]
    assert second["prepared_call"].tolist() == [2, 2]
    assert runtime.cache_stats["prepared_panel_memory_hits"] == 0
    assert runtime.cache_stats["prepared_panel_misses"] == 2


def test_walk_forward_profile_writes_json_and_csv(tmp_path: Path) -> None:
    runtime = wf.WalkForwardRuntime(
        root=tmp_path,
        profile_enabled=True,
        profile_output_dir=tmp_path / "perf",
    )
    runtime.profile_events.append({"event": "strategy_prepare_panel", "duration_ms": 12.3})
    summary = {"walk_forward_preset": "baseline"}

    json_path = wf._write_walk_forward_profile(runtime, summary=summary)

    assert json_path is not None
    assert json_path.exists()
    profile_payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert profile_payload["cache_manifest"]["cache_enabled"] is True
    assert "source_signature" in profile_payload["cache_manifest"]
    csv_path = Path(summary["walk_forward_profile_csv_path"])
    assert csv_path.exists()
    assert "strategy_prepare_panel" in csv_path.read_text(encoding="utf-8")


def test_fold_panel_cache_reuses_same_asof_input(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str, str]] = []

    def fake_load_symbol_map(symbols, years, as_of_date=None, price_adjustment=None):
        calls.append(("load", str(as_of_date), str(price_adjustment)))
        return {
            "SH.600000": pd.DataFrame(
                {
                    "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
                    "close": [10.0, 11.0, 12.0],
                }
            )
        }

    monkeypatch.setattr(wf, "_load_symbol_map", fake_load_symbol_map)
    monkeypatch.setattr(wf, "_add_cross_market_to_panel", lambda panel, years, strategy_cfg, xfeatures: panel)

    train_dates = {pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")}
    valid_dates = {pd.Timestamp("2024-01-04")}
    runtime = wf.WalkForwardRuntime(root=tmp_path)
    token = wf._WALK_FORWARD_RUNTIME.set(runtime)
    try:
        first_train, first_valid = wf._build_panel_for_fold_asof(
            ["SH.600000"],
            years=1,
            train_dates=train_dates,
            valid_dates=valid_dates,
            train_as_of_date=pd.Timestamp("2024-01-03").date(),
            valid_as_of_date=pd.Timestamp("2024-01-04").date(),
            strategy_cfg={"mode": "portfolio"},
        )
        second_train, second_valid = wf._build_panel_for_fold_asof(
            ["SH.600000"],
            years=1,
            train_dates=train_dates,
            valid_dates=valid_dates,
            train_as_of_date=pd.Timestamp("2024-01-03").date(),
            valid_as_of_date=pd.Timestamp("2024-01-04").date(),
            strategy_cfg={"mode": "portfolio"},
        )
    finally:
        wf._WALK_FORWARD_RUNTIME.reset(token)

    assert calls == [
        ("load", "2024-01-03", "qfq_asof"),
        ("load", "2024-01-04", "qfq_asof"),
    ]
    assert runtime.cache_stats["fold_panel_misses"] == 1
    assert runtime.cache_stats["fold_panel_memory_hits"] == 1
    assert first_train["close"].tolist() == [10.0, 11.0]
    assert second_train["close"].tolist() == [10.0, 11.0]
    assert first_valid["close"].tolist() == [12.0]
    assert second_valid["close"].tolist() == [12.0]


def test_symbol_ma_features_use_qfq_asof_prices_without_future_factor(tmp_path: Path) -> None:
    db_path = tmp_path / "history.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE market_daily_bars (
                market TEXT,
                symbol TEXT,
                date TEXT,
                adjust_type TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                adjusted_close REAL,
                change_pct REAL,
                change_amount REAL,
                amplitude REAL,
                turnover_rate REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE market_adj_factors (
                market TEXT,
                symbol TEXT,
                date TEXT,
                adj_factor REAL,
                source TEXT,
                updated_at TEXT
            )
            """
        )
        dates = pd.date_range("2023-10-06", "2024-01-04", freq="D")
        closes = [10.0] * (len(dates) - 3) + [10.0, 20.0, 30.0]
        bars = [
            (
                "CN",
                "SH.600000",
                day.date().isoformat(),
                "bfq",
                close,
                close,
                close,
                close,
                100.0,
                close * 100.0,
                close,
                0.0,
                0.0,
                0.0,
                0.0,
            )
            for day, close in zip(dates, closes, strict=True)
        ]
        conn.executemany(
            "INSERT INTO market_daily_bars VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            bars,
        )
        factors = [
            ("CN", "SH.600000", "2024-01-02", 1.0, "fixture", "2024-01-02T00:00:00"),
            ("CN", "SH.600000", "2024-01-03", 1.0, "fixture", "2024-01-03T00:00:00"),
            ("CN", "SH.600000", "2024-01-04", 2.0, "fixture", "2024-01-04T00:00:00"),
            ("CN", "SH.600000", "2024-01-05", 10.0, "future_fixture", "2024-01-05T00:00:00"),
        ]
        conn.executemany("INSERT INTO market_adj_factors VALUES (?, ?, ?, ?, ?, ?)", factors)

    original_settings = vars(local_history._settings).copy()
    wf._load_symbol_cached.cache_clear()
    try:
        local_history.configure_local_history(
            {
                **original_settings,
                "path": str(db_path),
                "prefer_daily_for_backtest": True,
                "price_adjustment_for_backtest": "qfq_asof",
            }
        )
        out = wf._load_symbol(
            "SH.600000",
            years=3,
            as_of_date="2024-01-04",
            price_adjustment="qfq_asof",
        )
    finally:
        wf._load_symbol_cached.cache_clear()
        local_history.configure_local_history(original_settings)

    row = out.loc[out["date"].eq(pd.Timestamp("2024-01-04"))].iloc[0]
    assert row["close"] == 30.0
    assert row["ma3"] == 15.0


def test_symbol_cache_reuses_same_source_signature(tmp_path: Path) -> None:
    original_hash = wf._SYMBOL_CACHE_SOURCE_HASH
    try:
        wf._SYMBOL_CACHE_SOURCE_HASH = None
        runtime = wf.WalkForwardRuntime(
            root=tmp_path,
            source_signature={"sources": [{"path": "a.sqlite", "mtime_ns": 1, "size": 10}]},
        )

        wf._manage_symbol_cache_for_runtime(runtime)
        wf._manage_symbol_cache_for_runtime(runtime)

        assert runtime.cache_stats["symbol_cache_clears"] == 1
        assert runtime.cache_stats["symbol_cache_reuses"] == 1
    finally:
        wf._SYMBOL_CACHE_SOURCE_HASH = original_hash


def test_symbol_cache_clears_when_source_signature_changes(tmp_path: Path) -> None:
    original_hash = wf._SYMBOL_CACHE_SOURCE_HASH
    try:
        wf._SYMBOL_CACHE_SOURCE_HASH = None
        first = wf.WalkForwardRuntime(
            root=tmp_path,
            source_signature={"sources": [{"path": "a.sqlite", "mtime_ns": 1, "size": 10}]},
        )
        second = wf.WalkForwardRuntime(
            root=tmp_path,
            source_signature={"sources": [{"path": "a.sqlite", "mtime_ns": 2, "size": 10}]},
        )

        wf._manage_symbol_cache_for_runtime(first)
        wf._manage_symbol_cache_for_runtime(second)

        assert first.cache_stats["symbol_cache_clears"] == 1
        assert second.cache_stats["symbol_cache_clears"] == 1
        assert second.cache_stats["symbol_cache_reuses"] == 0
    finally:
        wf._SYMBOL_CACHE_SOURCE_HASH = original_hash


def test_point_in_time_universe_cache_reuses_same_asof(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_load_point_in_time_universe(config, root, as_of_date):
        calls.append(str(as_of_date))
        return SimpleNamespace(symbols=["SH.600000"], as_of_date=str(as_of_date))

    monkeypatch.setattr(wf, "load_point_in_time_universe", fake_load_point_in_time_universe)
    runtime = wf.WalkForwardRuntime(
        root=tmp_path,
        source_signature={"sources": [{"path": "a.sqlite", "mtime_ns": 1, "size": 10}]},
    )
    token = wf._WALK_FORWARD_RUNTIME.set(runtime)
    try:
        first = wf._load_point_in_time_universe_cached({"universe": {"target_size": 500}}, tmp_path, pd.Timestamp("2024-01-03").date())
        second = wf._load_point_in_time_universe_cached({"universe": {"target_size": 500}}, tmp_path, pd.Timestamp("2024-01-03").date())
    finally:
        wf._WALK_FORWARD_RUNTIME.reset(token)

    assert calls == ["2024-01-03"]
    assert first is second
    assert runtime.cache_stats["universe_misses"] == 1
    assert runtime.cache_stats["universe_memory_hits"] == 1


def test_benchmark_fold_metrics_cache_reuses_same_window(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str, str]] = []

    def fake_load_index_daily_from_local_history(symbol, start, end):
        calls.append((symbol, str(start), str(end)))
        return pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
                "close": [100.0, 101.0, 103.0],
            }
        )

    monkeypatch.setattr(wf, "load_index_daily_from_local_history", fake_load_index_daily_from_local_history)
    runtime = wf.WalkForwardRuntime(root=tmp_path)
    token = wf._WALK_FORWARD_RUNTIME.set(runtime)
    try:
        first = wf._benchmark_fold_metrics({"benchmark_symbol": "SH.000300"}, "2024-01-02", "2024-01-04")
        second = wf._benchmark_fold_metrics({"benchmark_symbol": "SH.000300"}, "2024-01-02", "2024-01-04")
    finally:
        wf._WALK_FORWARD_RUNTIME.reset(token)

    assert calls == [("SH.000300", "2024-01-02", "2024-01-04")]
    assert first == second
    assert runtime.cache_stats["benchmark_misses"] == 1
    assert runtime.cache_stats["benchmark_memory_hits"] == 1
