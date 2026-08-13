"""Policy-event style rotation backtest with the full 70-event table (2015-2025).

Tests the symmetry claim: does 紧缩 (esp. US Fed hikes) reliably lead value,
and does 宽松 lead growth — now that the tight sample is 23 events (was 1).

Splits events by market (CN vs US) and direction, holds a direction bet for
N days after each event, and reports each variant's risk-adjusted performance.

Monthly rebalance, T+1, cost 0.1% per switch. Research layer only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.backtest_macro_rotation import load_style_monthly_returns

EVENTS_CSV = Path("data/macro_policy_events.csv")


def _metrics(ret: pd.Series) -> dict:
    ann = (1 + ret.mean()) ** 12 - 1
    sharpe = ret.mean() / ret.std() * np.sqrt(12) if ret.std() > 0 else 0.0
    equity = (1 + ret).cumprod()
    mdd = (equity / equity.cummax() - 1).min()
    return {"annual_return": ann, "sharpe": sharpe, "max_drawdown": mdd}


def _run(style: pd.DataFrame, w: pd.Series, cost: float = 0.001) -> dict:
    w = w.shift(1).fillna(0.5).clip(0.0, 1.0)
    ret = w * style["growth_ret"] + (1 - w) * style["value_ret"]
    turnover = w.diff().abs().fillna(0.0)
    ret = ret - turnover * cost
    m = _metrics(ret)
    m["n_switches"] = int((w.diff().abs() > 0.5).sum())
    return m


def _event_signal(
    events: pd.DataFrame,
    index: pd.DatetimeIndex,
    *,
    hold_days: int = 90,
    market: str | None = None,
    direction: str | None = None,
) -> pd.Series:
    """Hold growth (1) after loose, value (0) after tight, for hold_days.

    market/direction filter which events to act on; others leave weight neutral.
    """
    w = pd.Series(0.5, index=index)
    sub = events.copy()
    if market:
        sub = sub[sub["event_type"].isin(
            ["rate_hike", "rate_cut", "taper"] if market == "US"
            else [e for e in events["event_type"].unique() if e not in ("rate_hike", "rate_cut", "taper")]
        )]
    if direction:
        sub = sub[sub["direction"] == direction]
    for _, ev in sub.iterrows():
        end = ev["date"] + pd.Timedelta(days=hold_days)
        mask = (index >= ev["date"]) & (index <= end)
        if ev["direction"] == "loose":
            w[mask] = 1.0
        elif ev["direction"] == "tight":
            w[mask] = 0.0
    return w


def main() -> None:
    style = load_style_monthly_returns()
    start = pd.Timestamp("2015-03-01")
    style = style[style.index >= start]
    idx = style.index

    events = pd.read_csv(EVENTS_CSV)
    events["date"] = pd.to_datetime(events["date"])
    events = events[events["date"] >= start]
    print(f"事件表: {len(events)} 事件（2015-03 起）")
    print(f"  方向: {events['direction'].value_counts().to_dict()}")

    # classify market
    us_types = {"rate_hike", "rate_cut", "taper"}
    events["market"] = events["event_type"].map(lambda t: "US" if t in us_types else "CN")
    print(f"  市场: {events['market'].value_counts().to_dict()}")

    rows = []
    rows.append({"name": "持有成长", **_run(style, pd.Series(1.0, index=idx))})
    rows.append({"name": "持有价值", **_run(style, pd.Series(0.0, index=idx))})
    rows.append({"name": "50/50", **_run(style, pd.Series(0.5, index=idx))})

    # full table, all directions
    rows.append({"name": "全部事件(宽松成长/紧缩价值)", **_run(style, _event_signal(events, idx))})

    # US only
    rows.append({"name": "仅美国事件", **_run(style, _event_signal(events, idx, market="US"))})
    rows.append({"name": "仅美国紧缩(加息→价值)", **_run(style, _event_signal(events, idx, market="US", direction="tight"))})
    rows.append({"name": "仅美国宽松(降息→成长)", **_run(style, _event_signal(events, idx, market="US", direction="loose"))})

    # CN only
    rows.append({"name": "仅中国事件", **_run(style, _event_signal(events, idx, market="CN"))})
    rows.append({"name": "仅中国紧缩→价值", **_run(style, _event_signal(events, idx, market="CN", direction="tight"))})
    rows.append({"name": "仅中国宽松→成长", **_run(style, _event_signal(events, idx, market="CN", direction="loose"))})

    # key symmetry test: US tight vs US loose
    rows.append({"name": "美国紧缩vs宽松(净)", **_run(style, _event_signal(events, idx, market="US"))})

    df = pd.DataFrame(rows)
    df["年化"] = df["annual_return"].map(lambda x: f"{x*100:.1f}%")
    df["夏普"] = df["sharpe"].map(lambda x: f"{x:.2f}")
    df["回撤"] = df["max_drawdown"].map(lambda x: f"{x*100:.1f}%")
    df["切换"] = df["n_switches"]
    print("\n" + df[["name", "年化", "夏普", "回撤", "切换"]].to_string(index=False))


if __name__ == "__main__":
    main()
