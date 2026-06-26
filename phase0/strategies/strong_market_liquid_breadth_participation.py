from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from phase0.strategies.base import BaseStrategy, StrategyOutput
from phase0.strategies.low_vol_low_turnover_quality import LowVolLowTurnoverQualityStrategy
from phase0.strategies.registry import register
from phase0.strategies.strong_index_participation import (
    _add_index_context_features,
    _rank_component,
    build_hard_filter_masks,
)


@register
class StrongMarketLiquidBreadthParticipationStrategy(BaseStrategy):
    name = "strong_market_liquid_breadth_participation_v1"
    candidate_name = "strong_market_liquid_breadth_participation_v1"
    display_name = "Strong Market Liquid Breadth Participation"
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

        return _add_index_context_features(d, _strategy_cfg(strategy_cfg))

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
        d["strong_index_context"] = d["strong_index_context"].fillna(False).astype(bool)

        masks = build_hard_filter_masks(d, params)
        d["date_vol20_threshold"] = masks["date_vol20_p80"]
        hard_base = masks["hard_base"]

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
            float(weights_cfg.get("mom60", 0.28)) * d["mom60_rank_component"]
            + float(weights_cfg.get("mom20", 0.18)) * d["mom20_rank_component"]
            + float(weights_cfg.get("resid_mom20", 0.12)) * d["residual_rank_component"]
            + float(weights_cfg.get("industry_relative_mom20", 0.14)) * d["industry_relative_rank_component"]
            + float(weights_cfg.get("industry_relative_mom60", 0.08)) * d["industry_relative_60_rank_component"]
            + float(weights_cfg.get("amount_ratio20", 0.15)) * d["amount_rank_component"]
            + float(weights_cfg.get("low_vol20", 0.03)) * d["low_vol_rank_component"]
            + float(weights_cfg.get("breakout20", 0.02)) * d["breakout_rank_component"]
        )
        d["rank_score"] = d["score"].where(hard_base & d["score"].notna(), np.nan)
        d["rank"] = np.nan
        ranked = d[d["rank_score"].notna()].sort_values(["date", "rank_score", "symbol"], ascending=[True, False, True])
        if not ranked.empty:
            d.loc[ranked.index, "rank"] = ranked.groupby("date").cumcount() + 1

        buy_top_n = int(params.get("buy_top_n", 25))
        hold_top_n = int(params.get("hold_top_n", 50))
        rebalance_days = max(1, int(params.get("rebalance_days", 20)))
        min_hold_days = max(0, int(params.get("min_hold_days", 20)))
        max_symbol_weight = float(params.get("max_symbol_weight", 0.04))
        max_names_per_industry = LowVolLowTurnoverQualityStrategy._optional_positive_int(
            params.get("max_names_per_industry", 6)
        )

        current_weights: dict[str, float] = {}
        held_days: dict[str, int] = {}
        frames: list[pd.DataFrame] = []
        for idx, (_, day) in enumerate(d.groupby("date", sort=True)):
            day = day.copy()
            context_is_strong = bool(day["strong_index_context"].any())
            review_day = idx % rebalance_days == 0
            if review_day:
                indexed = day.set_index(day["symbol"].astype(str))
                for symbol in list(current_weights):
                    if symbol not in indexed.index:
                        rank = np.nan
                        score = np.nan
                    else:
                        row = indexed.loc[symbol]
                        rank = row["rank"]
                        score = row["rank_score"]
                    old_enough = held_days.get(symbol, 0) >= min_hold_days
                    outside_hold_band = pd.isna(rank) or float(rank) > hold_top_n or pd.isna(score)
                    if old_enough and outside_hold_band:
                        current_weights.pop(symbol, None)
                        held_days.pop(symbol, None)

                if context_is_strong:
                    candidates = day[day["rank_score"].notna()].sort_values(
                        ["rank_score", "symbol"], ascending=[False, True]
                    )
                    for symbol in candidates["symbol"].astype(str):
                        if len(current_weights) >= buy_top_n:
                            break
                        if symbol in current_weights:
                            continue
                        if not LowVolLowTurnoverQualityStrategy._industry_slot_available(
                            symbol=symbol,
                            day=day,
                            current_weights=current_weights,
                            max_names_per_industry=max_names_per_industry,
                        ):
                            continue
                        current_weights[symbol] = 0.0
                        held_days[symbol] = 0

                active = [symbol for symbol in current_weights if symbol in set(day["symbol"].astype(str))]
                if active:
                    raw_weight = min(max_symbol_weight, 1.0 / len(active))
                    current_weights = {symbol: raw_weight for symbol in active}
                else:
                    current_weights = {}

            day["review_day"] = review_day
            day["review_reason"] = "fixed_rebalance" if review_day else ""
            day["raw_weight"] = day["symbol"].astype(str).map(lambda symbol: 1.0 if symbol in current_weights else 0.0)
            day["weight_unshifted"] = day["symbol"].astype(str).map(lambda symbol: current_weights.get(symbol, 0.0))
            day["selected"] = (day["weight_unshifted"] > 0).astype(float)
            day["held_days"] = day["symbol"].astype(str).map(lambda symbol: held_days.get(symbol, 0)).fillna(0).astype(int)
            frames.append(day)
            for symbol in list(current_weights):
                held_days[symbol] = held_days.get(symbol, 0) + 1

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
            "strong_market_liquid_breadth_participation@"
            f"index={params.get('benchmark_symbol', '')},"
            f"trend={params.get('trend_window', '')}d,"
            f"ret={params.get('return_short_window', '')}/{params.get('return_long_window', '')}d,"
            f"vol={params.get('vol_window', '')}d@q{params.get('vol_quantile', '')},"
            f"drawdown>={params.get('drawdown_min', '')},"
            f"buy_top={params.get('buy_top_n', '')},"
            f"hold_top={params.get('hold_top_n', '')},"
            f"rebalance={params.get('rebalance_days', '')}d,"
            f"min_hold={params.get('min_hold_days', '')}d,"
            f"max_w={params.get('max_symbol_weight', '')},"
            f"max_industry_names={params.get('max_names_per_industry', '')},"
            f"threshold_status={params.get('threshold_status', '')}"
        )


def _strategy_cfg(strategy_cfg: dict[str, Any]) -> dict[str, Any]:
    return strategy_cfg.get("local_factor", {}).get("strong_market_liquid_breadth_participation", {})


def _fixed_params(cfg: dict[str, Any]) -> dict[str, Any]:
    factor_weights = cfg.get("factor_weights", {})
    return {
        "eligible": True,
        "benchmark_symbol": str(cfg.get("benchmark_symbol", "SH.000300")),
        "threshold_status": str(cfg.get("threshold_status", "pre_registered_i20_first_pass")),
        "trend_window": int(cfg.get("trend_window", 120)),
        "return_short_window": int(cfg.get("return_short_window", 20)),
        "return_long_window": int(cfg.get("return_long_window", 60)),
        "vol_window": int(cfg.get("vol_window", 20)),
        "vol_quantile": float(cfg.get("vol_quantile", 0.70)),
        "vol_threshold_lookback_days": int(cfg.get("vol_threshold_lookback_days", 252)),
        "drawdown_min": float(cfg.get("drawdown_min", -0.12)),
        "buy_top_n": int(cfg.get("top_n", cfg.get("buy_top_n", 25))),
        "hold_top_n": int(cfg.get("hold_top_n", 50)),
        "rebalance_days": int(cfg.get("rebalance_days", 20)),
        "min_hold_days": int(cfg.get("min_hold_days", 20)),
        "max_symbol_weight": float(cfg.get("max_symbol_weight", 0.04)),
        "max_names_per_industry": int(cfg.get("max_names_per_industry", 6)),
        "amount_ratio_min": float(cfg.get("amount_ratio_min", 1.0)),
        "amount_ratio_max": float(cfg.get("amount_ratio_max", 3.5)),
        "upper_shadow_max": float(cfg.get("upper_shadow_max", 1.2)),
        "vol_cross_section_quantile": float(cfg.get("vol_cross_section_quantile", 0.90)),
        "factor_weights": {
            "mom60": float(factor_weights.get("mom60", 0.28)),
            "mom20": float(factor_weights.get("mom20", 0.18)),
            "resid_mom20": float(factor_weights.get("resid_mom20", 0.12)),
            "industry_relative_mom20": float(factor_weights.get("industry_relative_mom20", 0.14)),
            "industry_relative_mom60": float(factor_weights.get("industry_relative_mom60", 0.08)),
            "amount_ratio20": float(factor_weights.get("amount_ratio20", 0.15)),
            "low_vol20": float(factor_weights.get("low_vol20", 0.03)),
            "breakout20": float(factor_weights.get("breakout20", 0.02)),
        },
    }


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
    strategy: StrongMarketLiquidBreadthParticipationStrategy,
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
