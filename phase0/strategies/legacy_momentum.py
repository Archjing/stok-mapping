from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from phase0.strategies.base import BaseStrategy, StrategyOutput
from phase0.strategies.registry import register


@register
class LegacyMomentumStrategy(BaseStrategy):
    name = "legacy_momentum"
    candidate_name = "legacy_momentum"
    display_name = "Legacy Momentum"
    category = "rule_based"
    panel_scope = "portfolio"

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

        best: dict[str, Any] | None = None
        cfg = strategy_cfg.get("legacy_momentum", {})
        mom_quantiles = cfg.get("mom_quantiles", [0.5])
        top_n_values = cfg.get("top_n_values", [strategy_cfg.get("top_n", 3)])
        target_vol = float(strategy_cfg.get("target_vol", 0.18))
        min_trades = int(strategy_cfg.get("train_min_trades", 5))

        for mom_q in mom_quantiles:
            threshold = float(train["mom5"].quantile(float(mom_q)))
            for top_n in top_n_values:
                params = {
                    "mom_quantile": float(mom_q),
                    "mom_threshold": threshold,
                    "top_n": int(top_n),
                    "target_vol": target_vol,
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

        if best is None:
            best = {
                "mom_quantile": 0.5,
                "mom_threshold": float(train["mom5"].median()),
                "top_n": int(top_n_values[0]) if top_n_values else int(strategy_cfg.get("top_n", 3)),
                "target_vol": target_vol,
                "train_score": 0.0,
                "train_sharpe": 0.0,
                "train_trades": 0,
            }
        return best

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
        d["score"] = d["mom5"]
        d["rank_score"] = d["mom5"].where(d["mom5"] > float(params["mom_threshold"]), np.nan)
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
        signal_frame = d[[c for c in ["date", "symbol", "score", "selected", "raw_weight", "weight", "ret", "position_ret"] if c in d.columns]].copy()
        return StrategyOutput(
            returns=returns,
            exposure=exposure,
            signal_frame=signal_frame,
            metadata=self.build_metadata(params),
        )

    def format_params(self, params: dict[str, Any]) -> str:
        return (
            f"legacy_mom5@q{params.get('mom_quantile', 0.5)},"
            f"top_n={params.get('top_n', '')},"
            f"target_vol={params.get('target_vol', '')}"
        )
