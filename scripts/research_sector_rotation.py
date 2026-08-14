"""A-share style-rotation research: identify historical growth/value & size regime periods.

Uses the relative-strength between growth and value indices (and large/small cap)
to identify style regime periods, then measures industry dispersion within each.

Data: market_index_bars in data/a_share_history.sqlite (2015-2026, daily).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DB = Path("data/a_share_history.sqlite")

# Style indices (growth vs value, large vs small)
GROWTH_IDX = "SH.000057"   # 全指成长
VALUE_IDX = "SH.000058"    # 全指价值
LARGE_IDX = "SZ.399372"    # 大盘成长 (use 大盘成长 as large proxy)
SMALL_IDX = "SZ.399376"    # 小盘成长


def _load_index(conn: sqlite3.Connection, symbol: str) -> pd.Series:
    df = pd.read_sql_query(
        "SELECT date, close FROM market_index_bars WHERE symbol=? ORDER BY date",
        conn, params=(symbol,),
    )
    if df.empty:
        return pd.Series(dtype=float)
    return pd.Series(df["close"].astype(float).values, index=pd.to_datetime(df["date"]))


def _cumulative_return(px: pd.Series) -> pd.Series:
    return px / px.iloc[0] - 1.0


def _relative_strength(growth: pd.Series, value: pd.Series) -> pd.Series:
    """Growth/value relative strength (cumulative log ratio)."""
    idx = growth.index.intersection(value.index)
    g = growth.loc[idx]
    v = value.loc[idx]
    return np.log(g / v)  # >0 means growth outperforming


def identify_style_regimes(
    *,
    growth_symbol: str = GROWTH_IDX,
    value_symbol: str = VALUE_IDX,
    min_regime_days: int = 120,
) -> pd.DataFrame:
    """Identify growth/value style regimes from half-year relative-strength sign.

    Uses half-year (6-month) growth-minus-value returns: consecutive half-years
    with the same sign are merged into one regime.  This produces the classic
    large regimes (2015H1 growth, 2015H2-2017 value, 2018 growth, 2019H2-2021H1
    growth, 2021H2-2024 value, 2026 growth rebound) without daily-noise
    fragmentation.
    """
    conn = sqlite3.connect(DB)
    growth = _load_index(conn, growth_symbol)
    value = _load_index(conn, value_symbol)
    conn.close()
    if growth.empty or value.empty:
        return pd.DataFrame()

    rs = _relative_strength(growth, value)
    rs.index = pd.to_datetime(rs.index)
    half = rs.resample("6ME").apply(lambda s: s.iloc[-1] - s.iloc[0]).dropna()

    # merge consecutive half-years with the same sign into regimes
    regimes: list[dict] = []
    current_regime = None
    current_start = None
    prev_end = None

    for dt, val in half.items():
        regime = "成长" if val > 0 else "价值"
        if current_regime is None:
            current_regime = regime
            current_start = dt - pd.offsets.MonthBegin(5)
        elif regime != current_regime:
            end = dt - pd.offsets.MonthBegin(1)
            duration = (end - current_start).days
            if duration >= min_regime_days:
                regimes.append({
                    "start": current_start.strftime("%Y-%m-%d"),
                    "end": end.strftime("%Y-%m-%d"),
                    "regime": current_regime,
                    "duration_days": duration,
                })
            current_regime = regime
            current_start = dt - pd.offsets.MonthBegin(5)
    # close last regime
    if current_regime is not None:
        end = half.index[-1]
        duration = (end - current_start).days
        if duration >= min_regime_days:
            regimes.append({
                "start": current_start.strftime("%Y-%m-%d"),
                "end": end.strftime("%Y-%m-%d"),
                "regime": current_regime,
                "duration_days": duration,
            })
    return pd.DataFrame(regimes)


def load_industry_indices() -> pd.DataFrame:
    """Load 一级行业指数 symbols + names with bars coverage."""
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query(
        """SELECT i.symbol, i.name, b.min_d, b.max_d
           FROM market_indices i
           JOIN (SELECT symbol, MIN(date) min_d, MAX(date) max_d FROM market_index_bars GROUP BY symbol) b
             ON i.symbol = b.symbol
           WHERE i.category='一级行业指数'
           ORDER BY i.symbol""",
        conn,
    )
    conn.close()
    return df


def industry_returns_in_regime(
    industry_indices: pd.DataFrame,
    regime_start: str,
    regime_end: str,
) -> pd.DataFrame:
    """Compute each industry's return (and excess vs equal-weight market) within a regime."""
    conn = sqlite3.connect(DB)
    rows = []
    for _, row in industry_indices.iterrows():
        px = _load_index(conn, row["symbol"])
        if px.empty:
            continue
        window = px.loc[regime_start:regime_end]
        if len(window) < 20:
            continue
        total = window.iloc[-1] / window.iloc[0] - 1.0
        rows.append({"symbol": row["symbol"], "name": row["name"], "return": total})
    conn.close()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # excess vs equal-weight mean across industries (proxy for market)
    df["excess"] = df["return"] - df["return"].mean()
    return df.sort_values("excess", ascending=False)


if __name__ == "__main__":
    print("=== 成长/价值风格切换区间 ===")
    regimes = identify_style_regimes()
    print(regimes.to_string(index=False))

    print("\n=== 各区间行业超额收益 TOP/BOTTOM ===")
    industries = load_industry_indices()
    print(f"行业指数数: {len(industries)}")
    for _, r in regimes.iterrows():
        print(f"\n--- {r['regime']} 区间 {r['start']} ~ {r['end']} ({r['duration_days']}天) ---")
        ret = industry_returns_in_regime(industries, r["start"], r["end"])
        if ret.empty:
            print("  (无数据)")
            continue
        print("  TOP5:")
        for _, x in ret.head(5).iterrows():
            print(f"    {x['name']}: {x['excess']*100:+.1f}%")
        print("  BOTTOM5:")
        for _, x in ret.tail(5).iterrows():
            print(f"    {x['name']}: {x['excess']*100:+.1f}%")
