from __future__ import annotations

import pandas as pd

from quant.strategies import available_strategies, get_strategy
from quant.strategies.strong_index_participation import (
    StrongIndexParticipationDynamicTriggerStrategy,
    StrongIndexParticipationStrategy,
)


def _panel(dates: pd.DatetimeIndex | None = None) -> pd.DataFrame:
    rows = []
    if dates is None:
        dates = pd.date_range("2024-01-10", periods=4, freq="D")
    symbols = [
        ("T1", "Tech", 0.60, 0.30, 1.6),
        ("T2", "Tech", 0.58, 0.29, 1.5),
        ("T3", "Tech", 0.56, 0.28, 1.4),
        ("T4", "Tech", 0.54, 0.27, 1.3),
        ("T5", "Tech", 0.52, 0.26, 1.2),
        ("H1", "Health", 0.40, 0.25, 1.1),
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
                    "mom20": 0.10,
                    "mom60": mom60,
                    "vol20": 0.10,
                    "amount_ratio20": amount_ratio,
                    "upper_shadow_pct": 0.5,
                    "breakout20": 1.0,
                    "resid_mom20": resid,
                    "industry_relative_mom20": 0.2 if industry == "Tech" else 0.1,
                    "industry": industry,
                    "strong_index_context": True,
                }
            )
    return pd.DataFrame(rows)


def _params(**overrides) -> dict:
    base = {
        "eligible": True,
        "benchmark_symbol": "SH.000300",
        "threshold_status": "pre_registered_unvalidated_first_pass",
        "trend_window": 3,
        "return_short_window": 1,
        "return_long_window": 2,
        "vol_window": 2,
        "vol_quantile": 0.7,
        "vol_threshold_lookback_days": 3,
        "drawdown_min": -0.12,
        "buy_top_n": 5,
        "hold_top_n": 10,
        "rebalance_days": 2,
        "min_hold_days": 1,
        "max_symbol_weight": 0.05,
        "max_names_per_industry": 4,
        "amount_ratio_min": 1.0,
        "amount_ratio_max": 3.0,
        "upper_shadow_max": 1.0,
        "vol_cross_section_quantile": 0.80,
        "factor_weights": {
            "mom60": 0.35,
            "resid_mom20": 0.25,
            "industry_relative_mom20": 0.20,
            "amount_ratio20": 0.10,
            "breakout20": 0.05,
            "low_vol20": 0.05,
        },
    }
    base.update(overrides)
    return base


def test_strong_index_participation_strategy_is_registered() -> None:
    assert "strong_index_participation_v1" in available_strategies()
    strategy = get_strategy("strong_index_participation_v1")
    assert isinstance(strategy, StrongIndexParticipationStrategy)
    assert strategy.supports_brief is False
    assert strategy.supports_paper_trade is False

    dynamic_strategy = get_strategy("strong_index_participation_dynamic_trigger_v1")
    assert isinstance(dynamic_strategy, StrongIndexParticipationDynamicTriggerStrategy)
    assert dynamic_strategy.supports_brief is False
    assert dynamic_strategy.supports_paper_trade is False


def test_strong_index_participation_shifts_index_context(monkeypatch) -> None:
    strategy = StrongIndexParticipationStrategy()
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    index_df = pd.DataFrame({"date": dates, "close": [10, 10, 10, 11, 12, 13, 14, 13, 12, 15]})

    def fake_load_index(symbol, start, end):
        assert symbol == "SH.000300"
        return index_df

    monkeypatch.setattr("quant.strategies.strong_index_participation.load_index_daily_from_local_history", fake_load_index)
    panel = _panel(pd.date_range("2024-01-01", periods=10, freq="D"))
    prepared = strategy.prepare_panel(
        panel,
        {
            "local_factor": {
                "strong_index_participation": {
                    "benchmark_symbol": "SH.000300",
                    "trend_window": 3,
                    "return_short_window": 1,
                    "return_long_window": 2,
                    "vol_window": 2,
                    "vol_threshold_lookback_days": 3,
                    "vol_quantile": 1.0,
                }
            }
        },
    )

    context_by_date = prepared.groupby("date")["strong_index_context"].first()
    assert bool(context_by_date.loc[pd.Timestamp("2024-01-05")]) is False
    assert bool(context_by_date.loc[pd.Timestamp("2024-01-06")]) is True


def test_strong_index_participation_uses_industry_cap_and_fixed_weight() -> None:
    strategy = StrongIndexParticipationStrategy()

    output = strategy.apply(_panel(), _params(), slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-10")]
    selected = first_day.loc[first_day["weight_unshifted"] > 0]
    assert set(selected["symbol"]) == {"T1", "T2", "T3", "T4", "H1"}
    assert "T5" not in set(selected["symbol"])
    assert selected.loc[selected["industry"] == "Tech", "symbol"].nunique() == 4
    assert selected["weight_unshifted"].eq(0.05).all()

    second_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-11")]
    assert second_day["weight"].sum() == 0.25


def test_strong_index_participation_missing_required_field_returns_cash() -> None:
    strategy = StrongIndexParticipationStrategy()
    panel = _panel().drop(columns=["ma60"])

    output = strategy.apply(panel, _params(), slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    assert output.returns.eq(0.0).all()
    assert output.exposure.eq(0.0).all()
    assert output.signal_frame.empty
    assert output.metadata["ineligible_reason"] == "missing_required_fields:ma60"


def test_strong_index_participation_does_not_open_when_context_is_weak() -> None:
    strategy = StrongIndexParticipationStrategy()
    panel = _panel()
    panel["strong_index_context"] = False

    output = strategy.apply(panel, _params(), slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    assert output.signal_frame["weight_unshifted"].eq(0.0).all()
    assert output.exposure.eq(0.0).all()


def test_dynamic_trigger_opens_on_non_rebalance_false_to_true_context() -> None:
    strategy = StrongIndexParticipationDynamicTriggerStrategy()
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

    trigger_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-11")]
    assert trigger_day["dynamic_review_trigger"].eq(True).all()
    assert trigger_day["review_reason"].eq("dynamic_strong_context_on").all()
    assert trigger_day["weight_unshifted"].sum() == 0.25

    next_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-12")]
    assert next_day["dynamic_review_trigger"].eq(False).all()
    assert next_day["review_reason"].eq("").all()
    assert next_day["weight"].sum() == 0.25


def test_base_strategy_does_not_open_on_non_rebalance_false_to_true_context() -> None:
    strategy = StrongIndexParticipationStrategy()
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

    assert output.signal_frame["dynamic_review_trigger"].eq(False).all()
    assert output.signal_frame["weight_unshifted"].eq(0.0).all()
    assert output.exposure.eq(0.0).all()


def test_strong_index_participation_row_with_missing_ret_is_not_selectable() -> None:
    strategy = StrongIndexParticipationStrategy()
    panel = _panel()
    first_day = panel["date"] == pd.Timestamp("2024-01-10")
    panel.loc[first_day & panel["symbol"].isin(["T1", "T2", "T3", "T4"]), "ret"] = pd.NA

    output = strategy.apply(panel, _params(), slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    selected = output.signal_frame[
        (output.signal_frame["date"] == pd.Timestamp("2024-01-10"))
        & (output.signal_frame["weight_unshifted"] > 0)
    ]
    assert not {"T1", "T2", "T3", "T4"} & set(selected["symbol"])
