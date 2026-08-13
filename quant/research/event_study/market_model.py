"""Single-factor market model for event-study abnormal returns.

Model: ``R_it = alpha_i + beta_i * R_mt + epsilon_it``.

Estimation window defaults to [-120, -21] trading sessions relative to the
event day (the standard ~100-day net window that excludes the event itself).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_EST_START = -120
DEFAULT_EST_END = -21


def _window_slice(n: int, event_idx: int, est_start: int, est_end: int) -> slice | None:
    """Return the estimation-window slice over a length-``n`` series.

    Returns None when the window has fewer than 2 observations (OLS needs >= 2)
    so callers can propagate NaN instead of crashing.
    """
    lo = event_idx + est_start
    hi = event_idx + est_end  # inclusive
    if lo < 0 or hi <= lo + 1 or hi >= n:
        return None
    return slice(lo, hi + 1)


def estimate_market_model(
    asset_returns: pd.Series,
    market_returns: pd.Series,
    *,
    event_idx: int,
    est_start: int = DEFAULT_EST_START,
    est_end: int = DEFAULT_EST_END,
) -> tuple[float, float]:
    """Estimate ``(alpha, beta)`` via OLS over the estimation window.

    Returns ``(nan, nan)`` when the window is unavailable (too short / out of
    range) so downstream computations degrade to NaN rather than crash.
    """
    if len(asset_returns) != len(market_returns):
        raise ValueError("asset and market returns must have equal length")
    n = len(asset_returns)
    sl = _window_slice(n, event_idx, est_start, est_end)
    if sl is None:
        return float("nan"), float("nan")
    y = asset_returns.iloc[sl].to_numpy(dtype=float)
    x = market_returns.iloc[sl].to_numpy(dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 2:
        return float("nan"), float("nan")
    xm, ym = x[mask], y[mask]
    beta = np.cov(xm, ym, ddof=1)[0, 1] / np.var(xm, ddof=1)
    alpha = ym.mean() - beta * xm.mean()
    return float(alpha), float(beta)


def expected_returns(
    market_returns: pd.Series,
    alpha: float,
    beta: float,
) -> pd.Series:
    """Expected asset returns ``alpha + beta * R_mt`` (index-aligned)."""
    return alpha + beta * market_returns
