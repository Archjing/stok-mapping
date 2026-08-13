"""Analyze whether macro policy events lead style rotation better than macro indicators alone.

Method: event study on policy announcements. For each loose-policy event
(降准/降息/LPR下调/政治局定调), measure growth-minus-value relative strength
in a window around the event. If loose policy (growth-friendly) is followed by
growth outperformance, then policy events LEAD style rotation — a signal the
slow-moving macro indicators (M2/social finance) would miss.

Then compare: policy-event timing vs macro-indicator turning points, to see
which leads the growth/value rotation more reliably.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

MARKET_DB = Path("data/a_share_history.sqlite")
MACRO_DB = Path("data/macro_history.sqlite")
EVENTS_CSV = Path("data/macro_policy_events.csv")
GROWTH_IDX = "SH.000057"
VALUE_IDX = "SH.000058"


def _load_index(conn: sqlite3.Connection, symbol: str) -> pd.Series:
    df = pd.read_sql_query(
        "SELECT date, close FROM market_index_bars WHERE symbol=? ORDER BY date",
        conn, params=(symbol,),
    )
    if df.empty:
        return pd.Series(dtype=float)
    return pd.Series(df["close"].astype(float).values, index=pd.to_datetime(df["date"]))


def load_relative_strength() -> pd.Series:
    """Growth-minus-value relative strength (daily log ratio)."""
    conn = sqlite3.connect(MARKET_DB)
    g = _load_index(conn, GROWTH_IDX)
    v = _load_index(conn, VALUE_IDX)
    conn.close()
    idx = g.index.intersection(v.index)
    return np.log(g.loc[idx] / v.loc[idx])


def load_policy_events() -> pd.DataFrame:
    df = pd.read_csv(EVENTS_CSV)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date")


def event_study_style(
    rs: pd.Series,
    events: pd.DataFrame,
    *,
    pre_days: int = 20,
    post_days: int = 60,
) -> pd.DataFrame:
    """Measure growth/value RS change around each loose-policy event.

    For each event, compute RS at event-day, then the change in RS over
    [+1..+post_days].  Positive = growth outperforms after the event.
    """
    rows = []
    for _, ev in events.iterrows():
        ed = ev["date"]
        # find nearest trading day >= event date
        future = rs.index[rs.index >= ed]
        if len(future) == 0:
            continue
        t0 = future[0]
        pos0 = rs.index.get_loc(t0)
        # RS level at event, and at +post_days
        base = rs.iloc[pos0]
        for horizon in [5, 10, 20, 40, 60]:
            end_pos = pos0 + horizon
            if end_pos >= len(rs):
                continue
            change = rs.iloc[end_pos] - base
            rows.append({
                "date": ev["date"],
                "event_type": ev["event_type"],
                "magnitude": ev["magnitude"],
                "horizon": horizon,
                "rs_change": change,
            })
    return pd.DataFrame(rows)


def macro_indicator_turning_points() -> pd.DataFrame:
    """Load M2 YoY and 10y yield, and mark their turning points (sign change of 3m diff)."""
    conn = sqlite3.connect(MACRO_DB)
    m2 = pd.read_sql_query(
        "SELECT date, value FROM macro_series WHERE symbol='CN_M2_YOY' ORDER BY date", conn
    )
    y10 = pd.read_sql_query(
        "SELECT date, value FROM macro_series WHERE symbol='CN_10Y_YIELD' ORDER BY date", conn
    )
    conn.close()
    out = {}
    for name, df in [("M2_YOY", m2), ("CN10Y", y10)]:
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df["diff"] = df["value"].diff(3)
        # turning point = sign change
        sign = np.sign(df["diff"]).fillna(0)
        turn = sign.diff().fillna(0) != 0
        df["turn"] = turn
        out[name] = df[["date", "value", "diff", "turn"]]
    return out


if __name__ == "__main__":
    rs = load_relative_strength()
    events = load_policy_events()
    print(f"成长/价值相对强弱: {len(rs)} 个交易日")
    print(f"宽松政策事件: {len(events)} 个")

    es = event_study_style(rs, events)
    print("\n=== 宽松政策公布后，成长相对价值的累计变化 ===")
    loose = es[es["date"].isin(events[events["direction"] == "loose"]["date"])]
    pivot = loose.pivot_table(index="horizon", values="rs_change", aggfunc=["mean", "count"])
    print(pivot.round(4).to_string())

    # 分时段检验对称性：2015-2017 vs 2018-2025
    print("\n=== 分时段（2015-2017 vs 2018-2025）===")
    for label, lo, hi in [("2015-2017", "2015-01-01", "2017-12-31"), ("2018-2025", "2018-01-01", "2025-12-31")]:
        sub = loose[(loose["date"] >= lo) & (loose["date"] <= hi)]
        pv = sub.pivot_table(index="horizon", values="rs_change", aggfunc="mean")
        print(f"{label}: {sub['date'].nunique()} 事件")
        print(pv.round(4).to_string())

    # 紧缩事件（2016-12 稳健中性定调）
    print("\n=== 紧缩事件（稳健中性定调）===")
    tight = es[es["date"].isin(events[events["direction"] == "tight"]["date"])]
    if not tight.empty:
        pv = tight.pivot_table(index="horizon", values="rs_change", aggfunc="mean")
        print(pv.round(4).to_string())

    # by magnitude: large vs medium (count unique events, not expanded rows)
    print("\n=== 按政策力度分（large vs medium）===")
    for mag in ["large", "medium"]:
        sub = loose[loose["magnitude"] == mag]
        n_events = sub["date"].nunique()
        pv = sub.pivot_table(index="horizon", values="rs_change", aggfunc="mean")
        print(f"{mag}: {n_events} 事件")
        print(pv.round(4).to_string())

    # baseline: average RS drift over 60 days (no event conditioning)
    rs_drift = rs.diff(60).mean()
    print(f"\n无事件条件下的 60 日 RS 平均漂移: {rs_drift:.4f}")

    print("\n=== 宏观指标拐点 ===")
    indicators = macro_indicator_turning_points()
    for name, df in indicators.items():
        n_turns = df["turn"].sum()
        print(f"{name}: {n_turns} 个拐点, 最新值 {df['value'].iloc[-1]:.2f}")
