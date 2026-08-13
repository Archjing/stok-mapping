"""Tests for the momentum + MACD golden cross + MA trend strategy."""
from __future__ import annotations

import numpy as np
import pandas as pd

from quant.strategies.momentum_macd_golden_cross import (
    MomentumMacdGoldenCrossStrategy,
    _add_macd,
)


def _panel(n_days: int = 120, n_symbols: int = 5, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    dates = pd.bdate_range("2024-01-01", periods=n_days)
    for s in range(n_symbols):
        symbol = f"SH.60000{s}"
        price = 10.0
        for d in dates:
            price *= 1 + rng.normal(0.0005, 0.02)
            rows.append({
                "date": d, "symbol": symbol, "close": price,
                "open": price * (1 + rng.normal(0, 0.005)),
                "ret": rng.normal(0.0005, 0.02),
            })
    return pd.DataFrame(rows)


def test_add_macd_computes_dif_dea_hist() -> None:
    panel = _panel()
    out = _add_macd(panel)
    assert "macd_dif" in out.columns
    assert "macd_dea" in out.columns
    assert "macd_hist" in out.columns
    assert "macd_golden_cross" in out.columns
    assert "ma_golden_cross" in out.columns
    # no cross-symbol leakage: dif == ema12 - ema26
    assert np.allclose(out["macd_dif"], out["close"].groupby(out["symbol"]).transform(
        lambda s: s.ewm(span=12, adjust=False).mean() - s.ewm(span=26, adjust=False).mean()
    ))


def test_golden_cross_flag_is_0_or_1() -> None:
    out = _add_macd(_panel())
    assert set(out["macd_golden_cross"].unique()) <= {0.0, 1.0}
    assert set(out["ma_golden_cross"].unique()) <= {0.0, 1.0}


def test_apply_produces_returns_and_exposure() -> None:
    panel = _add_macd(_panel())
    # add required fields mom20/ma60/vol20
    panel["mom20"] = panel["close"].groupby(panel["symbol"]).transform(lambda s: s.pct_change(20))
    panel["ma60"] = panel["close"].groupby(panel["symbol"]).transform(lambda s: s.rolling(60).mean())
    panel["vol20"] = panel["ret"].groupby(panel["symbol"]).transform(lambda s: s.rolling(20).std() * np.sqrt(252))

    strat = MomentumMacdGoldenCrossStrategy()
    params = {
        "eligible": True, "momentum_quantile": 0.5, "momentum_threshold": 0.0,
        "rebalance_days": 5, "top_n": 2, "cross_mode": "any", "require_trend": True,
        "target_vol": 0.18, "max_symbol_weight": 0.5,
    }
    out = strat.apply(panel, params, slippage=0.001, commission=0.0005, stamp_duty_sell=0.0005)
    assert not out.returns.empty
    assert not out.exposure.empty
    # exposure should never exceed 1.0
    assert (out.exposure <= 1.0 + 1e-9).all()


def test_select_params_returns_tradable_or_fallback() -> None:
    panel = _add_macd(_panel())
    panel["mom20"] = panel["close"].groupby(panel["symbol"]).transform(lambda s: s.pct_change(20))
    panel["ma60"] = panel["close"].groupby(panel["symbol"]).transform(lambda s: s.rolling(60).mean())
    panel["vol20"] = panel["ret"].groupby(panel["symbol"]).transform(lambda s: s.rolling(20).std() * np.sqrt(252))

    strat = MomentumMacdGoldenCrossStrategy()
    cfg = {"local_factor": {"momentum_macd_golden_cross": {
        "momentum_quantiles": [0.5], "rebalance_days_values": [5], "top_n_values": [2],
        "cross_modes": ["any"], "require_trend": True, "max_symbol_weight": 0.5,
    }}}
    params = strat.select_params(panel, cfg, slippage=0.001, commission=0.0005, stamp_duty_sell=0.0005)
    assert "momentum_threshold" in params
    assert "rebalance_days" in params
    assert params["rebalance_days"] >= 1
