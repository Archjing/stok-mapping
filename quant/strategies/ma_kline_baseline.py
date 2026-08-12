from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from quant.strategies.base import BaseStrategy, StrategyOutput
from quant.strategies.registry import register


@register
class MaKlineBaselineStrategy(BaseStrategy):
    name = "ma_kline_baseline_v1"
    candidate_name = "ma_kline_baseline_v1"
    display_name = "MA/K-line Baseline"
    category = "rule_based"

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return bool(strategy_cfg.get("baseline_ma_kline", {}).get("enabled", False))

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
        cfg = strategy_cfg.get("baseline_ma_kline", {})
        top_n_values = cfg.get("top_n_values", [strategy_cfg.get("top_n", 3)])
        trend_window_pairs = cfg.get("trend_window_pairs", [[20, 60]])
        amount_ratio_mins = cfg.get("amount_ratio_mins", [1.0, 1.2])
        upper_shadow_max_values = cfg.get("upper_shadow_max_values", [1.0, 1.5])

        for top_n in top_n_values:
            for pair in trend_window_pairs:
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    continue
                trend_window, confirm_window = int(pair[0]), int(pair[1])
                trend_col = f"ma{trend_window}"
                confirm_col = f"ma{confirm_window}"
                if trend_col not in train.columns or confirm_col not in train.columns:
                    continue
                for amount_ratio_min in amount_ratio_mins:
                    for upper_shadow_max in upper_shadow_max_values:
                        for vol_q in strategy_cfg.get("vol_quantiles", [0.75]):
                            vol_threshold = float(train["vol20"].quantile(float(vol_q)))
                            params = {
                                "trend_window": trend_window,
                                "confirm_window": confirm_window,
                                "amount_ratio_min": float(amount_ratio_min),
                                "upper_shadow_max": float(upper_shadow_max),
                                "vol_quantile": float(vol_q),
                                "vol_threshold": vol_threshold,
                                "target_vol": target_vol,
                                "top_n": int(top_n),
                            }
                            output = self.apply(
                                train,
                                params,
                                slippage=slippage,
                                commission=commission,
                                stamp_duty_sell=stamp_duty_sell,
                            )
                            from quant.research.metrics import calc_metrics as _calc_metrics

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
                "trend_window": 20,
                "confirm_window": 60,
                "amount_ratio_min": 1.0,
                "upper_shadow_max": 1.0,
                "vol_quantile": 0.75,
                "vol_threshold": float(train["vol20"].quantile(0.75)),
                "target_vol": target_vol,
                "top_n": int(top_n_values[0]) if top_n_values else int(strategy_cfg.get("top_n", 3)),
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
    ) -> tuple[pd.Series, pd.Series]:
        trend_col = f"ma{int(params['trend_window'])}"
        confirm_col = f"ma{int(params['confirm_window'])}"
        eligible = (
            (panel["close"] > panel[trend_col])
            & (panel[trend_col] > panel[confirm_col])
            & (panel["body_pct"] > 0)
            & (panel["upper_shadow_pct"] <= float(params["upper_shadow_max"]))
            & (panel["amount_ratio20"] >= float(params["amount_ratio_min"]))
            & (panel["vol20"] <= float(params["vol_threshold"]))
        )
        d = panel.copy()
        d["rank_score"] = (0.7 * d["mom20"] + 0.3 * d["breakout20"]).where(eligible, np.nan)
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
            f"ma{params['trend_window']}>ma{params['confirm_window']},"
            f"amount>={params['amount_ratio_min']},"
            f"upper_shadow<={params['upper_shadow_max']},"
            f"vol@q{params['vol_quantile']},"
            f"target_vol={params['target_vol']},"
            f"top_n={params.get('top_n', '')}"
        )
