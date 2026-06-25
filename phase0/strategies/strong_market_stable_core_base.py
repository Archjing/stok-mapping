from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from phase0.strategies.base import BaseStrategy, StrategyOutput
from phase0.strategies.low_vol_low_turnover_quality import LowVolLowTurnoverQualityStrategy
from phase0.strategies.registry import register
from phase0.strategies.strong_index_participation import _add_index_context_features, _rank_component
from phase0.strategies.strong_market_core_participation import (
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
        from phase0.walk_forward import _add_local_factor_features

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
        days_since_rebalance = 10**9
        frames: list[pd.DataFrame] = []
        for _, day in d.groupby("date", sort=True):
            day = day.copy()
            context_is_strong = bool(day["strong_index_context"].any())
            if days_since_rebalance < 10**8:
                days_since_rebalance += 1
            should_rebalance = days_since_rebalance >= int(params.get("rebalance_days", 20))
            should_rebalance = should_rebalance or (context_is_strong and not current_weights)
            missing_holdings = bool(current_weights) and not set(current_weights).intersection(set(day["symbol"].astype(str)))
            if should_rebalance or missing_holdings:
                current_weights = _target_weights_for_day(
                    day,
                    context_is_strong=context_is_strong,
                    base_exposure=float(params.get("base_exposure", 0.35)),
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
                )
                days_since_rebalance = 0

            day["review_day"] = bool(should_rebalance or missing_holdings)
            day["review_reason"] = (
                "strong_context_stable_core" if context_is_strong else "base_context_stable_core"
            )
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
            "benchmark_weight",
            "benchmark_weight_date",
            "benchmark_seeded_core",
            "strong_index_context",
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


def _strategy_cfg(strategy_cfg: dict[str, Any]) -> dict[str, Any]:
    return strategy_cfg.get("local_factor", {}).get("strong_market_stable_core_base", {})


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
    core = day[day["benchmark_weight"].gt(0) & day["core_score"].notna()].sort_values(
        ["core_score", "symbol"], ascending=[False, True]
    )
    caps: dict[str, float] = {}
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
