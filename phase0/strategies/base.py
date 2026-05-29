from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class BaseStrategy(ABC):
    name: str = ""
    candidate_name: str = ""

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return True

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        return panel

    @abstractmethod
    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def apply(
        self,
        panel: pd.DataFrame,
        params: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> tuple[pd.Series, pd.Series]:
        raise NotImplementedError

    @abstractmethod
    def format_params(self, params: dict[str, Any]) -> str:
        raise NotImplementedError
