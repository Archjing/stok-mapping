"""Presentation contracts that strategies may expose to reporting layers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

import pandas as pd


SeriesStorage = Literal["us_daily_bars", "etf_qfq"]
ThresholdOperator = Literal["lt", "lte", "gt", "gte"]


@dataclass(frozen=True)
class ComparisonSeriesConfig:
    """One source or target series used by a strategy mapping chart."""

    symbol: str
    label: str
    storage: SeriesStorage = "us_daily_bars"


@dataclass(frozen=True)
class ComparisonChartConfig:
    """Data and visual rules for one strategy mapping comparison chart."""

    slug: str
    title: str
    source: ComparisonSeriesConfig
    target: ComparisonSeriesConfig
    start_date: str | date
    end_date: str | date | None = None
    observation_band: tuple[float, float] | None = None
    daily_mapping_pct: float | None = 0.5
    absolute_threshold: float | None = None
    absolute_threshold_operator: ThresholdOperator | None = None
    consecutive_days: int = 3
    consecutive_daily_change_pct: float = 0.0

    def __post_init__(self) -> None:
        if self.consecutive_days < 2:
            raise ValueError("consecutive_days must be at least 2")
        if self.consecutive_daily_change_pct < 0:
            raise ValueError("consecutive_daily_change_pct must not be negative")
        if self.daily_mapping_pct is not None and self.daily_mapping_pct < 0:
            raise ValueError("daily_mapping_pct must not be negative")
        if self.observation_band is not None and self.observation_band[0] >= self.observation_band[1]:
            raise ValueError("observation_band must be ordered low, high")
        if (self.absolute_threshold is None) != (self.absolute_threshold_operator is None):
            raise ValueError("absolute_threshold and absolute_threshold_operator must be configured together")

    @property
    def start_timestamp(self) -> pd.Timestamp:
        return pd.Timestamp(self.start_date)

    @property
    def end_timestamp(self) -> pd.Timestamp | None:
        if self.end_date is None:
            return None
        return pd.Timestamp(self.end_date)  # type: ignore[return-value]


@dataclass(frozen=True)
class AccountMappingChart:
    """A strategy-owned chart plus its account-home card labels."""

    button_label: str
    button_kicker: str
    chart: ComparisonChartConfig
