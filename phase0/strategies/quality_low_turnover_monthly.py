from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from phase0.strategies.base import BaseStrategy, StrategyOutput
from phase0.strategies.registry import register


@register
class QualityLowTurnoverMonthlyStrategy(BaseStrategy):
    # T2.7 是 quality_growth_price_v1 的低频版本：质量是唯一核心 ranker，
    # 低波和低换手只负责约束与降权；通过 gate 前不进入 brief 或模拟账户。
    name = "quality_low_turnover_monthly_v1"
    candidate_name = "quality_low_turnover_monthly_v1"
    display_name = "Quality Low Turnover Monthly"
    category = "factor"
    panel_scope = "portfolio"
    supports_brief = False
    supports_paper_trade = False

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        """根据 config.yaml 中的本地因子配置判断策略是否启用。"""
        cfg = strategy_cfg.get("local_factor", {}).get("quality_low_turnover_monthly", {})
        return bool(cfg.get("enabled", False))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        """补齐 PIT 质量分、质量子因子贡献、低波窗口和低换手代理字段。"""
        from phase0.walk_forward import _add_quality_growth_features

        # 质量特征复用已有财务 PIT 逻辑；这里额外生成 vol60 与 turnover_rate20，
        # 并把 _roe_score 等内部质量子分数复制为可报告字段，便于解释质量贡献和缺失影响。
        d = _add_quality_growth_features(panel, strategy_cfg)
        if d.empty:
            return d
        d = d.copy().sort_values(["symbol", "date"]).reset_index(drop=True)
        if "vol60" not in d.columns and "ret" in d.columns:
            returns = pd.to_numeric(d["ret"], errors="coerce")
            d["vol60"] = returns.groupby(d["symbol"]).transform(lambda s: s.rolling(60, min_periods=20).std()) * np.sqrt(252)
        if "turnover_rate" in d.columns:
            turnover = pd.to_numeric(d["turnover_rate"], errors="coerce")
            d["turnover_rate20"] = turnover.groupby(d["symbol"]).transform(
                lambda s: s.rolling(20, min_periods=5).mean()
            )
        elif "amount_ratio20" in d.columns:
            d["turnover_rate20"] = pd.to_numeric(d["amount_ratio20"], errors="coerce")
        else:
            d["turnover_rate20"] = np.nan

        contribution_map = {
            "_roe_score": "quality_roe_component",
            "_cash_flow_score": "quality_cash_flow_component",
            "_profit_growth_score": "quality_profit_growth_component",
            "_revenue_growth_score": "quality_revenue_growth_component",
            "_low_debt_score": "quality_low_debt_component",
        }
        for source, target in contribution_map.items():
            d[target] = d[source] if source in d.columns else np.nan
        if "financial_available_fields" not in d.columns:
            d["financial_available_fields"] = np.nan
        return d

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        """在训练窗口内搜索质量准入阈值、低波/低换手约束和低频持仓参数。"""
        from phase0.research.metrics import calc_metrics as _calc_metrics

        # T2.7 不搜索短线趋势或动量窗口；训练评分仍惩罚回撤和换手，避免把财务慢变量日频交易化。
        cfg = strategy_cfg.get("local_factor", {}).get("quality_low_turnover_monthly", {})
        target_vol = float(cfg.get("target_vol", strategy_cfg.get("target_vol", 0.18)))
        min_trades = int(strategy_cfg.get("train_min_trades", 5))
        quality_scores = train.get("quality_growth_score", pd.Series(dtype=float)).dropna()
        turnover_scores = train.get("turnover_rate20", pd.Series(dtype=float)).dropna()
        if train.empty or quality_scores.empty or turnover_scores.empty:
            return self._fallback_params(train, cfg, target_vol)

        best: dict[str, Any] | None = None
        quality_quantiles = [float(item) for item in cfg.get("quality_quantiles", [0.6, 0.7])]
        low_vol_windows = [int(item) for item in cfg.get("low_vol_windows", [20, 60])]
        low_vol_quantiles = [float(item) for item in cfg.get("low_vol_quantiles", [0.5, 0.6])]
        low_turnover_quantiles = [float(item) for item in cfg.get("low_turnover_quantiles", [0.5])]
        top_n_values = [int(item) for item in cfg.get("top_n_values", [10, 20])]
        hold_rank_multipliers = [float(item) for item in cfg.get("hold_rank_multipliers", [2.0])]
        rebalance_days_values = [int(item) for item in cfg.get("rebalance_days_values", [20, 40])]
        min_hold_days_values = [int(item) for item in cfg.get("min_hold_days_values", [20])]
        turnover_penalties = [float(item) for item in cfg.get("turnover_penalties", [0.02])]
        use_xmarket_overlay = bool(cfg.get("use_xmarket_overlay", False))
        max_symbol_weight = float(cfg.get("max_symbol_weight", 0.10))

        for quality_q in quality_quantiles:
            quality_threshold = float(quality_scores.quantile(quality_q))
            for low_vol_window in low_vol_windows:
                vol_col = f"vol{low_vol_window}"
                if vol_col not in train.columns:
                    continue
                vol_scores = train[vol_col].dropna()
                if vol_scores.empty:
                    continue
                for low_vol_q in low_vol_quantiles:
                    vol_threshold = float(vol_scores.quantile(low_vol_q))
                    for low_turnover_q in low_turnover_quantiles:
                        turnover_threshold = float(turnover_scores.quantile(low_turnover_q))
                        for top_n in top_n_values:
                            for hold_multiplier in hold_rank_multipliers:
                                hold_top_n = max(top_n, int(round(top_n * hold_multiplier)))
                                for rebalance_days in rebalance_days_values:
                                    for min_hold_days in min_hold_days_values:
                                        if min_hold_days > rebalance_days * 3:
                                            continue
                                        params = {
                                            "eligible": True,
                                            "quality_quantile": quality_q,
                                            "quality_threshold": quality_threshold,
                                            "low_vol_window": low_vol_window,
                                            "low_vol_quantile": low_vol_q,
                                            "vol_threshold": vol_threshold,
                                            "low_turnover_quantile": low_turnover_q,
                                            "turnover_threshold": turnover_threshold,
                                            "top_n": top_n,
                                            "hold_top_n": hold_top_n,
                                            "rebalance_days": max(20, rebalance_days),
                                            "min_hold_days": max(20, min_hold_days),
                                            "target_vol": target_vol,
                                            "max_symbol_weight": max_symbol_weight,
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

        if best is None:
            return self._fallback_params(train, cfg, target_vol)
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
        """按质量分排序生成月频/低频持仓，并计算成本后组合收益。"""
        if panel.empty:
            return StrategyOutput(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame(), self.build_metadata(params))

        # 质量分是唯一排序分；低波和低换手只控制资格与仓位，不参与综合加权排序。
        d = panel.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        vol_col = f"vol{int(params.get('low_vol_window', 20))}"
        required = ["quality_growth_score", vol_col, "turnover_rate20", "ret"]
        if any(col not in d.columns for col in required) or not bool(params.get("eligible", True)):
            dates = pd.Index(sorted(d["date"].dropna().unique()))
            empty = pd.Series(0.0, index=dates)
            return StrategyOutput(empty, empty, pd.DataFrame(), self.build_metadata(params))

        eligible = (
            (d["quality_growth_score"] >= float(params["quality_threshold"]))
            & (d[vol_col] <= float(params["vol_threshold"]))
            & (d["turnover_rate20"] <= float(params["turnover_threshold"]))
            & d["quality_growth_score"].notna()
        )
        d["score"] = d["quality_growth_score"]
        d["rank_score"] = d["score"].where(eligible, np.nan)
        d["rank"] = d.groupby("date")["rank_score"].rank(method="first", ascending=False)
        d["vol_scale"] = np.minimum(1.0, float(params["target_vol"]) / d[vol_col].replace(0, np.nan)).fillna(0.0)
        if bool(params.get("use_xmarket_overlay", False)):
            d["overlay_scale"] = d.get("risk_scale", pd.Series(1.0, index=d.index)).clip(0.0, 1.0)
        else:
            d["overlay_scale"] = 1.0

        top_n = int(params["top_n"])
        hold_top_n = int(params["hold_top_n"])
        rebalance_days = max(20, int(params["rebalance_days"]))
        min_hold_days = max(20, int(params["min_hold_days"]))
        max_symbol_weight = float(params.get("max_symbol_weight", 0.10))

        # 每 20/40 个交易日才调仓；老持仓跌出宽排名区且已满足最短持有期才卖，
        # 避免把季度/年度财务质量信号交易成日频噪音。
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
                for symbol in candidates["symbol"].head(top_n).astype(str):
                    if len(current_weights) >= top_n:
                        break
                    if symbol not in current_weights:
                        current_weights[symbol] = 0.0
                        held_days[symbol] = 0

                active = [symbol for symbol in current_weights if symbol in set(day["symbol"].astype(str))]
                if active:
                    indexed = day.set_index(day["symbol"].astype(str))
                    raw_weight = min(max_symbol_weight, 1.0 / len(active))
                    current_weights = {
                        symbol: raw_weight
                        * float(indexed.loc[symbol, "vol_scale"])
                        * float(indexed.loc[symbol, "overlay_scale"])
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
                    "quality_growth_score",
                    "quality_threshold",
                    "low_vol_window",
                    "turnover_rate20",
                    "turnover_threshold",
                    "financial_announce_date",
                    "financial_available_fields",
                    "quality_roe_component",
                    "quality_cash_flow_component",
                    "quality_profit_growth_component",
                    "quality_revenue_growth_component",
                    "quality_low_debt_component",
                ]
                if col in out.columns
            ]
        ].copy()
        signal_frame["quality_threshold"] = float(params.get("quality_threshold", np.nan))
        signal_frame["low_vol_window"] = int(params.get("low_vol_window", 0))
        signal_frame["turnover_threshold"] = float(params.get("turnover_threshold", np.nan))
        return StrategyOutput(returns=returns, exposure=exposure, signal_frame=signal_frame, metadata=self.build_metadata(params))

    def format_params(self, params: dict[str, Any]) -> str:
        """把策略参数压缩成人类可读的报告摘要。"""
        return (
            f"quality_low_turnover_monthly@q{params.get('quality_quantile', '')},"
            f"vol_window={params.get('low_vol_window', '')},"
            f"vol_q={params.get('low_vol_quantile', '')},"
            f"turnover_q={params.get('low_turnover_quantile', '')},"
            f"top_n={params.get('top_n', '')},"
            f"hold_top={params.get('hold_top_n', '')},"
            f"rebalance={params.get('rebalance_days', '')}d,"
            f"min_hold={params.get('min_hold_days', '')}d,"
            f"max_w={params.get('max_symbol_weight', '')},"
            f"target_vol={params.get('target_vol', '')},"
            f"turnover_penalty={params.get('turnover_penalty', 0.0)}"
        )

    def _fallback_params(self, train: pd.DataFrame, cfg: dict[str, Any], target_vol: float) -> dict[str, Any]:
        """在训练数据不足时返回不可交易参数，保证策略显式空仓而不是误造信号。"""
        quality = train.get("quality_growth_score", pd.Series(dtype=float)).dropna()
        low_vol_window = int(cfg.get("low_vol_windows", [20])[0])
        vol = train.get(f"vol{low_vol_window}", pd.Series(dtype=float)).dropna()
        turnover = train.get("turnover_rate20", pd.Series(dtype=float)).dropna()
        quality_q = float(cfg.get("quality_quantiles", [0.7])[0])
        vol_q = float(cfg.get("low_vol_quantiles", [0.5])[0])
        turnover_q = float(cfg.get("low_turnover_quantiles", [0.5])[0])
        top_n = int(cfg.get("top_n_values", [10])[0])
        return {
            "eligible": False,
            "quality_quantile": quality_q,
            "quality_threshold": float(quality.quantile(quality_q)) if not quality.empty else 1.1,
            "low_vol_window": low_vol_window,
            "low_vol_quantile": vol_q,
            "vol_threshold": float(vol.quantile(vol_q)) if not vol.empty else 0.0,
            "low_turnover_quantile": turnover_q,
            "turnover_threshold": float(turnover.quantile(turnover_q)) if not turnover.empty else 0.0,
            "top_n": top_n,
            "hold_top_n": top_n * 2,
            "rebalance_days": int(cfg.get("rebalance_days_values", [20])[0]),
            "min_hold_days": int(cfg.get("min_hold_days_values", [20])[0]),
            "target_vol": target_vol,
            "max_symbol_weight": float(cfg.get("max_symbol_weight", 0.10)),
            "use_xmarket_overlay": bool(cfg.get("use_xmarket_overlay", False)),
            "turnover_penalty": float(cfg.get("turnover_penalties", [0.02])[0]),
            "train_score": 0.0,
            "train_sharpe": 0.0,
            "train_trades": 0,
            "train_turnover_annual": 0.0,
        }
