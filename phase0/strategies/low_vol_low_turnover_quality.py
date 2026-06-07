from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from phase0.strategies.base import BaseStrategy, StrategyOutput
from phase0.strategies.registry import register


@register
class LowVolLowTurnoverQualityStrategy(BaseStrategy):
    # 策略元信息用于注册表、候选比较报告和后续治理判断。当前候选尚未通过 gate，
    # 因此只允许进入 compare，不进入盘前 brief 或模拟账户。
    name = "low_vol_low_turnover_quality_v1"
    candidate_name = "low_vol_low_turnover_quality_v1"
    display_name = "Low Vol Low Turnover Quality"
    category = "factor"
    panel_scope = "portfolio"
    supports_brief = False
    supports_paper_trade = False

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        """根据 config.yaml 中的本地因子配置判断策略是否启用。"""
        cfg = strategy_cfg.get("local_factor", {}).get("low_vol_low_turnover_quality", {})
        return bool(cfg.get("enabled", False))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        """为策略补齐 point-in-time 质量因子和低换手代理字段。"""
        from phase0.walk_forward import _add_quality_growth_features

        # 质量因子复用现有 PIT 财务特征构造；若上游只提供 vol20，则在这里补 vol60，
        # 使低波窗口可以按 T2.6 要求在 20/60 之间切换。换手因子优先用 20 日平均换手率，
        # 缺少换手率时退化为成交额相对均值，二者都缺失则显式置空并在选参阶段 fallback。
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
        """在训练窗口内搜索低波、低换手、质量和中期动量的首版参数组合。"""
        from phase0.walk_forward import _calc_metrics

        # 首版只搜索阈值、持仓数量、调仓周期和中期动量窗口；因子权重固定，
        # 以降低参数空间和过拟合风险。训练样本不足时返回不可交易 fallback。
        cfg = strategy_cfg.get("local_factor", {}).get("low_vol_low_turnover_quality", {})
        target_vol = float(cfg.get("target_vol", strategy_cfg.get("target_vol", 0.18)))
        min_trades = int(strategy_cfg.get("train_min_trades", 5))
        weights = self._factor_weights(cfg)

        quality_scores = train.get("quality_growth_score", pd.Series(dtype=float)).dropna()
        turnover_scores = train.get("turnover_rate20", pd.Series(dtype=float)).dropna()
        if train.empty or quality_scores.empty or turnover_scores.empty:
            return self._fallback_params(train, strategy_cfg, cfg, target_vol, weights)

        # 参数网格来自 config.yaml：质量/低波/低换手分位决定硬筛选阈值，
        # top_n 和 hold_multiplier 决定买入区与继续持有区，rebalance/min_hold 控制低换手行为。
        best: dict[str, Any] | None = None
        quality_quantiles = [float(item) for item in cfg.get("quality_quantiles", [0.6, 0.7])]
        low_vol_windows = [int(item) for item in cfg.get("low_vol_windows", [20, 60])]
        low_vol_quantiles = [float(item) for item in cfg.get("low_vol_quantiles", [0.5])]
        low_turnover_quantiles = [float(item) for item in cfg.get("low_turnover_quantiles", [0.5])]
        momentum_windows = [int(item) for item in cfg.get("momentum_windows", [20, 60])]
        buy_top_n_values = [int(item) for item in cfg.get("top_n_values", cfg.get("buy_top_n_values", [10, 20]))]
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
                vol_col_values = train[vol_col].dropna()
                if vol_col_values.empty:
                    continue
                for low_vol_q in low_vol_quantiles:
                    vol_threshold = float(vol_col_values.quantile(low_vol_q))
                    for low_turnover_q in low_turnover_quantiles:
                        turnover_threshold = float(turnover_scores.quantile(low_turnover_q))
                        for momentum_window in momentum_windows:
                            mom_col = f"mom{momentum_window}"
                            if mom_col not in train.columns:
                                continue
                            for buy_top_n in buy_top_n_values:
                                for hold_multiplier in hold_rank_multipliers:
                                    hold_top_n = max(buy_top_n, int(round(buy_top_n * hold_multiplier)))
                                    for rebalance_days in rebalance_days_values:
                                        for min_hold_days in min_hold_days_values:
                                            if min_hold_days > rebalance_days * 3:
                                                continue
                                            base_params = {
                                                "eligible": True,
                                                "quality_quantile": quality_q,
                                                "quality_threshold": quality_threshold,
                                                "low_vol_window": low_vol_window,
                                                "low_vol_quantile": low_vol_q,
                                                "vol_threshold": vol_threshold,
                                                "low_turnover_quantile": low_turnover_q,
                                                "turnover_threshold": turnover_threshold,
                                                "momentum_window": momentum_window,
                                                "buy_top_n": buy_top_n,
                                                "hold_top_n": hold_top_n,
                                                "rebalance_days": max(1, rebalance_days),
                                                "min_hold_days": max(0, min_hold_days),
                                                "target_vol": target_vol,
                                                "max_symbol_weight": max_symbol_weight,
                                                "use_xmarket_overlay": use_xmarket_overlay,
                                                "factor_weights": weights,
                                            }
                                            output = self.apply(
                                                train,
                                                base_params,
                                                slippage=slippage,
                                                commission=commission,
                                                stamp_duty_sell=stamp_duty_sell,
                                            )
                                            metric = _calc_metrics(output.returns, output.exposure)
                                            if metric["trades"] < min_trades:
                                                continue
                                            for turnover_penalty in turnover_penalties:
                                                # 训练评分同时奖励 Sharpe、惩罚回撤和年化换手，避免选出高频高摩擦参数。
                                                score = (
                                                    metric["sharpe"]
                                                    + max(metric["max_drawdown"], -1.0) * 0.5
                                                    - turnover_penalty * metric["turnover_annual"]
                                                )
                                                candidate = {
                                                    **base_params,
                                                    "turnover_penalty": turnover_penalty,
                                                    "train_score": float(score),
                                                    "train_sharpe": float(metric["sharpe"]),
                                                    "train_trades": int(metric["trades"]),
                                                    "train_turnover_annual": float(metric["turnover_annual"]),
                                                }
                                                if best is None or candidate["train_score"] > best["train_score"]:
                                                    best = candidate

        if best is None:
            return self._fallback_params(train, strategy_cfg, cfg, target_vol, weights)
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
        """根据参数在给定窗口生成低频换仓信号、成本后收益和持仓明细。"""
        if panel.empty:
            return StrategyOutput(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame(), self.build_metadata(params))

        # 策略需要质量、波动、换手和收益字段；任一关键字段缺失或 fallback 标记为不可交易时，
        # 返回显式空仓结果，而不是用缺失值拼出虚假信号。
        d = panel.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        vol_col = f"vol{int(params.get('low_vol_window', 20))}"
        required = ["quality_growth_score", vol_col, "turnover_rate20", "ret"]
        if any(col not in d.columns for col in required) or not bool(params.get("eligible", True)):
            dates = pd.Index(sorted(d["date"].dropna().unique()))
            empty = pd.Series(0.0, index=dates)
            return StrategyOutput(empty, empty, pd.DataFrame(), self.build_metadata(params))

        mom_col = f"mom{int(params.get('momentum_window', 20))}"
        if mom_col not in d.columns:
            dates = pd.Index(sorted(d["date"].dropna().unique()))
            empty = pd.Series(0.0, index=dates)
            return StrategyOutput(empty, empty, pd.DataFrame(), self.build_metadata(params))

        # 四个因子都转成同日横截面分位后再加权，确保量纲可比；低波和低换手反向排名，
        # 即波动越低、换手越低，分位得分越高。total_weight 用于容忍配置权重和不等于 1。
        weights_cfg = params.get("factor_weights", {})
        quality_weight = float(weights_cfg.get("quality", 0.25))
        low_vol_weight = float(weights_cfg.get("low_volatility", 0.40))
        low_turnover_weight = float(weights_cfg.get("low_turnover", 0.25))
        momentum_weight = float(weights_cfg.get("medium_momentum", 0.10))
        total_weight = quality_weight + low_vol_weight + low_turnover_weight + momentum_weight
        if total_weight <= 0:
            total_weight = 1.0

        d["quality_rank_component"] = d.groupby("date")["quality_growth_score"].rank(method="average", pct=True)
        d["low_vol_rank_component"] = 1.0 - d.groupby("date")[vol_col].rank(method="average", pct=True)
        d["low_turnover_rank_component"] = 1.0 - d.groupby("date")["turnover_rate20"].rank(method="average", pct=True)
        d["medium_momentum_rank_component"] = d.groupby("date")[mom_col].rank(method="average", pct=True)
        d["score"] = (
            quality_weight * d["quality_rank_component"]
            + low_vol_weight * d["low_vol_rank_component"]
            + low_turnover_weight * d["low_turnover_rank_component"]
            + momentum_weight * d["medium_momentum_rank_component"]
        ) / total_weight

        # 先用质量、波动、换手三道硬门槛过滤，再对合格股票按综合分排序；
        # vol_scale 用近期波动缩放仓位，可选 overlay_scale 预留跨市场风险缩放。
        eligible = (
            (d["quality_growth_score"] >= float(params["quality_threshold"]))
            & (d[vol_col] <= float(params["vol_threshold"]))
            & (d["turnover_rate20"] <= float(params["turnover_threshold"]))
            & d["score"].notna()
        )
        d["rank_score"] = d["score"].where(eligible, np.nan)
        d["rank"] = d.groupby("date")["rank_score"].rank(method="first", ascending=False)
        d["vol_scale"] = np.minimum(1.0, float(params["target_vol"]) / d[vol_col].replace(0, np.nan)).fillna(0.0)
        if bool(params.get("use_xmarket_overlay", False)):
            d["overlay_scale"] = d.get("risk_scale", pd.Series(1.0, index=d.index)).clip(0.0, 1.0)
        else:
            d["overlay_scale"] = 1.0

        buy_top_n = int(params["buy_top_n"])
        hold_top_n = int(params["hold_top_n"])
        rebalance_days = max(1, int(params["rebalance_days"]))
        min_hold_days = max(0, int(params["min_hold_days"]))
        max_symbol_weight = float(params.get("max_symbol_weight", 0.10))

        # current_weights 是收盘后形成的目标持仓，held_days 用于执行最短持有期。
        # 只有调仓日才重新审视组合：老持仓持有够久且跌出宽持有区才卖，新候选按排名补足目标数量。
        current_weights: dict[str, float] = {}
        held_days: dict[str, int] = {}
        frames: list[pd.DataFrame] = []

        for idx, (_, day) in enumerate(d.groupby("date", sort=True)):
            day = day.copy()
            is_rebalance_day = idx % rebalance_days == 0
            if is_rebalance_day:
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
                for symbol in candidates["symbol"].head(buy_top_n).astype(str):
                    if len(current_weights) >= buy_top_n:
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

        # 收盘后得到的目标权重右移一天才生效，避免未来函数；随后按权重矩阵计算换手、
        # 卖出额、交易成本、成本后收益和组合敞口，并保留信号明细供报告和诊断复用。
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
                    "quality_rank_component",
                    "low_vol_rank_component",
                    "low_turnover_rank_component",
                    "medium_momentum_rank_component",
                ]
                if col in out.columns
            ]
        ].copy()
        return StrategyOutput(returns=returns, exposure=exposure, signal_frame=signal_frame, metadata=self.build_metadata(params))

    def format_params(self, params: dict[str, Any]) -> str:
        """把策略参数压缩成人类可读的报告摘要。"""
        return (
            f"low_vol_low_turnover_quality@q{params.get('quality_quantile', '')},"
            f"vol_window={params.get('low_vol_window', '')},"
            f"vol_q={params.get('low_vol_quantile', '')},"
            f"turnover_q={params.get('low_turnover_quantile', '')},"
            f"mom{params.get('momentum_window', '')},"
            f"buy_top={params.get('buy_top_n', '')},"
            f"hold_top={params.get('hold_top_n', '')},"
            f"rebalance={params.get('rebalance_days', '')}d,"
            f"min_hold={params.get('min_hold_days', '')}d,"
            f"max_w={params.get('max_symbol_weight', '')},"
            f"target_vol={params.get('target_vol', '')},"
            f"turnover_penalty={params.get('turnover_penalty', 0.0)}"
        )

    def _factor_weights(self, cfg: dict[str, Any]) -> dict[str, float]:
        """读取四因子权重配置，并提供符合 T2.6 首版方案的默认值。"""
        raw = cfg.get("factor_weights", {})
        return {
            "low_volatility": float(raw.get("low_volatility", 0.40)),
            "low_turnover": float(raw.get("low_turnover", 0.25)),
            "quality": float(raw.get("quality", 0.25)),
            "medium_momentum": float(raw.get("medium_momentum", 0.10)),
        }

    def _fallback_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        cfg: dict[str, Any],
        target_vol: float,
        weights: dict[str, float],
    ) -> dict[str, Any]:
        """在训练数据不足时返回不可交易参数，保证策略显式空仓而不是误造信号。"""
        # fallback 仍记录配置分位和可用样本阈值，便于报告解释为什么该折没有形成有效交易。
        quality = train.get("quality_growth_score", pd.Series(dtype=float)).dropna()
        low_vol_window = int(cfg.get("low_vol_windows", [20])[0])
        vol = train.get(f"vol{low_vol_window}", pd.Series(dtype=float)).dropna()
        turnover = train.get("turnover_rate20", pd.Series(dtype=float)).dropna()
        quality_q = float(cfg.get("quality_quantiles", [0.7])[0])
        vol_q = float(cfg.get("low_vol_quantiles", [0.5])[0])
        turnover_q = float(cfg.get("low_turnover_quantiles", [0.5])[0])
        return {
            "eligible": False,
            "quality_quantile": quality_q,
            "quality_threshold": float(quality.quantile(quality_q)) if not quality.empty else 1.1,
            "low_vol_window": low_vol_window,
            "low_vol_quantile": vol_q,
            "vol_threshold": float(vol.quantile(vol_q)) if not vol.empty else 0.0,
            "low_turnover_quantile": turnover_q,
            "turnover_threshold": float(turnover.quantile(turnover_q)) if not turnover.empty else 0.0,
            "momentum_window": int(cfg.get("momentum_windows", [20])[0]),
            "buy_top_n": int(cfg.get("top_n_values", cfg.get("buy_top_n_values", [10]))[0]),
            "hold_top_n": int(cfg.get("top_n_values", cfg.get("buy_top_n_values", [10]))[0]) * 2,
            "rebalance_days": int(cfg.get("rebalance_days_values", [20])[0]),
            "min_hold_days": int(cfg.get("min_hold_days_values", [20])[0]),
            "target_vol": target_vol,
            "max_symbol_weight": float(cfg.get("max_symbol_weight", 0.10)),
            "use_xmarket_overlay": bool(cfg.get("use_xmarket_overlay", False)),
            "factor_weights": weights,
            "turnover_penalty": float(cfg.get("turnover_penalties", [0.02])[0]),
            "train_score": 0.0,
            "train_sharpe": 0.0,
            "train_trades": 0,
            "train_turnover_annual": 0.0,
        }
