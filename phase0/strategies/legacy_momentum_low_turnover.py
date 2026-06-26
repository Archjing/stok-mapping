from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from phase0.strategies.base import BaseStrategy, StrategyOutput
from phase0.strategies.registry import register


@register
class LegacyMomentumLowTurnoverStrategy(BaseStrategy):
    name = "legacy_momentum_low_turnover_v1"
    candidate_name = "legacy_momentum_low_turnover_v1"
    display_name = "Legacy Momentum Low Turnover"
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
        from phase0.research.metrics import calc_metrics as _calc_metrics

        cfg = strategy_cfg.get("legacy_momentum_low_turnover", {})
        mom_windows = [int(item) for item in cfg.get("mom_windows", [5, 20])]
        buy_quantiles = [float(item) for item in cfg.get("buy_quantiles", [0.5, 0.6])]
        hold_quantiles = [float(item) for item in cfg.get("hold_quantiles", [0.4])]
        buy_top_n_values = [int(item) for item in cfg.get("buy_top_n_values", [5, 10])]
        hold_rank_multipliers = [float(item) for item in cfg.get("hold_rank_multipliers", [2.0])]
        rebalance_days_values = [int(item) for item in cfg.get("rebalance_days_values", [5, 10, 20])]
        min_hold_days_values = [int(item) for item in cfg.get("min_hold_days_values", [5, 10])]
        turnover_penalties = [float(item) for item in cfg.get("turnover_penalties", [0.005, 0.01])]
        target_vol = float(strategy_cfg.get("target_vol", 0.18))
        min_trades = int(strategy_cfg.get("train_min_trades", 5))

        # 只在训练窗口里试参数：模拟先复盘历史行情，再决定下一段验证期采用哪套看盘口径。
        best: dict[str, Any] | None = None
        for mom_window in mom_windows:
            mom_col = f"mom{mom_window}"
            if mom_col not in train.columns:
                continue
            scores = train[mom_col].dropna()
            if scores.empty:
                continue
            for buy_q in buy_quantiles:
                # 买入阈值取训练期动量分位数，代表“动量强到足够靠前才允许新买”。
                buy_threshold = float(scores.quantile(buy_q))
                for hold_q in hold_quantiles:
                    if hold_q > buy_q:
                        continue
                    # 持有阈值通常低于买入阈值，给老持仓更宽的观察空间，减少来回换股。
                    hold_threshold = float(scores.quantile(hold_q))
                    for buy_top_n in buy_top_n_values:
                        for hold_multiplier in hold_rank_multipliers:
                            # 持有排名范围大于新买排名范围：买入从强者里挑，卖出等明显掉队再处理。
                            hold_top_n = max(buy_top_n, int(round(buy_top_n * hold_multiplier)))
                            for rebalance_days in rebalance_days_values:
                                for min_hold_days in min_hold_days_values:
                                    if min_hold_days > rebalance_days * 3:
                                        continue
                                    base_params = {
                                        "mom_window": mom_window,
                                        "buy_quantile": buy_q,
                                        "buy_threshold": buy_threshold,
                                        "hold_quantile": hold_q,
                                        "hold_threshold": hold_threshold,
                                        "buy_top_n": buy_top_n,
                                        "hold_top_n": hold_top_n,
                                        "rebalance_days": rebalance_days,
                                        "min_hold_days": min_hold_days,
                                        "target_vol": target_vol,
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
                                        # 选参不只看 Sharpe，也惩罚回撤和高换手，模拟实盘对回撤、滑点和手续费的顾虑。
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
            best = {
                "mom_window": 5,
                "buy_quantile": 0.5,
                "buy_threshold": float(train["mom5"].median()),
                "hold_quantile": 0.4,
                "hold_threshold": float(train["mom5"].quantile(0.4)),
                "buy_top_n": 5,
                "hold_top_n": 10,
                "rebalance_days": 10,
                "min_hold_days": 5,
                "target_vol": target_vol,
                "turnover_penalty": 0.01,
                "train_score": 0.0,
                "train_sharpe": 0.0,
                "train_trades": 0,
                "train_turnover_annual": 0.0,
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
            empty = pd.Series(dtype=float)
            return StrategyOutput(empty, empty, pd.DataFrame(), self.build_metadata(params))

        d = panel.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        mom_col = f"mom{int(params['mom_window'])}"
        buy_threshold = float(params["buy_threshold"])
        hold_threshold = float(params.get("hold_threshold", buy_threshold))
        buy_top_n = int(params["buy_top_n"])
        hold_top_n = int(params["hold_top_n"])
        rebalance_days = max(1, int(params["rebalance_days"]))
        min_hold_days = max(0, int(params["min_hold_days"]))
        target_vol = float(params["target_vol"])

        d["score"] = d[mom_col]
        d["buy_score"] = d[mom_col].where(d[mom_col] > buy_threshold, np.nan)
        d["rank"] = d.groupby("date")["score"].rank(method="first", ascending=False)
        # vol_scale 是风险仓位尺子：股票近期波动越高，实际投入权重越低。
        d["vol_scale"] = np.minimum(1.0, target_vol / d["vol20"].replace(0, np.nan)).fillna(0.0)

        date_groups = [(date, day.copy()) for date, day in d.groupby("date", sort=True)]
        # current_weights 代表盘后形成的目标持仓清单；held_days 用来模拟最短持有期约束。
        current_weights: dict[str, float] = {}
        held_days: dict[str, int] = {}
        frames: list[pd.DataFrame] = []

        for idx, (_, day) in enumerate(date_groups):
            is_rebalance_day = idx % rebalance_days == 0
            if is_rebalance_day:
                # 调仓日先复查已有持仓：持有够久且跌出“继续观察区”才卖，避免频繁追涨杀跌。
                rank_by_symbol = day.set_index("symbol")["rank"].to_dict()
                score_by_symbol = day.set_index("symbol")["score"].to_dict()
                for symbol in list(current_weights):
                    rank = rank_by_symbol.get(symbol, np.nan)
                    score = score_by_symbol.get(symbol, np.nan)
                    old_enough = held_days.get(symbol, 0) >= min_hold_days
                    outside_hold_band = pd.isna(rank) or float(rank) > hold_top_n or pd.isna(score) or float(score) <= hold_threshold
                    if old_enough and outside_hold_band:
                        current_weights.pop(symbol, None)
                        held_days.pop(symbol, None)

                # 再看当日新候选：只从动量超过买入阈值的股票中，按排名补足目标持仓数量。
                ranked = day[day["buy_score"].notna()].sort_values("rank")
                for symbol in ranked["symbol"].head(buy_top_n).astype(str):
                    if len(current_weights) >= buy_top_n:
                        break
                    if symbol not in current_weights:
                        current_weights[symbol] = 0.0
                        held_days[symbol] = 0

                day_symbols = set(day["symbol"].astype(str))
                active = [symbol for symbol in current_weights if symbol in day_symbols]
                if active:
                    # 基础上等权分配；再乘以 vol_scale，模拟对高波动股票主动降仓。
                    vol_scale_by_symbol = day.set_index(day["symbol"].astype(str))["vol_scale"].to_dict()
                    weights = {}
                    for symbol in active:
                        vol_scale = float(vol_scale_by_symbol.get(symbol, 0.0))
                        weights[symbol] = (1.0 / len(active)) * vol_scale
                    current_weights = weights
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
        # 当日信号来自收盘后看盘，shift(1) 表示下一交易日才开始持仓，避免用未来价格成交。
        out["weight"] = out.groupby("symbol")["weight_unshifted"].shift(1).fillna(0.0)
        out["position_ret"] = out["weight"] * out["ret"]

        weights = out.pivot(index="date", columns="symbol", values="weight").fillna(0.0)
        turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
        sells = weights.diff().clip(upper=0).abs().sum(axis=1).fillna(0.0)
        gross = out.groupby("date")["position_ret"].sum()
        # 调仓额扣滑点和佣金，卖出额另扣印花税，用来模拟实盘交易摩擦。
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
                ]
                if col in out.columns
            ]
        ].copy()
        return StrategyOutput(
            returns=returns,
            exposure=exposure,
            signal_frame=signal_frame,
            metadata=self.build_metadata(params),
        )

    def format_params(self, params: dict[str, Any]) -> str:
        return (
            f"mom{params['mom_window']}@q{params['buy_quantile']},"
            f"hold_q={params.get('hold_quantile', '')},"
            f"buy_top={params['buy_top_n']},"
            f"hold_top={params['hold_top_n']},"
            f"rebalance={params['rebalance_days']}d,"
            f"min_hold={params['min_hold_days']}d,"
            f"turnover_penalty={params.get('turnover_penalty', 0.0)},"
            f"target_vol={params['target_vol']}"
        )
