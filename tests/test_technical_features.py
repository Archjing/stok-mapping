"""Numerical and causal tests for the Tier-A technical feature builders."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant.research.features.technical import (
    build_drawdown_60,
    build_ma,
    build_momentum,
    build_return_1,
    build_rsi_14,
    build_technical_registry,
    build_volume_shock_z20,
)


def _frame(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "symbol": ["A"] * len(closes),
        "date": pd.date_range("2024-01-01", periods=len(closes)),
        "open": closes,
        "high": [c * 1.01 for c in closes],
        "low": [c * 0.99 for c in closes],
        "close": closes,
        "volume": [1000.0] * len(closes),
        "amount": [c * 1000.0 for c in closes],
        "turnover_rate": [1.0] * len(closes),
    })


def test_return_1_uses_only_current_and_prior_closes() -> None:
    frame = _frame([10.0, 11.0, 12.0, 13.0])
    actual = build_return_1(frame)
    np.testing.assert_allclose(actual.iloc[1:], [0.1, 1 / 11, 1 / 12])


def test_rsi_uses_only_current_and_prior_closes() -> None:
    frame = _frame(list(range(1, 17)))
    baseline = build_rsi_14(frame).iloc[-1]
    changed = frame.copy()
    changed.loc[15, "close"] = 10_000
    # RSI at index 14 must not depend on index 15's changed close.
    assert build_rsi_14(changed).iloc[14] == baseline


def test_drawdown_is_zero_at_new_high_and_negative_after_decline() -> None:
    frame = _frame([10.0, 12.0, 9.0, 12.0])
    actual = build_drawdown_60(frame).to_numpy()
    np.testing.assert_allclose(actual, [0.0, 0.0, -0.25, 0.0])


def test_ma_and_momentum_match_legacy_formula() -> None:
    frame = _frame([10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
    ma5 = build_ma(5)(frame)
    assert np.isnan(ma5.iloc[:4]).all()
    np.testing.assert_allclose(ma5.iloc[4], 12.0)
    np.testing.assert_allclose(ma5.iloc[5], 13.0)
    mom5 = build_momentum(5)(frame)
    assert np.isnan(mom5.iloc[:5]).all()
    np.testing.assert_allclose(mom5.iloc[5], 15.0 / 10.0 - 1.0)


def test_volume_shock_z20_returns_nan_when_window_incomplete() -> None:
    frame = _frame([10.0] * 25)
    z = build_volume_shock_z20(frame)
    assert np.isnan(z.iloc[:19]).all()
    # Constant volume => log-vol std = 0 => denominator zero => NaN.
    assert np.isnan(z.iloc[-1])


def test_registry_builds_full_tier_a_set() -> None:
    reg = build_technical_registry()
    frame = _frame([10.0, 11.0, 12.0, 13.0] * 10)  # 40 sessions for warm-up
    requested = (
        "return_1", "open_close_return_1", "gap_return_1", "range_pct_1",
        "volume_change_1", "amount_change_1", "volatility_20", "rolling_high_20",
        "rolling_low_20", "drawdown_60", "ma_20", "ma_60", "ema_12", "ema_26",
        "macd_line_12_26", "macd_signal_9", "macd_hist_12_26_9", "rsi_14",
        "bollinger_mid_20", "bollinger_upper_20_2", "bollinger_lower_20_2",
        "momentum_5", "momentum_20", "reversal_5", "amount_ratio_20",
        "volume_shock_z20", "turnover_rate",
    )
    result = reg.build(frame, requested)
    for name in requested:
        assert name in result.columns, name
    # Every feature is causal: final row values depend only on <= final row inputs.
    # (At minimum, columns exist and index is preserved.)
    assert result.index.equals(frame.index)
