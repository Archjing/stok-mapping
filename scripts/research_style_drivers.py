"""Quantify what macro variables LEAD growth/value style rotation.

Method: lead-lag correlation scan at monthly frequency.

- Dependent: future growth-minus-value relative return over horizons 1/3/6 months.
- Explanatory: each macro series' level change (month-over-month), and for
  policy variables (rates) the level itself.
- Scan lag 0..3 months to find which macro variables lead the style rotation.

This is a *descriptive* lead-lag scan, not a trading signal. Sample is short
(2015-2026, ~130 months), so results are directional evidence, not proof.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

MARKET_DB = Path("data/a_share_history.sqlite")
MACRO_DB = Path("data/macro_history.sqlite")
GROWTH_IDX = "SH.000057"
VALUE_IDX = "SH.000058"


def _load_index_monthly(conn: sqlite3.Connection, symbol: str) -> pd.Series:
    """Monthly index close (last trading day of each month)."""
    df = pd.read_sql_query(
        "SELECT date, close FROM market_index_bars WHERE symbol=? ORDER BY date",
        conn, params=(symbol,),
    )
    if df.empty:
        return pd.Series(dtype=float)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")["close"].astype(float)
    monthly = df.resample("ME").last()
    return monthly


def load_style_relative_return() -> pd.Series:
    """Monthly growth-minus-value return (log return difference)."""
    conn = sqlite3.connect(MARKET_DB)
    g = _load_index_monthly(conn, GROWTH_IDX)
    v = _load_index_monthly(conn, VALUE_IDX)
    conn.close()
    idx = g.index.intersection(v.index)
    g_ret = np.log(g.loc[idx]).diff()
    v_ret = np.log(v.loc[idx]).diff()
    return (g_ret - v_ret).dropna()  # monthly style-relative return


def load_macro_monthly() -> pd.DataFrame:
    """Load all macro series aligned to monthly frequency (last value of month)."""
    conn = sqlite3.connect(MACRO_DB)
    df = pd.read_sql_query(
        "SELECT symbol, date, value FROM macro_series ORDER BY date", conn
    )
    conn.close()
    df["date"] = pd.to_datetime(df["date"], format="mixed", errors="coerce")
    df = df.dropna(subset=["date"])
    # pivot to wide: symbol × date
    wide = df.pivot_table(index="date", columns="symbol", values="value", aggfunc="last")
    wide = wide.resample("ME").last()  # month-end alignment
    return wide


def lead_lag_scan(
    style_ret: pd.Series,
    macro: pd.DataFrame,
    horizons: tuple[int, ...] = (1, 3, 6),
    max_lag: int = 3,
) -> pd.DataFrame:
    """Scan lead-lag correlation: macro change at t-lag vs future style return.

    Returns one row per (variable, horizon, lag) with correlation + sign.
    """
    rows = []
    for var in macro.columns:
        series = macro[var].dropna()
        if len(series) < 40:
            continue
        # change (level change for rates/indices; already YoY for M2/PPI/CPI)
        change = series.diff()  # month-over-month change
        for lag in range(0, max_lag + 1):
            x = change.shift(lag)  # macro change lagged by `lag` months
            for horizon in horizons:
                # future style return over `horizon` months
                y = style_ret.rolling(horizon).sum().shift(-horizon + 1)
                common = pd.concat([x, y], axis=1, join="inner").dropna()
                if len(common) < 30:
                    continue
                corr = common.iloc[:, 0].corr(common.iloc[:, 1])
                rows.append({
                    "variable": var,
                    "lag_months": lag,
                    "horizon_months": horizon,
                    "correlation": corr,
                    "n": len(common),
                })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    style_ret = load_style_relative_return()
    macro = load_macro_monthly()
    print(f"风格相对收益（月频）: {len(style_ret)} 个月")
    print(f"宏观序列: {list(macro.columns)}")
    print(f"宏观序列覆盖: {macro.index.min().date()} ~ {macro.index.max().date()}\n")

    scan = lead_lag_scan(style_ret, macro)
    if scan.empty:
        print("无足够数据")
        raise SystemExit(1)

    # best lead per variable (highest |correlation| at lag>=1, horizon 3m)
    print("=== 各宏观变量对未来 3 个月风格相对收益的领先相关性（lag=1 月）===")
    sub = scan[(scan["lag_months"] == 1) & (scan["horizon_months"] == 3)]
    sub = sub.sort_values("correlation", key=abs, ascending=False)
    for _, r in sub.iterrows():
        sign = "+" if r["correlation"] > 0 else "-"
        print(f"  {r['variable']:<18} {sign}{abs(r['correlation']):.3f}  (n={r['n']})")

    print("\n=== 全扫描 TOP15（|相关|最高，任何 lag/horizon）===")
    top = scan.reindex(scan["correlation"].abs().sort_values(ascending=False).index).head(15)
    for _, r in top.iterrows():
        sign = "+" if r["correlation"] > 0 else "-"
        print(f"  {r['variable']:<18} lag={r['lag_months']} h={r['horizon_months']}  {sign}{abs(r['correlation']):.3f}")
