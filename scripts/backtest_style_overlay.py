"""Overlay the style-rotation signal onto the SOX→semiconductor ETF mapping strategy.

Base strategy: buy 半导体ETF (512480/588200) when SOX overnight > threshold AND
VIX < threshold, hold 1 day.  Semiconductor is a growth-style asset.

Overlay: the policy-event style signal (loose→growth, tight→value) acts as a
POSITION GATE.  When the style signal says "value regime" (tight policy), we
suppress/halve the semiconductor position; when "growth regime" (loose policy),
we trade the base strategy normally.

Monthly overlay, applied at daily level: each day's base position is scaled by
the current style-regime gate (1.0 growth / 0.5 value / 0.0 if we go full gate).

Research layer only — the overlay is a hypothesis, not a configured account.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ETF_DB = Path("data/etf_history.sqlite")
EVENTS_CSV = Path("data/macro_policy_events.csv")
US_TYPES = {"rate_hike", "rate_cut", "taper", "qe"}

SOX_THRESHOLD = 0.005
VIX_THRESHOLD = 19.0


def _load_etf(symbol: str) -> pd.DataFrame:
    conn = sqlite3.connect(ETF_DB)
    df = pd.read_sql_query(
        "SELECT date, open, high, low, close FROM market_etf_daily_bars WHERE symbol=? ORDER BY date",
        conn, params=(symbol,),
    )
    conn.close()
    df["date"] = pd.to_datetime(df["date"], format="mixed", errors="coerce")
    df = df.dropna(subset=["date"])
    df["ret"] = df["close"].pct_change().fillna(0.0)
    return df.set_index("date")


def _load_sox_vix(start: str, end: str) -> pd.DataFrame:
    conn = sqlite3.connect("data/us_market_history.sqlite")
    sox = pd.read_sql_query(
        "SELECT date, adjusted_close AS close FROM us_daily_bars WHERE symbol='^SOX' ORDER BY date",
        conn,
    )
    vix = pd.read_sql_query(
        "SELECT date, close FROM us_daily_bars WHERE symbol='^VIX' ORDER BY date",
        conn,
    )
    conn.close()
    sox["date"] = pd.to_datetime(sox["date"])
    vix["date"] = pd.to_datetime(vix["date"])
    sox["sox_ret"] = sox["close"].pct_change().fillna(0.0)
    m = sox[["date", "sox_ret"]].merge(vix[["date", "close"]].rename(columns={"close": "vix"}), on="date")
    return m.set_index("date")


def _style_gate(events: pd.DataFrame, index: pd.DatetimeIndex, hold_days: int = 90) -> pd.Series:
    """Monthly policy-event style gate: 1.0 growth / 0.5 value / (0 if full gate)."""
    gate = pd.Series(0.5, index=index)  # neutral default
    us = events[events["event_type"].isin(US_TYPES)]
    for _, ev in us.iterrows():
        end = ev["date"] + pd.Timedelta(days=hold_days)
        mask = (index >= ev["date"]) & (index <= end)
        if ev["direction"] == "loose":
            gate[mask] = 1.0
        elif ev["direction"] == "tight":
            gate[mask] = 0.0  # full gate: value regime → no semiconductor
    return gate


def _metrics(daily_ret: pd.Series) -> dict:
    ann = (1 + daily_ret.mean()) ** 252 - 1
    sharpe = daily_ret.mean() / daily_ret.std() * np.sqrt(252) if daily_ret.std() > 0 else 0.0
    equity = (1 + daily_ret).cumprod()
    mdd = (equity / equity.cummax() - 1).min()
    return {"annual_return": ann, "sharpe": sharpe, "max_drawdown": mdd}


def run(symbol: str = "SH.512480", cost: float = 0.001) -> pd.DataFrame:
    etf = _load_etf(symbol)
    start, end = str(etf.index.min().date()), str(etf.index.max().date())
    sig = _load_sox_vix(start, end)

    # align: sox signal day t maps to CN trading day t+1
    sox_ret = sig["sox_ret"].reindex(etf.index, method="ffill").fillna(0.0)
    vix = sig["vix"].reindex(etf.index, method="ffill").fillna(999.0)
    base_signal = ((sox_ret > SOX_THRESHOLD) & (vix < VIX_THRESHOLD)).astype(float)

    # style gate (monthly, from US policy events)
    events = pd.read_csv(EVENTS_CSV)
    events["date"] = pd.to_datetime(events["date"])
    gate = _style_gate(events, etf.index)

    # overlay: base position × gate
    # base position is 1 on signal days, 0 otherwise (1-day hold, next-day execution)
    base_w = base_signal.shift(1).fillna(0.0)
    overlay_w = base_w * gate.shift(1).fillna(0.5)

    def _run(w: pd.Series) -> dict:
        ret = w * etf["ret"]
        turnover = w.diff().abs().fillna(w.abs())
        ret = ret - turnover * cost
        return _metrics(ret)

    rows = []
    rows.append({"name": "映射策略(无叠加)", **_run(base_w)})
    rows.append({"name": "映射策略+风格门控", **_run(overlay_w)})
    rows.append({"name": "买入持有ETF", **_run(pd.Series(1.0, index=etf.index))})

    df = pd.DataFrame(rows)
    df["年化"] = df["annual_return"].map(lambda x: f"{x*100:.1f}%")
    df["夏普"] = df["sharpe"].map(lambda x: f"{x:.2f}")
    df["回撤"] = df["max_drawdown"].map(lambda x: f"{x*100:.1f}%")
    return df[["name", "年化", "夏普", "回撤"]]


if __name__ == "__main__":
    for symbol in ["SH.512480", "SH.588200"]:
        print(f"\n=== {symbol} ===")
        print(run(symbol).to_string(index=False))
