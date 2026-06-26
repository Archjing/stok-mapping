from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from phase0.strategies.base import BaseStrategy, StrategyOutput
from phase0.strategies.registry import register


@register
class ResidualMomentumReversalV2Strategy(BaseStrategy):
    name = "residual_momentum_reversal_v2"
    candidate_name = "residual_momentum_reversal_v2"
    display_name = "Residual Momentum Reversal V2"
    category = "factor"

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        cfg = strategy_cfg.get("local_factor", {}).get("residual_reversal_v2", {})
        return bool(cfg.get("enabled", False))

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
        cfg = strategy_cfg.get("local_factor", {}).get("residual_reversal_v2", {})
        use_xmarket_overlay = bool(cfg.get("use_xmarket_overlay", False))

        residual_windows = cfg.get("residual_windows", [5, 10, 20])
        reversal_windows = cfg.get("reversal_windows", [1, 3])
        residual_quantiles = cfg.get("residual_quantiles", [0.6])
        reversal_quantiles = cfg.get("reversal_quantiles", [0.7])
        amount_ratio_mins = cfg.get("amount_ratio_mins", [1.0, 1.2])
        upper_shadow_max_values = cfg.get("upper_shadow_max_values", [1.0, 1.5])
        gap_ret_max_values = cfg.get("gap_ret_max_values", [0.03, 0.05])

        for residual_window in residual_windows:
            resid_col = f"resid_mom{int(residual_window)}"
            if resid_col not in train.columns:
                continue
            for residual_q in residual_quantiles:
                residual_threshold = float(train[resid_col].quantile(float(residual_q)))
                for reversal_window in reversal_windows:
                    reversal_col = f"mom{int(reversal_window)}"
                    if reversal_col not in train.columns:
                        continue
                    for reversal_q in reversal_quantiles:
                        reversal_threshold = float(train[reversal_col].quantile(float(reversal_q)))
                        for trend_window in strategy_cfg.get("trend_windows", [20]):
                            trend_col = f"ma{int(trend_window)}"
                            if trend_col not in train.columns:
                                continue
                            for vol_q in strategy_cfg.get("vol_quantiles", [0.75]):
                                vol_threshold = float(train["vol20"].quantile(float(vol_q)))
                                for amount_ratio_min in amount_ratio_mins:
                                    for upper_shadow_max in upper_shadow_max_values:
                                        for gap_ret_max in gap_ret_max_values:
                                            params = {
                                                "residual_window": int(residual_window),
                                                "residual_quantile": float(residual_q),
                                                "residual_threshold": residual_threshold,
                                                "reversal_window": int(reversal_window),
                                                "reversal_quantile": float(reversal_q),
                                                "reversal_threshold": reversal_threshold,
                                                "trend_window": int(trend_window),
                                                "vol_quantile": float(vol_q),
                                                "vol_threshold": vol_threshold,
                                                "amount_ratio_min": float(amount_ratio_min),
                                                "upper_shadow_max": float(upper_shadow_max),
                                                "gap_ret_max": float(gap_ret_max),
                                                "target_vol": target_vol,
                                                "top_n": top_n,
                                                "use_xmarket_overlay": use_xmarket_overlay,
                                            }
                                            output = self.apply(
                                                train,
                                                params,
                                                slippage=slippage,
                                                commission=commission,
                                                stamp_duty_sell=stamp_duty_sell,
                                            )
                                            from phase0.research.metrics import calc_metrics as _calc_metrics

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
                "residual_window": 10,
                "residual_quantile": 0.6,
                "residual_threshold": float(train.get("resid_mom10", pd.Series(0.0)).median()),
                "reversal_window": 3,
                "reversal_quantile": 0.7,
                "reversal_threshold": float(train.get("mom3", pd.Series(0.0)).quantile(0.7)),
                "trend_window": 20,
                "vol_quantile": 0.75,
                "vol_threshold": float(train["vol20"].quantile(0.75)),
                "amount_ratio_min": 1.0,
                "upper_shadow_max": 1.0,
                "gap_ret_max": 0.03,
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
            & (panel["amount_ratio20"] >= float(params["amount_ratio_min"]))
            & (panel["upper_shadow_pct"] <= float(params["upper_shadow_max"]))
            & (panel["gap_ret"] <= float(params["gap_ret_max"]))
        )
        d = panel.copy()
        d["resid_rank_component"] = d.groupby("date")[resid_col].rank(method="first", pct=True)
        d["reversal_rank_component"] = (1.0 - d.groupby("date")[reversal_col].rank(method="first", pct=True)).clip(0.0, 1.0)
        d["rank_score"] = (0.75 * d["resid_rank_component"] + 0.25 * d["reversal_rank_component"]).where(eligible, np.nan)
        d["rank"] = d.groupby("date")["rank_score"].rank(method="first", ascending=False)
        d["selected"] = ((d["rank"] <= int(params["top_n"])) & d["rank_score"].notna()).astype(float)
        daily_count = d.groupby("date")["selected"].transform("sum").replace(0, np.nan)
        d["raw_weight"] = (d["selected"] / daily_count).fillna(0.0)
        vol_scale = np.minimum(1.0, float(params["target_vol"]) / d["vol20"].replace(0, np.nan)).fillna(0.0)
        risk_scale = d.get("risk_scale", pd.Series(1.0, index=d.index)).clip(0.0, 1.0) if bool(params.get("use_xmarket_overlay", False)) else 1.0
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
            f"amt>={params['amount_ratio_min']},"
            f"upper_shadow<={params['upper_shadow_max']},"
            f"gap<={params['gap_ret_max']},"
            f"target_vol={params['target_vol']},"
            f"top_n={params.get('top_n', '')},"
            f"xmarket_overlay={params.get('use_xmarket_overlay', False)}"
        )
