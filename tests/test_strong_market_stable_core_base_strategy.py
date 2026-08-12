from __future__ import annotations

import pandas as pd
import pytest

from quant.strategies import available_strategies, get_strategy
from quant.strategies.strong_market_stable_core_base import (
    BenchmarkCoreAlphaOverlayStrategy,
    StrongBenchmarkRecoveryLeadershipStrategy,
    StrongBenchmarkRecoveryQualityStrategy,
    StrongBenchmarkRecoveryParticipationStrategy,
    StrongBenchmarkRecoveryTradableStrategy,
    StrongBenchmarkParticipationBoostStrategy,
    StrongMarketBenchmarkAwareCoreStrategy,
    StrongMarketStableCoreBaseStrategy,
    StrongMarketStableCoreOnlyStrategy,
    StrongMarketStableSatelliteOnlyStrategy,
    _apply_benchmark_aware_context,
    _apply_benchmark_recovery_context,
    _add_recovery_breadth_features,
    _add_recovery_leadership_features,
    _apply_benchmark_recovery_tradable_context,
    _benchmark_aware_fixed_params,
    _industry_neutral_rank_component,
)


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

    assert isinstance(get_strategy("strong_market_stable_core_only_v1"), StrongMarketStableCoreOnlyStrategy)
    assert isinstance(get_strategy("strong_market_stable_satellite_only_v1"), StrongMarketStableSatelliteOnlyStrategy)


def test_i48_split_variants_are_attribution_only_not_candidate_pool_members() -> None:
    for strategy_id in ["strong_market_stable_core_only_v1", "strong_market_stable_satellite_only_v1"]:
        strategy = get_strategy(strategy_id)
        metadata = strategy.build_metadata(_params())
        assert metadata["category"] == "attribution_diagnostic"
        assert metadata["strategy_role"] == "attribution_only"
        assert "do not add to baseline_admission_all_v1" in metadata["promotion_boundary"]
        assert metadata["supports_brief"] is False
        assert metadata["supports_paper_trade"] is False


def test_benchmark_aware_core_is_registered_research_only() -> None:
    assert "strong_market_benchmark_aware_core_v1" in available_strategies()
    strategy = get_strategy("strong_market_benchmark_aware_core_v1")
    assert isinstance(strategy, StrongMarketBenchmarkAwareCoreStrategy)
    assert strategy.supports_brief is False
    assert strategy.supports_paper_trade is False
    assert "research-only candidate" in strategy.build_metadata(_params())["promotion_boundary"]


def test_benchmark_core_alpha_overlay_is_registered_research_only() -> None:
    assert "benchmark_core_alpha_overlay_v1" in available_strategies()
    strategy = get_strategy("benchmark_core_alpha_overlay_v1")
    assert isinstance(strategy, BenchmarkCoreAlphaOverlayStrategy)
    assert strategy.supports_brief is False
    assert strategy.supports_paper_trade is False
    assert "research-only candidate" in strategy.build_metadata(_params())["promotion_boundary"]


def test_strong_benchmark_participation_boost_is_registered_research_only() -> None:
    assert "strong_benchmark_participation_boost_v1" in available_strategies()
    strategy = get_strategy("strong_benchmark_participation_boost_v1")
    assert isinstance(strategy, StrongBenchmarkParticipationBoostStrategy)
    assert strategy.supports_brief is False
    assert strategy.supports_paper_trade is False
    assert "research-only candidate" in strategy.build_metadata(_params())["promotion_boundary"]


def test_strong_benchmark_recovery_participation_is_registered_research_only() -> None:
    assert "strong_benchmark_recovery_participation_v1" in available_strategies()
    strategy = get_strategy("strong_benchmark_recovery_participation_v1")
    assert isinstance(strategy, StrongBenchmarkRecoveryParticipationStrategy)
    assert strategy.supports_brief is False
    assert strategy.supports_paper_trade is False
    assert "research-only candidate" in strategy.build_metadata(_params())["promotion_boundary"]


def test_strong_benchmark_recovery_quality_is_registered_research_only() -> None:
    assert "strong_benchmark_recovery_quality_v1" in available_strategies()
    strategy = get_strategy("strong_benchmark_recovery_quality_v1")
    assert isinstance(strategy, StrongBenchmarkRecoveryQualityStrategy)
    assert strategy.supports_brief is False
    assert strategy.supports_paper_trade is False
    assert "research-only candidate" in strategy.build_metadata(_params())["promotion_boundary"]


def test_strong_benchmark_recovery_tradable_is_registered_research_only() -> None:
    assert "strong_benchmark_recovery_tradable_v1" in available_strategies()
    strategy = get_strategy("strong_benchmark_recovery_tradable_v1")
    assert isinstance(strategy, StrongBenchmarkRecoveryTradableStrategy)
    assert strategy.supports_brief is False
    assert strategy.supports_paper_trade is False
    assert "research-only candidate" in strategy.build_metadata(_params())["promotion_boundary"]


def test_strong_benchmark_recovery_leadership_is_registered_research_only() -> None:
    assert "strong_benchmark_recovery_leadership_v1" in available_strategies()
    strategy = get_strategy("strong_benchmark_recovery_leadership_v1")
    assert isinstance(strategy, StrongBenchmarkRecoveryLeadershipStrategy)
    assert strategy.supports_brief is False
    assert strategy.supports_paper_trade is False
    assert "research-only candidate" in strategy.build_metadata(_params())["promotion_boundary"]


def test_strong_benchmark_participation_boost_raises_strong_context_exposure() -> None:
    strategy = StrongBenchmarkParticipationBoostStrategy()
    panel = _panel()
    params = _params(
        benchmark_aware_mode=True,
        core_selection_mode="benchmark_then_score",
        core_top_n=4,
        satellite_top_n=0,
        core_budget_ratio=1.0,
        satellite_budget_ratio=0.0,
        strong_target_exposure=0.90,
        max_symbol_weight=0.30,
        max_names_per_industry=0,
    )

    output = strategy.apply(panel, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-10")]
    selected = first_day[first_day["weight_unshifted"] > 0]
    assert selected["weight_unshifted"].sum() == pytest.approx(0.90)
    assert set(selected["symbol"]) == {"B1", "B2", "T1", "T2"}


def test_strong_benchmark_recovery_participation_uses_recovery_context_exposure() -> None:
    strategy = StrongBenchmarkRecoveryParticipationStrategy()
    panel = _panel()
    panel["strong_index_context"] = False
    panel["strong_index_close"] = 100.0
    panel["strong_index_ma120"] = 95.0
    panel["strong_index_ret20"] = 0.01
    panel["strong_index_ret60"] = 0.08
    panel["strong_index_vol20"] = 0.18
    panel["strong_index_vol_threshold"] = 0.25
    panel["strong_index_drawdown"] = -0.35
    panel["recovery_index_context"] = True
    params = _params(
        benchmark_aware_mode=True,
        core_selection_mode="benchmark_then_score",
        core_top_n=4,
        satellite_top_n=0,
        core_budget_ratio=1.0,
        satellite_budget_ratio=0.0,
        strong_target_exposure=0.85,
        recovery_target_exposure=0.65,
        risk_pressure_exposure=0.15,
        recovery_ret20_min=-0.02,
        recovery_ret60_min=0.03,
        recovery_max_vol_multiplier=1.25,
        recovery_drawdown_min=-0.50,
        recovery_drawdown_max=-0.12,
        max_symbol_weight=0.30,
        max_names_per_industry=0,
    )

    output = strategy.apply(panel, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-10")]
    selected = first_day[first_day["weight_unshifted"] > 0]
    assert selected["weight_unshifted"].sum() == pytest.approx(0.65)
    assert first_day["recovery_index_context"].eq(True).all()
    assert first_day["review_reason"].eq("recovery_context_stable_core").all()


def test_strong_benchmark_recovery_quality_splits_weak_and_quality_recovery() -> None:
    strategy = StrongBenchmarkRecoveryQualityStrategy()
    panel = _panel(pd.date_range("2024-01-10", periods=4, freq="D"))
    panel["strong_index_context"] = False
    panel["recovery_index_context"] = True
    panel["recovery_quality_index_context"] = False
    panel.loc[panel["date"] >= pd.Timestamp("2024-01-12"), "recovery_quality_index_context"] = True
    params = _params(
        benchmark_aware_mode=True,
        core_selection_mode="benchmark_then_score",
        core_top_n=4,
        satellite_top_n=0,
        core_budget_ratio=1.0,
        satellite_budget_ratio=0.0,
        strong_target_exposure=0.85,
        recovery_target_exposure=0.65,
        recovery_quality_target_exposure=0.65,
        recovery_weak_target_exposure=0.40,
        max_symbol_weight=0.30,
        max_names_per_industry=0,
        rebalance_days=1,
    )

    output = strategy.apply(panel, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    weak_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-10")]
    quality_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-12")]
    assert weak_day.loc[weak_day["weight_unshifted"] > 0, "weight_unshifted"].sum() == pytest.approx(0.40)
    assert quality_day.loc[quality_day["weight_unshifted"] > 0, "weight_unshifted"].sum() == pytest.approx(0.65)
    assert weak_day["review_reason"].eq("recovery_context_stable_core").all()
    assert quality_day["review_reason"].eq("recovery_quality_context_stable_core").all()


def test_recovery_tradable_context_requires_shifted_breadth() -> None:
    panel = _panel(pd.date_range("2024-01-10", periods=3, freq="D"))
    panel.loc[panel["date"] == pd.Timestamp("2024-01-10"), "mom20"] = -0.10
    panel.loc[panel["date"] == pd.Timestamp("2024-01-11"), "mom20"] = 0.10
    panel.loc[panel["date"] == pd.Timestamp("2024-01-12"), "mom20"] = -0.10
    panel["mom60"] = panel["mom20"]
    panel["amount_ratio20"] = 1.2
    panel["industry_mom20"] = panel.groupby(["date", "industry"])["mom20"].transform("mean")
    panel["recovery_index_context"] = True
    panel["recovery_quality_index_context"] = True
    params = _params(
        recovery_breadth_mom20_positive_min=0.50,
        recovery_breadth_mom60_positive_min=0.50,
        recovery_breadth_industry_positive_min=0.50,
        recovery_breadth_amount_ratio_min=1.00,
    )

    with_breadth = _add_recovery_breadth_features(panel, params)
    out = _apply_benchmark_recovery_tradable_context(with_breadth, params)

    first_day = out[out["date"] == pd.Timestamp("2024-01-10")]
    second_day = out[out["date"] == pd.Timestamp("2024-01-11")]
    third_day = out[out["date"] == pd.Timestamp("2024-01-12")]
    assert first_day["recovery_tradable_index_context"].eq(False).all()
    assert second_day["recovery_tradable_index_context"].eq(False).all()
    assert third_day["recovery_tradable_index_context"].eq(True).all()


def test_recovery_leadership_features_use_visible_history() -> None:
    panel = _panel(pd.date_range("2024-01-10", periods=7, freq="D"))
    panel["industry_mom20"] = -0.05
    panel.loc[panel["industry"] == "Bank", "industry_mom20"] = 0.20
    panel.loc[panel["date"] == pd.Timestamp("2024-01-16"), "industry_mom20"] = -0.05
    panel.loc[(panel["date"] == pd.Timestamp("2024-01-16")) & (panel["industry"] == "Tech"), "industry_mom20"] = 0.30
    params = _params(
        recovery_leadership_lookback_days=3,
        recovery_leadership_min_history_days=2,
    )

    out = _add_recovery_leadership_features(panel, params)

    first_day = out[out["date"] == pd.Timestamp("2024-01-10")]
    second_day = out[out["date"] == pd.Timestamp("2024-01-11")]
    stable_day = out[out["date"] == pd.Timestamp("2024-01-13")]
    switched_day = out[out["date"] == pd.Timestamp("2024-01-16")]
    assert first_day["recovery_leadership_stability_ratio"].isna().all()
    assert second_day["recovery_leadership_stability_ratio"].isna().all()
    assert stable_day["recovery_leadership_top_industry"].eq("Bank").all()
    assert stable_day["recovery_leadership_stability_ratio"].eq(1.0).all()
    assert switched_day["recovery_leadership_top_industry"].eq("Bank").all()
    assert switched_day["recovery_leadership_stability_ratio"].eq(1.0).all()


def test_strong_benchmark_recovery_tradable_downgrades_non_tradable_recovery() -> None:
    strategy = StrongBenchmarkRecoveryTradableStrategy()
    panel = _panel(pd.date_range("2024-01-10", periods=4, freq="D"))
    panel["strong_index_context"] = False
    panel["recovery_index_context"] = True
    panel["recovery_quality_index_context"] = True
    panel["recovery_tradable_index_context"] = False
    panel.loc[panel["date"] >= pd.Timestamp("2024-01-12"), "recovery_tradable_index_context"] = True
    panel.loc[panel["date"] < pd.Timestamp("2024-01-12"), "recovery_quality_index_context"] = False
    params = _params(
        benchmark_aware_mode=True,
        core_selection_mode="benchmark_then_score",
        core_top_n=4,
        satellite_top_n=0,
        core_budget_ratio=1.0,
        satellite_budget_ratio=0.0,
        strong_target_exposure=0.85,
        recovery_target_exposure=0.40,
        recovery_quality_target_exposure=0.65,
        recovery_weak_target_exposure=0.40,
        max_symbol_weight=0.30,
        max_names_per_industry=0,
        rebalance_days=1,
    )

    output = strategy.apply(panel, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    weak_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-10")]
    tradable_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-12")]
    assert weak_day.loc[weak_day["weight_unshifted"] > 0, "weight_unshifted"].sum() == pytest.approx(0.40)
    assert tradable_day.loc[tradable_day["weight_unshifted"] > 0, "weight_unshifted"].sum() == pytest.approx(0.65)
    assert weak_day["review_reason"].eq("recovery_context_stable_core").all()
    assert tradable_day["review_reason"].eq("recovery_quality_context_stable_core").all()


def test_recovery_context_marks_trend_repair_without_relaxing_deep_breakdown() -> None:
    panel = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2024-01-10"),
                "symbol": "AAA",
                "strong_index_close": 100.0,
                "strong_index_ma120": 95.0,
                "strong_index_ret20": 0.01,
                "strong_index_ret60": 0.08,
                "strong_index_vol20": 0.18,
                "strong_index_vol_threshold": 0.25,
                "strong_index_drawdown": -0.35,
                "strong_index_context": False,
            },
            {
                "date": pd.Timestamp("2024-01-11"),
                "symbol": "AAA",
                "strong_index_close": 90.0,
                "strong_index_ma120": 95.0,
                "strong_index_ret20": -0.05,
                "strong_index_ret60": -0.02,
                "strong_index_vol20": 0.40,
                "strong_index_vol_threshold": 0.25,
                "strong_index_drawdown": -0.55,
                "strong_index_context": False,
            },
        ]
    )
    params = _params(
        recovery_context_mode="trend_repair",
        recovery_ret20_min=-0.02,
        recovery_ret60_min=0.03,
        recovery_max_vol_multiplier=1.25,
        recovery_drawdown_min=-0.50,
        recovery_drawdown_max=-0.12,
    )

    out = _apply_benchmark_recovery_context(panel, params)

    assert bool(out.loc[0, "recovery_index_context"]) is True
    assert bool(out.loc[1, "recovery_index_context"]) is False


def test_benchmark_core_alpha_overlay_keeps_exposure_and_tilts_core_weights() -> None:
    strategy = BenchmarkCoreAlphaOverlayStrategy()
    panel = _panel()
    params = _params(
        benchmark_aware_mode=True,
        core_selection_mode="benchmark_then_alpha",
        anchor_sleeve_ratio=0.85,
        overlay_sleeve_ratio=0.15,
        alpha_tilt_strength=1.0,
        core_top_n=4,
        satellite_top_n=0,
        core_budget_ratio=1.0,
        satellite_budget_ratio=0.0,
        strong_target_exposure=0.70,
        max_symbol_weight=0.25,
        factor_weights={
            "benchmark_weight": 0.0,
            "mom60": 0.45,
            "mom20": 0.25,
            "low_vol20": 0.20,
            "amount_ratio20": 0.10,
            "industry_relative_mom20": 0.0,
        },
    )

    output = strategy.apply(panel, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-10")]
    selected = first_day[first_day["weight_unshifted"] > 0].set_index("symbol")
    assert selected["weight_unshifted"].sum() == pytest.approx(0.70)
    assert set(selected.index) == {"B1", "B2", "T1", "T2"}
    assert selected.loc["B1", "weight_unshifted"] < 0.25
    assert selected.loc["T2", "weight_unshifted"] > 0.10
    assert "industry_neutral_mom60_rank_component" in first_day.columns


def test_industry_neutral_rank_component_direction_matches_rank_component_semantics() -> None:
    panel = _panel(pd.date_range("2024-01-10", periods=1, freq="D"))
    eligible = panel["benchmark_weight"].gt(0)

    high_is_good = _industry_neutral_rank_component(panel, "mom60", eligible, higher_is_better=True)
    low_is_good = _industry_neutral_rank_component(panel, "vol20", eligible, higher_is_better=False)

    assert high_is_good.loc[panel["symbol"].eq("B1")].iloc[0] > high_is_good.loc[panel["symbol"].eq("B2")].iloc[0]
    assert low_is_good.loc[panel["symbol"].eq("B1")].iloc[0] > low_is_good.loc[panel["symbol"].eq("B2")].iloc[0]


def test_benchmark_aware_core_uses_three_exposure_buckets() -> None:
    strategy = StrongMarketBenchmarkAwareCoreStrategy()
    params = strategy.select_params(
        _panel(),
        {
            "local_factor": {
                "strong_market_benchmark_aware_core": {
                    "enabled": True,
                    "risk_pressure_exposure": 0.15,
                    "mixed_target_exposure": 0.40,
                    "strong_target_exposure": 0.70,
                    "core_budget_ratio": 0.85,
                    "satellite_budget_ratio": 0.15,
                    "core_top_n": 4,
                    "satellite_top_n": 1,
                    "benchmark_weight_multiplier": 1.0,
                    "max_symbol_weight": 0.25,
                    "alpha_tilt_strength": 0.20,
                }
            }
        },
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
    )

    strong_output = strategy.apply(_panel(), params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)
    strong_day = strong_output.signal_frame[strong_output.signal_frame["date"] == pd.Timestamp("2024-01-10")]
    assert strong_day["weight_unshifted"].sum() == pytest.approx(0.70)
    assert strong_day.loc[strong_day["benchmark_weight"] > 0, "weight_unshifted"].sum() >= 0.55

    mixed_panel = _panel()
    mixed_panel["strong_index_context"] = False
    mixed_panel["strong_index_drawdown"] = -0.03
    mixed_output = strategy.apply(mixed_panel, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)
    mixed_day = mixed_output.signal_frame[mixed_output.signal_frame["date"] == pd.Timestamp("2024-01-10")]
    assert mixed_day["weight_unshifted"].sum() == pytest.approx(0.40)
    assert set(mixed_day["review_reason"].unique()) == {"mixed_context_stable_core"}

    risk_panel = _panel()
    risk_panel["strong_index_context"] = False
    risk_panel["strong_index_drawdown"] = -0.20
    risk_output = strategy.apply(risk_panel, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)
    risk_day = risk_output.signal_frame[risk_output.signal_frame["date"] == pd.Timestamp("2024-01-10")]
    assert risk_day["weight_unshifted"].sum() == pytest.approx(0.15)
    assert set(risk_day["review_reason"].unique()) == {"risk_pressure_stable_core"}


def test_benchmark_aware_core_rebalances_when_context_bucket_changes() -> None:
    strategy = StrongMarketBenchmarkAwareCoreStrategy()
    panel = _panel(pd.date_range("2024-01-10", periods=5, freq="D"))
    panel["strong_index_context"] = False
    panel["strong_index_drawdown"] = -0.20
    panel.loc[panel["date"] >= pd.Timestamp("2024-01-12"), "strong_index_context"] = True
    panel.loc[panel["date"] >= pd.Timestamp("2024-01-12"), "strong_index_drawdown"] = -0.04
    params = _params(
        benchmark_aware_mode=True,
        risk_pressure_exposure=0.15,
        risk_drawdown_min=-0.12,
        mixed_target_exposure=0.40,
        strong_target_exposure=0.70,
        core_budget_ratio=0.85,
        satellite_budget_ratio=0.15,
        rebalance_days=20,
        rebalance_on_context_change=True,
    )

    output = strategy.apply(panel, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    day1 = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-10")]
    day3 = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-12")]
    assert day1["weight_unshifted"].sum() == pytest.approx(0.15)
    assert day3["weight_unshifted"].sum() == pytest.approx(0.70)
    assert day3["review_day"].max()


def test_benchmark_aware_context_can_relax_original_strong_filter() -> None:
    panel = _panel()
    panel["strong_index_context"] = False
    panel["strong_index_close"] = 100.0
    panel["strong_index_ma120"] = 95.0
    panel["strong_index_ret20"] = -0.01
    panel["strong_index_ret60"] = 0.03
    panel["strong_index_drawdown"] = -0.04

    prepared = _apply_benchmark_aware_context(
        panel,
        _benchmark_aware_fixed_params(
            {
                "context_mode": "benchmark_aware_relaxed",
                "relaxed_ret20_min": -0.02,
                "relaxed_ret60_min": 0.0,
                "drawdown_min": -0.12,
            }
        ),
    )

    assert prepared["strong_index_context"].any()


def test_benchmark_aware_context_is_standard_unless_configured() -> None:
    panel = _panel()
    panel["strong_index_context"] = False
    panel["strong_index_close"] = 100.0
    panel["strong_index_ma120"] = 95.0
    panel["strong_index_ret20"] = -0.01
    panel["strong_index_ret60"] = 0.03
    panel["strong_index_drawdown"] = -0.04

    prepared = _apply_benchmark_aware_context(panel, _benchmark_aware_fixed_params({}))

    assert not prepared["strong_index_context"].any()


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


def test_stable_core_only_removes_satellite_budget() -> None:
    strategy = StrongMarketStableCoreOnlyStrategy()
    params = strategy.select_params(_panel(), {"local_factor": {"strong_market_stable_core_base": {"enabled": True}}}, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)
    params.update(_params(core_budget_ratio=params["core_budget_ratio"], satellite_budget_ratio=params["satellite_budget_ratio"]))

    output = strategy.apply(_panel(), params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-10")]
    selected = first_day[first_day["weight_unshifted"] > 0]
    assert selected["weight_unshifted"].sum() == pytest.approx(0.70)
    assert selected.loc[selected["benchmark_weight"] <= 0, "weight_unshifted"].sum() == pytest.approx(0.0)


def test_stable_satellite_only_uses_satellite_only_in_strong_context_and_cash_otherwise() -> None:
    strategy = StrongMarketStableSatelliteOnlyStrategy()
    params = strategy.select_params(_panel(), {"local_factor": {"strong_market_stable_core_base": {"enabled": True}}}, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)
    params.update(_params(base_exposure=params["base_exposure"], core_budget_ratio=params["core_budget_ratio"], satellite_budget_ratio=params["satellite_budget_ratio"]))

    output = strategy.apply(_panel(), params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-10")]
    selected = first_day[first_day["weight_unshifted"] > 0]
    assert selected["weight_unshifted"].sum() == pytest.approx(0.70)
    assert selected.loc[selected["benchmark_weight"] > 0, "weight_unshifted"].sum() == pytest.approx(0.0)

    weak_panel = _panel()
    weak_panel["strong_index_context"] = False
    weak_output = strategy.apply(weak_panel, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)
    assert weak_output.signal_frame["weight_unshifted"].sum() == pytest.approx(0.0)


def test_stable_satellite_only_retries_after_empty_rebalance() -> None:
    strategy = StrongMarketStableSatelliteOnlyStrategy()
    params = _params(
        base_exposure=0.0,
        core_budget_ratio=0.0,
        satellite_budget_ratio=1.0,
        rebalance_days=20,
    )
    panel = _panel(pd.date_range("2024-01-10", periods=5, freq="D"))
    panel["strong_index_context"] = False
    panel.loc[panel["date"] >= pd.Timestamp("2024-01-11"), "strong_index_context"] = True

    output = strategy.apply(panel, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    day1 = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-10")]
    day2 = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-11")]
    assert day1["weight_unshifted"].sum() == pytest.approx(0.0)
    assert day2["weight_unshifted"].sum() == pytest.approx(0.70)
    assert day2.loc[day2["benchmark_weight"] > 0, "weight_unshifted"].sum() == pytest.approx(0.0)
