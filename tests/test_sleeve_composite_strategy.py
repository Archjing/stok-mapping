from __future__ import annotations

import pandas as pd
import pytest

from quant.strategies import available_strategies, get_strategy
from quant.strategies.sleeve_composite import SleeveCompositeLowChurnStrategy, SleeveCompositeStrategy


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


def _low_churn_characterization_panel() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=8)
    daily_scores = [
        {"AAA": 0.9, "BBB": 0.8, "CCC": 0.7},
        {"AAA": 0.8, "BBB": 0.9, "CCC": 0.7},
        {"AAA": 0.8, "BBB": 0.9, "CCC": 0.7},
        {"AAA": 0.6, "BBB": 0.9, "CCC": 0.8},
        {"AAA": 0.6, "BBB": 0.9, "CCC": 0.8},
        {"AAA": 0.6, "BBB": 0.9, "CCC": 0.8},
        {"AAA": 0.6, "BBB": 0.9, "CCC": 0.8},
        {"AAA": 0.6, "BBB": 0.9, "CCC": 0.8},
    ]
    returns = {"AAA": 0.01, "BBB": 0.02, "CCC": -0.01}
    rows = []
    for date, scores in zip(dates, daily_scores, strict=True):
        for symbol in ["AAA", "BBB", "CCC"]:
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "ret": returns[symbol],
                    "quality_growth_score": scores[symbol],
                }
            )
    return pd.DataFrame(rows)


def test_sleeve_composite_strategy_is_registered() -> None:
    assert "sleeve_composite_v1" in available_strategies()
    assert isinstance(get_strategy("sleeve_composite_v1"), SleeveCompositeStrategy)
    assert "sleeve_composite_low_churn_v1" in available_strategies()
    assert isinstance(get_strategy("sleeve_composite_low_churn_v1"), SleeveCompositeLowChurnStrategy)


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


def test_sleeve_composite_low_churn_holds_between_rebalance_days() -> None:
    strategy = SleeveCompositeLowChurnStrategy()
    panel = _sample_panel()
    panel.loc[panel["date"] == pd.Timestamp("2024-01-03"), "quality_growth_score"] = [0.10, 0.95, 0.30]
    params = {
        "defensive_quality_weight": 1.0,
        "low_turnover_momentum_weight": 0.0,
        "risk_overlay_weight": 0.0,
        "momentum_window": 20,
        "top_n": 1,
        "buy_top_n": 1,
        "hold_top_n": 2,
        "rebalance_days": 3,
        "min_hold_days": 3,
        "max_symbol_weight": 0.10,
        "max_names_per_industry": None,
    }

    output = strategy.apply(panel, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-02")]
    second_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-03")]
    assert set(first_day.loc[first_day["weight_unshifted"] > 0, "symbol"]) == {"AAA"}
    assert set(second_day.loc[second_day["weight_unshifted"] > 0, "symbol"]) == {"AAA"}
    assert second_day["review_reason"].eq("").all()
    assert second_day.set_index("symbol").loc["AAA", "held_days"] == 1


def test_sleeve_composite_low_churn_respects_industry_slots() -> None:
    strategy = SleeveCompositeLowChurnStrategy()
    panel = _sample_panel().assign(industry=["Tech", "Tech", "Health"] * 3)
    params = {
        "defensive_quality_weight": 1.0,
        "low_turnover_momentum_weight": 0.0,
        "risk_overlay_weight": 0.0,
        "momentum_window": 20,
        "top_n": 2,
        "buy_top_n": 2,
        "hold_top_n": 4,
        "rebalance_days": 3,
        "min_hold_days": 3,
        "max_symbol_weight": 0.50,
        "max_names_per_industry": 1,
    }

    output = strategy.apply(panel, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-02")]
    selected = set(first_day.loc[first_day["weight_unshifted"] > 0, "symbol"])
    assert selected == {"AAA", "CCC"}
    assert "BBB" not in selected


def test_sleeve_composite_low_churn_v1_characterization_with_costs() -> None:
    panel = _low_churn_characterization_panel()
    params = {
        "defensive_quality_weight": 1.0,
        "low_turnover_momentum_weight": 0.0,
        "risk_overlay_weight": 0.0,
        "momentum_window": 20,
        "top_n": 1,
        "buy_top_n": 1,
        "hold_top_n": 2,
        "rebalance_days": 2,
        "min_hold_days": 5,
        "max_symbol_weight": 0.50,
        "max_names_per_industry": None,
    }

    output = SleeveCompositeLowChurnStrategy().apply(
        panel,
        params,
        slippage=0.001,
        commission=0.00025,
        stamp_duty_sell=0.0005,
    )
    signal = output.signal_frame
    dates = list(pd.bdate_range("2024-01-02", periods=8))

    selected = signal.loc[signal["selected"] > 0, ["date", "symbol", "weight_unshifted", "held_days"]]
    assert list(selected.itertuples(index=False, name=None)) == [
        (dates[0], "AAA", 0.5, 0),
        (dates[1], "AAA", 0.5, 1),
        (dates[2], "AAA", 0.5, 2),
        (dates[3], "AAA", 0.5, 3),
        (dates[4], "AAA", 0.5, 4),
        (dates[5], "AAA", 0.5, 5),
        (dates[6], "BBB", 0.5, 0),
        (dates[7], "BBB", 0.5, 1),
    ]

    live = signal.loc[signal["weight"] > 0, ["date", "symbol", "weight"]]
    assert list(live.itertuples(index=False, name=None)) == [
        (dates[1], "AAA", 0.5),
        (dates[2], "AAA", 0.5),
        (dates[3], "AAA", 0.5),
        (dates[4], "AAA", 0.5),
        (dates[5], "AAA", 0.5),
        (dates[6], "AAA", 0.5),
        (dates[7], "BBB", 0.5),
    ]
    review_reason = signal.groupby("date")["review_reason"].first()
    assert review_reason.tolist() == [
        "fixed_rebalance",
        "",
        "fixed_rebalance",
        "",
        "fixed_rebalance",
        "",
        "fixed_rebalance",
        "",
    ]
    assert output.returns.tolist() == pytest.approx(
        [0.0, 0.004375, 0.005, 0.005, 0.005, 0.005, 0.005, 0.0085]
    )


def test_sleeve_composite_low_churn_v1_exits_only_at_eligible_review() -> None:
    panel = _low_churn_characterization_panel()
    params = {
        "defensive_quality_weight": 1.0,
        "low_turnover_momentum_weight": 0.0,
        "risk_overlay_weight": 0.0,
        "momentum_window": 20,
        "top_n": 1,
        "buy_top_n": 1,
        "hold_top_n": 2,
        "rebalance_days": 2,
        "min_hold_days": 5,
        "max_symbol_weight": 0.50,
        "max_names_per_industry": None,
    }

    signal = SleeveCompositeLowChurnStrategy().apply(
        panel,
        params,
        slippage=0.001,
        commission=0.00025,
        stamp_duty_sell=0.0005,
    ).signal_frame.set_index(["date", "symbol"])
    dates = list(pd.bdate_range("2024-01-02", periods=8))

    assert signal.loc[(dates[2], "AAA"), "rank"] == 2.0
    assert signal.loc[(dates[2], "AAA"), "selected"] == 1.0
    assert signal.loc[(dates[4], "AAA"), "rank"] == 3.0
    assert signal.loc[(dates[4], "AAA"), "held_days"] == 4
    assert signal.loc[(dates[4], "AAA"), "selected"] == 1.0
    assert signal.loc[(dates[5], "AAA"), "held_days"] == 5
    assert signal.loc[(dates[5], "AAA"), "review_reason"] == ""
    assert signal.loc[(dates[5], "AAA"), "selected"] == 1.0
    assert signal.loc[(dates[6], "AAA"), "selected"] == 0.0
    assert signal.loc[(dates[6], "BBB"), "selected"] == 1.0
