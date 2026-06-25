from __future__ import annotations

import sqlite3
from typing import Any

import numpy as np
import pandas as pd

from phase0.local_history import local_history_path
from phase0.strategies.base import BaseStrategy, StrategyOutput
from phase0.strategies.low_vol_low_turnover_quality import LowVolLowTurnoverQualityStrategy
from phase0.strategies.registry import register
from phase0.strategies.strong_index_participation import (
    _add_index_context_features,
    _rank_component,
    build_hard_filter_masks,
)


@register
class StrongMarketEffectiveParticipationStrategy(BaseStrategy):
    name = "strong_market_effective_participation_v1"
    candidate_name = "strong_market_effective_participation_v1"
    display_name = "Strong Market Effective Participation"
    category = "strong_market_participation"
    panel_scope = "portfolio"
    supports_brief = False
    supports_paper_trade = False

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        cfg = _strategy_cfg(strategy_cfg)
        return bool(cfg.get("enabled", False))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        from phase0.walk_forward import _add_local_factor_features

        d = _add_local_factor_features(panel)
        if d.empty:
            return d
        d = d.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        d["date"] = pd.to_datetime(d["date"], errors="coerce").dt.normalize().astype("datetime64[ns]")

        if {"date", "industry", "mom20"}.issubset(d.columns):
            industries = d["industry"].astype("string").str.strip()
            valid_industry = industries.notna() & (industries != "") & (industries.str.lower() != "nan")
            d["_industry_key"] = industries.where(valid_industry, pd.NA)
            for window in [20, 60]:
                mom_col = f"mom{window}"
                if mom_col not in d.columns:
                    continue
                industry_mom_col = f"industry_mom{window}"
                relative_col = f"industry_relative_mom{window}"
                d[industry_mom_col] = d.groupby(["date", "_industry_key"], dropna=True)[mom_col].transform("mean")
                d[relative_col] = d[industry_mom_col] - d.groupby("date")[mom_col].transform("mean")
            d = d.drop(columns=["_industry_key"])

        d = _add_index_context_features(d, _strategy_cfg(strategy_cfg))
        return _attach_benchmark_weights(d, _fixed_params(_strategy_cfg(strategy_cfg)))

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
        d["symbol"] = d["symbol"].astype(str)
        if "strong_index_context" not in d.columns:
            d["strong_index_context"] = False

        numeric_cols = [
            "close",
            "mom20",
            "mom60",
            "ma60",
            "amount_ratio20",
            "upper_shadow_pct",
            "vol20",
            "ret",
            "resid_mom20",
            "industry_relative_mom20",
            "industry_relative_mom60",
            "breakout20",
            "benchmark_weight",
        ]
        for col in numeric_cols:
            if col in d.columns:
                d[col] = pd.to_numeric(d[col], errors="coerce")
        d["breakout20"] = d.get("breakout20", pd.Series(0.0, index=d.index)).fillna(0.0)
        d["resid_mom20"] = d.get("resid_mom20", pd.Series(0.0, index=d.index)).fillna(0.0)
        d["industry_relative_mom20"] = d["industry_relative_mom20"].fillna(0.0)
        if "industry_relative_mom60" not in d.columns:
            d["industry_relative_mom60"] = d["industry_relative_mom20"]
        d["industry_relative_mom60"] = d["industry_relative_mom60"].fillna(0.0)
        if "benchmark_weight" not in d.columns:
            d["benchmark_weight"] = 0.0
        d["benchmark_weight"] = d["benchmark_weight"].fillna(0.0).clip(lower=0.0)
        d["strong_index_context"] = d["strong_index_context"].fillna(False).astype(bool)

        masks = build_hard_filter_masks(d, params)
        hard_base = masks["hard_base"]
        d["date_vol20_threshold"] = masks["date_vol20_p80"]
        d["mom60_rank_component"] = _rank_component(d, "mom60", hard_base, higher_is_better=True)
        d["mom20_rank_component"] = _rank_component(d, "mom20", hard_base, higher_is_better=True)
        d["residual_rank_component"] = _rank_component(d, "resid_mom20", hard_base, higher_is_better=True)
        d["industry_relative_rank_component"] = _rank_component(
            d, "industry_relative_mom20", hard_base, higher_is_better=True
        )
        d["industry_relative_60_rank_component"] = _rank_component(
            d, "industry_relative_mom60", hard_base, higher_is_better=True
        )
        d["amount_rank_component"] = _rank_component(d, "amount_ratio20", hard_base, higher_is_better=True)
        d["low_vol_rank_component"] = _rank_component(d, "vol20", hard_base, higher_is_better=False)
        d["breakout_rank_component"] = _rank_component(d, "breakout20", hard_base, higher_is_better=True)

        weights_cfg = params.get("factor_weights", {})
        d["score"] = (
            float(weights_cfg.get("benchmark_weight", 0.30)) * _benchmark_weight_component(d, hard_base)
            + float(weights_cfg.get("mom60", 0.22)) * d["mom60_rank_component"]
            + float(weights_cfg.get("mom20", 0.12)) * d["mom20_rank_component"]
            + float(weights_cfg.get("resid_mom20", 0.10)) * d["residual_rank_component"]
            + float(weights_cfg.get("industry_relative_mom20", 0.10)) * d["industry_relative_rank_component"]
            + float(weights_cfg.get("industry_relative_mom60", 0.06)) * d["industry_relative_60_rank_component"]
            + float(weights_cfg.get("amount_ratio20", 0.08)) * d["amount_rank_component"]
            + float(weights_cfg.get("low_vol20", 0.02)) * d["low_vol_rank_component"]
        )
        d["rank_score"] = d["score"].where(hard_base & d["score"].notna(), np.nan)
        d["rank"] = np.nan
        ranked = d[d["rank_score"].notna()].sort_values(["date", "rank_score", "symbol"], ascending=[True, False, True])
        if not ranked.empty:
            d.loc[ranked.index, "rank"] = ranked.groupby("date").cumcount() + 1

        buy_top_n = int(params.get("buy_top_n", 35))
        benchmark_core_min_weight = float(params.get("benchmark_core_min_weight", 0.70))
        target_exposure = float(params.get("target_exposure", 0.70))
        max_symbol_weight = float(params.get("max_symbol_weight", 0.08))
        benchmark_weight_multiplier = float(params.get("benchmark_weight_multiplier", 1.8))
        alpha_satellite_weight = max(0.0, min(1.0, 1.0 - benchmark_core_min_weight))
        max_names_per_industry = LowVolLowTurnoverQualityStrategy._optional_positive_int(
            params.get("max_names_per_industry", 8)
        )

        frames: list[pd.DataFrame] = []
        previous_weights: dict[str, float] = {}
        for _, day in d.groupby("date", sort=True):
            day = day.copy()
            context_is_strong = bool(day["strong_index_context"].any())
            if context_is_strong:
                current_weights = _target_weights_for_day(
                    day,
                    buy_top_n=buy_top_n,
                    target_exposure=target_exposure,
                    benchmark_core_min_weight=benchmark_core_min_weight,
                    alpha_satellite_weight=alpha_satellite_weight,
                    max_symbol_weight=max_symbol_weight,
                    benchmark_weight_multiplier=benchmark_weight_multiplier,
                    max_names_per_industry=max_names_per_industry,
                )
            else:
                current_weights = {}

            day["review_day"] = True
            day["review_reason"] = "strong_context_weight_aware" if context_is_strong else "not_strong_context"
            day["raw_weight"] = day["symbol"].astype(str).map(lambda symbol: 1.0 if symbol in current_weights else 0.0)
            day["weight_unshifted"] = day["symbol"].astype(str).map(lambda symbol: current_weights.get(symbol, 0.0))
            day["selected"] = (day["weight_unshifted"] > 0).astype(float)
            day["held_days"] = day["symbol"].astype(str).map(lambda symbol: 1 if symbol in previous_weights else 0).astype(int)
            frames.append(day)
            previous_weights = current_weights

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
        signal_frame = out[
            [
                col
                for col in [
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
                    "strong_index_context",
                    "strong_index_close",
                    "strong_index_ret20",
                    "strong_index_ret60",
                    "strong_index_ma120",
                    "strong_index_vol20",
                    "strong_index_vol_threshold",
                    "strong_index_drawdown",
                    "date_vol20_threshold",
                    "mom60_rank_component",
                    "mom20_rank_component",
                    "residual_rank_component",
                    "industry_relative_rank_component",
                    "industry_relative_60_rank_component",
                    "amount_rank_component",
                    "low_vol_rank_component",
                    "breakout_rank_component",
                    "industry_relative_mom20",
                    "industry_relative_mom60",
                    "industry",
                    "name",
                ]
                if col in out.columns
            ]
        ].copy()
        return StrategyOutput(returns, exposure, signal_frame, self.build_metadata(params))

    def format_params(self, params: dict[str, Any]) -> str:
        return (
            "strong_market_effective_participation@"
            f"index={params.get('benchmark_symbol', '')},"
            f"target_exposure={params.get('target_exposure', '')},"
            f"core_min={params.get('benchmark_core_min_weight', '')},"
            f"buy_top={params.get('buy_top_n', '')},"
            f"max_w={params.get('max_symbol_weight', '')},"
            f"weight_mult={params.get('benchmark_weight_multiplier', '')},"
            f"max_industry_names={params.get('max_names_per_industry', '')},"
            f"threshold_status={params.get('threshold_status', '')}"
        )


def _strategy_cfg(strategy_cfg: dict[str, Any]) -> dict[str, Any]:
    return strategy_cfg.get("local_factor", {}).get("strong_market_effective_participation", {})


def _fixed_params(cfg: dict[str, Any]) -> dict[str, Any]:
    factor_weights = cfg.get("factor_weights", {})
    return {
        "eligible": True,
        "benchmark_symbol": str(cfg.get("benchmark_symbol", "SH.000300")),
        "threshold_status": str(cfg.get("threshold_status", "pre_registered_i36_first_pass")),
        "trend_window": int(cfg.get("trend_window", 120)),
        "return_short_window": int(cfg.get("return_short_window", 20)),
        "return_long_window": int(cfg.get("return_long_window", 60)),
        "vol_window": int(cfg.get("vol_window", 20)),
        "vol_quantile": float(cfg.get("vol_quantile", 0.70)),
        "vol_threshold_lookback_days": int(cfg.get("vol_threshold_lookback_days", 252)),
        "drawdown_min": float(cfg.get("drawdown_min", -0.12)),
        "buy_top_n": int(cfg.get("top_n", cfg.get("buy_top_n", 35))),
        "target_exposure": float(cfg.get("target_exposure", 0.70)),
        "benchmark_core_min_weight": float(cfg.get("benchmark_core_min_weight", 0.70)),
        "benchmark_weight_multiplier": float(cfg.get("benchmark_weight_multiplier", 1.8)),
        "max_symbol_weight": float(cfg.get("max_symbol_weight", 0.08)),
        "max_names_per_industry": int(cfg.get("max_names_per_industry", 8)),
        "amount_ratio_min": float(cfg.get("amount_ratio_min", 1.0)),
        "amount_ratio_max": float(cfg.get("amount_ratio_max", 4.0)),
        "upper_shadow_max": float(cfg.get("upper_shadow_max", 1.3)),
        "vol_cross_section_quantile": float(cfg.get("vol_cross_section_quantile", 0.95)),
        "factor_weights": {
            "benchmark_weight": float(factor_weights.get("benchmark_weight", 0.30)),
            "mom60": float(factor_weights.get("mom60", 0.22)),
            "mom20": float(factor_weights.get("mom20", 0.12)),
            "resid_mom20": float(factor_weights.get("resid_mom20", 0.10)),
            "industry_relative_mom20": float(factor_weights.get("industry_relative_mom20", 0.10)),
            "industry_relative_mom60": float(factor_weights.get("industry_relative_mom60", 0.06)),
            "amount_ratio20": float(factor_weights.get("amount_ratio20", 0.08)),
            "low_vol20": float(factor_weights.get("low_vol20", 0.02)),
        },
    }


def _benchmark_weight_component(d: pd.DataFrame, eligible: pd.Series) -> pd.Series:
    values = pd.to_numeric(d["benchmark_weight"], errors="coerce").fillna(0.0).where(eligible, 0.0)
    ranked = values.groupby(d["date"]).rank(method="average", pct=True)
    return ranked.fillna(0.0)


def _attach_benchmark_weights(panel: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    if panel.empty or {"date", "symbol"}.difference(panel.columns):
        return panel
    if "benchmark_weight" in panel.columns and pd.to_numeric(panel["benchmark_weight"], errors="coerce").fillna(0.0).gt(0).any():
        return panel
    db_path = local_history_path()
    if not db_path.exists():
        out = panel.copy()
        out["benchmark_weight"] = 0.0
        out["benchmark_weight_date"] = ""
        return out
    dates = pd.to_datetime(panel["date"], errors="coerce").dropna().dt.normalize()
    if dates.empty:
        out = panel.copy()
        out["benchmark_weight"] = 0.0
        out["benchmark_weight_date"] = ""
        return out
    max_lookup_date = dates.max() - pd.Timedelta(days=1)
    try:
        with sqlite3.connect(db_path) as conn:
            has_table = bool(
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
                    ("cn_index_weights_asof",),
                ).fetchone()
            )
            if not has_table:
                weights = pd.DataFrame()
            else:
                weights = pd.read_sql_query(
                    """
                    SELECT trade_date, symbol, weight
                    FROM cn_index_weights_asof
                    WHERE index_code = ?
                      AND trade_date <= ?
                    ORDER BY trade_date, symbol
                    """,
                    conn,
                    params=(str(params.get("benchmark_symbol", "SH.000300")), max_lookup_date.date().isoformat()),
                )
    except sqlite3.Error:
        weights = pd.DataFrame()
    if weights.empty:
        out = panel.copy()
        out["benchmark_weight"] = 0.0
        out["benchmark_weight_date"] = ""
        return out

    weights["benchmark_weight_date"] = pd.to_datetime(weights["trade_date"], errors="coerce").dt.normalize()
    weights = weights.dropna(subset=["benchmark_weight_date"]).copy()
    weights["symbol"] = weights["symbol"].astype(str).str.strip()
    weights["benchmark_weight"] = pd.to_numeric(weights["weight"], errors="coerce").fillna(0.0)
    sums = weights.groupby("benchmark_weight_date")["benchmark_weight"].transform("sum")
    divisor = np.where(sums > 2.0, 100.0, 1.0)
    weights["benchmark_weight"] = weights["benchmark_weight"] / divisor

    unique_dates = pd.DataFrame({"date": pd.to_datetime(sorted(dates.unique())).astype("datetime64[ns]")})
    unique_weight_dates = pd.DataFrame(
        {"benchmark_weight_date": pd.to_datetime(sorted(weights["benchmark_weight_date"].unique())).astype("datetime64[ns]")}
    )
    unique_dates["lookup_date"] = unique_dates["date"] - pd.Timedelta(days=1)
    date_map = pd.merge_asof(
        unique_dates,
        unique_weight_dates,
        left_on="lookup_date",
        right_on="benchmark_weight_date",
        direction="backward",
    )[["date", "benchmark_weight_date"]]

    keyed_weights = weights[["benchmark_weight_date", "symbol", "benchmark_weight"]].copy()
    out = panel.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out["symbol"] = out["symbol"].astype(str).str.strip()
    out = out.merge(date_map, on="date", how="left")
    out = out.merge(keyed_weights, on=["benchmark_weight_date", "symbol"], how="left")
    out["benchmark_weight"] = pd.to_numeric(out["benchmark_weight"], errors="coerce").fillna(0.0)
    out["benchmark_weight_date"] = out["benchmark_weight_date"].dt.strftime("%Y-%m-%d").fillna("")
    return out


def _target_weights_for_day(
    day: pd.DataFrame,
    *,
    buy_top_n: int,
    target_exposure: float,
    benchmark_core_min_weight: float,
    alpha_satellite_weight: float,
    max_symbol_weight: float,
    benchmark_weight_multiplier: float,
    max_names_per_industry: int | None,
) -> dict[str, float]:
    candidates = day[day["rank_score"].notna()].sort_values(["rank_score", "symbol"], ascending=[False, True])
    if candidates.empty:
        return {}

    selected: list[str] = []
    current_weights: dict[str, float] = {}
    benchmark_candidates = candidates[pd.to_numeric(candidates["benchmark_weight"], errors="coerce").fillna(0.0) > 0]
    satellite_candidates = candidates[pd.to_numeric(candidates["benchmark_weight"], errors="coerce").fillna(0.0) <= 0]
    core_budget = max(0.0, min(target_exposure, target_exposure * benchmark_core_min_weight))
    satellite_budget = max(0.0, min(target_exposure - core_budget, target_exposure * alpha_satellite_weight))

    for _, row in benchmark_candidates.iterrows():
        symbol = str(row["symbol"])
        if len(selected) >= buy_top_n:
            break
        if not _industry_slot_available(day, selected, symbol, max_names_per_industry):
            continue
        weight_cap = min(max_symbol_weight, max(0.02, float(row["benchmark_weight"]) * benchmark_weight_multiplier))
        current_weights[symbol] = weight_cap
        selected.append(symbol)
        if sum(current_weights.values()) >= core_budget:
            break

    current_weights = _scale_to_budget(current_weights, core_budget)
    remaining_slots = max(0, buy_top_n - len(current_weights))
    if remaining_slots > 0 and satellite_budget > 0:
        satellite_weights: dict[str, float] = {}
        for _, row in satellite_candidates.iterrows():
            symbol = str(row["symbol"])
            if len(satellite_weights) >= remaining_slots:
                break
            if not _industry_slot_available(day, [*current_weights.keys(), *satellite_weights.keys()], symbol, max_names_per_industry):
                continue
            satellite_weights[symbol] = max_symbol_weight
        current_weights.update(_scale_to_budget(satellite_weights, satellite_budget))

    return {symbol: weight for symbol, weight in current_weights.items() if weight > 1e-12}


def _scale_to_budget(weights: dict[str, float], budget: float) -> dict[str, float]:
    if not weights or budget <= 0:
        return {}
    total = sum(weights.values())
    if total <= 0:
        return {}
    if total <= budget:
        return dict(weights)
    scale = budget / total
    return {symbol: weight * scale for symbol, weight in weights.items()}


def _industry_slot_available(
    day: pd.DataFrame,
    selected_symbols: list[str],
    symbol: str,
    max_names_per_industry: int | None,
) -> bool:
    if max_names_per_industry is None or max_names_per_industry <= 0:
        return True
    indexed = day.set_index(day["symbol"].astype(str))
    if symbol not in indexed.index:
        return False
    industry = str(indexed.loc[symbol].get("industry", "")).strip()
    if not industry:
        return True
    selected_industries = [
        str(indexed.loc[item].get("industry", "")).strip()
        for item in selected_symbols
        if item in indexed.index
    ]
    return selected_industries.count(industry) < int(max_names_per_industry)


def _ineligible_reason(panel: pd.DataFrame) -> str | None:
    required = [
        "date",
        "symbol",
        "close",
        "mom20",
        "mom60",
        "ma60",
        "amount_ratio20",
        "upper_shadow_pct",
        "vol20",
        "ret",
        "industry",
    ]
    missing = [col for col in required if col not in panel.columns]
    if missing:
        return "missing_required_fields:" + ",".join(missing)
    if "industry_relative_mom20" not in panel.columns:
        return "missing_required_industry_relative_mom20"
    if pd.to_numeric(panel["industry_relative_mom20"], errors="coerce").dropna().empty:
        return "empty_required_industry_relative_mom20"
    return None


def _all_cash_output(
    panel: pd.DataFrame,
    params: dict[str, Any],
    strategy: StrongMarketEffectiveParticipationStrategy,
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
