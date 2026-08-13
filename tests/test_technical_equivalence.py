"""Equivalence: registry Tier-A features match walk_forward legacy formulas.

The legacy columns live in ``quant.walk_forward``; before any migration the
registry builders must reproduce the same numbers on a deterministic fixture
(for the overlapping columns where the archive plan requires equivalence).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from quant.research.features.technical import (
    build_ma,
    build_momentum,
    build_open_close_return_1,
    build_volatility_20,
)


def _fixture(n: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = 10.0 + np.cumsum(rng.normal(0, 0.1, n))
    open_ = close * (1 + rng.normal(0, 0.005, n))
    return pd.DataFrame({
        "symbol": ["A"] * n,
        "date": pd.date_range("2024-01-01", periods=n),
        "open": open_,
        "high": np.maximum(open_, close) * 1.01,
        "low": np.minimum(open_, close) * 0.99,
        "close": close,
        "volume": rng.integers(1000, 5000, n).astype(float),
        "amount": rng.integers(10_000, 50_000, n).astype(float),
        "turnover_rate": rng.uniform(0.5, 2.0, n),
    })


def test_ma_matches_legacy() -> None:
    frame = _fixture()
    legacy = frame["close"].rolling(20).mean()
    actual = build_ma(20)(frame)
    pd.testing.assert_series_equal(actual, legacy, check_names=False)


def test_momentum_matches_legacy() -> None:
    frame = _fixture()
    legacy = frame["close"].pct_change(20)
    actual = build_momentum(20)(frame)
    pd.testing.assert_series_equal(actual, legacy, check_names=False)


def test_volatility_20_matches_legacy_ret_std() -> None:
    frame = _fixture()
    legacy_ret = frame["close"].pct_change().fillna(0.0)
    legacy = legacy_ret.rolling(20).std() * np.sqrt(252)
    actual = build_volatility_20(frame)
    # Known semantic difference: legacy fills the first return's NaN with 0.0
    # so its 20-day window is populated one session earlier; the registry
    # preserves NaN (missing_data_policy=preserve_nan). From index 20 onward
    # both windows are full and must match.
    pd.testing.assert_series_equal(actual.iloc[20:], legacy.iloc[20:], check_names=False)


def test_open_close_return_matches_legacy_oc_ret() -> None:
    frame = _fixture()
    legacy = (frame["close"] / frame["open"].replace(0, np.nan) - 1.0).fillna(0.0)
    actual = build_open_close_return_1(frame)
    pd.testing.assert_series_equal(actual, legacy, check_names=False)
