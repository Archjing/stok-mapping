"""Event-day alignment and abnormal/cumulative abnormal return computation."""
from __future__ import annotations

import bisect

import numpy as np
import pandas as pd

from quant.research.event_study.market_model import (
    DEFAULT_EST_END,
    DEFAULT_EST_START,
    estimate_market_model,
)

DEFAULT_WINDOWS = [(-1, 1), (-5, 10), (-5, 20)]


def map_event_to_trading_day(
    calendar: pd.DataFrame,
    published_date: str,
) -> str | None:
    """Map a publish date to the first trading day strictly after it.

    ``calendar`` must have a ``date`` column of ascending ``YYYY-MM-DD`` strings.
    Returns None when the publish date is at or past the last trading day.
    """
    dates = sorted(str(d) for d in calendar["date"].dropna().unique())
    if not dates:
        return None
    idx = bisect.bisect_right(dates, str(published_date))
    if idx >= len(dates):
        return None
    return dates[idx]


def compute_ar_car(
    asset_returns: pd.Series,
    market_returns: pd.Series,
    alpha: float,
    beta: float,
    *,
    event_idx: int,
    windows: list[tuple[int, int]] | None = None,
) -> pd.DataFrame:
    """Compute abnormal returns and CARs over the given event windows.

    Returns one row per window with columns: ``window``, ``ar_0`` (event-day AR),
    ``car`` (cumulative AR over the window), ``n_days`` (valid observations).
    """
    windows = windows or DEFAULT_WINDOWS
    n = len(asset_returns)
    expected = alpha + beta * market_returns
    ar = asset_returns - expected

    rows: list[dict[str, float | int | str]] = []
    for start, end in windows:
        lo = event_idx + start
        hi = event_idx + end  # inclusive
        if lo < 0 or hi >= n or hi < lo:
            rows.append({
                "window": f"({start:+d}, {end:+d})",
                "ar_0": float("nan"),
                "car": float("nan"),
                "n_days": 0,
            })
            continue
        window_ar = ar.iloc[lo : hi + 1]
        valid = window_ar[np.isfinite(window_ar)]
        car = float(valid.sum()) if len(valid) else float("nan")
        ar_0_val = ar.iloc[event_idx] if 0 <= event_idx < n else float("nan")
        rows.append({
            "window": f"({start:+d}, {end:+d})",
            "ar_0": float(ar_0_val),
            "car": car,
            "n_days": int(len(valid)),
        })
    return pd.DataFrame(rows)


def run_single_event(
    asset_returns: pd.Series,
    market_returns: pd.Series,
    *,
    event_idx: int,
    windows: list[tuple[int, int]] | None = None,
    est_start: int = DEFAULT_EST_START,
    est_end: int = DEFAULT_EST_END,
) -> pd.DataFrame:
    """Estimate the market model and return the AR/CAR frame in one call."""
    alpha, beta = estimate_market_model(
        asset_returns, market_returns, event_idx=event_idx,
        est_start=est_start, est_end=est_end,
    )
    return compute_ar_car(
        asset_returns, market_returns, alpha, beta,
        event_idx=event_idx, windows=windows,
    )
