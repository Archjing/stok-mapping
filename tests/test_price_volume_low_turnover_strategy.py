from __future__ import annotations

import pandas as pd

from phase0.strategies import available_strategies, get_strategy
from phase0.strategies.price_volume_low_turnover import PriceVolumeLowTurnoverStrategy


def _panel() -> pd.DataFrame:
    rows = []
    symbols = [
        ("AAA", "Tech", 0.50, 0.20),
        ("BBB", "Tech", 0.49, 0.19),
        ("CCC", "Health", 0.35, 0.16),
    ]
    for idx, date in enumerate(pd.date_range("2024-01-02", periods=4, freq="D")):
        for symbol, industry, resid, mom in symbols:
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "ret": 0.01,
                    "close": 10.0 + idx,
                    "ma20": 9.0,
                    "vol20": 0.10,
                    "amount_ratio20": 1.2,
                    "upper_shadow_pct": 0.5,
                    "breakout20": 1.0,
                    "resid_mom20": resid,
                    "mom20": mom,
                    "industry": industry,
                }
            )
    return pd.DataFrame(rows)


def test_price_volume_low_turnover_strategy_is_registered() -> None:
    assert "price_volume_low_turnover_v1" in available_strategies()
    assert isinstance(get_strategy("price_volume_low_turnover_v1"), PriceVolumeLowTurnoverStrategy)


def test_price_volume_low_turnover_respects_rebalance_and_industry_cap() -> None:
    strategy = PriceVolumeLowTurnoverStrategy()
    params = {
        "eligible": True,
        "residual_window": 20,
        "residual_quantile": 0.0,
        "residual_threshold": 0.0,
        "momentum_window": 20,
        "momentum_quantile": 0.0,
        "momentum_threshold": 0.0,
        "trend_window": 20,
        "vol_quantile": 1.0,
        "vol_threshold": 1.0,
        "amount_ratio_min": 1.0,
        "amount_ratio_max": 3.0,
        "upper_shadow_max": 1.0,
        "breakout_required": False,
        "buy_top_n": 2,
        "hold_top_n": 4,
        "rebalance_days": 3,
        "min_hold_days": 3,
        "max_symbol_weight": 0.50,
        "target_vol": 1.0,
        "max_names_per_industry": 1,
        "factor_weights": {
            "residual_momentum": 1.0,
            "momentum": 0.0,
            "low_volatility": 0.0,
            "amount_confirmation": 0.0,
        },
    }

    output = strategy.apply(_panel(), params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-02")]
    selected = set(first_day.loc[first_day["weight_unshifted"] > 0, "symbol"])
    assert selected == {"AAA", "CCC"}
    assert "BBB" not in selected

    second_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-03")]
    assert set(second_day.loc[second_day["weight_unshifted"] > 0, "symbol"]) == selected


def test_price_volume_low_turnover_builds_industry_relative_strength_features() -> None:
    strategy = PriceVolumeLowTurnoverStrategy()

    prepared = strategy.prepare_panel(_panel(), {})

    assert "industry_mom20" in prepared.columns
    assert "industry_relative_mom20" in prepared.columns
    first_day = prepared[prepared["date"] == pd.Timestamp("2024-01-02")]
    tech = first_day[first_day["industry"] == "Tech"]["industry_mom20"].iloc[0]
    market = first_day["mom20"].mean()
    assert tech == pd.Series([0.20, 0.19]).mean()
    assert first_day[first_day["symbol"] == "AAA"]["industry_relative_mom20"].iloc[0] == tech - market


def test_price_volume_low_turnover_can_rank_by_industry_relative_strength() -> None:
    strategy = PriceVolumeLowTurnoverStrategy()
    panel = _panel()
    panel.loc[panel["symbol"] == "AAA", "industry_relative_mom20"] = -0.20
    panel.loc[panel["symbol"] == "BBB", "industry_relative_mom20"] = -0.20
    panel.loc[panel["symbol"] == "CCC", "industry_relative_mom20"] = 0.30
    params = {
        "eligible": True,
        "residual_window": 20,
        "residual_quantile": 0.0,
        "residual_threshold": 0.0,
        "momentum_window": 20,
        "momentum_quantile": 0.0,
        "momentum_threshold": 0.0,
        "trend_window": 20,
        "vol_quantile": 1.0,
        "vol_threshold": 1.0,
        "amount_ratio_min": 1.0,
        "amount_ratio_max": 3.0,
        "upper_shadow_max": 1.0,
        "breakout_required": False,
        "industry_relative_enabled": True,
        "industry_relative_window": 20,
        "industry_relative_quantile": 0.0,
        "industry_relative_threshold": -1.0,
        "buy_top_n": 1,
        "hold_top_n": 2,
        "rebalance_days": 3,
        "min_hold_days": 3,
        "max_symbol_weight": 1.0,
        "target_vol": 1.0,
        "max_names_per_industry": None,
        "factor_weights": {
            "residual_momentum": 0.0,
            "momentum": 0.0,
            "low_volatility": 0.0,
            "amount_confirmation": 0.0,
            "industry_relative_strength": 1.0,
        },
    }

    output = strategy.apply(panel, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-02")]
    selected = set(first_day.loc[first_day["weight_unshifted"] > 0, "symbol"])
    assert selected == {"CCC"}
    assert first_day.loc[first_day["symbol"] == "CCC", "industry_relative_rank_component"].iloc[0] == 1.0


def test_price_volume_low_turnover_does_not_filter_industry_relative_strength_by_default() -> None:
    strategy = PriceVolumeLowTurnoverStrategy()
    panel = _panel()
    panel["industry_relative_mom20"] = -1.0
    params = {
        "eligible": True,
        "residual_window": 20,
        "residual_quantile": 0.0,
        "residual_threshold": 0.0,
        "momentum_window": 20,
        "momentum_quantile": 0.0,
        "momentum_threshold": 0.0,
        "trend_window": 20,
        "vol_quantile": 1.0,
        "vol_threshold": 1.0,
        "amount_ratio_min": 1.0,
        "amount_ratio_max": 3.0,
        "upper_shadow_max": 1.0,
        "breakout_required": False,
        "industry_relative_window": 20,
        "industry_relative_quantile": 0.0,
        "industry_relative_threshold": 0.0,
        "buy_top_n": 1,
        "hold_top_n": 2,
        "rebalance_days": 3,
        "min_hold_days": 3,
        "max_symbol_weight": 1.0,
        "target_vol": 1.0,
        "max_names_per_industry": None,
        "factor_weights": {
            "residual_momentum": 1.0,
            "momentum": 0.0,
            "low_volatility": 0.0,
            "amount_confirmation": 0.0,
            "industry_relative_strength": 0.0,
        },
    }

    output = strategy.apply(panel, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-02")]
    selected = set(first_day.loc[first_day["weight_unshifted"] > 0, "symbol"])
    assert selected == {"AAA"}
