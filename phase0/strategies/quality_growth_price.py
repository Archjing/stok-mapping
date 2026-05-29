from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from phase0.strategies.base import BaseStrategy, StrategyOutput
from phase0.strategies.registry import register


@register
class QualityGrowthPriceStrategy(BaseStrategy):
    name = "quality_growth_price_v1"
    candidate_name = "quality_growth_price_v1"
    display_name = "Quality Growth Price"
    category = "factor"

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return bool(strategy_cfg.get("local_factor", {}).get("quality_growth", {}).get("enabled", False))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        from phase0.walk_forward import _add_quality_growth_features

        return _add_quality_growth_features(panel, strategy_cfg)

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
        min_trades = int(strategy_cfg.get("train_min_trades", 5))
        target_vol = float(strategy_cfg.get("target_vol", 0.18))
        lcfg = strategy_cfg.get("local_factor", {})
        qcfg = lcfg.get("quality_growth", {})
        top_n_values = qcfg.get("top_n_values", [strategy_cfg.get("top_n", 3)])
        use_xmarket_overlay = bool(qcfg.get("use_xmarket_overlay", True))
        scores = train.get("quality_growth_score", pd.Series(dtype=float)).dropna()

        if scores.empty:
            return {
                "eligible": False,
                "quality_quantile": 1.0,
                "quality_threshold": 1.1,
                "trend_window": 20,
                "vol_quantile": 0.75,
                "vol_threshold": float(train["vol20"].quantile(0.75)),
                "target_vol": target_vol,
                "top_n": int(top_n_values[0]) if top_n_values else int(strategy_cfg.get("top_n", 3)),
                "use_xmarket_overlay": use_xmarket_overlay,
                "train_score": 0.0,
                "train_sharpe": 0.0,
                "train_trades": 0,
            }

        for quality_q in qcfg.get("quality_quantiles", [0.7]):
            quality_threshold = float(scores.quantile(float(quality_q)))
            for trend_window in strategy_cfg.get("trend_windows", [20]):
                trend_col = f"ma{trend_window}"
                if trend_col not in train.columns:
                    continue
                for vol_q in strategy_cfg.get("vol_quantiles", [0.75]):
                    vol_threshold = float(train["vol20"].quantile(float(vol_q)))
                    for top_n in top_n_values:
                        params = {
                            "eligible": True,
                            "quality_quantile": float(quality_q),
                            "quality_threshold": quality_threshold,
                            "trend_window": int(trend_window),
                            "vol_quantile": float(vol_q),
                            "vol_threshold": vol_threshold,
                            "target_vol": target_vol,
                            "top_n": int(top_n),
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

        if best is None:
            best = {
                "eligible": False,
                "quality_quantile": 0.7,
                "quality_threshold": float(scores.quantile(0.7)),
                "trend_window": 20,
                "vol_quantile": 0.75,
                "vol_threshold": float(train["vol20"].quantile(0.75)),
                "target_vol": target_vol,
                "top_n": int(top_n_values[0]) if top_n_values else int(strategy_cfg.get("top_n", 3)),
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
        if panel.empty:
            return StrategyOutput(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame(), self.build_metadata(params))

        d = panel.copy()
        trend_col = f"ma{int(params['trend_window'])}"
        if "quality_growth_score" not in d.columns or trend_col not in d.columns:
            dates = pd.Index(sorted(d["date"].dropna().unique()))
            empty = pd.Series(0.0, index=dates)
            return StrategyOutput(empty, empty, pd.DataFrame(), self.build_metadata(params))

        eligible = (
            (d["quality_growth_score"] >= float(params["quality_threshold"]))
            & (d["close"] > d[trend_col])
            & (d["vol20"] <= float(params["vol_threshold"]))
        )
        d["rank_score"] = d["quality_growth_score"].where(eligible, np.nan)
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
            f"quality_growth@q{params['quality_quantile']},"
            f"ma{params['trend_window']},"
            f"vol@q{params['vol_quantile']},"
            f"target_vol={params['target_vol']},"
            f"top_n={params.get('top_n', '')},"
            f"xmarket_overlay={params.get('use_xmarket_overlay', True)}"
        )
