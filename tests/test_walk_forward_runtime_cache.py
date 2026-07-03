from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

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
    calls: list[tuple[str, str]] = []

    def fake_load_symbol_map(symbols, years, as_of_date=None, price_adjustment=None):
        calls.append(("load", str(as_of_date)))
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

    assert len(calls) == 2
    assert runtime.cache_stats["fold_panel_misses"] == 1
    assert runtime.cache_stats["fold_panel_memory_hits"] == 1
    assert first_train["close"].tolist() == [10.0, 11.0]
    assert second_train["close"].tolist() == [10.0, 11.0]
    assert first_valid["close"].tolist() == [12.0]
    assert second_valid["close"].tolist() == [12.0]
