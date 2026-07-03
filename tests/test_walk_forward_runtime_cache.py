from __future__ import annotations

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
    csv_path = Path(summary["walk_forward_profile_csv_path"])
    assert csv_path.exists()
    assert "strategy_prepare_panel" in csv_path.read_text(encoding="utf-8")
