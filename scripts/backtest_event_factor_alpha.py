"""Event-factor alpha backtest: does forecast direction predict holding-period alpha?

The event study showed a direction gradient in the [-1,+1] event window. This
script asks the *alpha* question at HIGH frequency: does that gradient persist
over short holding periods (T+1..T+5, T+1..T+10) after the event?  And does a
long-预增 / short-首亏 portfolio earn positive alpha?

Method (honest, no lookahead, market-neutral):
- event day T = first trading day strictly after the announcement
- holding returns measured T+1 .. T+N (qfq close-to-close)
- LONG/SHORT: events are paired by event_day; each day with both 预增 and 首亏
  forms a matched pair, so the long-short spread is market-beta-neutral by
  construction.  This is the clean alpha measure — NOT raw excess vs CSI300
  (which is contaminated by style exposure of the forecast-issuing universe).

Research layer only — this does NOT go through the strategy admission gate.
"""
from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quant.research.event_study.abnormal_returns import map_event_to_trading_day

BENCHMARK = "SH.000300"
CORPUS_DB = Path("data/ai_corpus/ai_corpus.sqlite")
MARKET_DB = Path("data/a_share_history.sqlite")


def _load_forecast_events(corpus_db: Path) -> pd.DataFrame:
    conn = sqlite3.connect(corpus_db)
    df = pd.read_sql_query(
        """SELECT document_id, symbols, published_at, topics
           FROM ai_corpus_documents
           WHERE provider='cninfo' AND event_type='earnings_forecast'""",
        conn,
    )
    conn.close()
    df["direction"] = df["topics"].str.extract(r"direction=([^|]+)")
    df = df[df["direction"].notna()]
    df["symbol"] = df["symbols"].apply(_norm)
    return df[df["symbol"].notna()]


def _norm(code: str) -> str | None:
    code = str(code).strip()
    if code.startswith(("SH.", "SZ.")):
        return code
    if len(code) == 6 and code.isdigit():
        if code.startswith(("60", "68", "90")):
            return f"SH.{code}"
        if code.startswith(("00", "30")):
            return f"SZ.{code}"
    return None


def _load_close(conn: sqlite3.Connection, symbol: str, table: str, price_col: str) -> pd.Series:
    try:
        df = pd.read_sql_query(
            f"SELECT date, {price_col} AS px FROM {table} WHERE symbol=? ORDER BY date",
            conn, params=(symbol,),
        )
    except sqlite3.Error:
        return pd.Series(dtype=float)
    if df.empty:
        return pd.Series(dtype=float)
    return pd.Series(df["px"].astype(float).values, index=df["date"].values)


def _stock_close(conn: sqlite3.Connection, symbol: str) -> pd.Series:
    try:
        df = pd.read_sql_query(
            "SELECT date, adjusted_close AS px FROM market_daily_bars "
            "WHERE symbol=? AND adjust_type='qfq' ORDER BY date",
            conn, params=(symbol,),
        )
    except sqlite3.Error:
        return pd.Series(dtype=float)
    if df.empty:
        return pd.Series(dtype=float)
    return pd.Series(df["px"].astype(float).values, index=df["date"].values)


def _calendar(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT DISTINCT date FROM market_daily_bars ORDER BY date", conn
    )


def _event_forward_return(
    stock_px: pd.Series,
    bench_px: pd.Series,
    calendar: pd.DataFrame,
    event_day: str,
    horizon: int,
) -> float | None:
    """Excess return of stock vs benchmark from T+1 to T+horizon (close-to-close)."""
    all_dates = list(stock_px.index)
    try:
        t = all_dates.index(event_day)
    except ValueError:
        return None
    # T+1 .. T+horizon
    start_idx = t + 1
    end_idx = t + horizon
    if end_idx >= len(all_dates) or start_idx >= len(all_dates):
        return None
    s0 = stock_px.iloc[start_idx - 1]  # close at T (base for T+1 return)
    s1 = stock_px.iloc[end_idx]
    if s0 <= 0 or s1 <= 0:
        return None
    stock_ret = s1 / s0 - 1.0
    # benchmark same window (on its own date axis, align by date labels)
    d_start = all_dates[start_idx - 1]
    d_end = all_dates[end_idx]
    b_dates = list(bench_px.index)
    if d_start not in b_dates or d_end not in b_dates:
        return None
    b0 = bench_px.loc[d_start]
    b1 = bench_px.loc[d_end]
    if b0 <= 0 or b1 <= 0:
        return None
    bench_ret = b1 / b0 - 1.0
    return stock_ret - bench_ret


def _cross_sectional_test(series: pd.Series) -> dict[str, float | int]:
    import math

    s = series.dropna()
    n = int(len(s))
    if n < 2:
        return {"n": n, "mean": float("nan"), "t": float("nan"), "p": float("nan")}
    mean = float(s.mean())
    std = float(s.std(ddof=1))
    if std == 0:
        return {"n": n, "mean": mean, "t": float("nan"), "p": float("nan")}
    t = mean / (std / math.sqrt(n))
    p = float(1.0 - math.erf(abs(t) / math.sqrt(2.0)))
    return {"n": n, "mean": mean, "t": float(t), "p": p}


@dataclass
class EventAlphaResult:
    holding_table: pd.DataFrame  # direction × horizon → mean excess, t, p
    long_short: pd.DataFrame     # horizon → long-short mean, t, p


def run_event_alpha_backtest(
    *,
    corpus_db: Path = CORPUS_DB,
    market_db: Path = MARKET_DB,
    horizons: tuple[int, ...] = (5, 10),
) -> EventAlphaResult:
    events = _load_forecast_events(corpus_db)
    conn = sqlite3.connect(market_db)
    calendar = _calendar(conn)
    bench_px = _load_close(conn, BENCHMARK, "market_index_bars", "close")

    rows: list[dict[str, Any]] = []
    for _, ev in events.iterrows():
        event_day = map_event_to_trading_day(calendar, str(ev["published_at"]))
        if event_day is None:
            continue
        stock_px = _stock_close(conn, ev["symbol"])
        if len(stock_px) < 100:
            continue
        for horizon in horizons:
            excess = _event_forward_return(stock_px, bench_px, calendar, event_day, horizon)
            rows.append({
                "direction": ev["direction"],
                "symbol": ev["symbol"],
                "event_day": event_day,
                "horizon": horizon,
                "excess": excess,
            })
    conn.close()

    frame = pd.DataFrame(rows)

    # per direction × horizon (excess vs CSI300, for reference only)
    holding_rows = []
    for direction in ["预增", "扭亏", "预减", "首亏"]:
        sub = frame[frame["direction"] == direction]
        for horizon in horizons:
            h = sub[sub["horizon"] == horizon]["excess"]
            stats = _cross_sectional_test(h)
            holding_rows.append({"direction": direction, "horizon": horizon, **stats})
    holding_table = pd.DataFrame(holding_rows)

    # market-neutral long-short: 预增 minus 首亏, PAIRED BY EVENT DAY.
    # Each event_day with >=1 预增 and >=1 首亏 forms one pair = mean(预增) - mean(首亏).
    # This removes the market beta on that day by construction.
    ls_rows = []
    for horizon in horizons:
        up = frame[(frame["direction"] == "预增") & (frame["horizon"] == horizon)]
        down = frame[(frame["direction"] == "首亏") & (frame["horizon"] == horizon)]
        up_grp = up.groupby("event_day")["excess"].mean()
        down_grp = down.groupby("event_day")["excess"].mean()
        common_days = up_grp.index.intersection(down_grp.index)
        spread = (up_grp.loc[common_days] - down_grp.loc[common_days]).dropna()
        stats = _cross_sectional_test(spread)
        ls_rows.append({
            "horizon": horizon,
            "n_pairs": len(spread),
            "n_up": len(up), "n_down": len(down),
            "long_short_mean": stats["mean"],
            "t": stats["t"],
            "p": stats["p"],
        })
    long_short = pd.DataFrame(ls_rows)
    return EventAlphaResult(holding_table=holding_table, long_short=long_short)


if __name__ == "__main__":
    result = run_event_alpha_backtest()
    print("=== 持有期超额收益（相对沪深300，事件后 T+1..T+N）— 参考，受风格暴露污染 ===")
    print(result.holding_table.pivot(index="direction", columns="horizon", values="mean").round(4).to_string())
    print()
    print("=== 市场中性多空组合（预增 - 首亏，按事件日配对）===")
    print(result.long_short.to_string(index=False))

