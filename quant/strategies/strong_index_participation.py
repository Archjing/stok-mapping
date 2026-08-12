from __future__ import annotations

from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd

from quant.data_access.local_history import load_index_daily_from_local_history
from quant.strategies.base import BaseStrategy, StrategyOutput
from quant.strategies.low_vol_low_turnover_quality import LowVolLowTurnoverQualityStrategy
from quant.strategies.registry import register


@register
class StrongIndexParticipationStrategy(BaseStrategy):
    name = "strong_index_participation_v1"
    candidate_name = "strong_index_participation_v1"
    display_name = "Strong Index Participation"
    category = "strong_index_participation"
    panel_scope = "portfolio"
    supports_brief = False
    supports_paper_trade = False
    dynamic_strong_context_trigger = False

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        cfg = _strategy_cfg(strategy_cfg)
        return bool(cfg.get("enabled", False))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        from quant.walk_forward import _add_local_factor_features

        d = _add_local_factor_features(panel)
        if d.empty:
            return d
        d = d.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        d["date"] = pd.to_datetime(d["date"], errors="coerce").dt.normalize().astype("datetime64[ns]")

        if {"date", "industry", "mom20"}.issubset(d.columns):
            industries = d["industry"].astype("string").str.strip()
            valid_industry = industries.notna() & (industries != "") & (industries.str.lower() != "nan")
            d["_industry_key"] = industries.where(valid_industry, pd.NA)
            d["industry_mom20"] = d.groupby(["date", "_industry_key"], dropna=True)["mom20"].transform("mean")
            d["industry_relative_mom20"] = d["industry_mom20"] - d.groupby("date")["mom20"].transform("mean")
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
        params["dynamic_strong_context_trigger"] = bool(self.dynamic_strong_context_trigger)
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
        params = dict(params)
        params["dynamic_strong_context_trigger"] = bool(
            params.get("dynamic_strong_context_trigger", False) or self.dynamic_strong_context_trigger
        )
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
            "breakout20",
        ]
        for col in numeric_cols:
            if col in d.columns:
                d[col] = pd.to_numeric(d[col], errors="coerce")
        d["breakout20"] = d.get("breakout20", pd.Series(0.0, index=d.index)).fillna(0.0)
        d["resid_mom20"] = d.get("resid_mom20", pd.Series(0.0, index=d.index)).fillna(0.0)
        d["industry_relative_mom20"] = d["industry_relative_mom20"].fillna(0.0)
        d["strong_index_context"] = d["strong_index_context"].fillna(False).astype(bool)

        masks = build_hard_filter_masks(d, params)
        d["date_vol20_p80"] = masks["date_vol20_p80"]
        hard_base = masks["hard_base"]

        d["momentum_rank_component"] = _rank_component(d, "mom60", hard_base, higher_is_better=True)
        d["residual_rank_component"] = _rank_component(d, "resid_mom20", hard_base, higher_is_better=True)
        d["industry_relative_rank_component"] = _rank_component(
            d, "industry_relative_mom20", hard_base, higher_is_better=True
        )
        d["amount_rank_component"] = _rank_component(d, "amount_ratio20", hard_base, higher_is_better=True)
        d["breakout_rank_component"] = _rank_component(d, "breakout20", hard_base, higher_is_better=True)
        d["low_vol_rank_component"] = _rank_component(d, "vol20", hard_base, higher_is_better=False)

        weights_cfg = params.get("factor_weights", {})
        d["score"] = (
            float(weights_cfg.get("mom60", 0.35)) * d["momentum_rank_component"]
            + float(weights_cfg.get("resid_mom20", 0.25)) * d["residual_rank_component"]
            + float(weights_cfg.get("industry_relative_mom20", 0.20)) * d["industry_relative_rank_component"]
            + float(weights_cfg.get("amount_ratio20", 0.10)) * d["amount_rank_component"]
            + float(weights_cfg.get("breakout20", 0.05)) * d["breakout_rank_component"]
            + float(weights_cfg.get("low_vol20", 0.05)) * d["low_vol_rank_component"]
        )
        d["rank_score"] = d["score"].where(hard_base & d["score"].notna(), np.nan)
        d["rank"] = np.nan
        ranked = d[d["rank_score"].notna()].sort_values(["date", "rank_score", "symbol"], ascending=[True, False, True])
        if not ranked.empty:
            d.loc[ranked.index, "rank"] = ranked.groupby("date").cumcount() + 1

        buy_top_n = int(params.get("buy_top_n", 20))
        hold_top_n = int(params.get("hold_top_n", 40))
        rebalance_days = max(1, int(params.get("rebalance_days", 20)))
        min_hold_days = max(0, int(params.get("min_hold_days", 10)))
        max_symbol_weight = float(params.get("max_symbol_weight", 0.05))
        max_names_per_industry = LowVolLowTurnoverQualityStrategy._optional_positive_int(
            params.get("max_names_per_industry", 4)
        )

        current_weights: dict[str, float] = {}
        held_days: dict[str, int] = {}
        frames: list[pd.DataFrame] = []
        previous_context_is_strong = False
        for idx, (_, day) in enumerate(d.groupby("date", sort=True)):
            day = day.copy()
            context_is_strong = bool(day["strong_index_context"].any())
            review_reason = _review_reason(
                idx=idx,
                rebalance_days=rebalance_days,
                context_is_strong=context_is_strong,
                previous_context_is_strong=previous_context_is_strong,
                dynamic_strong_context_trigger=bool(params.get("dynamic_strong_context_trigger", False)),
            )
            if review_reason:
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
                current_weights = {symbol: max_symbol_weight for symbol in active}

            day["review_day"] = bool(review_reason)
            day["review_reason"] = review_reason
            day["dynamic_review_trigger"] = review_reason == "dynamic_strong_context_on"
            day["raw_weight"] = day["symbol"].astype(str).map(lambda symbol: 1.0 if symbol in current_weights else 0.0)
            day["weight_unshifted"] = day["symbol"].astype(str).map(lambda symbol: current_weights.get(symbol, 0.0))
            day["selected"] = (day["weight_unshifted"] > 0).astype(float)
            day["held_days"] = day["symbol"].astype(str).map(lambda symbol: held_days.get(symbol, 0)).fillna(0).astype(int)
            frames.append(day)
            for symbol in list(current_weights):
                held_days[symbol] = held_days.get(symbol, 0) + 1
            previous_context_is_strong = context_is_strong

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
                    "dynamic_review_trigger",
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
                    "date_vol20_p80",
                    "momentum_rank_component",
                    "residual_rank_component",
                    "industry_relative_rank_component",
                    "amount_rank_component",
                    "breakout_rank_component",
                    "low_vol_rank_component",
                    "industry_relative_mom20",
                    "industry",
                    "name",
                ]
                if col in out.columns
            ]
        ].copy()
        return StrategyOutput(returns, exposure, signal_frame, self.build_metadata(params))

    def format_params(self, params: dict[str, Any]) -> str:
        return (
            "strong_index_participation@"
            f"index={params.get('benchmark_symbol', '')},"
            f"trend={params.get('trend_window', '')}d,"
            f"ret={params.get('return_short_window', '')}/{params.get('return_long_window', '')}d,"
            f"vol={params.get('vol_window', '')}d@q{params.get('vol_quantile', '')},"
            f"drawdown>={params.get('drawdown_min', '')},"
            f"buy_top={params.get('buy_top_n', '')},"
            f"hold_top={params.get('hold_top_n', '')},"
            f"rebalance={params.get('rebalance_days', '')}d,"
            f"dynamic_trigger={params.get('dynamic_strong_context_trigger', False)},"
            f"min_hold={params.get('min_hold_days', '')}d,"
            f"max_w={params.get('max_symbol_weight', '')},"
            f"max_industry_names={params.get('max_names_per_industry', '')},"
            f"threshold_status={params.get('threshold_status', '')}"
        )


@register
class StrongIndexParticipationDynamicTriggerStrategy(StrongIndexParticipationStrategy):
    name = "strong_index_participation_dynamic_trigger_v1"
    candidate_name = "strong_index_participation_dynamic_trigger_v1"
    display_name = "Strong Index Participation Dynamic Trigger"
    dynamic_strong_context_trigger = True


def _strategy_cfg(strategy_cfg: dict[str, Any]) -> dict[str, Any]:
    return strategy_cfg.get("local_factor", {}).get("strong_index_participation", {})


def _fixed_params(cfg: dict[str, Any]) -> dict[str, Any]:
    factor_weights = cfg.get("factor_weights", {})
    return {
        "eligible": True,
        "dynamic_strong_context_trigger": False,
        "benchmark_symbol": str(cfg.get("benchmark_symbol", "SH.000300")),
        "threshold_status": str(cfg.get("threshold_status", "pre_registered_unvalidated_first_pass")),
        "trend_window": int(cfg.get("trend_window", 120)),
        "return_short_window": int(cfg.get("return_short_window", 20)),
        "return_long_window": int(cfg.get("return_long_window", 60)),
        "vol_window": int(cfg.get("vol_window", 20)),
        "vol_quantile": float(cfg.get("vol_quantile", 0.70)),
        "vol_threshold_lookback_days": int(cfg.get("vol_threshold_lookback_days", 252)),
        "drawdown_min": float(cfg.get("drawdown_min", -0.12)),
        "buy_top_n": int(cfg.get("top_n", cfg.get("buy_top_n", 20))),
        "hold_top_n": int(cfg.get("hold_top_n", 40)),
        "rebalance_days": int(cfg.get("rebalance_days", 20)),
        "min_hold_days": int(cfg.get("min_hold_days", 10)),
        "max_symbol_weight": float(cfg.get("max_symbol_weight", 0.05)),
        "max_names_per_industry": int(cfg.get("max_names_per_industry", 4)),
        "amount_ratio_min": float(cfg.get("amount_ratio_min", 1.0)),
        "amount_ratio_max": float(cfg.get("amount_ratio_max", 3.0)),
        "upper_shadow_max": float(cfg.get("upper_shadow_max", 1.0)),
        "vol_cross_section_quantile": float(cfg.get("vol_cross_section_quantile", 0.80)),
        "factor_weights": {
            "mom60": float(factor_weights.get("mom60", 0.35)),
            "resid_mom20": float(factor_weights.get("resid_mom20", 0.25)),
            "industry_relative_mom20": float(factor_weights.get("industry_relative_mom20", 0.20)),
            "amount_ratio20": float(factor_weights.get("amount_ratio20", 0.10)),
            "breakout20": float(factor_weights.get("breakout20", 0.05)),
            "low_vol20": float(factor_weights.get("low_vol20", 0.05)),
        },
    }


def _review_reason(
    *,
    idx: int,
    rebalance_days: int,
    context_is_strong: bool,
    previous_context_is_strong: bool,
    dynamic_strong_context_trigger: bool,
) -> str:
    if idx % rebalance_days == 0:
        return "fixed_rebalance"
    if dynamic_strong_context_trigger and context_is_strong and not previous_context_is_strong:
        return "dynamic_strong_context_on"
    return ""


def _add_index_context_features(panel: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    d = panel.copy()
    stale_context_cols = [
        col
        for col in [
            "strong_index_context",
            "strong_index_close",
            "strong_index_ret20",
            "strong_index_ret60",
            "strong_index_ma120",
            "strong_index_vol20",
            "strong_index_vol_threshold",
            "strong_index_drawdown",
        ]
        if col in d.columns
    ]
    if stale_context_cols:
        d = d.drop(columns=stale_context_cols)
    dates = pd.to_datetime(d["date"], errors="coerce").dt.normalize()
    if dates.dropna().empty:
        return _with_empty_context(d)

    params = _fixed_params(cfg)
    lookback_days = max(
        400,
        int(params["trend_window"]) * 4,
        int(params["return_long_window"]) * 5,
        int(params["vol_threshold_lookback_days"]) + int(params["vol_window"]) + 30,
    )
    start = dates.min().date() - timedelta(days=lookback_days)
    end = dates.max().date()
    index_df = load_index_daily_from_local_history(str(params["benchmark_symbol"]), start, end)
    if index_df.empty:
        return _with_empty_context(d)

    features = _build_shifted_index_context(index_df, params)
    d = d.sort_values("date")
    merged = pd.merge_asof(
        d,
        features.sort_values("date"),
        on="date",
        direction="backward",
    )
    merged["strong_index_context"] = merged["strong_index_context"].fillna(False).astype(bool)
    return merged.sort_values(["date", "symbol"]).reset_index(drop=True)


def _build_shifted_index_context(index_df: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    features = index_df[["date", "close"]].copy().sort_values("date").reset_index(drop=True)
    features["date"] = pd.to_datetime(features["date"], errors="coerce").dt.normalize().astype("datetime64[ns]")
    close = pd.to_numeric(features["close"], errors="coerce")
    trend_window = int(params["trend_window"])
    short_window = int(params["return_short_window"])
    long_window = int(params["return_long_window"])
    vol_window = int(params["vol_window"])
    vol_lookback = int(params["vol_threshold_lookback_days"])
    vol_quantile = float(params["vol_quantile"])
    min_vol_periods = min(max(20, vol_lookback // 4), vol_lookback)

    features["strong_index_close"] = close
    features["strong_index_ret20"] = close / close.shift(short_window) - 1.0
    features["strong_index_ret60"] = close / close.shift(long_window) - 1.0
    features["strong_index_ma120"] = close.rolling(trend_window, min_periods=trend_window).mean()
    daily_ret = close.pct_change()
    features["strong_index_vol20"] = daily_ret.rolling(vol_window, min_periods=vol_window).std() * np.sqrt(252)
    features["strong_index_vol_threshold"] = features["strong_index_vol20"].rolling(
        vol_lookback, min_periods=min_vol_periods
    ).quantile(vol_quantile)
    trailing_high = close.cummax()
    features["strong_index_drawdown"] = close / trailing_high - 1.0
    raw_context = (
        close.gt(features["strong_index_ma120"])
        & features["strong_index_ret20"].gt(0)
        & features["strong_index_ret60"].gt(0)
        & features["strong_index_vol20"].le(features["strong_index_vol_threshold"])
        & features["strong_index_drawdown"].ge(float(params["drawdown_min"]))
    )
    features["strong_index_context"] = raw_context.fillna(False)

    shifted_cols = [
        "strong_index_close",
        "strong_index_ret20",
        "strong_index_ret60",
        "strong_index_ma120",
        "strong_index_vol20",
        "strong_index_vol_threshold",
        "strong_index_drawdown",
        "strong_index_context",
    ]
    features[shifted_cols] = features[shifted_cols].shift(1)
    features["strong_index_context"] = features["strong_index_context"].fillna(False).astype(bool)
    return features[["date", *shifted_cols]]


def _with_empty_context(panel: pd.DataFrame) -> pd.DataFrame:
    d = panel.copy()
    d["strong_index_context"] = False
    for col in [
        "strong_index_close",
        "strong_index_ret20",
        "strong_index_ret60",
        "strong_index_ma120",
        "strong_index_vol20",
        "strong_index_vol_threshold",
        "strong_index_drawdown",
    ]:
        d[col] = np.nan
    return d


def _rank_component(
    d: pd.DataFrame,
    column: str,
    eligible: pd.Series,
    *,
    higher_is_better: bool,
) -> pd.Series:
    if column not in d.columns:
        return pd.Series(0.0, index=d.index)
    values = pd.to_numeric(d[column], errors="coerce").where(eligible)
    ranked = values.groupby(d["date"]).rank(method="average", pct=True)
    if not higher_is_better:
        ranked = 1.0 - ranked
    return ranked.fillna(0.0)


def build_hard_filter_masks(d: pd.DataFrame, params: dict[str, Any]) -> dict[str, pd.Series]:
    vol_quantile = float(params.get("vol_cross_section_quantile", 0.80))
    date_vol20_p80 = d.groupby("date")["vol20"].transform(lambda s: pd.to_numeric(s, errors="coerce").dropna().quantile(vol_quantile))
    industries = d["industry"].astype("string").str.strip()
    valid_industry = industries.notna() & (industries != "") & (industries.str.lower() != "nan")
    row_required = [
        "close",
        "mom20",
        "mom60",
        "ma60",
        "amount_ratio20",
        "upper_shadow_pct",
        "vol20",
        "ret",
    ]
    complete_required = d[row_required].notna().all(axis=1)
    masks: dict[str, pd.Series] = {
        "complete_required": complete_required,
        "mom20_positive": pd.to_numeric(d["mom20"], errors="coerce").gt(0),
        "mom60_positive": pd.to_numeric(d["mom60"], errors="coerce").gt(0),
        "close_above_ma60": pd.to_numeric(d["close"], errors="coerce").gt(pd.to_numeric(d["ma60"], errors="coerce")),
        "amount_ratio_min": pd.to_numeric(d["amount_ratio20"], errors="coerce").ge(float(params.get("amount_ratio_min", 1.0))),
        "amount_ratio_max": pd.to_numeric(d["amount_ratio20"], errors="coerce").le(float(params.get("amount_ratio_max", 3.0))),
        "upper_shadow": pd.to_numeric(d["upper_shadow_pct"], errors="coerce").le(float(params.get("upper_shadow_max", 1.0))),
        "vol20_p80": pd.to_numeric(d["vol20"], errors="coerce").le(date_vol20_p80),
        "valid_industry": valid_industry.fillna(False),
        "date_vol20_p80": date_vol20_p80,
    }
    masks["hard_base"] = (
        masks["complete_required"]
        & masks["mom20_positive"]
        & masks["mom60_positive"]
        & masks["close_above_ma60"]
        & masks["amount_ratio_min"]
        & masks["amount_ratio_max"]
        & masks["upper_shadow"]
        & masks["vol20_p80"]
        & masks["valid_industry"]
    )
    return masks


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
    strategy: StrongIndexParticipationStrategy,
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
