from __future__ import annotations

import pandas as pd

from quant.research.participation.overlay import _overlay_daily_rows, _overlay_summary


def test_participation_overlay_scales_low_exposure_day_with_symbol_cap() -> None:
    holdings = pd.DataFrame(
        [
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline",
                "fold": 4,
                "market_context_label": "relative_lag_in_strong_benchmark_context",
                "date": "2024-04-01",
                "symbol": "AAA",
                "live_weight": 0.05,
                "ret": 0.02,
            },
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline",
                "fold": 4,
                "market_context_label": "relative_lag_in_strong_benchmark_context",
                "date": "2024-04-01",
                "symbol": "BBB",
                "live_weight": 0.05,
                "ret": 0.01,
            },
        ]
    )
    daily_exposure = pd.DataFrame(
        [
            {
                "walk_forward_preset": "baseline",
                "fold": 4,
                "date": "2024-04-01",
                "benchmark_daily_return": 0.01,
            }
        ]
    )

    daily = _overlay_daily_rows(
        holdings,
        daily_exposure,
        min_exposure=0.20,
        max_symbol_weight=0.08,
        max_scale=3.0,
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
    )

    row = daily.iloc[0]
    assert row["base_live_exposure"] == 0.10
    assert row["overlay_live_exposure"] == 0.16
    assert row["overlay_scale"] == 2.0
    assert row["overlay_net_return"] > row["base_net_return"]


def test_participation_overlay_summary_marks_improvement() -> None:
    daily = pd.DataFrame(
        [
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline",
                "fold": 4,
                "market_context_label": "relative_lag_in_strong_benchmark_context",
                "date": "2024-04-01",
                "base_net_return": 0.005,
                "overlay_net_return": 0.010,
                "benchmark_daily_return": 0.012,
                "base_live_exposure": 0.10,
                "overlay_live_exposure": 0.20,
                "overlay_scale": 2.0,
                "live_holding_count": 2,
                "base_cost": 0.0,
                "overlay_cost": 0.0,
            },
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline",
                "fold": 4,
                "market_context_label": "relative_lag_in_strong_benchmark_context",
                "date": "2024-04-02",
                "base_net_return": 0.004,
                "overlay_net_return": 0.008,
                "benchmark_daily_return": 0.010,
                "base_live_exposure": 0.12,
                "overlay_live_exposure": 0.24,
                "overlay_scale": 2.0,
                "live_holding_count": 2,
                "base_cost": 0.0,
                "overlay_cost": 0.0,
            },
        ]
    )

    summary = _overlay_summary(daily)

    fold = summary[summary["scope"] == "fold"].iloc[0]
    assert fold["overlay_annualized_return"] > fold["base_annualized_return"]
    assert "improves participation" in fold["interpretation"]
    assert "ALL" in set(summary["walk_forward_preset"])
