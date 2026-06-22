from __future__ import annotations

import pandas as pd

from phase0.strategies import available_strategies, get_strategy
from phase0.strategies.sleeve_composite import SleeveCompositeStrategy


def _sample_panel() -> pd.DataFrame:
    rows = []
    for date in pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]):
        rows.extend(
            [
                {
                    "date": date,
                    "symbol": "AAA",
                    "ts_code": "AAA.SZ",
                    "ret": 0.01,
                    "quality_growth_score": 0.90,
                    "vol60": 0.10,
                    "turnover_rate20": 0.10,
                    "mom20": 0.30,
                    "risk_scale": 1.00,
                },
                {
                    "date": date,
                    "symbol": "BBB",
                    "ts_code": "BBB.SZ",
                    "ret": 0.00,
                    "quality_growth_score": 0.60,
                    "vol60": 0.20,
                    "turnover_rate20": 0.20,
                    "mom20": 0.10,
                    "risk_scale": 0.80,
                },
                {
                    "date": date,
                    "symbol": "CCC",
                    "ts_code": "CCC.SZ",
                    "ret": -0.01,
                    "quality_growth_score": 0.30,
                    "vol60": 0.30,
                    "turnover_rate20": 0.30,
                    "mom20": -0.10,
                    "risk_scale": 0.60,
                },
            ]
        )
    return pd.DataFrame(rows)


def test_sleeve_composite_strategy_is_registered() -> None:
    assert "sleeve_composite_v1" in available_strategies()
    assert isinstance(get_strategy("sleeve_composite_v1"), SleeveCompositeStrategy)


def test_sleeve_composite_scores_rank_and_shift_weights() -> None:
    strategy = SleeveCompositeStrategy()
    params = {
        "defensive_quality_weight": 0.55,
        "low_turnover_momentum_weight": 0.25,
        "risk_overlay_weight": 0.20,
        "momentum_window": 20,
        "top_n": 1,
        "max_symbol_weight": 0.10,
    }

    output = strategy.apply(
        _sample_panel(),
        params,
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
    )

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-02")]
    scores = first_day.set_index("symbol")["final_score"]
    assert scores["AAA"] > scores["BBB"] > scores["CCC"]
    assert first_day.set_index("symbol").loc["AAA", "selected"] == 1.0
    assert first_day.set_index("symbol").loc["BBB", "selected"] == 0.0

    second_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-03")]
    assert second_day.set_index("symbol").loc["AAA", "weight"] == 0.10
    assert output.returns.loc[pd.Timestamp("2024-01-03")] == 0.001


def test_sleeve_composite_missing_fields_degrade_to_neutral_scores() -> None:
    strategy = SleeveCompositeStrategy()
    panel = pd.DataFrame(
        [
            {"date": pd.Timestamp("2024-01-02"), "symbol": "AAA", "ret": 0.01},
            {"date": pd.Timestamp("2024-01-02"), "symbol": "BBB", "ret": -0.01},
        ]
    )
    params = strategy.select_params(panel, {"sleeve_composite": {"enabled": True}}, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    output = strategy.apply(panel, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    assert set(output.signal_frame["defensive_quality_score"]) == {0.5}
    assert set(output.signal_frame["low_turnover_momentum_score"]) == {0.5}
    assert set(output.signal_frame["risk_overlay_score"]) == {0.5}
    assert output.signal_frame["sleeve_degradation_reasons"].str.contains("degraded:missing_fields").all()


def test_sleeve_composite_missing_quality_core_does_not_score_as_quality() -> None:
    strategy = SleeveCompositeStrategy()
    panel = _sample_panel().drop(columns=["quality_growth_score"])
    params = {
        "defensive_quality_weight": 0.55,
        "low_turnover_momentum_weight": 0.25,
        "risk_overlay_weight": 0.20,
        "momentum_window": 20,
        "top_n": 1,
        "max_symbol_weight": 0.10,
    }

    output = strategy.apply(panel, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    assert set(output.signal_frame["defensive_quality_score"]) == {0.5}
    assert output.signal_frame["defensive_quality_status"].str.contains("missing_required=quality_growth_score").all()


def test_sleeve_composite_preserves_financial_diagnostic_fields() -> None:
    strategy = SleeveCompositeStrategy()
    panel = _sample_panel().assign(
        financial_available_fields=5,
        financial_announce_date="2023-12-31",
        quality_roe_component=0.8,
        quality_cash_flow_component=0.7,
        quality_profit_growth_component=0.6,
        quality_revenue_growth_component=0.5,
        quality_low_debt_component=0.4,
    )
    params = {
        "defensive_quality_weight": 0.55,
        "low_turnover_momentum_weight": 0.25,
        "risk_overlay_weight": 0.20,
        "momentum_window": 20,
        "top_n": 1,
        "max_symbol_weight": 0.10,
    }

    output = strategy.apply(panel, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    assert "financial_available_fields" in output.signal_frame.columns
    assert "financial_announce_date" in output.signal_frame.columns
    assert "quality_cash_flow_component" in output.signal_frame.columns


def test_sleeve_composite_risk_scale_reduces_position_weight() -> None:
    strategy = SleeveCompositeStrategy()
    panel = _sample_panel()
    panel.loc[panel["date"] == pd.Timestamp("2024-01-02"), "risk_scale"] = 0.5
    params = {
        "defensive_quality_weight": 0.55,
        "low_turnover_momentum_weight": 0.25,
        "risk_overlay_weight": 0.20,
        "momentum_window": 20,
        "top_n": 1,
        "max_symbol_weight": 0.10,
    }

    output = strategy.apply(panel, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-02")]
    second_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-03")]
    assert first_day.set_index("symbol").loc["AAA", "weight_unshifted"] == 0.05
    assert second_day.set_index("symbol").loc["AAA", "weight"] == 0.05


def test_sleeve_composite_normalizes_configured_weights() -> None:
    strategy = SleeveCompositeStrategy()
    params = strategy.select_params(
        _sample_panel(),
        {
            "sleeve_composite": {
                "defensive_quality_weight": 2.0,
                "low_turnover_momentum_weight": 1.0,
                "risk_overlay_weight": 1.0,
            }
        },
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
    )

    total = (
        params["defensive_quality_weight"]
        + params["low_turnover_momentum_weight"]
        + params["risk_overlay_weight"]
    )
    assert total == 1.0
    assert params["defensive_quality_weight"] == 0.5


def test_sleeve_composite_empty_input_returns_empty_output() -> None:
    output = SleeveCompositeStrategy().apply(
        pd.DataFrame(),
        {
            "defensive_quality_weight": 0.55,
            "low_turnover_momentum_weight": 0.25,
            "risk_overlay_weight": 0.20,
        },
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
    )

    assert output.returns.empty
    assert output.exposure.empty
    assert output.signal_frame.empty
