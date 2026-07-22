from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import phase0.strategies as strategies_package
from phase0.research.factors import DEFAULT_WEIGHTS
from phase0.strategies.sleeve_composite import QUALITY_COMPONENT_COLUMNS
from phase0.strategies.registry import get_strategy
from phase0.strategies.sleeve_composite_low_churn_v2 import SleeveCompositeLowChurnV2Strategy


SLOW_SCORE_COLUMNS = [
    "slow_quality_score",
    "slow_earnings_score",
    "slow_value_score",
    "slow_low_vol_score",
    "slow_residual_momentum_score",
]
REQUIRED_SLOW_COLUMNS = [
    *SLOW_SCORE_COLUMNS,
    "slow_factor_available_count",
    "slow_composite_score",
]


def test_strategy_is_exported_and_registered_as_research_only() -> None:
    package_strategy = getattr(strategies_package, "SleeveCompositeLowChurnV2Strategy", None)

    assert package_strategy is SleeveCompositeLowChurnV2Strategy
    registered = get_strategy("sleeve_composite_low_churn_v2")
    assert isinstance(registered, SleeveCompositeLowChurnV2Strategy)
    assert registered.supports_paper_trade is False
    assert registered.supports_brief is False


def _sample_panel() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=140)
    specifications = [
        ("AAA", "Technology", 100.0, 10.0, 1.0, 0.12, 0.0010),
        ("BBB", "Technology", 140.0, 14.0, 1.4, 0.16, 0.0008),
        ("CCC", "Technology", 180.0, 18.0, 1.8, 0.20, 0.0006),
        ("DDD", "Finance", 220.0, 8.0, 0.8, 0.10, 0.0012),
        ("EEE", "Finance", 280.0, 20.0, 2.0, 0.24, 0.0005),
        ("FFF", "Finance", 360.0, 28.0, 2.8, 0.30, 0.0003),
    ]
    rows: list[dict[str, object]] = []
    for symbol_index, (symbol, industry, market_cap, pe_ttm, pb, vol60, daily_return) in enumerate(
        specifications
    ):
        quality_level = 0.9 - symbol_index * 0.1
        for date_index, date in enumerate(dates):
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "ts_code": f"{symbol}.SZ",
                    "name": f"Company {symbol}",
                    "industry": industry,
                    "ret": daily_return,
                    "close": (20.0 + symbol_index * 5.0) * (1.0 + daily_return) ** date_index,
                    "market_cap": market_cap,
                    "pe_ttm": pe_ttm,
                    "pb": pb,
                    "vol60": vol60,
                    "risk_scale": 1.0 - symbol_index * 0.05,
                    "roe": 20.0 - symbol_index,
                    "cash_flow_quality": 1.4 - symbol_index * 0.1,
                    "profit_growth": 30.0 - symbol_index,
                    "revenue_growth": 25.0 - symbol_index,
                    "debt_to_asset": 30.0 + symbol_index,
                    "financial_available_fields": 5,
                    "financial_announce_date": pd.Timestamp("2023-12-29"),
                    "quality_roe_component": quality_level,
                    "quality_cash_flow_component": quality_level - 0.05,
                    "quality_profit_growth_component": quality_level - 0.10,
                    "quality_revenue_growth_component": quality_level - 0.15,
                    "quality_low_debt_component": quality_level - 0.20,
                }
            )
    return pd.DataFrame(rows).sample(frac=1.0, random_state=43).reset_index(drop=True)


def _config(**overrides: object) -> dict[str, object]:
    candidate = {"enabled": True, **overrides}
    return {
        "local_factor": {"quality_growth": {"enabled": False}},
        "sleeve_composite_low_churn_v2": candidate,
    }


def _select(strategy: SleeveCompositeLowChurnV2Strategy, panel: pd.DataFrame, config: dict[str, object]) -> dict[str, object]:
    return strategy.select_params(
        panel,
        config,
        slippage=0.001,
        commission=0.00025,
        stamp_duty_sell=0.0005,
    )


def _prepare_and_apply(panel: pd.DataFrame):
    strategy = SleeveCompositeLowChurnV2Strategy()
    config = _config()
    prepared = strategy.prepare_panel(panel, config)
    params = _select(strategy, prepared, config)
    output = strategy.apply(
        prepared,
        params,
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
    )
    return strategy, prepared, params, output


def test_select_params_uses_normalized_fixed_defaults() -> None:
    strategy = SleeveCompositeLowChurnV2Strategy()

    params = _select(strategy, _sample_panel(), _config())

    assert params["factor_weights"] == DEFAULT_WEIGHTS
    assert sum(params["factor_weights"].values()) == pytest.approx(1.0)
    assert params["min_available_factors"] == 4
    assert "min_available" not in params
    assert params["buy_top_n"] == 30
    assert params["hold_top_n"] == 50
    assert params["rebalance_days"] == 20
    assert params["min_hold_days"] == 20
    assert params["max_symbol_weight"] == 0.04
    assert params["max_names_per_industry"] == 3
    assert (params["train_score"], params["train_sharpe"], params["train_trades"]) == (0.0, 0.0, 0)


def test_select_params_is_independent_of_training_window_contents() -> None:
    strategy = SleeveCompositeLowChurnV2Strategy()
    config = _config(factor_weights={"slow_quality_score": 2.0, "slow_value_score": 1.0})
    first = _sample_panel().head(12)
    second = _sample_panel().tail(27).assign(ret=999.0, slow_composite_score=-999.0)

    first_params = _select(strategy, first, config)
    second_params = _select(strategy, second, config)

    assert first_params == second_params
    assert first_params["factor_weights"] == {
        "slow_quality_score": pytest.approx(2.0 / 3.0),
        "slow_value_score": pytest.approx(1.0 / 3.0),
    }


def test_select_params_rejects_nonpositive_factor_weight_total() -> None:
    strategy = SleeveCompositeLowChurnV2Strategy()

    with pytest.raises(ValueError, match="positive"):
        _select(
            strategy,
            _sample_panel().head(1),
            _config(factor_weights={"slow_quality_score": -1.0, "slow_value_score": 0.0}),
        )


def test_prepare_scores_slow_factors_and_apply_delays_live_weights() -> None:
    panel = _sample_panel()
    config = _config()
    original_config = {
        "local_factor": {"quality_growth": {"enabled": False}},
        "sleeve_composite_low_churn_v2": {"enabled": True},
    }
    strategy = SleeveCompositeLowChurnV2Strategy()

    prepared = strategy.prepare_panel(panel, config)
    params = _select(strategy, prepared, config)
    output = strategy.apply(prepared, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    assert config == original_config
    assert set(REQUIRED_SLOW_COLUMNS).issubset(prepared.columns)
    assert not any(column.startswith("forward_ret_") for column in prepared.columns)
    final_day = prepared[prepared["date"] == prepared["date"].max()]
    assert final_day["slow_factor_available_count"].ge(4).all()
    assert final_day["slow_composite_score"].notna().all()
    first_date = output.signal_frame["date"].min()
    assert output.signal_frame.loc[output.signal_frame["date"] == first_date, "weight"].eq(0.0).all()
    assert output.signal_frame.loc[output.signal_frame["date"] > first_date, "weight"].gt(0.0).any()
    assert "quality_cash_flow_component" in output.signal_frame.columns
    assert output.signal_frame["final_score"].equals(output.signal_frame["slow_composite_score"])
    assert output.signal_frame["score"].equals(output.signal_frame["slow_composite_score"])


@pytest.mark.parametrize(
    ("symbol", "missing_columns"),
    [
        (
            "AAA",
            [
                "roe",
                "cash_flow_quality",
                "debt_to_asset",
                "quality_roe_component",
                "quality_cash_flow_component",
                "quality_low_debt_component",
            ],
        ),
        (
            "BBB",
            [
                "profit_growth",
                "revenue_growth",
                "quality_profit_growth_component",
                "quality_revenue_growth_component",
            ],
        ),
    ],
)
def test_mandatory_quality_and_earnings_gates_exclude_incomplete_symbols(
    symbol: str,
    missing_columns: list[str],
) -> None:
    panel = _sample_panel()
    panel.loc[panel["symbol"] == symbol, missing_columns] = np.nan

    _, prepared, _, output = _prepare_and_apply(panel)

    prepared_symbol = prepared[prepared["symbol"] == symbol]
    signal_symbol = output.signal_frame[output.signal_frame["symbol"] == symbol]
    assert prepared_symbol["slow_composite_score"].isna().all()
    assert signal_symbol["final_score"].isna().all()
    assert signal_symbol["weight_unshifted"].eq(0.0).all()
    assert signal_symbol["weight"].eq(0.0).all()


def test_apply_empty_ineligible_and_missing_features_degrade_safely() -> None:
    strategy = SleeveCompositeLowChurnV2Strategy()
    params = _select(strategy, pd.DataFrame(), _config())

    empty = strategy.apply(pd.DataFrame(), params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)
    ineligible = strategy.apply(
        _sample_panel().head(6),
        {**params, "eligible": False},
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
    )
    prepared = strategy.prepare_panel(_sample_panel(), _config()).drop(columns=["slow_quality_score"])
    degraded = strategy.apply(prepared, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    assert empty.returns.empty and empty.exposure.empty and empty.signal_frame.empty
    assert ineligible.returns.empty and ineligible.exposure.empty and ineligible.signal_frame.empty
    expected_dates = pd.Index(sorted(prepared["date"].unique()))
    pd.testing.assert_series_equal(degraded.returns, pd.Series(0.0, index=expected_dates))
    pd.testing.assert_series_equal(degraded.exposure, pd.Series(0.0, index=expected_dates))
    assert degraded.signal_frame.empty
    assert degraded.metadata["strategy_id"] == "sleeve_composite_low_churn_v2"


def test_research_only_identity_enablement_and_stable_format() -> None:
    strategy = SleeveCompositeLowChurnV2Strategy()
    params = _select(strategy, pd.DataFrame(), _config())

    assert strategy.name == "sleeve_composite_low_churn_v2"
    assert strategy.candidate_name == "sleeve_composite_low_churn_v2"
    assert strategy.category == "sleeve_composite_low_churn_v2"
    assert strategy.panel_scope == "portfolio"
    assert strategy.supports_brief is False
    assert strategy.supports_paper_trade is False
    assert strategy.is_enabled({}) is False
    assert strategy.is_enabled(_config()) is True
    assert strategy.format_params(params) == (
        "sleeve_composite_low_churn_v2:"
        "w=slow_quality_score:0.3/slow_value_score:0.2/slow_low_vol_score:0.2/"
        "slow_earnings_score:0.15/slow_residual_momentum_score:0.15,"
        "min_available=4,buy_top=30,hold_top=50,rebalance=20d,min_hold=20d,"
        "max_w=0.04,industry_cap=3"
    )
    assert set(QUALITY_COMPONENT_COLUMNS).issuperset(
        {"quality_roe_component", "quality_profit_growth_component"}
    )


def test_format_params_audits_minimum_factor_availability() -> None:
    strategy = SleeveCompositeLowChurnV2Strategy()
    params = _select(strategy, pd.DataFrame(), _config())

    default_format = strategy.format_params(params)
    stricter_format = strategy.format_params({**params, "min_available_factors": 5})

    assert "min_available=4" in default_format
    assert "min_available=5" in stricter_format
    assert default_format != stricter_format
