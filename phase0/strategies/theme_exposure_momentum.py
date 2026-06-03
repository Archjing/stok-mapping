from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from phase0.strategies.base import BaseStrategy, StrategyOutput
from phase0.strategies.registry import register


@register
class ThemeExposureMomentumStrategy(BaseStrategy):
    name = "theme_exposure_momentum_v1"
    candidate_name = "theme_exposure_momentum_v1"
    display_name = "Theme Exposure Momentum"
    category = "theme_exposure"

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return bool(strategy_cfg.get("theme_exposure_momentum", {}).get("enabled", False))

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        from phase0.walk_forward import _calc_metrics

        cfg = strategy_cfg.get("theme_exposure_momentum", {})
        best: dict[str, Any] | None = None
        min_trades = int(strategy_cfg.get("train_min_trades", 5))
        target_vol = float(strategy_cfg.get("target_vol", 0.18))
        mom_windows = [int(item) for item in cfg.get("mom_windows", [10, 20])]
        mom_quantiles = [float(item) for item in cfg.get("mom_quantiles", [0.6, 0.7])]
        top_n_values = [int(item) for item in cfg.get("top_n_values", [3, 5])]
        amount_ratio_mins = [float(item) for item in cfg.get("amount_ratio_mins", [1.0, 1.2])]
        breakout_required_values = [bool(item) for item in cfg.get("breakout_required_values", [True])]
        use_xmarket_overlay = bool(cfg.get("use_xmarket_overlay", True))
        xthresholds = [float(item) for item in cfg.get("xmarket_thresholds", [0.0, 0.5])]

        for mom_window in mom_windows:
            mom_col = f"mom{mom_window}"
            if mom_col not in train.columns:
                continue
            scores = train[mom_col].dropna()
            if scores.empty:
                continue
            for mom_q in mom_quantiles:
                mom_threshold = float(scores.quantile(mom_q))
                for trend_window in strategy_cfg.get("trend_windows", [20, 60]):
                    trend_col = f"ma{trend_window}"
                    if trend_col not in train.columns:
                        continue
                    for vol_q in strategy_cfg.get("vol_quantiles", [0.75]):
                        vol_threshold = float(train["vol20"].quantile(float(vol_q)))
                        for amount_ratio_min in amount_ratio_mins:
                            for breakout_required in breakout_required_values:
                                thresholds = xthresholds if use_xmarket_overlay else [0.0]
                                for xthreshold in thresholds:
                                    for top_n in top_n_values:
                                        params = {
                                            "mom_window": mom_window,
                                            "mom_quantile": mom_q,
                                            "mom_threshold": mom_threshold,
                                            "trend_window": int(trend_window),
                                            "vol_quantile": float(vol_q),
                                            "vol_threshold": vol_threshold,
                                            "amount_ratio_min": amount_ratio_min,
                                            "breakout_required": breakout_required,
                                            "xmarket_threshold": xthreshold,
                                            "top_n": top_n,
                                            "target_vol": target_vol,
                                            "use_xmarket_overlay": use_xmarket_overlay,
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
                                        score = metric["sharpe"] + max(metric["max_drawdown"], -1.0) * 0.5
                                        candidate = {
                                            **params,
                                            "train_score": float(score),
                                            "train_sharpe": float(metric["sharpe"]),
                                            "train_trades": int(metric["trades"]),
                                        }
                                        if best is None or candidate["train_score"] > best["train_score"]:
                                            best = candidate

        return best or {
            "mom_window": 10,
            "mom_quantile": 0.6,
            "mom_threshold": float(train.get("mom10", pd.Series(0.0)).quantile(0.6)),
            "trend_window": 20,
            "vol_quantile": 0.75,
            "vol_threshold": float(train["vol20"].quantile(0.75)),
            "amount_ratio_min": 1.0,
            "breakout_required": True,
            "xmarket_threshold": 0.0,
            "top_n": int(top_n_values[0]),
            "target_vol": target_vol,
            "use_xmarket_overlay": use_xmarket_overlay,
            "train_score": 0.0,
            "train_sharpe": 0.0,
            "train_trades": 0,
        }

    def apply(
        self,
        panel: pd.DataFrame,
        params: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> StrategyOutput:
        d = panel.copy()
        mom_col = f"mom{int(params['mom_window'])}"
        trend_col = f"ma{int(params['trend_window'])}"
        if mom_col not in d.columns or trend_col not in d.columns:
            dates = pd.Index(sorted(d["date"].dropna().unique()))
            empty = pd.Series(0.0, index=dates)
            return StrategyOutput(empty, empty, pd.DataFrame(), self.build_metadata(params))

        xscore = d.get("mapped_xmarket_score", pd.Series(0.0, index=d.index))
        eligible = (
            (d[mom_col] > float(params["mom_threshold"]))
            & (d["close"] > d[trend_col])
            & (d["vol20"] <= float(params["vol_threshold"]))
            & (d["amount_ratio20"] >= float(params["amount_ratio_min"]))
            & ((xscore >= float(params["xmarket_threshold"])) if bool(params.get("use_xmarket_overlay", False)) else True)
        )
        if bool(params.get("breakout_required", True)):
            eligible = eligible & (d["breakout20"] > 0)

        d["mom_rank_component"] = d.groupby("date")[mom_col].rank(method="first", pct=True)
        d["xmarket_rank_component"] = d.groupby("date")["mapped_xmarket_score"].rank(method="first", pct=True) if "mapped_xmarket_score" in d.columns else 0.0
        d["rank_score"] = (
            0.75 * d["mom_rank_component"]
            + 0.25 * d["xmarket_rank_component"]
        ).where(eligible, np.nan)
        d["rank"] = d.groupby("date")["rank_score"].rank(method="first", ascending=False)
        d["selected"] = ((d["rank"] <= int(params["top_n"])) & d["rank_score"].notna()).astype(float)
        daily_count = d.groupby("date")["selected"].transform("sum").replace(0, np.nan)
        d["raw_weight"] = (d["selected"] / daily_count).fillna(0.0)
        vol_scale = np.minimum(1.0, float(params["target_vol"]) / d["vol20"].replace(0, np.nan)).fillna(0.0)
        d["weight"] = d["raw_weight"] * vol_scale
        d["weight"] = d.groupby("symbol")["weight"].shift(1).fillna(0.0)
        d["position_ret"] = d["weight"] * d["ret"]

        weights = d.pivot(index="date", columns="symbol", values="weight").fillna(0.0)
        turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
        sells = weights.diff().clip(upper=0).abs().sum(axis=1).fillna(0.0)
        gross = d.groupby("date")["position_ret"].sum()
        costs = turnover * (slippage + commission) + sells * stamp_duty_sell
        returns = gross.sub(costs, fill_value=0.0)
        exposure = weights.sum(axis=1)
        signal_frame = d[[c for c in ["date", "symbol", "rank_score", "selected", "raw_weight", "weight", "ret", "position_ret"] if c in d.columns]].copy().rename(columns={"rank_score": "score"})
        return StrategyOutput(
            returns=returns,
            exposure=exposure,
            signal_frame=signal_frame,
            metadata=self.build_metadata(params),
        )

    def format_params(self, params: dict[str, Any]) -> str:
        return (
            f"theme_mom{params['mom_window']}@q{params['mom_quantile']},"
            f"ma{params['trend_window']},"
            f"vol@q{params['vol_quantile']},"
            f"amt>={params['amount_ratio_min']},"
            f"breakout_required={params['breakout_required']},"
            f"xscore>={params['xmarket_threshold']},"
            f"top_n={params['top_n']},"
            f"target_vol={params['target_vol']}"
        )
