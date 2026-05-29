from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from phase0.strategies.base import BaseStrategy
from phase0.strategies.registry import register


@register
class LegacyMomentumStrategy(BaseStrategy):
    name = "legacy_momentum"
    candidate_name = "legacy_momentum"

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
    ) -> tuple[pd.Series, pd.Series]:
        signal = (panel["mom5"] > float(params["mom_threshold"]))
        signal = signal.astype(float).shift(1).fillna(0.0)
        trade_size = signal.diff().abs().fillna(signal.abs())
        costs = trade_size * (slippage + commission)
        sell_size = (signal.shift(1).fillna(0.0) - signal).clip(lower=0)
        costs += sell_size * stamp_duty_sell
        returns = signal * panel["ret"] - costs
        return returns, signal

    def format_params(self, params: dict[str, Any]) -> str:
        return "legacy_mom5_median"
