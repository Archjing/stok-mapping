from __future__ import annotations

import pandas as pd

from quant.strategies import available_strategies, get_strategy
from quant.strategies.quality_low_turnover_regime_gate import (
    QualityLowTurnoverRegimeGateStrategy,
    _add_index_regime_features,
)


def _sample_panel() -> pd.DataFrame:
    rows = []
    for date in pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]):
        for symbol, quality in [("AAA", 0.9), ("BBB", 0.8)]:
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "ret": 0.01,
                    "quality_growth_score": quality,
                    "vol20": 0.10,
                    "turnover_rate20": 0.10,
                    "mom20": 0.20,
                    "industry": "Tech" if symbol == "AAA" else "Health",
                    "financial_available_fields": 5,
                    "financial_announce_date": "2023-12-31",
                    "quality_roe_component": 0.8,
                    "quality_cash_flow_component": 0.7,
                    "quality_profit_growth_component": 0.6,
                    "quality_revenue_growth_component": 0.5,
                    "quality_low_debt_component": 0.4,
                }
            )
    return pd.DataFrame(rows)


def test_quality_low_turnover_regime_gate_strategy_is_registered() -> None:
    assert "quality_low_turnover_regime_gate_v1" in available_strategies()
    assert isinstance(get_strategy("quality_low_turnover_regime_gate_v1"), QualityLowTurnoverRegimeGateStrategy)


def test_quality_low_turnover_regime_gate_scales_next_day_weight() -> None:
    strategy = QualityLowTurnoverRegimeGateStrategy()
    panel = _sample_panel()
    panel["regime_scale"] = 1.0
    panel.loc[panel["date"] == pd.Timestamp("2024-01-02"), "regime_scale"] = 0.25
    params = {
        "eligible": True,
        "quality_threshold": 0.0,
        "low_vol_window": 20,
        "vol_threshold": 1.0,
        "turnover_threshold": 1.0,
        "momentum_window": 20,
        "buy_top_n": 1,
        "hold_top_n": 2,
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
        "regime_index_symbol": "SH.000300",
        "regime_trend_window": 2,
        "regime_vol_window": 2,
        "regime_vol_quantile": 0.7,
        "regime_risk_scale": 0.25,
        "regime_scale_mode": "trend_only",
    }

    output = strategy.apply(panel, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-02")]
    second_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-03")]
    assert first_day.set_index("symbol").loc["AAA", "weight_unshifted"] == 0.125
    assert second_day.set_index("symbol").loc["AAA", "weight"] == 0.125
    assert "financial_available_fields" in output.signal_frame.columns


def test_add_index_regime_features_uses_previous_index_close(monkeypatch) -> None:
    panel = pd.DataFrame(
        [
            {"date": pd.Timestamp("2024-01-02"), "symbol": "AAA", "ret": 0.0},
            {"date": pd.Timestamp("2024-01-03"), "symbol": "AAA", "ret": 0.0},
        ]
    )
    index = pd.DataFrame(
        [
            {"date": pd.Timestamp("2024-01-01"), "close": 100.0},
            {"date": pd.Timestamp("2024-01-02"), "close": 90.0},
            {"date": pd.Timestamp("2024-01-03"), "close": 80.0},
        ]
    )

    def fake_load_index(symbol, start, end):
        return index

    monkeypatch.setattr(
        "quant.strategies.quality_low_turnover_regime_gate.load_index_daily_from_local_history",
        fake_load_index,
    )

    out = _add_index_regime_features(
        panel,
        {
            "index_symbol": "SH.000300",
            "regime_trend_window": 2,
            "regime_vol_window": 2,
            "regime_scale_mode": "trend_only",
            "regime_risk_scale": 0.25,
        },
    )

    by_date = out.set_index("date")
    assert by_date.loc[pd.Timestamp("2024-01-02"), "regime_index_close"] == 100.0
    assert by_date.loc[pd.Timestamp("2024-01-03"), "regime_index_close"] == 90.0
