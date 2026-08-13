"""Tests for the event-study core: market model, AR/CAR, cross-sectional tests."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from quant.research.event_study.abnormal_returns import (
    compute_ar_car,
    map_event_to_trading_day,
)
from quant.research.event_study.aggregation import cross_sectional_test
from quant.research.event_study.market_model import (
    estimate_market_model,
    expected_returns,
)


# ── synthetic data helpers ─────────────────────────────────────────────

def _synthetic_returns(
    n: int = 300,
    beta: float = 1.5,
    alpha: float = 0.0001,
    shock: float = 0.0,
    shock_idx: int | None = None,
    seed: int = 0,
) -> tuple[pd.Series, pd.Series]:
    """Build asset + market return series with a known market model.

    market ~ N(0, 0.01); asset = alpha + beta * market + noise; optional shock.
    """
    rng = np.random.default_rng(seed)
    market = pd.Series(rng.normal(0.0, 0.01, n))
    noise = rng.normal(0.0, 0.008, n)
    asset = alpha + beta * market + noise
    if shock_idx is not None:
        asset.iloc[shock_idx] += shock
    return asset, market


def _calendar(n: int = 400, start: str = "2024-01-01") -> pd.DataFrame:
    # weekdays only -> a trading calendar approximation
    dates = pd.bdate_range(start, periods=n)
    return pd.DataFrame({"date": dates.strftime("%Y-%m-%d")})


# ── market model ───────────────────────────────────────────────────────

def test_estimate_market_model_recovers_beta() -> None:
    asset, market = _synthetic_returns(beta=1.5, alpha=0.0002)
    alpha, beta = estimate_market_model(asset, market, est_start=-120, est_end=-21, event_idx=200)
    assert beta == pytest.approx(1.5, abs=0.15)
    assert alpha == pytest.approx(0.0002, abs=0.01)


def test_estimate_market_model_returns_nan_when_window_too_short() -> None:
    asset, market = _synthetic_returns(n=40)
    alpha, beta = estimate_market_model(asset, market, est_start=-120, est_end=-21, event_idx=20)
    assert np.isnan(alpha) and np.isnan(beta)


def test_expected_returns_uses_beta() -> None:
    asset, market = _synthetic_returns(n=300, beta=1.5, alpha=0.0)
    alpha, beta = estimate_market_model(asset, market, est_start=-120, est_end=-21, event_idx=200)
    expected = expected_returns(market, alpha, beta)
    # expected = alpha + beta * market
    pd.testing.assert_series_equal(expected, alpha + beta * market, check_names=False)


# ── event-day mapping ──────────────────────────────────────────────────

def test_map_event_to_trading_day_uses_next_strictly_later_day() -> None:
    cal = _calendar(400)
    # 2024-01-05 is a Friday trading day -> next strictly later = Monday 2024-01-08
    assert map_event_to_trading_day(cal, "2024-01-05") == "2024-01-08"


def test_map_event_to_trading_day_on_weekend() -> None:
    cal = _calendar(400)
    # 2024-01-06 is Saturday -> next trading day = Monday 2024-01-08
    assert map_event_to_trading_day(cal, "2024-01-06") == "2024-01-08"


def test_map_event_to_trading_day_past_end_returns_none() -> None:
    cal = _calendar(5)
    assert map_event_to_trading_day(cal, "2025-12-31") is None


# ── AR/CAR ─────────────────────────────────────────────────────────────

def test_compute_ar_car_detects_positive_shock() -> None:
    asset, market = _synthetic_returns(n=300, beta=1.5, shock=0.05, shock_idx=200)
    alpha, beta = estimate_market_model(asset, market, est_start=-120, est_end=-21, event_idx=200)
    # AR on shock day should be ~ +5% (after removing market + beta)
    ar_car = compute_ar_car(asset, market, alpha, beta, event_idx=200, windows=[(-1, 1)])
    row = ar_car.iloc[0]
    # CAR over [-1,+1] includes the +5% shock minus two ~0 days
    assert row["car"] == pytest.approx(0.05, abs=0.02)
    assert row["ar_0"] == pytest.approx(0.05, abs=0.02)


def test_compute_ar_car_windows_expand() -> None:
    asset, market = _synthetic_returns(n=300)
    alpha, beta = estimate_market_model(asset, market, est_start=-120, est_end=-21, event_idx=200)
    ar_car = compute_ar_car(asset, market, alpha, beta, event_idx=200, windows=[(-1, 1), (-5, 20)])
    assert len(ar_car) == 2
    assert list(ar_car["window"]) == ["(-1, +1)", "(-5, +20)"]


# ── cross-sectional test ───────────────────────────────────────────────

def test_cross_sectional_test_positive_mean() -> None:
    rng = np.random.default_rng(1)
    cars = pd.Series(rng.normal(0.02, 0.05, 50))
    result = cross_sectional_test(cars)
    assert result["n"] == 50
    assert result["mean_car"] == pytest.approx(0.02, abs=0.02)
    assert result["t_stat"] > 1.5  # mean clearly positive vs noise
    assert 0 < result["p_value"] <= 1
    assert result["positive_share"] == pytest.approx(cars.gt(0).mean(), abs=0.1)


def test_cross_sectional_test_single_observation() -> None:
    result = cross_sectional_test(pd.Series([0.03]))
    assert result["n"] == 1
    assert math.isnan(result["t_stat"])
    assert math.isnan(result["p_value"])
