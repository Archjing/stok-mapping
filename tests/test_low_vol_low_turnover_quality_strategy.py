from __future__ import annotations

import pandas as pd

from quant.strategies.low_vol_low_turnover_quality import LowVolLowTurnoverQualityStrategy


def _panel_with_industry_crowding() -> pd.DataFrame:
    rows = []
    for date in pd.to_datetime(["2024-01-02", "2024-01-03"]):
        rows.extend(
            [
                {
                    "date": date,
                    "symbol": "AAA",
                    "ret": 0.01,
                    "quality_growth_score": 0.95,
                    "vol20": 0.10,
                    "turnover_rate20": 0.10,
                    "mom20": 0.40,
                    "industry": "Tech",
                },
                {
                    "date": date,
                    "symbol": "BBB",
                    "ret": 0.01,
                    "quality_growth_score": 0.94,
                    "vol20": 0.10,
                    "turnover_rate20": 0.10,
                    "mom20": 0.39,
                    "industry": "Tech",
                },
                {
                    "date": date,
                    "symbol": "CCC",
                    "ret": 0.01,
                    "quality_growth_score": 0.70,
                    "vol20": 0.10,
                    "turnover_rate20": 0.10,
                    "mom20": 0.20,
                    "industry": "Health",
                },
            ]
        )
    return pd.DataFrame(rows)


def test_low_vol_low_turnover_quality_respects_industry_name_cap_when_adding_names() -> None:
    strategy = LowVolLowTurnoverQualityStrategy()
    params = {
        "eligible": True,
        "quality_threshold": 0.0,
        "low_vol_window": 20,
        "vol_threshold": 1.0,
        "turnover_threshold": 1.0,
        "momentum_window": 20,
        "buy_top_n": 2,
        "hold_top_n": 4,
        "rebalance_days": 20,
        "min_hold_days": 20,
        "target_vol": 1.0,
        "max_symbol_weight": 0.50,
        "max_names_per_industry": 1,
        "factor_weights": {
            "quality": 1.0,
            "low_volatility": 0.0,
            "low_turnover": 0.0,
            "medium_momentum": 0.0,
        },
    }

    output = strategy.apply(
        _panel_with_industry_crowding(),
        params,
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
    )

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-02")]
    selected = set(first_day.loc[first_day["weight_unshifted"] > 0, "symbol"])
    assert selected == {"AAA", "CCC"}
    assert "BBB" not in selected
