"""Causal daily technical-feature builders (Tier-A local price/volume).

Pure functions only: no I/O, no network, no SQLite writes, no strategy-specific
ranking.  Every builder takes a panel (one or more symbols) and returns a Series
aligned to the input index.  Rolling/EMA calculations are grouped by ``symbol``
so one symbol's history never leaks into another.

Formulas match the project's existing legacy columns where they overlap
(``maN``, ``momN``, ``vol20``, ``amount_ratio20``, gap/range) so equivalence
tests can pin them before any walk-forward migration.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _sort(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a symbol-major, date-ascending frame without mutating the input."""
    return frame.sort_values(["symbol", "date"], kind="stable")


def _drop_symbol_level(series: pd.Series) -> pd.Series:
    """Reset a (symbol, index) MultiIndex back to the flat input index."""
    if isinstance(series.index, pd.MultiIndex):
        return series.reset_index(level=0, drop=True)
    return series


def build_return_1(frame: pd.DataFrame) -> pd.Series:
    d = _sort(frame)
    return d.groupby("symbol", sort=False)["close"].pct_change()


def build_open_close_return_1(frame: pd.DataFrame) -> pd.Series:
    return frame["close"] / frame["open"] - 1.0


def build_gap_return_1(frame: pd.DataFrame) -> pd.Series:
    d = _sort(frame)
    prev_close = d.groupby("symbol", sort=False)["close"].shift(1)
    return d["open"] / prev_close - 1.0


def build_range_pct_1(frame: pd.DataFrame) -> pd.Series:
    return (frame["high"] - frame["low"]) / frame["close"]


def build_volume_change_1(frame: pd.DataFrame) -> pd.Series:
    d = _sort(frame)
    return d.groupby("symbol", sort=False)["volume"].pct_change()


def build_amount_change_1(frame: pd.DataFrame) -> pd.Series:
    d = _sort(frame)
    return d.groupby("symbol", sort=False)["amount"].pct_change()


def build_volatility_20(frame: pd.DataFrame) -> pd.Series:
    d = _sort(frame)
    ret = d.groupby("symbol", sort=False)["close"].pct_change()
    roll = ret.groupby(d["symbol"], sort=False).rolling(20).std()
    return _drop_symbol_level(roll) * np.sqrt(252)


def build_rolling_high_20(frame: pd.DataFrame) -> pd.Series:
    d = _sort(frame)
    return _drop_symbol_level(d.groupby("symbol", sort=False)["high"].rolling(20).max())


def build_rolling_low_20(frame: pd.DataFrame) -> pd.Series:
    d = _sort(frame)
    return _drop_symbol_level(d.groupby("symbol", sort=False)["low"].rolling(20).min())


def build_drawdown_60(frame: pd.DataFrame) -> pd.Series:
    d = _sort(frame)
    roll_max = _drop_symbol_level(
        d.groupby("symbol", sort=False)["close"].rolling(60, min_periods=1).max()
    )
    return d["close"] / roll_max - 1.0


def build_ma(window: int) -> callable:
    def _build(frame: pd.DataFrame) -> pd.Series:
        d = _sort(frame)
        return _drop_symbol_level(d.groupby("symbol", sort=False)["close"].rolling(window).mean())
    _build.__name__ = f"build_ma_{window}"
    return _build


def build_ema(span: int) -> callable:
    def _build(frame: pd.DataFrame) -> pd.Series:
        d = _sort(frame)
        return _drop_symbol_level(
            d.groupby("symbol", sort=False)["close"].ewm(span=span, adjust=False).mean()
        )
    _build.__name__ = f"build_ema_{span}"
    return _build


def build_macd_line_12_26(frame: pd.DataFrame) -> pd.Series:
    return build_ema(12)(frame) - build_ema(26)(frame)


def build_macd_signal_9(frame: pd.DataFrame) -> pd.Series:
    d = _sort(frame)
    line = build_macd_line_12_26(d)
    return _drop_symbol_level(
        line.groupby(d["symbol"], sort=False).ewm(span=9, adjust=False).mean()
    )


def build_macd_hist_12_26_9(frame: pd.DataFrame) -> pd.Series:
    return build_macd_line_12_26(frame) - build_macd_signal_9(frame)


def build_rsi_14(frame: pd.DataFrame) -> pd.Series:
    d = _sort(frame)
    close = d.groupby("symbol", sort=False)["close"]
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = _drop_symbol_level(
        gain.groupby(d["symbol"], sort=False).ewm(alpha=1 / 14, min_periods=14).mean()
    )
    avg_loss = _drop_symbol_level(
        loss.groupby(d["symbol"], sort=False).ewm(alpha=1 / 14, min_periods=14).mean()
    )
    # avg_loss == 0 with avg_gain > 0 => RSI 100 (all gains); both zero => NaN.
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def build_bollinger_mid_20(frame: pd.DataFrame) -> pd.Series:
    d = _sort(frame)
    return _drop_symbol_level(d.groupby("symbol", sort=False)["close"].rolling(20).mean())


def _bollinger_std_20(frame: pd.DataFrame) -> pd.Series:
    d = _sort(frame)
    return _drop_symbol_level(d.groupby("symbol", sort=False)["close"].rolling(20).std(ddof=0))


def build_bollinger_upper_20_2(frame: pd.DataFrame) -> pd.Series:
    return build_bollinger_mid_20(frame) + 2.0 * _bollinger_std_20(frame)


def build_bollinger_lower_20_2(frame: pd.DataFrame) -> pd.Series:
    return build_bollinger_mid_20(frame) - 2.0 * _bollinger_std_20(frame)


def build_momentum(window: int) -> callable:
    def _build(frame: pd.DataFrame) -> pd.Series:
        d = _sort(frame)
        return d.groupby("symbol", sort=False)["close"].pct_change(window)
    _build.__name__ = f"build_momentum_{window}"
    return _build


def build_reversal_5(frame: pd.DataFrame) -> pd.Series:
    return -build_momentum(5)(frame)


def build_amount_ratio_20(frame: pd.DataFrame) -> pd.Series:
    d = _sort(frame)
    ma20 = _drop_symbol_level(d.groupby("symbol", sort=False)["amount"].rolling(20).mean())
    # preserve_nan: a missing/zero denominator stays NaN (legacy walk_forward
    # `_shadow_ratio` fills 0 instead; equivalence must be pinned before migration).
    return d["amount"] / ma20.replace(0.0, np.nan)


def build_volume_shock_z20(frame: pd.DataFrame) -> pd.Series:
    d = _sort(frame)
    log_vol = np.log(d["volume"].replace(0.0, np.nan))
    mean = _drop_symbol_level(log_vol.groupby(d["symbol"], sort=False).rolling(20).mean())
    std = _drop_symbol_level(log_vol.groupby(d["symbol"], sort=False).rolling(20).std())
    return (log_vol - mean) / std.replace(0.0, np.nan)


def build_turnover_rate(frame: pd.DataFrame) -> pd.Series:
    if "turnover_rate" in frame.columns:
        return frame["turnover_rate"]
    return pd.Series(index=frame.index, dtype=float)


# ── registry construction ──────────────────────────────────────────────

def build_technical_registry() -> "FeatureRegistry":
    """Return a FeatureRegistry with all Tier-A technical features registered."""
    from quant.research.features.registry import FeatureRegistry, FeatureSpec

    reg = FeatureRegistry.with_base_fields(
        {"symbol", "date", "open", "high", "low", "close", "volume", "amount", "turnover_rate"}
    )

    def add(name: str, inputs: tuple[str, ...], lookback: int, builder) -> None:
        reg.register(FeatureSpec(
            name=name, version="1", inputs=inputs,
            lookback_sessions=lookback, availability_lag_sessions=0,
            missing_data_policy="preserve_nan", builder=builder,
        ))

    add("return_1", ("close",), 1, build_return_1)
    add("open_close_return_1", ("open", "close"), 1, build_open_close_return_1)
    add("gap_return_1", ("open", "close"), 1, build_gap_return_1)
    add("range_pct_1", ("high", "low", "close"), 1, build_range_pct_1)
    add("volume_change_1", ("volume",), 1, build_volume_change_1)
    add("amount_change_1", ("amount",), 1, build_amount_change_1)
    add("volatility_20", ("close",), 20, build_volatility_20)
    add("rolling_high_20", ("high",), 20, build_rolling_high_20)
    add("rolling_low_20", ("low",), 20, build_rolling_low_20)
    add("drawdown_60", ("close",), 60, build_drawdown_60)
    add("ma_3", ("close",), 3, build_ma(3))
    add("ma_5", ("close",), 5, build_ma(5))
    add("ma_10", ("close",), 10, build_ma(10))
    add("ma_20", ("close",), 20, build_ma(20))
    add("ma_60", ("close",), 60, build_ma(60))
    add("ema_12", ("close",), 12, build_ema(12))
    add("ema_26", ("close",), 26, build_ema(26))
    add("macd_line_12_26", ("ema_12", "ema_26"), 26, build_macd_line_12_26)
    add("macd_signal_9", ("macd_line_12_26",), 35, build_macd_signal_9)
    add("macd_hist_12_26_9", ("macd_line_12_26", "macd_signal_9"), 35, build_macd_hist_12_26_9)
    add("rsi_14", ("close",), 14, build_rsi_14)
    add("bollinger_mid_20", ("close",), 20, build_bollinger_mid_20)
    add("bollinger_upper_20_2", ("bollinger_mid_20",), 20, build_bollinger_upper_20_2)
    add("bollinger_lower_20_2", ("bollinger_mid_20",), 20, build_bollinger_lower_20_2)
    add("momentum_5", ("close",), 5, build_momentum(5))
    add("momentum_20", ("close",), 20, build_momentum(20))
    add("reversal_5", ("momentum_5",), 5, build_reversal_5)
    add("amount_ratio_20", ("amount",), 20, build_amount_ratio_20)
    add("volume_shock_z20", ("volume",), 20, build_volume_shock_z20)
    add("turnover_rate", ("turnover_rate",), 1, build_turnover_rate)
    return reg
