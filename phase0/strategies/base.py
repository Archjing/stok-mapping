from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class StrategyOutput:
    returns: pd.Series
    exposure: pd.Series
    signal_frame: pd.DataFrame
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseStrategy(ABC):
    name: str = ""
    candidate_name: str = ""
    display_name: str = ""
    category: str = "generic"
    strategy_role: str = "candidate"
    promotion_boundary: str = ""
    panel_scope: str = "portfolio"
    supports_compare: bool = True
    supports_brief: bool = True
    supports_paper_trade: bool = True

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return True

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        return panel

    def build_metadata(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "strategy_id": self.name,
            "candidate_name": self.candidate_name,
            "display_name": self.display_name or self.name,
            "category": self.category,
            "strategy_role": self.strategy_role,
            "promotion_boundary": self.promotion_boundary,
            "panel_scope": self.panel_scope,
            "supports_compare": self.supports_compare,
            "supports_brief": self.supports_brief,
            "supports_paper_trade": self.supports_paper_trade,
            "formatted_params": self.format_params(params),
        }

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
    ) -> StrategyOutput | tuple[pd.Series, pd.Series]:
        raise NotImplementedError

    @abstractmethod
    def format_params(self, params: dict[str, Any]) -> str:
        raise NotImplementedError
