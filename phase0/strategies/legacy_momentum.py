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
    panel_scope = "symbol"

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        return {"mom_threshold": float(train["mom5"].median())}

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
        d["selected"] = (d["mom5"] > float(params["mom_threshold"]))
        d["selected"] = d["selected"].astype(float)
        d["weight"] = d["selected"].shift(1).fillna(0.0)
        trade_size = d["weight"].diff().abs().fillna(d["weight"].abs())
        costs = trade_size * (slippage + commission)
        sell_size = (d["weight"].shift(1).fillna(0.0) - d["weight"]).clip(lower=0)
        costs += sell_size * stamp_duty_sell
        returns = d["weight"] * d["ret"] - costs
        d["position_ret"] = returns
        d["raw_weight"] = d["selected"]
        signal_frame = d[[c for c in ["date", "symbol", "score", "selected", "raw_weight", "weight", "ret", "position_ret"] if c in d.columns]].copy()
        return StrategyOutput(
            returns=returns,
            exposure=d["weight"],
            signal_frame=signal_frame,
            metadata=self.build_metadata(params),
        )

    def format_params(self, params: dict[str, Any]) -> str:
        return "legacy_mom5_median"
