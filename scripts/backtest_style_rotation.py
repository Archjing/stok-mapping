"""Pure-price style-rotation backtest (plan A): growth vs value, 2005-2026.

Signals tested (all on the growth/value relative-strength RS = log(G/V)):
- momentum: hold growth when RS above its N-day MA, value otherwise
- mean_reversion: hold the side that underperformed over the lookback
- long_short_momentum: short-RS-MA vs long-RS-MA crossover

Baselines: always-growth, always-value, 50/50.

Execution: switch at next-day open (T+1), daily rebalance between the two
indices, cost = slippage + commission per switch. Research layer only.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DB = Path("data/a_share_history.sqlite")
GROWTH = "SH.000057"
VALUE = "SH.000058"


def _load_index(conn: sqlite3.Connection, symbol: str) -> pd.Series:
    df = pd.read_sql_query(
        "SELECT date, close FROM market_index_bars WHERE symbol=? ORDER BY date",
        conn, params=(symbol,),
    )
    if df.empty:
        return pd.Series(dtype=float)
    return pd.Series(df["close"].astype(float).values, index=pd.to_datetime(df["date"]))


def load_style_prices() -> tuple[pd.Series, pd.Series]:
    conn = sqlite3.connect(DB)
    g = _load_index(conn, GROWTH)
    v = _load_index(conn, VALUE)
    conn.close()
    idx = g.index.intersection(v.index)
    return g.loc[idx], v.loc[idx]


def _daily_returns(px: pd.Series) -> pd.Series:
    return px.pct_change().fillna(0.0)


@dataclass
class BacktestResult:
    name: str
    annual_return: float
    sharpe: float
    max_drawdown: float
    n_switches: int
    returns: pd.Series


def _metrics(ret: pd.Series) -> dict:
    ann = (1 + ret.mean()) ** 252 - 1
    sharpe = ret.mean() / ret.std() * np.sqrt(252) if ret.std() > 0 else 0.0
    equity = (1 + ret).cumprod()
    mdd = (equity / equity.cummax() - 1).min()
    return {"annual_return": ann, "sharpe": sharpe, "max_drawdown": mdd}


def _run_signal(g_ret: pd.Series, v_ret: pd.Series, weight_growth: pd.Series, *, cost: float) -> BacktestResult:
    """weight_growth: 0..1 fraction held in growth each day (pre-shift)."""
    # shift by 1 day (T+1 execution): today's signal → tomorrow's position
    w = weight_growth.shift(1).fillna(0.5).clip(0.0, 1.0)
    ret = w * g_ret + (1 - w) * v_ret
    # switch cost: |w_t - w_{t-1}| * cost
    turnover = w.diff().abs().fillna(0.0)
    ret = ret - turnover * cost
    m = _metrics(ret)
    n_switches = int((w.diff().abs() > 0.5).sum())
    return BacktestResult("", m["annual_return"], m["sharpe"], m["max_drawdown"], n_switches, ret)


def backtest_style_rotation(cost: float = 0.001) -> pd.DataFrame:
    g, v = load_style_prices()
    g_ret = _daily_returns(g)
    v_ret = _daily_returns(v)
    rs = np.log(g / v)  # growth/value relative strength

    results = []

    # baselines
    for name, w in [("持有成长", pd.Series(1.0, index=rs.index)),
                    ("持有价值", pd.Series(0.0, index=rs.index)),
                    ("50/50", pd.Series(0.5, index=rs.index))]:
        r = _run_signal(g_ret, v_ret, w, cost=cost)
        r.name = name
        results.append(r)

    # momentum: hold growth when RS > MA(N)
    for n in [20, 60, 120]:
        ma = rs.rolling(n).mean()
        w = (rs > ma).astype(float)
        r = _run_signal(g_ret, v_ret, w, cost=cost)
        r.name = f"动量 RS>MA{n}"
        results.append(r)

    # mean reversion: hold the side that underperformed over lookback
    for n in [20, 60, 120]:
        past = rs.diff(n)  # RS change over n days (positive = growth outperformed)
        w = (past < 0).astype(float)  # growth underperformed → buy growth (mean revert)
        r = _run_signal(g_ret, v_ret, w, cost=cost)
        r.name = f"均值回归 RS回撤{n}"
        results.append(r)

    # long/short momentum crossover: short MA vs long MA
    for short, long in [(20, 60), (20, 120), (60, 120)]:
        ma_s = rs.rolling(short).mean()
        ma_l = rs.rolling(long).mean()
        w = (ma_s > ma_l).astype(float)
        r = _run_signal(g_ret, v_ret, w, cost=cost)
        r.name = f"双均线 {short}/{long}"
        results.append(r)

    return pd.DataFrame([{
        "策略": r.name,
        "年化收益": f"{r.annual_return*100:.1f}%",
        "夏普": f"{r.sharpe:.2f}",
        "最大回撤": f"{r.max_drawdown*100:.1f}%",
        "切换次数": r.n_switches,
    } for r in results])


if __name__ == "__main__":
    g, v = load_style_prices()
    print(f"风格指数样本: {g.index.min().date()} ~ {g.index.max().date()} ({len(g)} 个交易日)")
    print(f"成长全程收益: {(g.iloc[-1]/g.iloc[0]-1)*100:.0f}%")
    print(f"价值全程收益: {(v.iloc[-1]/v.iloc[0]-1)*100:.0f}%")
    print()

    df = backtest_style_rotation(cost=0.001)
    print(df.to_string(index=False))
