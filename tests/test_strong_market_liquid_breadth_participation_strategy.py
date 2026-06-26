from __future__ import annotations

import pandas as pd

from phase0.strategies import available_strategies, get_strategy
from phase0.strategies.strong_market_liquid_breadth_participation import (
    StrongMarketLiquidBreadthParticipationStrategy,
)


def _panel(dates: pd.DatetimeIndex | None = None) -> pd.DataFrame:
    rows = []
    if dates is None:
        dates = pd.date_range("2024-01-10", periods=4, freq="D")
    symbols = [
        ("T1", "Tech", 0.60, 0.30, 1.8),
        ("T2", "Tech", 0.58, 0.28, 1.7),
        ("T3", "Tech", 0.56, 0.26, 1.6),
        ("T4", "Tech", 0.54, 0.24, 1.5),
        ("H1", "Health", 0.44, 0.18, 1.4),
        ("I1", "Industrial", 0.42, 0.16, 1.3),
    ]
    for idx, date in enumerate(dates):
        for symbol, industry, mom60, resid, amount_ratio in symbols:
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "ret": 0.01,
                    "close": 10.0 + idx,
                    "ma60": 9.0,
                    "mom20": 0.10 + resid / 10.0,
                    "mom60": mom60,
                    "vol20": 0.10,
                    "amount_ratio20": amount_ratio,
                    "upper_shadow_pct": 0.5,
                    "breakout20": 1.0,
                    "resid_mom20": resid,
                    "industry_relative_mom20": 0.20 if industry == "Tech" else 0.10,
                    "industry_relative_mom60": 0.22 if industry == "Tech" else 0.08,
                    "industry": industry,
                    "strong_index_context": True,
                }
            )
    return pd.DataFrame(rows)


def _params(**overrides) -> dict:
    base = {
        "eligible": True,
        "benchmark_symbol": "SH.000300",
        "threshold_status": "pre_registered_i20_first_pass",
        "trend_window": 3,
        "return_short_window": 1,
        "return_long_window": 2,
        "vol_window": 2,
        "vol_quantile": 0.7,
        "vol_threshold_lookback_days": 3,
        "drawdown_min": -0.12,
        "buy_top_n": 6,
        "hold_top_n": 10,
        "rebalance_days": 2,
        "min_hold_days": 1,
        "max_symbol_weight": 0.04,
        "max_names_per_industry": 3,
        "amount_ratio_min": 1.0,
        "amount_ratio_max": 3.5,
        "upper_shadow_max": 1.2,
        "vol_cross_section_quantile": 0.90,
        "factor_weights": {
            "mom60": 0.28,
            "mom20": 0.18,
            "resid_mom20": 0.12,
            "industry_relative_mom20": 0.14,
            "industry_relative_mom60": 0.08,
            "amount_ratio20": 0.15,
            "low_vol20": 0.03,
            "breakout20": 0.02,
        },
    }
    base.update(overrides)
    return base


def test_strong_market_liquid_breadth_strategy_is_registered_research_only() -> None:
    assert "strong_market_liquid_breadth_participation_v1" in available_strategies()
    strategy = get_strategy("strong_market_liquid_breadth_participation_v1")
    assert isinstance(strategy, StrongMarketLiquidBreadthParticipationStrategy)
    assert strategy.supports_brief is False
    assert strategy.supports_paper_trade is False


def test_strong_market_liquid_breadth_uses_industry_cap_and_delayed_weight() -> None:
    strategy = StrongMarketLiquidBreadthParticipationStrategy()

    output = strategy.apply(_panel(), _params(), slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-10")]
    selected = first_day.loc[first_day["weight_unshifted"] > 0]
    assert set(selected["symbol"]) == {"T1", "T2", "T3", "H1", "I1"}
    assert selected.loc[selected["industry"] == "Tech", "symbol"].nunique() == 3
    assert selected["weight_unshifted"].eq(0.04).all()
    assert first_day["weight"].sum() == 0.0

    second_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-11")]
    assert second_day["weight"].sum() == 0.20


def test_strong_market_liquid_breadth_does_not_open_when_context_is_weak() -> None:
    strategy = StrongMarketLiquidBreadthParticipationStrategy()
    panel = _panel()
    panel["strong_index_context"] = False

    output = strategy.apply(panel, _params(), slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    assert output.signal_frame["weight_unshifted"].eq(0.0).all()
    assert output.exposure.eq(0.0).all()


def test_strong_market_liquid_breadth_has_no_dynamic_trigger_review() -> None:
    strategy = StrongMarketLiquidBreadthParticipationStrategy()
    dates = pd.date_range("2024-01-10", periods=4, freq="D")
    panel = _panel(dates)
    panel["strong_index_context"] = panel["date"].isin([pd.Timestamp("2024-01-11"), pd.Timestamp("2024-01-12")])

    output = strategy.apply(
        panel,
        _params(rebalance_days=20, min_hold_days=1),
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
    )

    non_rebalance_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-11")]
    assert non_rebalance_day["review_reason"].eq("").all()
    assert non_rebalance_day["weight_unshifted"].eq(0.0).all()


def test_strong_market_liquid_breadth_missing_required_field_returns_cash() -> None:
    strategy = StrongMarketLiquidBreadthParticipationStrategy()
    panel = _panel().drop(columns=["ma60"])

    output = strategy.apply(panel, _params(), slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    assert output.returns.eq(0.0).all()
    assert output.exposure.eq(0.0).all()
    assert output.signal_frame.empty
    assert output.metadata["ineligible_reason"] == "missing_required_fields:ma60"
