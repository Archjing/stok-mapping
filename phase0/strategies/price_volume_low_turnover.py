from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from phase0.strategies.base import BaseStrategy, StrategyOutput
from phase0.strategies.low_vol_low_turnover_quality import LowVolLowTurnoverQualityStrategy
from phase0.strategies.registry import register


@register
class PriceVolumeLowTurnoverStrategy(BaseStrategy):
    name = "price_volume_low_turnover_v1"
    candidate_name = "price_volume_low_turnover_v1"
    display_name = "Price Volume Low Turnover"
    category = "price_volume_low_turnover"
    supports_brief = False
    supports_paper_trade = False

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        cfg = strategy_cfg.get("local_factor", {}).get("price_volume_low_turnover", {})
        return bool(cfg.get("enabled", False))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        from phase0.walk_forward import _add_local_factor_features

        d = _add_local_factor_features(panel)
        if d.empty or "industry" not in d.columns:
            return d
        d = d.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        industries = d["industry"].fillna("UNKNOWN").astype(str).str.strip().replace("", "UNKNOWN")
        d["_industry_key"] = industries.where(industries.str.lower() != "nan", "UNKNOWN")
        for window in [20, 60]:
            mom_col = f"mom{window}"
            if mom_col not in d.columns:
                continue
            industry_mom_col = f"industry_mom{window}"
            relative_col = f"industry_relative_mom{window}"
            d[industry_mom_col] = d.groupby(["date", "_industry_key"])[mom_col].transform("mean")
            d[relative_col] = d[industry_mom_col] - d.groupby("date")[mom_col].transform("mean")
        return d.drop(columns=["_industry_key"])

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        from phase0.research.metrics import calc_metrics as _calc_metrics

        cfg = strategy_cfg.get("local_factor", {}).get("price_volume_low_turnover", {})
        best: dict[str, Any] | None = None
        min_trades = int(strategy_cfg.get("train_min_trades", 5))
        target_vol = float(strategy_cfg.get("target_vol", 0.18))
        residual_windows = [int(item) for item in cfg.get("residual_windows", [20])]
        residual_quantiles = [float(item) for item in cfg.get("residual_quantiles", [0.6])]
        momentum_windows = [int(item) for item in cfg.get("momentum_windows", [20])]
        momentum_quantiles = [float(item) for item in cfg.get("momentum_quantiles", [0.55])]
        top_n_values = [int(item) for item in cfg.get("top_n_values", [10])]
        hold_rank_multipliers = [float(item) for item in cfg.get("hold_rank_multipliers", [2.0])]
        rebalance_days_values = [int(item) for item in cfg.get("rebalance_days_values", [40])]
        min_hold_days_values = [int(item) for item in cfg.get("min_hold_days_values", [20])]
        amount_ratio_mins = [float(item) for item in cfg.get("amount_ratio_mins", [1.0])]
        amount_ratio_max_values = [float(item) for item in cfg.get("amount_ratio_max_values", [3.0])]
        upper_shadow_max_values = [float(item) for item in cfg.get("upper_shadow_max_values", [1.0])]
        vol_quantiles = [float(item) for item in cfg.get("vol_quantiles", strategy_cfg.get("vol_quantiles", [0.75]))]
        breakout_required_values = [bool(item) for item in cfg.get("breakout_required_values", [False])]
        turnover_penalties = [float(item) for item in cfg.get("turnover_penalties", [0.02])]
        weights = {
            "residual_momentum": float(cfg.get("factor_weights", {}).get("residual_momentum", 0.45)),
            "momentum": float(cfg.get("factor_weights", {}).get("momentum", 0.25)),
            "low_volatility": float(cfg.get("factor_weights", {}).get("low_volatility", 0.20)),
            "amount_confirmation": float(cfg.get("factor_weights", {}).get("amount_confirmation", 0.10)),
            "industry_relative_strength": float(cfg.get("factor_weights", {}).get("industry_relative_strength", 0.0)),
        }
        industry_relative_enabled = bool(
            cfg.get("industry_relative_enabled", False)
            or "industry_relative_quantiles" in cfg
            or weights["industry_relative_strength"] > 0
        )
        industry_relative_window = int(cfg.get("industry_relative_window", 20))
        industry_relative_col = f"industry_relative_mom{industry_relative_window}"
        industry_relative_quantiles = [
            float(item)
            for item in cfg.get("industry_relative_quantiles", [0.0 if industry_relative_enabled else -np.inf])
        ]
        if industry_relative_enabled and industry_relative_col not in train.columns:
            industry_relative_quantiles = [1.0]
        max_names_per_industry = LowVolLowTurnoverQualityStrategy._optional_positive_int(
            strategy_cfg.get("constraints", {}).get("industry", {}).get("max_names_per_industry")
        )

        for residual_window in residual_windows:
            resid_col = f"resid_mom{residual_window}"
            if resid_col not in train.columns:
                continue
            resid_scores = train[resid_col].dropna()
            if resid_scores.empty:
                continue
            for residual_q in residual_quantiles:
                residual_threshold = float(resid_scores.quantile(residual_q))
                for momentum_window in momentum_windows:
                    mom_col = f"mom{momentum_window}"
                    if mom_col not in train.columns:
                        continue
                    mom_scores = train[mom_col].dropna()
                    if mom_scores.empty:
                        continue
                    for momentum_q in momentum_quantiles:
                        momentum_threshold = float(mom_scores.quantile(momentum_q))
                        for trend_window in strategy_cfg.get("trend_windows", [20]):
                            trend_col = f"ma{int(trend_window)}"
                            if trend_col not in train.columns:
                                continue
                            for vol_q in vol_quantiles:
                                vol_threshold = float(train["vol20"].quantile(vol_q))
                                for amount_ratio_min in amount_ratio_mins:
                                    for amount_ratio_max in amount_ratio_max_values:
                                        for upper_shadow_max in upper_shadow_max_values:
                                            for breakout_required in breakout_required_values:
                                                for industry_relative_q in industry_relative_quantiles:
                                                    industry_relative_threshold = self._industry_relative_threshold(
                                                        train,
                                                        industry_relative_col,
                                                        industry_relative_q,
                                                    )
                                                    for top_n in top_n_values:
                                                        for hold_multiplier in hold_rank_multipliers:
                                                            hold_top_n = max(int(top_n), int(round(int(top_n) * hold_multiplier)))
                                                            for rebalance_days in rebalance_days_values:
                                                                for min_hold_days in min_hold_days_values:
                                                                    params = {
                                                                        "eligible": True,
                                                                        "residual_window": residual_window,
                                                                        "residual_quantile": residual_q,
                                                                        "residual_threshold": residual_threshold,
                                                                        "momentum_window": momentum_window,
                                                                        "momentum_quantile": momentum_q,
                                                                        "momentum_threshold": momentum_threshold,
                                                                        "trend_window": int(trend_window),
                                                                        "vol_quantile": vol_q,
                                                                        "vol_threshold": vol_threshold,
                                                                        "amount_ratio_min": amount_ratio_min,
                                                                        "amount_ratio_max": amount_ratio_max,
                                                                        "upper_shadow_max": upper_shadow_max,
                                                                        "breakout_required": breakout_required,
                                                                        "industry_relative_window": industry_relative_window,
                                                                        "industry_relative_enabled": industry_relative_enabled,
                                                                        "industry_relative_quantile": industry_relative_q,
                                                                        "industry_relative_threshold": industry_relative_threshold,
                                                                        "buy_top_n": int(top_n),
                                                                        "hold_top_n": hold_top_n,
                                                                        "rebalance_days": int(rebalance_days),
                                                                        "min_hold_days": int(min_hold_days),
                                                                        "max_symbol_weight": float(cfg.get("max_symbol_weight", 0.10)),
                                                                        "target_vol": target_vol,
                                                                        "max_names_per_industry": max_names_per_industry,
                                                                        "factor_weights": weights,
                                                                    }
                                                                    output = self.apply(
                                                                        train,
                                                                        params,
                                                                        slippage=slippage,
                                                                        commission=commission,
                                                                        stamp_duty_sell=stamp_duty_sell,
                                                                    )
                                                                    metric = _calc_metrics(output.returns, output.exposure)
                                                                    if metric["trades"] < min_trades:
                                                                        continue
                                                                    for turnover_penalty in turnover_penalties:
                                                                        score = (
                                                                            metric["sharpe"]
                                                                            + max(metric["max_drawdown"], -1.0) * 0.5
                                                                            - turnover_penalty * metric["turnover_annual"]
                                                                        )
                                                                        candidate = {
                                                                            **params,
                                                                            "turnover_penalty": turnover_penalty,
                                                                            "train_score": float(score),
                                                                            "train_sharpe": float(metric["sharpe"]),
                                                                            "train_trades": int(metric["trades"]),
                                                                            "train_turnover_annual": float(metric["turnover_annual"]),
                                                                        }
                                                                        if best is None or candidate["train_score"] > best["train_score"]:
                                                                            best = candidate

        return best or self._fallback_params(train, strategy_cfg, cfg, target_vol, weights, max_names_per_industry)

    def apply(
        self,
        panel: pd.DataFrame,
        params: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> StrategyOutput:
        if not bool(params.get("eligible", True)) or panel.empty:
            dates = pd.Index(sorted(panel["date"].dropna().unique())) if "date" in panel.columns else pd.Index([])
            empty = pd.Series(0.0, index=dates)
            return StrategyOutput(empty, empty, pd.DataFrame(), self.build_metadata(params))

        d = panel.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        resid_col = f"resid_mom{int(params['residual_window'])}"
        mom_col = f"mom{int(params['momentum_window'])}"
        trend_col = f"ma{int(params['trend_window'])}"
        required = [resid_col, mom_col, trend_col, "vol20", "amount_ratio20", "upper_shadow_pct", "ret"]
        if any(col not in d.columns for col in required):
            dates = pd.Index(sorted(d["date"].dropna().unique()))
            empty = pd.Series(0.0, index=dates)
            return StrategyOutput(empty, empty, pd.DataFrame(), self.build_metadata(params))

        eligible = (
            (d[resid_col] > float(params["residual_threshold"]))
            & (d[mom_col] > float(params["momentum_threshold"]))
            & (d["close"] > d[trend_col])
            & (d["vol20"] <= float(params["vol_threshold"]))
            & (d["amount_ratio20"] >= float(params["amount_ratio_min"]))
            & (d["amount_ratio20"] <= float(params["amount_ratio_max"]))
            & (d["upper_shadow_pct"] <= float(params["upper_shadow_max"]))
        )
        if bool(params.get("breakout_required", False)):
            eligible = eligible & (d["breakout20"] > 0)
        industry_relative_window = int(params.get("industry_relative_window", params.get("momentum_window", 20)))
        industry_relative_col = f"industry_relative_mom{industry_relative_window}"
        industry_relative_enabled = bool(params.get("industry_relative_enabled", False))
        if industry_relative_enabled and industry_relative_col in d.columns:
            eligible = eligible & (d[industry_relative_col] >= float(params.get("industry_relative_threshold", -np.inf)))
        elif industry_relative_enabled:
            eligible = eligible & False
            d[industry_relative_col] = np.nan
        else:
            d[industry_relative_col] = np.nan

        weights_cfg = params.get("factor_weights", {})
        residual_weight = float(weights_cfg.get("residual_momentum", 0.45))
        momentum_weight = float(weights_cfg.get("momentum", 0.25))
        low_vol_weight = float(weights_cfg.get("low_volatility", 0.20))
        amount_weight = float(weights_cfg.get("amount_confirmation", 0.10))
        industry_relative_weight = float(weights_cfg.get("industry_relative_strength", 0.0))
        total_weight = residual_weight + momentum_weight + low_vol_weight + amount_weight + industry_relative_weight
        if total_weight <= 0:
            residual_weight, momentum_weight, low_vol_weight, amount_weight, industry_relative_weight, total_weight = 0.45, 0.25, 0.20, 0.10, 0.0, 1.0

        d["residual_rank_component"] = d.groupby("date")[resid_col].rank(method="average", pct=True)
        d["momentum_rank_component"] = d.groupby("date")[mom_col].rank(method="average", pct=True)
        d["low_vol_rank_component"] = 1.0 - d.groupby("date")["vol20"].rank(method="average", pct=True)
        d["amount_rank_component"] = d.groupby("date")["amount_ratio20"].rank(method="average", pct=True)
        d["industry_relative_rank_component"] = d.groupby("date")[industry_relative_col].rank(method="average", pct=True)
        d["score"] = (
            residual_weight * d["residual_rank_component"]
            + momentum_weight * d["momentum_rank_component"]
            + low_vol_weight * d["low_vol_rank_component"]
            + amount_weight * d["amount_rank_component"]
            + industry_relative_weight * d["industry_relative_rank_component"].fillna(0.0)
        ) / total_weight
        d["rank_score"] = d["score"].where(eligible & d["score"].notna(), np.nan)
        d["rank"] = d.groupby("date")["rank_score"].rank(method="first", ascending=False)
        d["vol_scale"] = np.minimum(1.0, float(params["target_vol"]) / d["vol20"].replace(0, np.nan)).fillna(0.0)

        buy_top_n = int(params["buy_top_n"])
        hold_top_n = int(params["hold_top_n"])
        rebalance_days = max(1, int(params["rebalance_days"]))
        min_hold_days = max(0, int(params["min_hold_days"]))
        max_symbol_weight = float(params.get("max_symbol_weight", 0.10))
        max_names_per_industry = LowVolLowTurnoverQualityStrategy._optional_positive_int(
            params.get("max_names_per_industry")
        )

        current_weights: dict[str, float] = {}
        held_days: dict[str, int] = {}
        frames: list[pd.DataFrame] = []
        for idx, (_, day) in enumerate(d.groupby("date", sort=True)):
            day = day.copy()
            if idx % rebalance_days == 0:
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

                candidates = day[day["rank_score"].notna()].sort_values(["rank", "symbol"])
                for symbol in candidates["symbol"].astype(str):
                    if len(current_weights) >= buy_top_n:
                        break
                    if not LowVolLowTurnoverQualityStrategy._industry_slot_available(
                        symbol=symbol,
                        day=day,
                        current_weights=current_weights,
                        max_names_per_industry=max_names_per_industry,
                    ):
                        continue
                    if symbol not in current_weights:
                        current_weights[symbol] = 0.0
                        held_days[symbol] = 0

                active = [symbol for symbol in current_weights if symbol in set(day["symbol"].astype(str))]
                if active:
                    indexed = day.set_index(day["symbol"].astype(str))
                    raw_weight = min(max_symbol_weight, 1.0 / len(active))
                    current_weights = {
                        symbol: raw_weight * float(indexed.loc[symbol, "vol_scale"])
                        for symbol in active
                    }
                else:
                    current_weights = {}

            day["raw_weight"] = day["symbol"].astype(str).map(lambda symbol: 1.0 if symbol in current_weights else 0.0)
            day["weight_unshifted"] = day["symbol"].astype(str).map(lambda symbol: current_weights.get(symbol, 0.0))
            day["selected"] = (day["weight_unshifted"] > 0).astype(float)
            day["held_days"] = day["symbol"].astype(str).map(lambda symbol: held_days.get(symbol, 0)).fillna(0).astype(int)
            frames.append(day)
            for symbol in list(current_weights):
                held_days[symbol] = held_days.get(symbol, 0) + 1

        out = pd.concat(frames, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)
        out["weight"] = out.groupby("symbol")["weight_unshifted"].shift(1).fillna(0.0)
        out["position_ret"] = out["weight"] * out["ret"]
        weights = out.pivot(index="date", columns="symbol", values="weight").fillna(0.0)
        turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
        sells = weights.diff().clip(upper=0).abs().sum(axis=1).fillna(0.0)
        gross = out.groupby("date")["position_ret"].sum()
        costs = turnover * (slippage + commission) + sells * stamp_duty_sell
        returns = gross.sub(costs, fill_value=0.0)
        exposure = weights.sum(axis=1)
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
                    "ret",
                    "position_ret",
                    "residual_rank_component",
                    "momentum_rank_component",
                    "low_vol_rank_component",
                    "amount_rank_component",
                    "industry_relative_rank_component",
                    industry_relative_col,
                    "industry",
                    "name",
                ]
                if col in out.columns
            ]
        ].copy()
        return StrategyOutput(returns=returns, exposure=exposure, signal_frame=signal_frame, metadata=self.build_metadata(params))

    def format_params(self, params: dict[str, Any]) -> str:
        return (
            f"price_volume_low_turnover@resid_mom{params.get('residual_window', '')}"
            f"@q{params.get('residual_quantile', '')},"
            f"mom{params.get('momentum_window', '')}@q{params.get('momentum_quantile', '')},"
            f"ma{params.get('trend_window', '')},"
            f"vol@q{params.get('vol_quantile', '')},"
            f"amt={params.get('amount_ratio_min', '')}-{params.get('amount_ratio_max', '')},"
            f"upper_shadow<={params.get('upper_shadow_max', '')},"
            f"breakout_required={params.get('breakout_required', False)},"
            f"industry_rel_mom{params.get('industry_relative_window', '')}"
            f"@q{params.get('industry_relative_quantile', '')},"
            f"buy_top={params.get('buy_top_n', '')},"
            f"hold_top={params.get('hold_top_n', '')},"
            f"rebalance={params.get('rebalance_days', '')}d,"
            f"min_hold={params.get('min_hold_days', '')}d,"
            f"max_w={params.get('max_symbol_weight', '')},"
            f"target_vol={params.get('target_vol', '')},"
            f"turnover_penalty={params.get('turnover_penalty', 0.0)}"
        )

    def _fallback_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        cfg: dict[str, Any],
        target_vol: float,
        weights: dict[str, float],
        max_names_per_industry: int | None,
    ) -> dict[str, Any]:
        residual_window = int(cfg.get("residual_windows", [20])[0])
        momentum_window = int(cfg.get("momentum_windows", [20])[0])
        resid_col = f"resid_mom{residual_window}"
        mom_col = f"mom{momentum_window}"
        return {
            "eligible": False,
            "residual_window": residual_window,
            "residual_quantile": float(cfg.get("residual_quantiles", [0.6])[0]),
            "residual_threshold": float(train.get(resid_col, pd.Series(0.0)).median()),
            "momentum_window": momentum_window,
            "momentum_quantile": float(cfg.get("momentum_quantiles", [0.55])[0]),
            "momentum_threshold": float(train.get(mom_col, pd.Series(0.0)).median()),
            "trend_window": int(strategy_cfg.get("trend_windows", [20])[0]),
            "vol_quantile": float(cfg.get("vol_quantiles", strategy_cfg.get("vol_quantiles", [0.75]))[0]),
            "vol_threshold": float(train.get("vol20", pd.Series(0.0)).quantile(0.75)),
            "amount_ratio_min": float(cfg.get("amount_ratio_mins", [1.0])[0]),
            "amount_ratio_max": float(cfg.get("amount_ratio_max_values", [3.0])[0]),
            "upper_shadow_max": float(cfg.get("upper_shadow_max_values", [1.0])[0]),
            "breakout_required": bool(cfg.get("breakout_required_values", [False])[0]),
            "industry_relative_window": int(cfg.get("industry_relative_window", 20)),
            "industry_relative_enabled": bool(
                cfg.get("industry_relative_enabled", False)
                or "industry_relative_quantiles" in cfg
                or weights.get("industry_relative_strength", 0.0) > 0
            ),
            "industry_relative_quantile": float(cfg.get("industry_relative_quantiles", [-np.inf])[0]),
            "industry_relative_threshold": -np.inf,
            "buy_top_n": int(cfg.get("top_n_values", [10])[0]),
            "hold_top_n": int(cfg.get("top_n_values", [10])[0]) * 2,
            "rebalance_days": int(cfg.get("rebalance_days_values", [40])[0]),
            "min_hold_days": int(cfg.get("min_hold_days_values", [20])[0]),
            "max_symbol_weight": float(cfg.get("max_symbol_weight", 0.10)),
            "target_vol": target_vol,
            "max_names_per_industry": max_names_per_industry,
            "factor_weights": weights,
            "turnover_penalty": float(cfg.get("turnover_penalties", [0.02])[0]),
            "train_score": 0.0,
            "train_sharpe": 0.0,
            "train_trades": 0,
            "train_turnover_annual": 0.0,
        }

    @staticmethod
    def _industry_relative_threshold(train: pd.DataFrame, column: str, quantile: float) -> float:
        if column not in train.columns:
            return -np.inf
        values = pd.to_numeric(train[column], errors="coerce").dropna()
        if values.empty:
            return -np.inf
        return float(values.quantile(float(quantile)))
