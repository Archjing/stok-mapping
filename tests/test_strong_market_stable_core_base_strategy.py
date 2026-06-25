from __future__ import annotations

import pandas as pd
import pytest

from phase0.strategies import available_strategies, get_strategy
from phase0.strategies.strong_market_stable_core_base import StrongMarketStableCoreBaseStrategy


def _panel(dates: pd.DatetimeIndex | None = None) -> pd.DataFrame:
    rows = []
    if dates is None:
        dates = pd.date_range("2024-01-10", periods=25, freq="D")
    symbols = [
        ("B1", "Bank", 0.060, 0.60, 0.10, 1.8, 0.10),
        ("B2", "Bank", 0.045, 0.58, 0.08, 1.7, 0.11),
        ("T1", "Tech", 0.035, 0.56, 0.06, 1.6, 0.12),
        ("T2", "Tech", 0.025, 0.54, 0.04, 1.5, 0.13),
        ("A1", "Alpha", 0.000, 0.62, 0.12, 1.9, 0.14),
        ("A2", "Alpha", 0.000, 0.50, 0.02, 1.3, 0.15),
    ]
    for idx, date in enumerate(dates):
        for symbol, industry, benchmark_weight, mom60, mom20, amount_ratio, vol20 in symbols:
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "ret": 0.01,
                    "close": 10.0 + idx,
                    "open": 9.9 + idx,
                    "high": 10.2 + idx,
                    "low": 9.8 + idx,
                    "amount": 1000.0,
                    "ma60": 9.0,
                    "mom20": mom20,
                    "mom60": mom60,
                    "vol20": vol20,
                    "amount_ratio20": amount_ratio,
                    "industry_relative_mom20": 0.05,
                    "industry": industry,
                    "name": symbol,
                    "benchmark_weight": benchmark_weight,
                    "benchmark_weight_date": "2024-01-09",
                    "strong_index_context": True,
                    "benchmark_seeded_core": benchmark_weight > 0,
                }
            )
    return pd.DataFrame(rows)


def _params(**overrides) -> dict:
    base = {
        "eligible": True,
        "benchmark_symbol": "SH.000300",
        "threshold_status": "pre_registered_i47_first_pass",
        "seed_top_n": 20,
        "seed_core_top_n": 60,
        "seed_core_cumulative_weight": 0.60,
        "core_top_n": 4,
        "satellite_top_n": 1,
        "base_exposure": 0.35,
        "strong_target_exposure": 0.70,
        "core_budget_ratio": 0.80,
        "satellite_budget_ratio": 0.20,
        "benchmark_weight_multiplier": 2.0,
        "max_symbol_weight": 0.25,
        "max_names_per_industry": 2,
        "rebalance_days": 20,
        "amount_min": 0.0,
        "amount_ratio_min": 0.0,
        "factor_weights": {
            "benchmark_weight": 0.55,
            "mom60": 0.14,
            "mom20": 0.08,
            "amount_ratio20": 0.10,
            "low_vol20": 0.08,
            "industry_relative_mom20": 0.05,
        },
    }
    base.update(overrides)
    return base


def test_stable_core_base_is_registered_research_only() -> None:
    assert "strong_market_stable_core_base_v1" in available_strategies()
    strategy = get_strategy("strong_market_stable_core_base_v1")
    assert isinstance(strategy, StrongMarketStableCoreBaseStrategy)
    assert strategy.supports_brief is False
    assert strategy.supports_paper_trade is False


def test_stable_core_base_keeps_base_core_exposure_when_context_is_weak() -> None:
    strategy = StrongMarketStableCoreBaseStrategy()
    panel = _panel()
    panel["strong_index_context"] = False

    output = strategy.apply(panel, _params(), slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-10")]
    assert first_day["weight_unshifted"].sum() == pytest.approx(0.35)
    assert first_day.loc[first_day["benchmark_weight"] > 0, "weight_unshifted"].sum() == pytest.approx(0.35)
    second_day_exposure = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-11")]["weight"].sum()
    assert second_day_exposure == pytest.approx(0.35)


def test_stable_core_base_expands_core_and_satellite_in_strong_context() -> None:
    strategy = StrongMarketStableCoreBaseStrategy()

    output = strategy.apply(_panel(), _params(), slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-10")]
    selected = first_day[first_day["weight_unshifted"] > 0]
    assert selected["weight_unshifted"].sum() == pytest.approx(0.70)
    assert selected.loc[selected["benchmark_weight"] > 0, "weight_unshifted"].sum() >= 0.50
    assert selected.loc[selected["benchmark_weight"] <= 0, "weight_unshifted"].sum() <= 0.14


def test_stable_core_base_does_not_rebalance_daily() -> None:
    strategy = StrongMarketStableCoreBaseStrategy()

    output = strategy.apply(_panel(), _params(rebalance_days=20), slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    review_counts = output.signal_frame.groupby("date")["review_day"].max().astype(bool)
    assert bool(review_counts.iloc[0]) is True
    assert not review_counts.iloc[1:20].any()
    assert bool(review_counts.iloc[20]) is True


def test_stable_core_base_does_not_hard_filter_benchmark_core_by_industry() -> None:
    strategy = StrongMarketStableCoreBaseStrategy()

    output = strategy.apply(
        _panel(),
        _params(max_names_per_industry=1),
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
    )

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-10")]
    selected_core = first_day[(first_day["benchmark_weight"] > 0) & (first_day["weight_unshifted"] > 0)]
    assert set(selected_core.loc[selected_core["industry"] == "Bank", "symbol"]) == {"B1", "B2"}
    assert selected_core["weight_unshifted"].sum() >= 0.50
