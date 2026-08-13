"""Cross-sectional aggregation and significance tests for event studies."""
from __future__ import annotations

import numpy as np
import pandas as pd


def cross_sectional_test(cars: pd.Series) -> dict[str, float | int]:
    """Standard event-study J1 cross-sectional t-test over a CAR series.

    ``t_stat = mean(car) / (std(car) / sqrt(n))`` with ddof=1.  Returns NaN
    for the t-statistic and p-value when ``n < 2`` (std undefined).
    """
    series = pd.Series(cars).dropna()
    n = int(len(series))
    if n == 0:
        return {
            "n": 0, "mean_car": float("nan"), "std_car": float("nan"),
            "t_stat": float("nan"), "p_value": float("nan"),
            "positive_share": float("nan"),
        }
    mean = float(series.mean())
    std = float(series.std(ddof=1))
    if n < 2 or not np.isfinite(std) or std == 0:
        return {
            "n": n, "mean_car": mean, "std_car": float("nan"),
            "t_stat": float("nan"), "p_value": float("nan"),
            "positive_share": float((series > 0).mean()),
        }
    t_stat = mean / (std / np.sqrt(n))
    # two-sided p-value via the normal approximation (large-sample event study).
    # norm CDF via erf: Phi(x) = 0.5 * (1 + erf(x / sqrt(2))).
    import math

    z = abs(t_stat)
    p_value = float(1.0 - math.erf(z / math.sqrt(2.0)))
    return {
        "n": n, "mean_car": mean, "std_car": std,
        "t_stat": float(t_stat), "p_value": p_value,
        "positive_share": float((series > 0).mean()),
    }


def aggregate_events(car_frame: pd.DataFrame, group_col: str | None = None) -> pd.DataFrame:
    """Aggregate per-event CAR rows into cross-sectional test statistics.

    ``car_frame`` must contain a ``car`` column (one row per event), plus an
    optional grouping column (e.g. ``window`` or ``industry``).  Returns one
    row per group with mean CAR, t-stat, p-value, N, and positive share.
    """
    if "car" not in car_frame.columns:
        raise ValueError("car_frame requires a 'car' column")
    if group_col is None or group_col not in car_frame.columns:
        stats = cross_sectional_test(car_frame["car"])
        return pd.DataFrame([{**stats, "group": "all"}])

    frames = []
    for key, sub in car_frame.groupby(group_col, dropna=False):
        stats = cross_sectional_test(sub["car"])
        frames.append({**stats, "group": key})
    return pd.DataFrame(frames)
