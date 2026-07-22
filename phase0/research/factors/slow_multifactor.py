from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd


DEFAULT_WEIGHTS = {
    "slow_quality_score": 0.30,
    "slow_value_score": 0.20,
    "slow_low_vol_score": 0.20,
    "slow_earnings_score": 0.15,
    "slow_residual_momentum_score": 0.15,
}

_FACTOR_SCORES = tuple(DEFAULT_WEIGHTS)


def _numeric_column(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _mean_available(frame: pd.DataFrame, columns: Sequence[str]) -> pd.Series:
    available = [
        pd.to_numeric(frame[column], errors="coerce").rename(column)
        for column in columns
        if column in frame.columns
    ]
    if not available:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.concat(available, axis=1).mean(axis=1)


def _neutralize_one_day(day: pd.DataFrame, raw_column: str) -> pd.Series:
    raw = _numeric_column(day, raw_column).replace([np.inf, -np.inf], np.nan)
    industry = day.get("industry", pd.Series("", index=day.index)).fillna("").astype(str)
    centered_raw = raw - raw.groupby(industry).transform("mean")

    market_cap = _numeric_column(day, "market_cap").where(lambda values: values.gt(0))
    log_size = pd.Series(np.log(market_cap), index=day.index).where(centered_raw.notna())
    centered_size = log_size - log_size.groupby(industry).transform("mean")
    valid = centered_raw.notna() & centered_size.notna()

    result = centered_raw.copy()
    if int(valid.sum()) < 3:
        return result

    valid_size = centered_size.loc[valid]
    size_variance = float(valid_size.var())
    if not np.isfinite(size_variance) or size_variance <= 0:
        return result

    beta = float(centered_raw.loc[valid].cov(valid_size) / size_variance)
    result.loc[valid] = centered_raw.loc[valid] - beta * valid_size
    return result


def _neutralized_rank(frame: pd.DataFrame, raw_column: str, output_prefix: str) -> pd.DataFrame:
    neutral_column = f"{output_prefix}_neutral"
    score_column = f"{output_prefix}_score"
    neutral = pd.Series(np.nan, index=frame.index, dtype=float)

    for _, day in frame.groupby("date", sort=True):
        neutral.loc[day.index] = _neutralize_one_day(day, raw_column)

    frame[neutral_column] = neutral
    frame[score_column] = frame.groupby("date", sort=False)[neutral_column].rank(method="average", pct=True)
    return frame


def _normalized_weights(weights: Mapping[str, float] | None) -> dict[str, float]:
    source = DEFAULT_WEIGHTS if weights is None else weights
    normalized = {column: max(float(weight), 0.0) for column, weight in source.items()}
    total = float(sum(normalized.values()))
    if not np.isfinite(total) or total <= 0:
        raise ValueError("slow multifactor weights must have a positive total")
    unknown = set(normalized).difference(_FACTOR_SCORES)
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"unknown slow multifactor score weights: {names}")
    return {column: weight / total for column, weight in normalized.items()}


def add_slow_multifactor_features(
    panel: pd.DataFrame,
    *,
    weights: Mapping[str, float] | None = None,
    min_available_factors: int = 4,
) -> pd.DataFrame:
    """Add deterministic point-in-time slow factor features to a panel."""
    if panel.empty:
        return panel.copy()

    frame = panel.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.strip()
    frame = frame.sort_values(["symbol", "date"], kind="stable").reset_index(drop=True)
    if "industry" not in frame.columns:
        frame["industry"] = ""
    else:
        frame["industry"] = frame["industry"].fillna("").astype(str).str.strip()

    for column in ["close", "market_cap", "pe_ttm", "pb", "vol60"]:
        frame[column] = _numeric_column(frame, column)

    frame["slow_quality_raw"] = _mean_available(
        frame,
        [
            "quality_roe_component",
            "quality_cash_flow_component",
            "quality_low_debt_component",
        ],
    )
    frame["slow_earnings_raw"] = _mean_available(
        frame,
        [
            "quality_profit_growth_component",
            "quality_revenue_growth_component",
        ],
    )
    earnings_yield = (1.0 / frame["pe_ttm"].where(frame["pe_ttm"].gt(0))).replace(
        [np.inf, -np.inf], np.nan
    )
    book_yield = (1.0 / frame["pb"].where(frame["pb"].gt(0))).replace([np.inf, -np.inf], np.nan)
    frame["slow_value_raw"] = pd.concat([earnings_yield, book_yield], axis=1).mean(axis=1)
    frame["slow_low_vol_raw"] = -frame["vol60"]

    grouped_close = frame.groupby("symbol", sort=False)["close"]
    frame["slow_residual_momentum_raw"] = grouped_close.shift(20) / grouped_close.shift(120) - 1.0

    for raw_column, prefix in [
        ("slow_quality_raw", "slow_quality"),
        ("slow_earnings_raw", "slow_earnings"),
        ("slow_value_raw", "slow_value"),
        ("slow_low_vol_raw", "slow_low_vol"),
        ("slow_residual_momentum_raw", "slow_residual_momentum"),
    ]:
        frame = _neutralized_rank(frame, raw_column, prefix)

    factor_weights = _normalized_weights(weights)
    frame["slow_factor_available_count"] = frame[list(_FACTOR_SCORES)].notna().sum(axis=1)
    weighted_sum = pd.Series(0.0, index=frame.index)
    available_weight = pd.Series(0.0, index=frame.index)
    for score_column, weight in factor_weights.items():
        available = frame[score_column].notna()
        weighted_sum = weighted_sum + frame[score_column].fillna(0.0) * weight
        available_weight = available_weight + available.astype(float) * weight

    composite = weighted_sum / available_weight.where(available_weight.gt(0))
    eligible = (
        frame["slow_quality_score"].notna()
        & frame["slow_earnings_score"].notna()
        & frame["slow_factor_available_count"].ge(int(min_available_factors))
    )
    frame["slow_composite_score"] = composite.where(eligible)
    return frame
