from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from quant.strategies.base import BaseStrategy, StrategyOutput
from quant.strategies.low_vol_low_turnover_quality import LowVolLowTurnoverQualityStrategy
from quant.strategies.registry import register
from quant.strategies.strong_index_participation import _add_index_context_features, _rank_component
from quant.strategies.strong_market_core_participation import (
    _add_industry_relative_features,
    _attach_benchmark_weights,
    _basic_eligible,
    _industry_slot_available,
    _ineligible_reason,
    _scale_to_budget,
    _seed_core_panel,
)


@register
class StrongMarketStableCoreBaseStrategy(BaseStrategy):
    name = "strong_market_stable_core_base_v1"
    candidate_name = "strong_market_stable_core_base_v1"
    display_name = "Strong Market Stable Core Base"
    category = "strong_market_participation"
    panel_scope = "portfolio"
    supports_brief = False
    supports_paper_trade = False

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return bool(_strategy_cfg(strategy_cfg).get("enabled", False))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        from quant.walk_forward import _add_local_factor_features

        cfg = _strategy_cfg(strategy_cfg)
        d = _add_local_factor_features(panel)
        if d.empty:
            return d
        d = d.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        d["date"] = pd.to_datetime(d["date"], errors="coerce").dt.normalize().astype("datetime64[ns]")
        d["symbol"] = d["symbol"].astype(str).str.strip()
        d["benchmark_seeded_core"] = False

        d = _seed_core_panel(d, cfg, strategy_cfg.get("_fold_prepare_context", {}))
        d = _add_index_context_features(d, cfg)
        d = _attach_benchmark_weights(d, _fixed_params(cfg))
        if "industry" in d.columns:
            d["industry"] = d["industry"].fillna("").astype(str).str.strip().replace({"": "UNKNOWN", "nan": "UNKNOWN"})
        d = _add_industry_relative_features(d)
        return d.sort_values(["date", "symbol"]).reset_index(drop=True)

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        del slippage, commission, stamp_duty_sell
        cfg = _strategy_cfg(strategy_cfg)
        params = _fixed_params(cfg)
        reason = _ineligible_reason(train)
        if reason:
            params["eligible"] = False
            params["ineligible_reason"] = reason
        return params

    def apply(
        self,
        panel: pd.DataFrame,
        params: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> StrategyOutput:
        if panel.empty:
            return _all_cash_output(panel, params, self, reason="empty_panel")
        if not bool(params.get("eligible", True)):
            return _all_cash_output(panel, params, self, reason=str(params.get("ineligible_reason", "ineligible")))
        reason = _ineligible_reason(panel)
        if reason:
            return _all_cash_output(panel, params, self, reason=reason)

        d = panel.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        d["date"] = pd.to_datetime(d["date"], errors="coerce").dt.normalize().astype("datetime64[ns]")
        d["symbol"] = d["symbol"].astype(str).str.strip()
        for col in [
            "close",
            "mom20",
            "mom60",
            "ma60",
            "amount_ratio20",
            "vol20",
            "ret",
            "benchmark_weight",
            "industry_relative_mom20",
        ]:
            if col in d.columns:
                d[col] = pd.to_numeric(d[col], errors="coerce")
        d["benchmark_weight"] = d.get("benchmark_weight", pd.Series(0.0, index=d.index)).fillna(0.0).clip(lower=0.0)
        d["strong_index_context"] = d.get("strong_index_context", pd.Series(False, index=d.index)).fillna(False).astype(bool)
        d["recovery_index_context"] = d.get("recovery_index_context", pd.Series(False, index=d.index)).fillna(False).astype(bool)
        d["recovery_quality_index_context"] = (
            d.get("recovery_quality_index_context", pd.Series(False, index=d.index)).fillna(False).astype(bool)
        )
        d["benchmark_seeded_core"] = d.get("benchmark_seeded_core", pd.Series(False, index=d.index)).fillna(False).astype(bool)

        eligible = _basic_eligible(d, params)
        benchmark_eligible = eligible & d["benchmark_weight"].gt(0)
        satellite_eligible = eligible & d["benchmark_weight"].le(0)
        weights_cfg = params.get("factor_weights", {})
        d["benchmark_rank_component"] = _rank_component(d, "benchmark_weight", benchmark_eligible, higher_is_better=True)
        d["mom60_rank_component"] = _rank_component(d, "mom60", eligible, higher_is_better=True)
        d["mom20_rank_component"] = _rank_component(d, "mom20", eligible, higher_is_better=True)
        d["amount_rank_component"] = _rank_component(d, "amount_ratio20", eligible, higher_is_better=True)
        d["low_vol_rank_component"] = _rank_component(d, "vol20", eligible, higher_is_better=False)
        d["industry_relative_rank_component"] = _rank_component(
            d, "industry_relative_mom20", eligible, higher_is_better=True
        )
        if str(params.get("core_selection_mode", "")) == "benchmark_then_alpha":
            d["industry_neutral_mom60_rank_component"] = _industry_neutral_rank_component(
                d, "mom60", benchmark_eligible, higher_is_better=True
            )
            d["industry_neutral_mom20_rank_component"] = _industry_neutral_rank_component(
                d, "mom20", benchmark_eligible, higher_is_better=True
            )
            d["industry_neutral_low_vol_rank_component"] = _industry_neutral_rank_component(
                d, "vol20", benchmark_eligible, higher_is_better=False
            )
            d["industry_neutral_amount_rank_component"] = _industry_neutral_rank_component(
                d, "amount_ratio20", benchmark_eligible, higher_is_better=True
            )
            d["core_score"] = (
                float(weights_cfg.get("mom60", 0.45)) * d["industry_neutral_mom60_rank_component"]
                + float(weights_cfg.get("mom20", 0.25)) * d["industry_neutral_mom20_rank_component"]
                + float(weights_cfg.get("low_vol20", 0.20)) * d["industry_neutral_low_vol_rank_component"]
                + float(weights_cfg.get("amount_ratio20", 0.10)) * d["industry_neutral_amount_rank_component"]
            )
        else:
            d["core_score"] = (
                float(weights_cfg.get("benchmark_weight", 0.55)) * d["benchmark_rank_component"]
                + float(weights_cfg.get("mom60", 0.14)) * d["mom60_rank_component"]
                + float(weights_cfg.get("mom20", 0.08)) * d["mom20_rank_component"]
                + float(weights_cfg.get("amount_ratio20", 0.10)) * d["amount_rank_component"]
                + float(weights_cfg.get("low_vol20", 0.08)) * d["low_vol_rank_component"]
                + float(weights_cfg.get("industry_relative_mom20", 0.05)) * d["industry_relative_rank_component"]
            )
        d["satellite_score"] = (
            0.35 * d["mom60_rank_component"]
            + 0.20 * d["mom20_rank_component"]
            + 0.20 * d["amount_rank_component"]
            + 0.15 * d["industry_relative_rank_component"]
            + 0.10 * d["low_vol_rank_component"]
        )
        d["rank_score"] = np.where(benchmark_eligible, d["core_score"], np.where(satellite_eligible, d["satellite_score"], np.nan))
        d["rank"] = np.nan
        ranked = d[d["rank_score"].notna()].sort_values(["date", "rank_score", "symbol"], ascending=[True, False, True])
        if not ranked.empty:
            d.loc[ranked.index, "rank"] = ranked.groupby("date").cumcount() + 1

        current_weights: dict[str, float] = {}
        held_days: dict[str, int] = {}
        previous_context_bucket = ""
        days_since_rebalance = 10**9
        frames: list[pd.DataFrame] = []
        for _, day in d.groupby("date", sort=True):
            day = day.copy()
            context_is_strong = bool(day["strong_index_context"].any())
            context_is_recovery_quality = bool(day["recovery_quality_index_context"].any()) and not context_is_strong
            context_is_recovery = bool(day["recovery_index_context"].any()) and not context_is_strong
            index_drawdown = pd.to_numeric(day.get("strong_index_drawdown", pd.Series(np.nan, index=day.index)), errors="coerce")
            risk_pressure = (
                not context_is_strong
                and not context_is_recovery
                and bool(index_drawdown.notna().any())
                and float(index_drawdown.min()) < float(params.get("risk_drawdown_min", -1.0))
            )
            if context_is_strong:
                context_bucket = "strong"
            elif context_is_recovery_quality:
                context_bucket = "recovery_quality"
            elif context_is_recovery:
                context_bucket = "recovery"
            elif risk_pressure:
                context_bucket = "risk"
            else:
                context_bucket = "mixed"
            if days_since_rebalance < 10**8:
                days_since_rebalance += 1
            should_rebalance = days_since_rebalance >= int(params.get("rebalance_days", 20))
            should_rebalance = should_rebalance or (context_is_strong and not current_weights)
            should_rebalance = should_rebalance or (
                bool(params.get("rebalance_on_context_change", False))
                and bool(previous_context_bucket)
                and context_bucket != previous_context_bucket
            )
            missing_holdings = bool(current_weights) and not set(current_weights).intersection(set(day["symbol"].astype(str)))
            if should_rebalance or missing_holdings:
                base_exposure = (
                    float(params.get("risk_pressure_exposure", params.get("base_exposure", 0.35)))
                    if risk_pressure
                    else float(params.get("mixed_target_exposure", params.get("base_exposure", 0.35)))
                )
                if context_is_recovery_quality:
                    base_exposure = float(params.get("recovery_quality_target_exposure", params.get("recovery_target_exposure", base_exposure)))
                elif context_is_recovery:
                    base_exposure = float(params.get("recovery_weak_target_exposure", params.get("recovery_target_exposure", base_exposure)))
                current_weights = _target_weights_for_day(
                    day,
                    context_is_strong=context_is_strong,
                    base_exposure=base_exposure,
                    strong_target_exposure=float(params.get("strong_target_exposure", 0.70)),
                    core_budget_ratio=float(params.get("core_budget_ratio", 0.82)),
                    satellite_budget_ratio=float(params.get("satellite_budget_ratio", 0.18)),
                    core_top_n=int(params.get("core_top_n", 50)),
                    satellite_top_n=int(params.get("satellite_top_n", 6)),
                    max_symbol_weight=float(params.get("max_symbol_weight", 0.08)),
                    benchmark_weight_multiplier=float(params.get("benchmark_weight_multiplier", 1.8)),
                    max_names_per_industry=LowVolLowTurnoverQualityStrategy._optional_positive_int(
                        params.get("max_names_per_industry", 8)
                    ),
                    benchmark_aware_mode=bool(params.get("benchmark_aware_mode", False)),
                    alpha_tilt_strength=float(params.get("alpha_tilt_strength", 0.0)),
                    core_selection_mode=str(params.get("core_selection_mode", "score")),
                    anchor_sleeve_ratio=float(params.get("anchor_sleeve_ratio", 0.85)),
                    overlay_sleeve_ratio=float(params.get("overlay_sleeve_ratio", 0.15)),
                    overlay_tilt_strength=float(params.get("alpha_tilt_strength", 1.0)),
                )
                days_since_rebalance = 0
            previous_context_bucket = context_bucket

            day["review_day"] = bool(should_rebalance or missing_holdings)
            if context_is_strong:
                review_reason = "strong_context_stable_core"
            elif context_is_recovery_quality:
                review_reason = "recovery_quality_context_stable_core"
            elif context_is_recovery:
                review_reason = "recovery_context_stable_core"
            elif risk_pressure:
                review_reason = "risk_pressure_stable_core"
            else:
                review_reason = "mixed_context_stable_core"
            day["review_reason"] = review_reason
            day["raw_weight"] = day["symbol"].map(lambda symbol: 1.0 if str(symbol) in current_weights else 0.0)
            day["weight_unshifted"] = day["symbol"].map(lambda symbol: current_weights.get(str(symbol), 0.0))
            day["selected"] = (day["weight_unshifted"] > 0).astype(float)
            day["held_days"] = day["symbol"].map(lambda symbol: held_days.get(str(symbol), 0)).fillna(0).astype(int)
            frames.append(day)
            held_days = {symbol: held_days.get(symbol, 0) + 1 for symbol in current_weights}

        out = pd.concat(frames, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)
        out["weight"] = out.groupby("symbol")["weight_unshifted"].shift(1).fillna(0.0)
        out["position_ret"] = out["weight"] * out["ret"].fillna(0.0)
        portfolio_weights = out.pivot(index="date", columns="symbol", values="weight").fillna(0.0)
        turnover = portfolio_weights.diff().abs().sum(axis=1).fillna(portfolio_weights.abs().sum(axis=1))
        sells = portfolio_weights.diff().clip(upper=0).abs().sum(axis=1).fillna(0.0)
        gross = out.groupby("date")["position_ret"].sum()
        costs = turnover * (slippage + commission) + sells * stamp_duty_sell
        returns = gross.sub(costs, fill_value=0.0)
        exposure = portfolio_weights.sum(axis=1)
        signal_cols = [
            "date",
            "symbol",
            "score",
            "rank",
            "selected",
            "raw_weight",
            "weight_unshifted",
            "weight",
            "held_days",
            "review_day",
            "review_reason",
            "ret",
            "position_ret",
            "mom20",
            "mom60",
            "amount_ratio20",
            "vol20",
            "benchmark_weight",
            "benchmark_weight_date",
            "benchmark_seeded_core",
            "strong_index_context",
            "recovery_index_context",
            "recovery_quality_index_context",
            "recovery_tradable_index_context",
            "recovery_breadth_mom20_positive_ratio",
            "recovery_breadth_mom60_positive_ratio",
            "recovery_breadth_industry_positive_ratio",
            "recovery_breadth_avg_amount_ratio20",
            "recovery_leadership_index_context",
            "recovery_leadership_stability_ratio",
            "recovery_leadership_top_industry",
            "strong_index_close",
            "strong_index_ret20",
            "strong_index_ret60",
            "strong_index_ma120",
            "strong_index_vol20",
            "strong_index_vol_threshold",
            "strong_index_drawdown",
            "benchmark_rank_component",
            "mom60_rank_component",
            "mom20_rank_component",
            "amount_rank_component",
            "low_vol_rank_component",
            "industry_relative_rank_component",
            "industry_neutral_mom60_rank_component",
            "industry_neutral_mom20_rank_component",
            "industry_neutral_low_vol_rank_component",
            "industry_neutral_amount_rank_component",
            "industry_relative_mom20",
            "industry",
            "name",
        ]
        out["score"] = out["rank_score"]
        signal_frame = out[[col for col in signal_cols if col in out.columns]].copy()
        return StrategyOutput(returns, exposure, signal_frame, self.build_metadata(params))

    def format_params(self, params: dict[str, Any]) -> str:
        return (
            "strong_market_stable_core_base@"
            f"index={params.get('benchmark_symbol', '')},"
            f"base_exposure={params.get('base_exposure', '')},"
            f"strong_exposure={params.get('strong_target_exposure', '')},"
            f"core_budget={params.get('core_budget_ratio', '')},"
            f"rebalance={params.get('rebalance_days', '')},"
            f"core_top={params.get('core_top_n', '')},"
            f"satellite_top={params.get('satellite_top_n', '')},"
            f"max_w={params.get('max_symbol_weight', '')},"
            f"threshold_status={params.get('threshold_status', '')}"
        )


@register
class StrongMarketStableCoreOnlyStrategy(StrongMarketStableCoreBaseStrategy):
    name = "strong_market_stable_core_only_v1"
    candidate_name = "strong_market_stable_core_only_v1"
    display_name = "Strong Market Stable Core Only (I48 Attribution Only)"
    category = "attribution_diagnostic"
    strategy_role = "attribution_only"
    promotion_boundary = "I48/I49 diagnostic variant; do not add to baseline_admission_all_v1, paper review, simulation, daily brief, or watchlist."

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        params = super().select_params(
            train,
            strategy_cfg,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
        )
        params["threshold_status"] = "i48_core_only_attribution"
        params["core_budget_ratio"] = 1.0
        params["satellite_budget_ratio"] = 0.0
        params["satellite_top_n"] = 0
        return params


@register
class StrongMarketStableSatelliteOnlyStrategy(StrongMarketStableCoreBaseStrategy):
    name = "strong_market_stable_satellite_only_v1"
    candidate_name = "strong_market_stable_satellite_only_v1"
    display_name = "Strong Market Stable Satellite Only (I48 Attribution Only)"
    category = "attribution_diagnostic"
    strategy_role = "attribution_only"
    promotion_boundary = "I48/I49 diagnostic variant; do not add to baseline_admission_all_v1, paper review, simulation, daily brief, or watchlist."

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        params = super().select_params(
            train,
            strategy_cfg,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
        )
        params["threshold_status"] = "i48_satellite_only_attribution"
        params["base_exposure"] = 0.0
        params["core_budget_ratio"] = 0.0
        params["satellite_budget_ratio"] = 1.0
        params["satellite_top_n"] = max(1, int(params.get("satellite_top_n", 6)))
        return params


@register
class StrongMarketBenchmarkAwareCoreStrategy(StrongMarketStableCoreBaseStrategy):
    name = "strong_market_benchmark_aware_core_v1"
    candidate_name = "strong_market_benchmark_aware_core_v1"
    display_name = "Strong Market Benchmark-Aware Core"
    category = "strong_market_participation"
    panel_scope = "portfolio"
    supports_brief = False
    supports_paper_trade = False
    promotion_boundary = (
        "I51 research-only candidate; do not add to baseline_admission_all_v1, paper review, "
        "simulation, daily brief, or watchlist before scoped admission and diagnostics pass."
    )

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return bool(_benchmark_aware_strategy_cfg(strategy_cfg).get("enabled", False))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        from quant.walk_forward import _add_local_factor_features

        cfg = _benchmark_aware_strategy_cfg(strategy_cfg)
        d = _add_local_factor_features(panel)
        if d.empty:
            return d
        d = d.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        d["date"] = pd.to_datetime(d["date"], errors="coerce").dt.normalize().astype("datetime64[ns]")
        d["symbol"] = d["symbol"].astype(str).str.strip()
        d["benchmark_seeded_core"] = False

        d = _seed_core_panel(d, cfg, strategy_cfg.get("_fold_prepare_context", {}))
        d = _add_index_context_features(d, cfg)
        d = _apply_benchmark_aware_context(d, _benchmark_aware_fixed_params(cfg))
        d = d.drop(columns=[col for col in ["benchmark_weight", "benchmark_weight_date"] if col in d.columns])
        d = _attach_benchmark_weights(d, _benchmark_aware_fixed_params(cfg))
        if "industry" in d.columns:
            d["industry"] = d["industry"].fillna("").astype(str).str.strip().replace({"": "UNKNOWN", "nan": "UNKNOWN"})
        d = _add_industry_relative_features(d)
        return d.sort_values(["date", "symbol"]).reset_index(drop=True)

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        del slippage, commission, stamp_duty_sell
        cfg = _benchmark_aware_strategy_cfg(strategy_cfg)
        params = _benchmark_aware_fixed_params(cfg)
        reason = _ineligible_reason(train)
        if reason:
            params["eligible"] = False
            params["ineligible_reason"] = reason
        return params

    def format_params(self, params: dict[str, Any]) -> str:
        return (
            "strong_market_benchmark_aware_core@"
            f"index={params.get('benchmark_symbol', '')},"
            f"risk_exposure={params.get('risk_pressure_exposure', '')},"
            f"mixed_exposure={params.get('mixed_target_exposure', '')},"
            f"strong_exposure={params.get('strong_target_exposure', '')},"
            f"core_budget={params.get('core_budget_ratio', '')},"
            f"satellite_budget={params.get('satellite_budget_ratio', '')},"
            f"core_top={params.get('core_top_n', '')},"
            f"max_w={params.get('max_symbol_weight', '')},"
            f"threshold_status={params.get('threshold_status', '')}"
        )


@register
class BenchmarkCoreAlphaOverlayStrategy(StrongMarketBenchmarkAwareCoreStrategy):
    name = "benchmark_core_alpha_overlay_v1"
    candidate_name = "benchmark_core_alpha_overlay_v1"
    display_name = "Benchmark Core Alpha Overlay"
    category = "strong_market_participation"
    panel_scope = "portfolio"
    supports_brief = False
    supports_paper_trade = False
    promotion_boundary = (
        "I55 research-only candidate; do not add to baseline_admission_all_v1, paper review, "
        "simulation, daily brief, or watchlist before scoped admission and alpha attribution pass."
    )

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return bool(_benchmark_core_alpha_overlay_cfg(strategy_cfg).get("enabled", False))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        from quant.walk_forward import _add_local_factor_features

        cfg = _benchmark_core_alpha_overlay_cfg(strategy_cfg)
        d = _add_local_factor_features(panel)
        if d.empty:
            return d
        d = d.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        d["date"] = pd.to_datetime(d["date"], errors="coerce").dt.normalize().astype("datetime64[ns]")
        d["symbol"] = d["symbol"].astype(str).str.strip()
        d["benchmark_seeded_core"] = False

        d = _seed_core_panel(d, cfg, strategy_cfg.get("_fold_prepare_context", {}))
        d = _add_index_context_features(d, cfg)
        d = _apply_benchmark_aware_context(d, _benchmark_core_alpha_overlay_fixed_params(cfg))
        d = d.drop(columns=[col for col in ["benchmark_weight", "benchmark_weight_date"] if col in d.columns])
        d = _attach_benchmark_weights(d, _benchmark_core_alpha_overlay_fixed_params(cfg))
        if "industry" in d.columns:
            d["industry"] = d["industry"].fillna("").astype(str).str.strip().replace({"": "UNKNOWN", "nan": "UNKNOWN"})
        d = _add_industry_relative_features(d)
        return d.sort_values(["date", "symbol"]).reset_index(drop=True)

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        del slippage, commission, stamp_duty_sell
        cfg = _benchmark_core_alpha_overlay_cfg(strategy_cfg)
        params = _benchmark_core_alpha_overlay_fixed_params(cfg)
        reason = _ineligible_reason(train)
        if reason:
            params["eligible"] = False
            params["ineligible_reason"] = reason
        return params

    def format_params(self, params: dict[str, Any]) -> str:
        return (
            "benchmark_core_alpha_overlay@"
            f"index={params.get('benchmark_symbol', '')},"
            f"anchor={params.get('anchor_sleeve_ratio', '')},"
            f"overlay={params.get('overlay_sleeve_ratio', '')},"
            f"strong_exposure={params.get('strong_target_exposure', '')},"
            f"core_top={params.get('core_top_n', '')},"
            f"max_w={params.get('max_symbol_weight', '')},"
            f"threshold_status={params.get('threshold_status', '')}"
        )


@register
class StrongBenchmarkParticipationBoostStrategy(StrongMarketBenchmarkAwareCoreStrategy):
    name = "strong_benchmark_participation_boost_v1"
    candidate_name = "strong_benchmark_participation_boost_v1"
    display_name = "Strong Benchmark Participation Boost"
    category = "strong_market_participation"
    panel_scope = "portfolio"
    supports_brief = False
    supports_paper_trade = False
    promotion_boundary = (
        "I57 research-only candidate; do not add to baseline_admission_all_v1, paper review, "
        "simulation, daily brief, or watchlist before scoped admission and alpha attribution pass."
    )

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return bool(_strong_benchmark_participation_boost_cfg(strategy_cfg).get("enabled", False))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        from quant.walk_forward import _add_local_factor_features

        cfg = _strong_benchmark_participation_boost_cfg(strategy_cfg)
        d = _add_local_factor_features(panel)
        if d.empty:
            return d
        d = d.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        d["date"] = pd.to_datetime(d["date"], errors="coerce").dt.normalize().astype("datetime64[ns]")
        d["symbol"] = d["symbol"].astype(str).str.strip()
        d["benchmark_seeded_core"] = False

        d = _seed_core_panel(d, cfg, strategy_cfg.get("_fold_prepare_context", {}))
        d = _add_index_context_features(d, cfg)
        d = _apply_benchmark_aware_context(d, _strong_benchmark_participation_boost_fixed_params(cfg))
        d = d.drop(columns=[col for col in ["benchmark_weight", "benchmark_weight_date"] if col in d.columns])
        d = _attach_benchmark_weights(d, _strong_benchmark_participation_boost_fixed_params(cfg))
        if "industry" in d.columns:
            d["industry"] = d["industry"].fillna("").astype(str).str.strip().replace({"": "UNKNOWN", "nan": "UNKNOWN"})
        d = _add_industry_relative_features(d)
        return d.sort_values(["date", "symbol"]).reset_index(drop=True)

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        del slippage, commission, stamp_duty_sell
        cfg = _strong_benchmark_participation_boost_cfg(strategy_cfg)
        params = _strong_benchmark_participation_boost_fixed_params(cfg)
        reason = _ineligible_reason(train)
        if reason:
            params["eligible"] = False
            params["ineligible_reason"] = reason
        return params

    def format_params(self, params: dict[str, Any]) -> str:
        return (
            "strong_benchmark_participation_boost@"
            f"index={params.get('benchmark_symbol', '')},"
            f"strong_exposure={params.get('strong_target_exposure', '')},"
            f"mixed_exposure={params.get('mixed_target_exposure', '')},"
            f"risk_exposure={params.get('risk_pressure_exposure', '')},"
            f"core_top={params.get('core_top_n', '')},"
            f"max_w={params.get('max_symbol_weight', '')},"
            f"threshold_status={params.get('threshold_status', '')}"
        )


@register
class StrongBenchmarkRecoveryParticipationStrategy(StrongMarketBenchmarkAwareCoreStrategy):
    name = "strong_benchmark_recovery_participation_v1"
    candidate_name = "strong_benchmark_recovery_participation_v1"
    display_name = "Strong Benchmark Recovery Participation"
    category = "strong_market_participation"
    panel_scope = "portfolio"
    supports_brief = False
    supports_paper_trade = False
    promotion_boundary = (
        "I61 research-only candidate; do not add to baseline_admission_all_v1, paper review, "
        "simulation, daily brief, or watchlist before scoped admission and recovery-context attribution pass."
    )

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return bool(_strong_benchmark_recovery_participation_cfg(strategy_cfg).get("enabled", False))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        from quant.walk_forward import _add_local_factor_features

        cfg = _strong_benchmark_recovery_participation_cfg(strategy_cfg)
        d = _add_local_factor_features(panel)
        if d.empty:
            return d
        d = d.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        d["date"] = pd.to_datetime(d["date"], errors="coerce").dt.normalize().astype("datetime64[ns]")
        d["symbol"] = d["symbol"].astype(str).str.strip()
        d["benchmark_seeded_core"] = False

        d = _seed_core_panel(d, cfg, strategy_cfg.get("_fold_prepare_context", {}))
        d = _add_index_context_features(d, cfg)
        d = _apply_benchmark_recovery_context(d, _strong_benchmark_recovery_participation_fixed_params(cfg))
        d = d.drop(columns=[col for col in ["benchmark_weight", "benchmark_weight_date"] if col in d.columns])
        d = _attach_benchmark_weights(d, _strong_benchmark_recovery_participation_fixed_params(cfg))
        if "industry" in d.columns:
            d["industry"] = d["industry"].fillna("").astype(str).str.strip().replace({"": "UNKNOWN", "nan": "UNKNOWN"})
        d = _add_industry_relative_features(d)
        return d.sort_values(["date", "symbol"]).reset_index(drop=True)

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        del slippage, commission, stamp_duty_sell
        cfg = _strong_benchmark_recovery_participation_cfg(strategy_cfg)
        params = _strong_benchmark_recovery_participation_fixed_params(cfg)
        reason = _ineligible_reason(train)
        if reason:
            params["eligible"] = False
            params["ineligible_reason"] = reason
        return params

    def format_params(self, params: dict[str, Any]) -> str:
        return (
            "strong_benchmark_recovery_participation@"
            f"index={params.get('benchmark_symbol', '')},"
            f"strong_exposure={params.get('strong_target_exposure', '')},"
            f"recovery_exposure={params.get('recovery_target_exposure', '')},"
            f"risk_exposure={params.get('risk_pressure_exposure', '')},"
            f"core_top={params.get('core_top_n', '')},"
            f"max_w={params.get('max_symbol_weight', '')},"
            f"threshold_status={params.get('threshold_status', '')}"
        )


@register
class StrongBenchmarkRecoveryQualityStrategy(StrongBenchmarkRecoveryParticipationStrategy):
    name = "strong_benchmark_recovery_quality_v1"
    candidate_name = "strong_benchmark_recovery_quality_v1"
    display_name = "Strong Benchmark Recovery Quality"
    category = "strong_market_participation"
    panel_scope = "portfolio"
    supports_brief = False
    supports_paper_trade = False
    promotion_boundary = (
        "I63 research-only candidate; do not add to baseline_admission_all_v1, paper review, "
        "simulation, daily brief, or watchlist before scoped admission and recovery-quality attribution pass."
    )

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return bool(_strong_benchmark_recovery_quality_cfg(strategy_cfg).get("enabled", False))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        from quant.walk_forward import _add_local_factor_features

        cfg = _strong_benchmark_recovery_quality_cfg(strategy_cfg)
        d = _add_local_factor_features(panel)
        if d.empty:
            return d
        d = d.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        d["date"] = pd.to_datetime(d["date"], errors="coerce").dt.normalize().astype("datetime64[ns]")
        d["symbol"] = d["symbol"].astype(str).str.strip()
        d["benchmark_seeded_core"] = False

        d = _seed_core_panel(d, cfg, strategy_cfg.get("_fold_prepare_context", {}))
        d = _add_index_context_features(d, cfg)
        d = _apply_benchmark_recovery_quality_context(d, _strong_benchmark_recovery_quality_fixed_params(cfg))
        d = d.drop(columns=[col for col in ["benchmark_weight", "benchmark_weight_date"] if col in d.columns])
        d = _attach_benchmark_weights(d, _strong_benchmark_recovery_quality_fixed_params(cfg))
        if "industry" in d.columns:
            d["industry"] = d["industry"].fillna("").astype(str).str.strip().replace({"": "UNKNOWN", "nan": "UNKNOWN"})
        d = _add_industry_relative_features(d)
        return d.sort_values(["date", "symbol"]).reset_index(drop=True)

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        del slippage, commission, stamp_duty_sell
        cfg = _strong_benchmark_recovery_quality_cfg(strategy_cfg)
        params = _strong_benchmark_recovery_quality_fixed_params(cfg)
        reason = _ineligible_reason(train)
        if reason:
            params["eligible"] = False
            params["ineligible_reason"] = reason
        return params

    def format_params(self, params: dict[str, Any]) -> str:
        return (
            "strong_benchmark_recovery_quality@"
            f"index={params.get('benchmark_symbol', '')},"
            f"strong_exposure={params.get('strong_target_exposure', '')},"
            f"quality_recovery_exposure={params.get('recovery_quality_target_exposure', '')},"
            f"weak_recovery_exposure={params.get('recovery_target_exposure', '')},"
            f"risk_exposure={params.get('risk_pressure_exposure', '')},"
            f"core_top={params.get('core_top_n', '')},"
            f"max_w={params.get('max_symbol_weight', '')},"
            f"threshold_status={params.get('threshold_status', '')}"
        )


@register
class StrongBenchmarkRecoveryTradableStrategy(StrongBenchmarkRecoveryQualityStrategy):
    name = "strong_benchmark_recovery_tradable_v1"
    candidate_name = "strong_benchmark_recovery_tradable_v1"
    display_name = "Strong Benchmark Recovery Tradable"
    category = "strong_market_participation"
    panel_scope = "portfolio"
    supports_brief = False
    supports_paper_trade = False
    promotion_boundary = (
        "I67 research-only candidate; do not add to baseline_admission_all_v1, paper review, "
        "simulation, daily brief, or watchlist before scoped admission and recovery-breadth attribution pass."
    )

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return bool(_strong_benchmark_recovery_tradable_cfg(strategy_cfg).get("enabled", False))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        from quant.walk_forward import _add_local_factor_features

        cfg = _strong_benchmark_recovery_tradable_cfg(strategy_cfg)
        d = _add_local_factor_features(panel)
        if d.empty:
            return d
        d = d.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        d["date"] = pd.to_datetime(d["date"], errors="coerce").dt.normalize().astype("datetime64[ns]")
        d["symbol"] = d["symbol"].astype(str).str.strip()
        d["benchmark_seeded_core"] = False

        params = _strong_benchmark_recovery_tradable_fixed_params(cfg)
        d = _seed_core_panel(d, cfg, strategy_cfg.get("_fold_prepare_context", {}))
        d = _add_index_context_features(d, cfg)
        d = _apply_benchmark_recovery_quality_context(d, params)
        d = d.drop(columns=[col for col in ["benchmark_weight", "benchmark_weight_date"] if col in d.columns])
        d = _attach_benchmark_weights(d, params)
        if "industry" in d.columns:
            d["industry"] = d["industry"].fillna("").astype(str).str.strip().replace({"": "UNKNOWN", "nan": "UNKNOWN"})
        d = _add_industry_relative_features(d)
        d = _add_recovery_breadth_features(d, params)
        d = _apply_benchmark_recovery_tradable_context(d, params)
        return d.sort_values(["date", "symbol"]).reset_index(drop=True)

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        del slippage, commission, stamp_duty_sell
        cfg = _strong_benchmark_recovery_tradable_cfg(strategy_cfg)
        params = _strong_benchmark_recovery_tradable_fixed_params(cfg)
        reason = _ineligible_reason(train)
        if reason:
            params["eligible"] = False
            params["ineligible_reason"] = reason
        return params

    def format_params(self, params: dict[str, Any]) -> str:
        return (
            "strong_benchmark_recovery_tradable@"
            f"index={params.get('benchmark_symbol', '')},"
            f"strong_exposure={params.get('strong_target_exposure', '')},"
            f"tradable_recovery_exposure={params.get('recovery_quality_target_exposure', '')},"
            f"weak_recovery_exposure={params.get('recovery_target_exposure', '')},"
            f"breadth20_min={params.get('recovery_breadth_mom20_positive_min', '')},"
            f"industry_breadth_min={params.get('recovery_breadth_industry_positive_min', '')},"
            f"threshold_status={params.get('threshold_status', '')}"
        )


@register
class StrongBenchmarkRecoveryLeadershipStrategy(StrongBenchmarkRecoveryTradableStrategy):
    name = "strong_benchmark_recovery_leadership_v1"
    candidate_name = "strong_benchmark_recovery_leadership_v1"
    display_name = "Strong Benchmark Recovery Leadership"
    category = "strong_market_participation"
    panel_scope = "portfolio"
    supports_brief = False
    supports_paper_trade = False
    promotion_boundary = (
        "I70 research-only candidate; tests T-1 visible recovery leadership stability and amount expansion. "
        "Do not add to baseline_admission_all_v1, paper review, simulation, daily brief, or watchlist before "
        "scoped admission and leakage audit pass."
    )

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return bool(_strong_benchmark_recovery_leadership_cfg(strategy_cfg).get("enabled", False))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        d = super().prepare_panel(panel, strategy_cfg)
        if d.empty:
            return d
        cfg = _strong_benchmark_recovery_leadership_cfg(strategy_cfg)
        params = _strong_benchmark_recovery_leadership_fixed_params(cfg)
        d = _add_recovery_leadership_features(d, params)
        d = _apply_benchmark_recovery_leadership_context(d, params)
        return d.sort_values(["date", "symbol"]).reset_index(drop=True)

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        del slippage, commission, stamp_duty_sell
        cfg = _strong_benchmark_recovery_leadership_cfg(strategy_cfg)
        params = _strong_benchmark_recovery_leadership_fixed_params(cfg)
        reason = _ineligible_reason(train)
        if reason:
            params["eligible"] = False
            params["ineligible_reason"] = reason
        return params

    def format_params(self, params: dict[str, Any]) -> str:
        return (
            "strong_benchmark_recovery_leadership@"
            f"index={params.get('benchmark_symbol', '')},"
            f"strong_exposure={params.get('strong_target_exposure', '')},"
            f"leadership_recovery_exposure={params.get('recovery_quality_target_exposure', '')},"
            f"weak_recovery_exposure={params.get('recovery_target_exposure', '')},"
            f"leadership_stability_min={params.get('recovery_leadership_stability_min', '')},"
            f"amount_min={params.get('recovery_leadership_amount_ratio_min', '')},"
            f"threshold_status={params.get('threshold_status', '')}"
        )


def _strategy_cfg(strategy_cfg: dict[str, Any]) -> dict[str, Any]:
    return strategy_cfg.get("local_factor", {}).get("strong_market_stable_core_base", {})


def _benchmark_aware_strategy_cfg(strategy_cfg: dict[str, Any]) -> dict[str, Any]:
    return strategy_cfg.get("local_factor", {}).get("strong_market_benchmark_aware_core", {})


def _benchmark_core_alpha_overlay_cfg(strategy_cfg: dict[str, Any]) -> dict[str, Any]:
    return strategy_cfg.get("local_factor", {}).get("benchmark_core_alpha_overlay", {})


def _strong_benchmark_participation_boost_cfg(strategy_cfg: dict[str, Any]) -> dict[str, Any]:
    return strategy_cfg.get("local_factor", {}).get("strong_benchmark_participation_boost", {})


def _strong_benchmark_recovery_participation_cfg(strategy_cfg: dict[str, Any]) -> dict[str, Any]:
    return strategy_cfg.get("local_factor", {}).get("strong_benchmark_recovery_participation", {})


def _strong_benchmark_recovery_quality_cfg(strategy_cfg: dict[str, Any]) -> dict[str, Any]:
    return strategy_cfg.get("local_factor", {}).get("strong_benchmark_recovery_quality", {})


def _strong_benchmark_recovery_tradable_cfg(strategy_cfg: dict[str, Any]) -> dict[str, Any]:
    return strategy_cfg.get("local_factor", {}).get("strong_benchmark_recovery_tradable", {})


def _strong_benchmark_recovery_leadership_cfg(strategy_cfg: dict[str, Any]) -> dict[str, Any]:
    local_cfg = strategy_cfg.get("local_factor", {})
    cfg = dict(local_cfg.get("strong_benchmark_recovery_tradable", {}) or {})
    cfg.update(local_cfg.get("strong_benchmark_recovery_leadership", {}) or {})
    return cfg


def _fixed_params(cfg: dict[str, Any]) -> dict[str, Any]:
    factor_weights = cfg.get("factor_weights", {})
    return {
        "eligible": True,
        "benchmark_symbol": str(cfg.get("benchmark_symbol", "SH.000300")),
        "threshold_status": str(cfg.get("threshold_status", "pre_registered_i47_first_pass")),
        "trend_window": int(cfg.get("trend_window", 120)),
        "return_short_window": int(cfg.get("return_short_window", 20)),
        "return_long_window": int(cfg.get("return_long_window", 60)),
        "vol_window": int(cfg.get("vol_window", 20)),
        "vol_quantile": float(cfg.get("vol_quantile", 0.70)),
        "vol_threshold_lookback_days": int(cfg.get("vol_threshold_lookback_days", 252)),
        "drawdown_min": float(cfg.get("drawdown_min", -0.12)),
        "seed_top_n": int(cfg.get("seed_top_n", 20)),
        "seed_core_top_n": int(cfg.get("seed_core_top_n", 60)),
        "seed_core_cumulative_weight": float(cfg.get("seed_core_cumulative_weight", 0.60)),
        "core_top_n": int(cfg.get("core_top_n", 50)),
        "satellite_top_n": int(cfg.get("satellite_top_n", 6)),
        "base_exposure": float(cfg.get("base_exposure", 0.35)),
        "strong_target_exposure": float(cfg.get("strong_target_exposure", 0.70)),
        "core_budget_ratio": float(cfg.get("core_budget_ratio", 0.82)),
        "satellite_budget_ratio": float(cfg.get("satellite_budget_ratio", 0.18)),
        "benchmark_weight_multiplier": float(cfg.get("benchmark_weight_multiplier", 1.8)),
        "max_symbol_weight": float(cfg.get("max_symbol_weight", 0.08)),
        "max_names_per_industry": int(cfg.get("max_names_per_industry", 8)),
        "rebalance_days": int(cfg.get("rebalance_days", 20)),
        "amount_min": float(cfg.get("amount_min", 0.0)),
        "amount_ratio_min": float(cfg.get("amount_ratio_min", 0.0)),
        "factor_weights": {
            "benchmark_weight": float(factor_weights.get("benchmark_weight", 0.55)),
            "mom60": float(factor_weights.get("mom60", 0.14)),
            "mom20": float(factor_weights.get("mom20", 0.08)),
            "amount_ratio20": float(factor_weights.get("amount_ratio20", 0.10)),
            "low_vol20": float(factor_weights.get("low_vol20", 0.08)),
            "industry_relative_mom20": float(factor_weights.get("industry_relative_mom20", 0.05)),
        },
    }


def _benchmark_aware_fixed_params(cfg: dict[str, Any]) -> dict[str, Any]:
    params = _fixed_params(cfg)
    factor_weights = cfg.get("factor_weights", {})
    params.update(
        {
            "threshold_status": str(cfg.get("threshold_status", "pre_registered_i51_first_pass")),
            "seed_top_n": int(cfg.get("seed_top_n", 30)),
            "seed_core_top_n": int(cfg.get("seed_core_top_n", 80)),
            "seed_core_cumulative_weight": float(cfg.get("seed_core_cumulative_weight", 0.70)),
            "core_top_n": int(cfg.get("core_top_n", 80)),
            "satellite_top_n": int(cfg.get("satellite_top_n", 6)),
            "risk_pressure_exposure": float(cfg.get("risk_pressure_exposure", 0.15)),
            "mixed_target_exposure": float(cfg.get("mixed_target_exposure", 0.40)),
            "strong_target_exposure": float(cfg.get("strong_target_exposure", 0.70)),
            "core_budget_ratio": float(cfg.get("core_budget_ratio", 0.85)),
            "satellite_budget_ratio": float(cfg.get("satellite_budget_ratio", 0.15)),
            "benchmark_weight_multiplier": float(cfg.get("benchmark_weight_multiplier", 1.0)),
            "max_symbol_weight": float(cfg.get("max_symbol_weight", 0.08)),
            "max_names_per_industry": int(cfg.get("max_names_per_industry", 0)),
            "rebalance_days": int(cfg.get("rebalance_days", 20)),
            "rebalance_on_context_change": bool(cfg.get("rebalance_on_context_change", False)),
            "benchmark_aware_mode": True,
            "core_selection_mode": str(cfg.get("core_selection_mode", "benchmark_then_score")),
            "alpha_tilt_strength": float(cfg.get("alpha_tilt_strength", 0.20)),
            "risk_drawdown_min": float(cfg.get("risk_drawdown_min", cfg.get("drawdown_min", -0.12))),
            "context_mode": str(cfg.get("context_mode", "standard")),
            "relaxed_ret20_min": float(cfg.get("relaxed_ret20_min", -0.02)),
            "relaxed_ret60_min": float(cfg.get("relaxed_ret60_min", 0.0)),
            "factor_weights": {
                "benchmark_weight": float(factor_weights.get("benchmark_weight", 0.55)),
                "mom60": float(factor_weights.get("mom60", 0.15)),
                "mom20": float(factor_weights.get("mom20", 0.10)),
                "amount_ratio20": float(factor_weights.get("amount_ratio20", 0.10)),
                "low_vol20": float(factor_weights.get("low_vol20", 0.05)),
                "industry_relative_mom20": float(factor_weights.get("industry_relative_mom20", 0.05)),
            },
        }
    )
    return params


def _benchmark_core_alpha_overlay_fixed_params(cfg: dict[str, Any]) -> dict[str, Any]:
    params = _benchmark_aware_fixed_params(cfg)
    factor_weights = cfg.get("factor_weights", {})
    params.update(
        {
            "threshold_status": str(cfg.get("threshold_status", "pre_registered_i55_first_pass")),
            "benchmark_aware_mode": True,
            "core_selection_mode": str(cfg.get("core_selection_mode", "benchmark_then_alpha")),
            "anchor_sleeve_ratio": float(cfg.get("anchor_sleeve_ratio", 0.85)),
            "overlay_sleeve_ratio": float(cfg.get("overlay_sleeve_ratio", 0.15)),
            "alpha_tilt_strength": float(cfg.get("alpha_tilt_strength", 1.0)),
            "factor_weights": {
                "benchmark_weight": float(factor_weights.get("benchmark_weight", 0.0)),
                "mom60": float(factor_weights.get("mom60", 0.45)),
                "mom20": float(factor_weights.get("mom20", 0.25)),
                "amount_ratio20": float(factor_weights.get("amount_ratio20", 0.10)),
                "low_vol20": float(factor_weights.get("low_vol20", 0.20)),
                "industry_relative_mom20": float(factor_weights.get("industry_relative_mom20", 0.0)),
            },
        }
    )
    return params


def _strong_benchmark_participation_boost_fixed_params(cfg: dict[str, Any]) -> dict[str, Any]:
    params = _benchmark_aware_fixed_params(cfg)
    factor_weights = cfg.get("factor_weights", {})
    params.update(
        {
            "threshold_status": str(cfg.get("threshold_status", "pre_registered_i57_first_pass")),
            "benchmark_aware_mode": True,
            "core_selection_mode": str(cfg.get("core_selection_mode", "benchmark_then_score")),
            "strong_target_exposure": float(cfg.get("strong_target_exposure", 0.85)),
            "mixed_target_exposure": float(cfg.get("mixed_target_exposure", 0.40)),
            "risk_pressure_exposure": float(cfg.get("risk_pressure_exposure", 0.15)),
            "core_budget_ratio": float(cfg.get("core_budget_ratio", 1.0)),
            "satellite_budget_ratio": float(cfg.get("satellite_budget_ratio", 0.0)),
            "satellite_top_n": int(cfg.get("satellite_top_n", 0)),
            "core_top_n": int(cfg.get("core_top_n", 80)),
            "benchmark_weight_multiplier": float(cfg.get("benchmark_weight_multiplier", 1.0)),
            "max_symbol_weight": float(cfg.get("max_symbol_weight", 0.08)),
            "max_names_per_industry": int(cfg.get("max_names_per_industry", 0)),
            "alpha_tilt_strength": float(cfg.get("alpha_tilt_strength", 0.10)),
            "factor_weights": {
                "benchmark_weight": float(factor_weights.get("benchmark_weight", 0.70)),
                "mom60": float(factor_weights.get("mom60", 0.12)),
                "mom20": float(factor_weights.get("mom20", 0.06)),
                "amount_ratio20": float(factor_weights.get("amount_ratio20", 0.06)),
                "low_vol20": float(factor_weights.get("low_vol20", 0.02)),
                "industry_relative_mom20": float(factor_weights.get("industry_relative_mom20", 0.04)),
            },
        }
    )
    return params


def _strong_benchmark_recovery_participation_fixed_params(cfg: dict[str, Any]) -> dict[str, Any]:
    params = _strong_benchmark_participation_boost_fixed_params(cfg)
    params.update(
        {
            "threshold_status": str(cfg.get("threshold_status", "pre_registered_i61_recovery_first_pass")),
            "recovery_context_mode": str(cfg.get("recovery_context_mode", "trend_repair")),
            "recovery_target_exposure": float(cfg.get("recovery_target_exposure", 0.65)),
            "recovery_ret20_min": float(cfg.get("recovery_ret20_min", -0.02)),
            "recovery_ret60_min": float(cfg.get("recovery_ret60_min", 0.03)),
            "recovery_drawdown_min": float(cfg.get("recovery_drawdown_min", -0.50)),
            "recovery_drawdown_max": float(cfg.get("recovery_drawdown_max", -0.12)),
            "recovery_max_vol_multiplier": float(cfg.get("recovery_max_vol_multiplier", 1.25)),
        }
    )
    return params


def _strong_benchmark_recovery_quality_fixed_params(cfg: dict[str, Any]) -> dict[str, Any]:
    params = _strong_benchmark_recovery_participation_fixed_params(cfg)
    params.update(
        {
            "threshold_status": str(cfg.get("threshold_status", "pre_registered_i63_recovery_quality_first_pass")),
            "recovery_target_exposure": float(cfg.get("recovery_weak_target_exposure", cfg.get("recovery_target_exposure", 0.40))),
            "recovery_quality_target_exposure": float(cfg.get("recovery_quality_target_exposure", 0.65)),
            "recovery_quality_ret20_min": float(cfg.get("recovery_quality_ret20_min", 0.0)),
            "recovery_quality_ret60_min": float(cfg.get("recovery_quality_ret60_min", 0.05)),
            "recovery_quality_max_vol_multiplier": float(cfg.get("recovery_quality_max_vol_multiplier", 1.00)),
        }
    )
    return params


def _strong_benchmark_recovery_tradable_fixed_params(cfg: dict[str, Any]) -> dict[str, Any]:
    params = _strong_benchmark_recovery_quality_fixed_params(cfg)
    params.update(
        {
            "threshold_status": str(cfg.get("threshold_status", "pre_registered_i67_recovery_tradable_first_pass")),
            "recovery_breadth_mom20_positive_min": float(cfg.get("recovery_breadth_mom20_positive_min", 0.45)),
            "recovery_breadth_mom60_positive_min": float(cfg.get("recovery_breadth_mom60_positive_min", 0.35)),
            "recovery_breadth_industry_positive_min": float(cfg.get("recovery_breadth_industry_positive_min", 0.50)),
            "recovery_breadth_amount_ratio_min": float(cfg.get("recovery_breadth_amount_ratio_min", 0.90)),
        }
    )
    return params


def _strong_benchmark_recovery_leadership_fixed_params(cfg: dict[str, Any]) -> dict[str, Any]:
    params = _strong_benchmark_recovery_tradable_fixed_params(cfg)
    params.update(
        {
            "threshold_status": str(cfg.get("threshold_status", "pre_registered_i70_recovery_leadership_first_pass")),
            "recovery_leadership_lookback_days": int(cfg.get("recovery_leadership_lookback_days", 10)),
            "recovery_leadership_min_history_days": int(cfg.get("recovery_leadership_min_history_days", 5)),
            "recovery_leadership_stability_min": float(cfg.get("recovery_leadership_stability_min", 0.50)),
            "recovery_leadership_amount_ratio_min": float(cfg.get("recovery_leadership_amount_ratio_min", 1.05)),
        }
    )
    return params


def _apply_benchmark_aware_context(panel: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    if str(params.get("context_mode", "")) != "benchmark_aware_relaxed":
        return panel
    required = {"strong_index_close", "strong_index_ma120", "strong_index_ret20", "strong_index_ret60", "strong_index_drawdown"}
    if not required.issubset(panel.columns):
        return panel
    d = panel.copy()
    close = pd.to_numeric(d["strong_index_close"], errors="coerce")
    ma = pd.to_numeric(d["strong_index_ma120"], errors="coerce")
    ret20 = pd.to_numeric(d["strong_index_ret20"], errors="coerce")
    ret60 = pd.to_numeric(d["strong_index_ret60"], errors="coerce")
    drawdown = pd.to_numeric(d["strong_index_drawdown"], errors="coerce")
    relaxed = (
        close.gt(ma)
        & ret20.ge(float(params.get("relaxed_ret20_min", -0.02)))
        & ret60.ge(float(params.get("relaxed_ret60_min", 0.0)))
        & drawdown.ge(float(params.get("drawdown_min", -0.12)))
    )
    d["strong_index_context"] = (
        d.get("strong_index_context", pd.Series(False, index=d.index)).fillna(False).astype(bool)
        | relaxed.fillna(False)
    )
    return d


def _apply_benchmark_recovery_context(panel: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    d = _apply_benchmark_aware_context(panel, params)
    if str(params.get("recovery_context_mode", "")) != "trend_repair":
        d["recovery_index_context"] = False
        return d
    required = {
        "strong_index_close",
        "strong_index_ma120",
        "strong_index_ret20",
        "strong_index_ret60",
        "strong_index_vol20",
        "strong_index_vol_threshold",
        "strong_index_drawdown",
    }
    if not required.issubset(d.columns):
        d["recovery_index_context"] = False
        return d
    close = pd.to_numeric(d["strong_index_close"], errors="coerce")
    ma = pd.to_numeric(d["strong_index_ma120"], errors="coerce")
    ret20 = pd.to_numeric(d["strong_index_ret20"], errors="coerce")
    ret60 = pd.to_numeric(d["strong_index_ret60"], errors="coerce")
    vol20 = pd.to_numeric(d["strong_index_vol20"], errors="coerce")
    vol_threshold = pd.to_numeric(d["strong_index_vol_threshold"], errors="coerce")
    drawdown = pd.to_numeric(d["strong_index_drawdown"], errors="coerce")
    recovery = (
        close.gt(ma)
        & ret20.ge(float(params.get("recovery_ret20_min", -0.02)))
        & ret60.ge(float(params.get("recovery_ret60_min", 0.03)))
        & vol20.le(vol_threshold * float(params.get("recovery_max_vol_multiplier", 1.25)))
        & drawdown.ge(float(params.get("recovery_drawdown_min", -0.50)))
        & drawdown.lt(float(params.get("recovery_drawdown_max", -0.12)))
    )
    d["recovery_index_context"] = recovery.fillna(False)
    return d


def _apply_benchmark_recovery_quality_context(panel: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    d = _apply_benchmark_recovery_context(panel, params)
    if "recovery_index_context" not in d.columns:
        d["recovery_quality_index_context"] = False
        return d
    ret20 = pd.to_numeric(d.get("strong_index_ret20", pd.Series(np.nan, index=d.index)), errors="coerce")
    ret60 = pd.to_numeric(d.get("strong_index_ret60", pd.Series(np.nan, index=d.index)), errors="coerce")
    vol20 = pd.to_numeric(d.get("strong_index_vol20", pd.Series(np.nan, index=d.index)), errors="coerce")
    vol_threshold = pd.to_numeric(d.get("strong_index_vol_threshold", pd.Series(np.nan, index=d.index)), errors="coerce")
    quality = (
        d["recovery_index_context"].fillna(False).astype(bool)
        & ret20.ge(float(params.get("recovery_quality_ret20_min", 0.0)))
        & ret60.ge(float(params.get("recovery_quality_ret60_min", 0.05)))
        & vol20.le(vol_threshold * float(params.get("recovery_quality_max_vol_multiplier", 1.00)))
    )
    d["recovery_quality_index_context"] = quality.fillna(False)
    return d


def _add_recovery_breadth_features(panel: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    del params
    d = panel.copy()
    required = {"date", "symbol", "mom20", "mom60", "amount_ratio20"}
    if not required.issubset(d.columns):
        for col in [
            "recovery_breadth_mom20_positive_ratio",
            "recovery_breadth_mom60_positive_ratio",
            "recovery_breadth_industry_positive_ratio",
            "recovery_breadth_avg_amount_ratio20",
        ]:
            d[col] = np.nan
        return d
    d["_breadth_mom20_positive"] = pd.to_numeric(d["mom20"], errors="coerce").gt(0)
    d["_breadth_mom60_positive"] = pd.to_numeric(d["mom60"], errors="coerce").gt(0)
    d["_breadth_amount_ratio20"] = pd.to_numeric(d["amount_ratio20"], errors="coerce")
    d["recovery_breadth_mom20_positive_ratio"] = d.groupby("date")["_breadth_mom20_positive"].transform("mean")
    d["recovery_breadth_mom60_positive_ratio"] = d.groupby("date")["_breadth_mom60_positive"].transform("mean")
    d["recovery_breadth_avg_amount_ratio20"] = d.groupby("date")["_breadth_amount_ratio20"].transform("mean")
    if {"industry", "industry_mom20"}.issubset(d.columns):
        industry_daily = d[["date", "industry", "industry_mom20"]].copy()
        industry_key = industry_daily["industry"].astype("string").str.strip()
        valid_industry = industry_key.notna() & (industry_key != "") & (industry_key.str.lower() != "nan")
        industry_daily["_industry_key"] = industry_key.where(valid_industry, pd.NA)
        industry_daily["_industry_positive"] = pd.to_numeric(industry_daily["industry_mom20"], errors="coerce").gt(0)
        industry_daily = industry_daily.dropna(subset=["_industry_key"]).drop_duplicates(["date", "_industry_key"])
        industry_ratio = industry_daily.groupby("date")["_industry_positive"].mean().rename("recovery_breadth_industry_positive_ratio")
        d = d.drop(columns=["recovery_breadth_industry_positive_ratio"], errors="ignore").merge(
            industry_ratio.reset_index(),
            on="date",
            how="left",
        )
    else:
        d["recovery_breadth_industry_positive_ratio"] = np.nan
    shift_cols = [
        "recovery_breadth_mom20_positive_ratio",
        "recovery_breadth_mom60_positive_ratio",
        "recovery_breadth_industry_positive_ratio",
        "recovery_breadth_avg_amount_ratio20",
    ]
    date_features = d[["date", *shift_cols]].drop_duplicates("date").sort_values("date").reset_index(drop=True)
    date_features[shift_cols] = date_features[shift_cols].shift(1)
    d = d.drop(columns=shift_cols).merge(date_features, on="date", how="left")
    return d.drop(
        columns=[
            "_breadth_mom20_positive",
            "_breadth_mom60_positive",
            "_breadth_amount_ratio20",
        ],
        errors="ignore",
    )


def _apply_benchmark_recovery_tradable_context(panel: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    d = panel.copy()
    if "recovery_quality_index_context" not in d.columns:
        d["recovery_tradable_index_context"] = False
        return d
    mom20_ratio = pd.to_numeric(
        d.get("recovery_breadth_mom20_positive_ratio", pd.Series(np.nan, index=d.index)),
        errors="coerce",
    )
    mom60_ratio = pd.to_numeric(
        d.get("recovery_breadth_mom60_positive_ratio", pd.Series(np.nan, index=d.index)),
        errors="coerce",
    )
    industry_ratio = pd.to_numeric(
        d.get("recovery_breadth_industry_positive_ratio", pd.Series(np.nan, index=d.index)),
        errors="coerce",
    )
    amount_ratio = pd.to_numeric(
        d.get("recovery_breadth_avg_amount_ratio20", pd.Series(np.nan, index=d.index)),
        errors="coerce",
    )
    tradable = (
        d["recovery_quality_index_context"].fillna(False).astype(bool)
        & mom20_ratio.ge(float(params.get("recovery_breadth_mom20_positive_min", 0.45)))
        & mom60_ratio.ge(float(params.get("recovery_breadth_mom60_positive_min", 0.35)))
        & industry_ratio.ge(float(params.get("recovery_breadth_industry_positive_min", 0.50)))
        & amount_ratio.ge(float(params.get("recovery_breadth_amount_ratio_min", 0.90)))
    )
    d["recovery_tradable_index_context"] = tradable.fillna(False)
    d["recovery_quality_index_context"] = d["recovery_tradable_index_context"]
    return d


def _add_recovery_leadership_features(panel: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    d = panel.copy()
    out_cols = [
        "recovery_leadership_stability_ratio",
        "recovery_leadership_top_industry",
    ]
    required = {"date", "industry", "industry_mom20"}
    if not required.issubset(d.columns):
        for col in out_cols:
            d[col] = np.nan if col.endswith("_ratio") else ""
        return d
    industry_daily = d[["date", "industry", "industry_mom20"]].copy()
    industry_daily["_industry_key"] = industry_daily["industry"].astype("string").str.strip()
    valid_industry = (
        industry_daily["_industry_key"].notna()
        & (industry_daily["_industry_key"] != "")
        & (industry_daily["_industry_key"].str.lower() != "nan")
    )
    industry_daily = industry_daily[valid_industry].copy()
    industry_daily["_industry_mom20"] = pd.to_numeric(industry_daily["industry_mom20"], errors="coerce")
    industry_daily = industry_daily.dropna(subset=["_industry_mom20"])
    industry_daily = industry_daily.drop_duplicates(["date", "_industry_key"])
    if industry_daily.empty:
        for col in out_cols:
            d[col] = np.nan if col.endswith("_ratio") else ""
        return d
    leaders = (
        industry_daily.sort_values(["date", "_industry_mom20", "_industry_key"], ascending=[True, False, True])
        .groupby("date", as_index=False)
        .head(1)[["date", "_industry_key"]]
        .rename(columns={"_industry_key": "current_top_industry"})
        .sort_values("date")
        .reset_index(drop=True)
    )
    shifted = leaders.copy()
    shifted["visible_top_industry"] = shifted["current_top_industry"].shift(1)
    lookback = max(1, int(params.get("recovery_leadership_lookback_days", 10)))
    min_history = max(1, int(params.get("recovery_leadership_min_history_days", 5)))
    visible = shifted["visible_top_industry"]
    stability = []
    for idx, industry in enumerate(visible):
        window = visible.iloc[max(0, idx - lookback + 1) : idx + 1].dropna()
        if pd.isna(industry) or len(window) < min_history:
            stability.append(np.nan)
            continue
        stability.append(float((window == industry).mean()))
    shifted["recovery_leadership_stability_ratio"] = stability
    date_features = shifted[["date", "visible_top_industry", "recovery_leadership_stability_ratio"]].rename(
        columns={"visible_top_industry": "recovery_leadership_top_industry"}
    )
    d = d.drop(columns=out_cols, errors="ignore").merge(date_features, on="date", how="left")
    d["recovery_leadership_top_industry"] = d["recovery_leadership_top_industry"].fillna("")
    return d


def _apply_benchmark_recovery_leadership_context(panel: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    d = panel.copy()
    if "recovery_tradable_index_context" not in d.columns:
        d["recovery_leadership_index_context"] = False
        return d
    stability = pd.to_numeric(
        d.get("recovery_leadership_stability_ratio", pd.Series(np.nan, index=d.index)),
        errors="coerce",
    )
    amount_ratio = pd.to_numeric(
        d.get("recovery_breadth_avg_amount_ratio20", pd.Series(np.nan, index=d.index)),
        errors="coerce",
    )
    leadership = (
        d["recovery_tradable_index_context"].fillna(False).astype(bool)
        & stability.ge(float(params.get("recovery_leadership_stability_min", 0.50)))
        & amount_ratio.ge(float(params.get("recovery_leadership_amount_ratio_min", 1.05)))
    )
    d["recovery_leadership_index_context"] = leadership.fillna(False)
    d["recovery_quality_index_context"] = d["recovery_leadership_index_context"]
    return d


def _target_weights_for_day(
    day: pd.DataFrame,
    *,
    context_is_strong: bool,
    base_exposure: float,
    strong_target_exposure: float,
    core_budget_ratio: float,
    satellite_budget_ratio: float,
    core_top_n: int,
    satellite_top_n: int,
    max_symbol_weight: float,
    benchmark_weight_multiplier: float,
    max_names_per_industry: int | None,
    benchmark_aware_mode: bool = False,
    alpha_tilt_strength: float = 0.0,
    core_selection_mode: str = "score",
    anchor_sleeve_ratio: float = 0.85,
    overlay_sleeve_ratio: float = 0.15,
    overlay_tilt_strength: float = 1.0,
) -> dict[str, float]:
    target_exposure = strong_target_exposure if context_is_strong else base_exposure
    target_exposure = max(0.0, min(1.0, target_exposure))
    if target_exposure <= 0:
        return {}
    if context_is_strong:
        core_budget = max(0.0, min(target_exposure, target_exposure * core_budget_ratio))
        satellite_budget = max(0.0, min(target_exposure - core_budget, target_exposure * satellite_budget_ratio))
    else:
        core_budget = target_exposure
        satellite_budget = 0.0

    selected: dict[str, float] = {}
    core = day[day["benchmark_weight"].gt(0) & day["core_score"].notna()].copy()
    if benchmark_aware_mode and core_selection_mode == "benchmark_then_alpha":
        core = core.sort_values(["benchmark_weight", "core_score", "symbol"], ascending=[False, False, True])
    elif benchmark_aware_mode and core_selection_mode == "benchmark_then_score":
        core = core.sort_values(["benchmark_weight", "core_score", "symbol"], ascending=[False, False, True])
    else:
        core = core.sort_values(["core_score", "symbol"], ascending=[False, True])
    caps: dict[str, float] = {}
    if benchmark_aware_mode and core_selection_mode == "benchmark_then_alpha":
        selected = _benchmark_core_alpha_overlay_weights(
            core,
            core_budget=core_budget,
            core_top_n=core_top_n,
            max_symbol_weight=max_symbol_weight,
            anchor_sleeve_ratio=anchor_sleeve_ratio,
            overlay_sleeve_ratio=overlay_sleeve_ratio,
            overlay_tilt_strength=overlay_tilt_strength,
        )
    elif benchmark_aware_mode:
        core = core.head(max(1, core_top_n)).copy()
        if not core.empty:
            score = pd.to_numeric(core["core_score"], errors="coerce").fillna(0.0)
            centered = score - float(score.mean())
            tilt = (1.0 + float(alpha_tilt_strength) * centered).clip(lower=0.85, upper=1.15)
            raw = pd.to_numeric(core["benchmark_weight"], errors="coerce").fillna(0.0).clip(lower=0.0) * tilt
            total = float(raw.sum())
            if total > 0:
                for symbol, weight in zip(core["symbol"].astype(str), raw / total * core_budget, strict=False):
                    selected[symbol] = float(weight)
                    caps[symbol] = max_symbol_weight
        selected = _scale_to_budget(selected, core_budget, caps=caps)
    else:
        for _, row in core.iterrows():
            if len(selected) >= core_top_n:
                break
            symbol = str(row["symbol"])
            cap = min(max_symbol_weight, max(0.01, float(row["benchmark_weight"]) * benchmark_weight_multiplier))
            selected[symbol] = cap
            caps[symbol] = max_symbol_weight
            if sum(selected.values()) >= core_budget:
                break
        selected = _scale_to_budget(selected, core_budget, caps=caps)

    satellite: dict[str, float] = {}
    if satellite_budget > 0:
        satellite_candidates = day[day["benchmark_weight"].le(0) & day["satellite_score"].notna()].sort_values(
            ["satellite_score", "symbol"], ascending=[False, True]
        )
        for _, row in satellite_candidates.iterrows():
            if len(satellite) >= satellite_top_n:
                break
            symbol = str(row["symbol"])
            if not _industry_slot_available(day, [*selected.keys(), *satellite.keys()], symbol, max_names_per_industry):
                continue
            satellite[symbol] = max_symbol_weight
    selected.update(_scale_to_budget(satellite, satellite_budget))
    return {symbol: weight for symbol, weight in selected.items() if weight > 1e-12}


def _benchmark_core_alpha_overlay_weights(
    core: pd.DataFrame,
    *,
    core_budget: float,
    core_top_n: int,
    max_symbol_weight: float,
    anchor_sleeve_ratio: float,
    overlay_sleeve_ratio: float,
    overlay_tilt_strength: float,
) -> dict[str, float]:
    if core_budget <= 0 or core.empty:
        return {}
    selected_core = core.head(max(1, core_top_n)).copy()
    benchmark_weight = pd.to_numeric(selected_core["benchmark_weight"], errors="coerce").fillna(0.0).clip(lower=0.0)
    benchmark_total = float(benchmark_weight.sum())
    if benchmark_total <= 0:
        return {}
    anchor_ratio = max(0.0, min(1.0, float(anchor_sleeve_ratio)))
    overlay_ratio = max(0.0, min(1.0 - anchor_ratio, float(overlay_sleeve_ratio)))
    residual_ratio = max(0.0, 1.0 - anchor_ratio - overlay_ratio)
    anchor = benchmark_weight / benchmark_total
    score = pd.to_numeric(selected_core["core_score"], errors="coerce").fillna(0.0)
    tilt_strength = max(0.0, float(overlay_tilt_strength))
    if score.nunique(dropna=False) <= 1 or tilt_strength <= 0:
        overlay = anchor
    else:
        overlay = score.rank(method="first", pct=True)
        overlay = overlay.pow(tilt_strength)
        overlay = overlay / overlay.sum()
    raw = (anchor_ratio + residual_ratio) * anchor + overlay_ratio * overlay
    weights = {
        symbol: float(weight)
        for symbol, weight in zip(selected_core["symbol"].astype(str), raw * core_budget, strict=False)
    }
    caps = {symbol: float(max_symbol_weight) for symbol in weights}
    return _scale_to_budget(weights, core_budget, caps=caps)


def _industry_neutral_rank_component(
    d: pd.DataFrame,
    column: str,
    eligible: pd.Series,
    *,
    higher_is_better: bool,
) -> pd.Series:
    if column not in d.columns:
        return pd.Series(0.5, index=d.index)
    fallback = _rank_component(d, column, eligible, higher_is_better=higher_is_better)
    if "industry" not in d.columns:
        return fallback
    out = pd.Series(np.nan, index=d.index, dtype=float)
    values = pd.to_numeric(d[column], errors="coerce")
    frame = d[["date", "industry"]].copy()
    frame["_value"] = values
    frame["_eligible"] = eligible.fillna(False).astype(bool)
    frame["_industry_key"] = frame["industry"].astype("string").str.strip()
    valid_industry = frame["_industry_key"].notna() & (frame["_industry_key"] != "") & (frame["_industry_key"].str.lower() != "nan")
    frame["_industry_key"] = frame["_industry_key"].where(valid_industry, pd.NA)
    for _, group in frame[frame["_eligible"] & frame["_value"].notna()].groupby(["date", "_industry_key"], dropna=True):
        if len(group) < 2:
            continue
        out.loc[group.index] = group["_value"].rank(method="average", pct=True, ascending=True)
        if not higher_is_better:
            out.loc[group.index] = 1.0 - out.loc[group.index]
    return out.fillna(fallback).fillna(0.5)


def _all_cash_output(
    panel: pd.DataFrame,
    params: dict[str, Any],
    strategy: StrongMarketStableCoreBaseStrategy,
    *,
    reason: str,
) -> StrategyOutput:
    dates = pd.Index([])
    if "date" in panel.columns:
        dates = pd.Index(sorted(pd.to_datetime(panel["date"], errors="coerce").dropna().unique()))
    empty = pd.Series(0.0, index=dates)
    metadata = strategy.build_metadata(params)
    metadata["ineligible_reason"] = reason
    return StrategyOutput(empty, empty, pd.DataFrame(), metadata)
