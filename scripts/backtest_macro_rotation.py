"""Plan B: macro-driven style rotation backtest (2015-2026).

Signals (monthly rebalance, T+1 execution):
- rates: US fed funds / US 10y / CN 10y rising → value, falling → growth
- liquidity: CN M2 YoY rising → growth, falling → value
- policy events: tight (稳健中性) → value; large loose → growth

Only uses point-in-time macro data (monthly values known at month end).

Research layer only.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

DB = Path("data/a_share_history.sqlite")
MACRO_DB = Path("data/macro_history.sqlite")
EVENTS_CSV = Path("data/macro_policy_events.csv")
GROWTH = "SH.000057"
VALUE = "SH.000058"


def _load_index_monthly(conn: sqlite3.Connection, symbol: str) -> pd.Series:
    df = pd.read_sql_query(
        "SELECT date, close FROM market_index_bars WHERE symbol=? ORDER BY date",
        conn, params=(symbol,),
    )
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")["close"].astype(float)
    return df.resample("ME").last()


def load_style_monthly_returns() -> pd.DataFrame:
    conn = sqlite3.connect(DB)
    g = _load_index_monthly(conn, GROWTH)
    v = _load_index_monthly(conn, VALUE)
    conn.close()
    idx = g.index.intersection(v.index)
    return pd.DataFrame({
        "growth_ret": g.loc[idx].pct_change().fillna(0.0),
        "value_ret": v.loc[idx].pct_change().fillna(0.0),
    })


def load_macro_monthly() -> pd.DataFrame:
    """Monthly macro: rates (mean of month), M2 (last value)."""
    conn = sqlite3.connect(MACRO_DB)
    df = pd.read_sql_query("SELECT symbol, date, value FROM macro_series ORDER BY date", conn)
    conn.close()
    df["date"] = pd.to_datetime(df["date"], format="mixed", errors="coerce")
    df = df.dropna(subset=["date"])
    # rates: monthly mean; M2/PPI etc are already monthly -> last
    wide = df.pivot_table(index="date", columns="symbol", values="value", aggfunc="mean")
    wide = wide.resample("ME").last()
    return wide


def _monthly_signal_rates(macro: pd.DataFrame, series: str) -> pd.Series:
    """Hold growth (1) when the rate is falling, value (0) when rising.

    Signal at month t uses change over prior 3 months (point-in-time known).
    NaN (no data yet) → 0.5 neutral, NOT a directional bet.
    """
    s = macro[series]
    change = s.diff(3)
    w = (change < 0).astype(float)
    w = w.mask(s.isna(), 0.5)  # no data → neutral
    return w.reindex(macro.index).fillna(0.5)


def _monthly_signal_m2(macro: pd.DataFrame) -> pd.Series:
    """Hold growth when M2 YoY is rising."""
    s = macro["CN_M2_YOY"]
    change = s.diff(3)
    w = (change > 0).astype(float)
    w = w.mask(s.isna(), 0.5)
    return w.reindex(macro.index).fillna(0.5)


def _policy_signal(macro_index: pd.DatetimeIndex) -> pd.Series:
    """Policy events: loose (esp large) → growth; tight → value.

    Event sets weight = 1 (growth) for 60 trading days after a large loose event,
    = 0 (value) for 60 days after a tight event.
    """
    events = pd.read_csv(EVENTS_CSV)
    events["date"] = pd.to_datetime(events["date"])
    w = pd.Series(0.5, index=macro_index)
    for _, ev in events.iterrows():
        end = ev["date"] + pd.Timedelta(days=90)
        if ev["direction"] == "loose" and ev["magnitude"] == "large":
            mask = (macro_index >= ev["date"]) & (macro_index <= end)
            w[mask] = 1.0
        elif ev["direction"] == "tight":
            mask = (macro_index >= ev["date"]) & (macro_index <= end)
            w[mask] = 0.0
    return w


def _backtest_monthly(style: pd.DataFrame, weight_growth: pd.Series, *, cost: float) -> dict:
    w = weight_growth.shift(1).fillna(0.5).clip(0.0, 1.0)
    ret = w * style["growth_ret"] + (1 - w) * style["value_ret"]
    turnover = w.diff().abs().fillna(0.0)
    ret = ret - turnover * cost
    ann = (1 + ret.mean()) ** 12 - 1
    sharpe = ret.mean() / ret.std() * np.sqrt(12) if ret.std() > 0 else 0.0
    equity = (1 + ret).cumprod()
    mdd = (equity / equity.cummax() - 1).min()
    n_switches = int((w.diff().abs() > 0.5).sum())
    return {"annual_return": ann, "sharpe": sharpe, "max_drawdown": mdd, "n_switches": n_switches}


def run_macro_rotation(cost: float = 0.001, start: str = "2015-03-01") -> pd.DataFrame:
    """Run macro-driven rotation. ``start`` limits to the rate-data-valid period.

    Rate signals only have data from 2015-01, so the full backtest is restricted
    to 2015-03 onward (allowing 3 months for the change signal to warm up).
    """
    style = load_style_monthly_returns()
    macro = load_macro_monthly()
    idx = style.index.intersection(macro.index)
    style = style.loc[idx]
    macro = macro.loc[idx]
    # restrict to macro-signal-valid period
    mask = style.index >= pd.Timestamp(start)
    style = style.loc[mask]
    macro = macro.loc[mask]
    idx = style.index

    results = []
    # baselines
    for name, w in [("持有成长", pd.Series(1.0, index=idx)),
                    ("持有价值", pd.Series(0.0, index=idx)),
                    ("50/50", pd.Series(0.5, index=idx))]:
        m = _backtest_monthly(style, w, cost=cost)
        results.append({"策略": name, **m})

    # rates signals
    for series, label in [("US_FED_FUNDS", "美联邦基金利率"), ("US_10Y_YIELD", "美10Y"), ("CN_10Y_YIELD", "中10Y")]:
        if series in macro.columns:
            w = _monthly_signal_rates(macro, series)
            m = _backtest_monthly(style, w, cost=cost)
            results.append({"策略": f"利率信号 {label}", **m})

    # M2 signal
    if "CN_M2_YOY" in macro.columns:
        w = _monthly_signal_m2(macro)
        m = _backtest_monthly(style, w, cost=cost)
        results.append({"策略": "M2信号", **m})

    # combined: rates falling AND M2 rising → growth
    w_rates = _monthly_signal_rates(macro, "US_FED_FUNDS") if "US_FED_FUNDS" in macro.columns else pd.Series(0.5, index=idx)
    w_m2 = _monthly_signal_m2(macro) if "CN_M2_YOY" in macro.columns else pd.Series(0.5, index=idx)
    w_comb = ((w_rates > 0.5) & (w_m2 > 0.5)).astype(float)
    w_comb = w_comb.mask((w_rates < 0.5) & (w_m2 < 0.5), 0.0)
    m = _backtest_monthly(style, w_comb, cost=cost)
    results.append({"策略": "组合:利率降+M2升", **m})

    # policy events signal
    w_pol = _policy_signal(idx)
    m = _backtest_monthly(style, w_pol, cost=cost)
    results.append({"策略": "政策事件信号", **m})

    df = pd.DataFrame(results)
    df["年化"] = df["annual_return"].map(lambda x: f"{x*100:.1f}%")
    df["夏普"] = df["sharpe"].map(lambda x: f"{x:.2f}")
    df["回撤"] = df["max_drawdown"].map(lambda x: f"{x*100:.1f}%")
    df["切换"] = df["n_switches"]
    return df[["策略", "年化", "夏普", "回撤", "切换"]]


if __name__ == "__main__":
    style = load_style_monthly_returns()
    macro = load_macro_monthly()
    print(f"风格月频样本: {style.index.min().date()} ~ {style.index.max().date()} ({len(style)} 个月)")
    print(f"宏观覆盖: {macro.index.min().date()} ~ {macro.index.max().date()}\n")

    df = run_macro_rotation(cost=0.001)
    print(df.to_string(index=False))
