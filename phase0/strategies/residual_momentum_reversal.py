from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from phase0.strategies.base import BaseStrategy, StrategyOutput
from phase0.strategies.registry import register


@register
class ResidualMomentumReversalStrategy(BaseStrategy):
    name = "residual_momentum_reversal_v1"
    candidate_name = "residual_momentum_reversal_v1"
    display_name = "Residual Momentum Reversal V1"
    category = "factor"

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return bool(strategy_cfg.get("local_factor", {}).get("enabled", False))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        from phase0.walk_forward import _add_local_factor_features

        return _add_local_factor_features(panel)

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        best: dict[str, Any] | None = None
        min_trades = int(strategy_cfg.get("train_min_trades", 5))
        target_vol = float(strategy_cfg.get("target_vol", 0.18))
        top_n = int(strategy_cfg.get("top_n", 2))
        lcfg = strategy_cfg.get("local_factor", {})
        reversal_window = int(lcfg.get("reversal_window", 3))
        use_xmarket_overlay = bool(lcfg.get("use_xmarket_overlay", True))

        for residual_window in lcfg.get("residual_momentum_windows", [10, 20]):
            resid_col = f"resid_mom{int(residual_window)}"
            if resid_col not in train.columns:
                continue
            for residual_q in lcfg.get("residual_momentum_quantiles", [0.6]):
                residual_threshold = float(train[resid_col].quantile(float(residual_q)))
                reversal_col = f"mom{reversal_window}"
                if reversal_col not in train.columns:
                    continue
                for reversal_q in lcfg.get("reversal_quantiles", [0.7]):
                    reversal_threshold = float(train[reversal_col].quantile(float(reversal_q)))
                    for trend_window in strategy_cfg.get("trend_windows", [20]):
                        trend_col = f"ma{trend_window}"
                        if trend_col not in train.columns:
                            continue
                        for vol_q in strategy_cfg.get("vol_quantiles", [0.75]):
                            vol_threshold = float(train["vol20"].quantile(float(vol_q)))
                            output = self.apply(
                                train,
                                {
                                    "residual_window": int(residual_window),
                                    "residual_quantile": float(residual_q),
                                    "residual_threshold": residual_threshold,
                                    "reversal_window": reversal_window,
                                    "reversal_quantile": float(reversal_q),
                                    "reversal_threshold": reversal_threshold,
                                    "trend_window": int(trend_window),
                                    "vol_quantile": float(vol_q),
                                    "vol_threshold": vol_threshold,
                                    "target_vol": target_vol,
                                    "top_n": top_n,
                                    "use_xmarket_overlay": use_xmarket_overlay,
                                },
                                slippage=slippage,
                                commission=commission,
                                stamp_duty_sell=stamp_duty_sell,
                            )
                            from phase0.walk_forward import _calc_metrics

                            metric = _calc_metrics(output.returns, output.exposure)
                            if metric["trades"] < min_trades:
                                continue
                            score = metric["sharpe"] + max(metric["max_drawdown"], -1.0) * 0.5
                            candidate = {
                                "residual_window": int(residual_window),
                                "residual_quantile": float(residual_q),
                                "residual_threshold": residual_threshold,
                                "reversal_window": reversal_window,
                                "reversal_quantile": float(reversal_q),
                                "reversal_threshold": reversal_threshold,
                                "trend_window": int(trend_window),
                                "vol_quantile": float(vol_q),
                                "vol_threshold": vol_threshold,
                                "target_vol": target_vol,
                                "top_n": top_n,
                                "use_xmarket_overlay": use_xmarket_overlay,
                                "train_score": float(score),
                                "train_sharpe": float(metric["sharpe"]),
                                "train_trades": int(metric["trades"]),
                            }
                            if best is None or candidate["train_score"] > best["train_score"]:
                                best = candidate

        if best is None:
            best = {
                "residual_window": 20,
                "residual_quantile": 0.6,
                "residual_threshold": float(train.get("resid_mom20", pd.Series(0.0)).median()),
                "reversal_window": reversal_window,
                "reversal_quantile": 0.7,
                "reversal_threshold": float(train.get(f"mom{reversal_window}", pd.Series(0.0)).quantile(0.7)),
                "trend_window": 20,
                "vol_quantile": 0.75,
                "vol_threshold": float(train["vol20"].quantile(0.75)),
                "target_vol": target_vol,
                "top_n": top_n,
                "use_xmarket_overlay": use_xmarket_overlay,
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
        resid_col = f"resid_mom{int(params['residual_window'])}"
        reversal_col = f"mom{int(params['reversal_window'])}"
        trend_col = f"ma{int(params['trend_window'])}"
        eligible = (
            (panel[resid_col] > float(params["residual_threshold"]))
            & (panel[reversal_col] <= float(params["reversal_threshold"]))
            & (panel["close"] > panel[trend_col])
            & (panel["vol20"] <= float(params["vol_threshold"]))
        )
        d = panel.copy()
        d["resid_rank_component"] = d.groupby("date")[resid_col].rank(method="first", pct=True)
        d["reversal_rank_component"] = (1.0 - d.groupby("date")[reversal_col].rank(method="first", pct=True)).clip(0.0, 1.0)
        d["rank_score"] = (d["resid_rank_component"] + 0.5 * d["reversal_rank_component"]).where(eligible, np.nan)
        d["rank"] = d.groupby("date")["rank_score"].rank(method="first", ascending=False)
        d["selected"] = ((d["rank"] <= int(params["top_n"])) & d["rank_score"].notna()).astype(float)
        daily_count = d.groupby("date")["selected"].transform("sum").replace(0, np.nan)
        d["raw_weight"] = (d["selected"] / daily_count).fillna(0.0)
        vol_scale = np.minimum(1.0, float(params["target_vol"]) / d["vol20"].replace(0, np.nan)).fillna(0.0)
        risk_scale = d.get("risk_scale", pd.Series(1.0, index=d.index)).clip(0.0, 1.0) if bool(params.get("use_xmarket_overlay", True)) else 1.0
        d["weight"] = d["raw_weight"] * vol_scale * risk_scale
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
            f"resid_mom{params['residual_window']}@q{params['residual_quantile']},"
            f"reversal_mom{params['reversal_window']}<=q{params['reversal_quantile']},"
            f"ma{params['trend_window']},"
            f"vol@q{params['vol_quantile']},"
            f"target_vol={params['target_vol']},"
            f"top_n={params.get('top_n', '')},"
            f"xmarket_overlay={params.get('use_xmarket_overlay', True)}"
        )
