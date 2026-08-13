"""Full-sample (2005-2026) policy-event style rotation backtest.

Extends backtest_policy_events_full.py to the full 2005-2026 sample now that:
- policy events cover 2005-2025 (105 events, CN+US)
- 5 core indices are backfilled to 2005

Monthly rebalance, T+1 execution, 0.1% cost per switch. Research layer only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.backtest_macro_rotation import load_style_monthly_returns

EVENTS_CSV = Path("data/macro_policy_events.csv")
US_TYPES = {"rate_hike", "rate_cut", "taper", "qe"}


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
    w = pd.Series(0.5, index=index)
    sub = events.copy()
    if market == "US":
        sub = sub[sub["event_type"].isin(US_TYPES)]
    elif market == "CN":
        sub = sub[~sub["event_type"].isin(US_TYPES)]
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
    # full sample from 2005
    start = pd.Timestamp("2005-01-01")
    style = style[style.index >= start]
    idx = style.index

    events = pd.read_csv(EVENTS_CSV)
    events["date"] = pd.to_datetime(events["date"])
    events["market"] = events["event_type"].map(lambda t: "US" if t in US_TYPES else "CN")
    print(f"样本: {idx.min().date()} ~ {idx.max().date()} ({len(idx)} 月)")
    print(f"事件表: {len(events)} 事件")
    print(f"  市场: {events['market'].value_counts().to_dict()}")
    print(f"  方向: {events['direction'].value_counts().to_dict()}\n")

    rows = []
    rows.append({"name": "持有成长", **_run(style, pd.Series(1.0, index=idx))})
    rows.append({"name": "持有价值", **_run(style, pd.Series(0.0, index=idx))})
    rows.append({"name": "50/50", **_run(style, pd.Series(0.5, index=idx))})

    # full policy-event signals
    rows.append({"name": "全部事件(宽松成长/紧缩价值)", **_run(style, _event_signal(events, idx))})
    rows.append({"name": "仅美国事件", **_run(style, _event_signal(events, idx, market="US"))})
    rows.append({"name": "仅中国事件", **_run(style, _event_signal(events, idx, market="CN"))})
    rows.append({"name": "美国紧缩→价值", **_run(style, _event_signal(events, idx, market="US", direction="tight"))})
    rows.append({"name": "美国宽松→成长", **_run(style, _event_signal(events, idx, market="US", direction="loose"))})
    rows.append({"name": "中国紧缩→价值", **_run(style, _event_signal(events, idx, market="CN", direction="tight"))})
    rows.append({"name": "中国宽松→成长", **_run(style, _event_signal(events, idx, market="CN", direction="loose"))})

    df = pd.DataFrame(rows)
    df["年化"] = df["annual_return"].map(lambda x: f"{x*100:.1f}%")
    df["夏普"] = df["sharpe"].map(lambda x: f"{x:.2f}")
    df["回撤"] = df["max_drawdown"].map(lambda x: f"{x*100:.1f}%")
    df["切换"] = df["n_switches"]
    print(df[["name", "年化", "夏普", "回撤", "切换"]].to_string(index=False))


if __name__ == "__main__":
    main()
