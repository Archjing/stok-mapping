from __future__ import annotations

import pandas as pd
import pytest

from quant.strategies import available_strategies, get_strategy
from quant.strategies.strong_market_core_participation import StrongMarketCoreParticipationStrategy


def _panel(dates: pd.DatetimeIndex | None = None) -> pd.DataFrame:
    rows = []
    if dates is None:
        dates = pd.date_range("2024-01-10", periods=4, freq="D")
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
        "threshold_status": "pre_registered_i45_first_pass",
        "seed_top_n": 20,
        "seed_core_top_n": 60,
        "seed_core_cumulative_weight": 0.60,
        "core_top_n": 4,
        "satellite_top_n": 1,
        "target_exposure": 0.70,
        "core_budget_ratio": 0.80,
        "satellite_budget_ratio": 0.20,
        "benchmark_weight_multiplier": 2.0,
        "max_symbol_weight": 0.25,
        "max_names_per_industry": 2,
        "amount_min": 0.0,
        "amount_ratio_min": 0.0,
        "factor_weights": {
            "benchmark_weight": 0.40,
            "mom60": 0.20,
            "mom20": 0.10,
            "amount_ratio20": 0.15,
            "low_vol20": 0.10,
            "industry_relative_mom20": 0.05,
        },
    }
    base.update(overrides)
    return base


def test_strong_market_core_participation_is_registered_research_only() -> None:
    assert "strong_market_core_participation_v1" in available_strategies()
    strategy = get_strategy("strong_market_core_participation_v1")
    assert isinstance(strategy, StrongMarketCoreParticipationStrategy)
    assert strategy.supports_brief is False
    assert strategy.supports_paper_trade is False


def test_core_participation_targets_benchmark_core_before_satellite() -> None:
    strategy = StrongMarketCoreParticipationStrategy()

    output = strategy.apply(_panel(), _params(), slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-10")]
    selected = first_day[first_day["weight_unshifted"] > 0]
    assert selected["weight_unshifted"].sum() == pytest.approx(0.70)
    assert selected.loc[selected["benchmark_weight"] > 0, "weight_unshifted"].sum() >= 0.50
    assert selected.loc[selected["benchmark_weight"] <= 0, "weight_unshifted"].sum() <= 0.14
    assert selected["weight_unshifted"].max() <= 0.25

    second_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-11")]
    assert second_day["weight"].sum() == pytest.approx(0.70)


def test_core_participation_does_not_hard_filter_benchmark_core_by_industry() -> None:
    strategy = StrongMarketCoreParticipationStrategy()

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


def test_core_participation_stays_cash_when_context_is_weak() -> None:
    strategy = StrongMarketCoreParticipationStrategy()
    panel = _panel()
    panel["strong_index_context"] = False

    output = strategy.apply(panel, _params(), slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    assert output.signal_frame["weight_unshifted"].eq(0.0).all()
    assert output.exposure.eq(0.0).all()
