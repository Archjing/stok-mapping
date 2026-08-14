"""Calendar-time portfolio regression: is the forecast-direction alpha real?

The matched-pair long-short (+1.99% over T+1..T+10) could be driven by a
*calendar* effect: earnings-forecast season days (Jan/Apr/Jul/Oct) happen to
favour 预增 over 首亏 for reasons unrelated to the forecast itself.

The standard fix is a calendar-time portfolio regression (Jaffe 1974, Fama 1998):
- aggregate event returns into a DAILY portfolio: on each trading day, hold an
  equal-weight portfolio of all events still inside their holding window
- build a long-short daily return series: 预增 portfolio minus 首亏 portfolio
- regress the long-short series on market (RMRF), size (SMB), value (HML) factors
- the intercept (alpha) is the event-driven excess return net of factor exposure

Executable convention (no lookahead): buy at T+1 OPEN, sell at T+N CLOSE.

Research layer only — not admission.
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

CORPUS_DB = Path("data/ai_corpus/ai_corpus.sqlite")
MARKET_DB = Path("data/a_share_history.sqlite")
BENCHMARK = "SH.000300"


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
    df = df[df["direction"].isin(["预增", "首亏"])]
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


def _load_ohlc(conn: sqlite3.Connection, symbol: str, table: str, cols: str) -> pd.DataFrame:
    try:
        return pd.read_sql_query(
            f"SELECT date, {cols} FROM {table} WHERE symbol=? ORDER BY date",
            conn, params=(symbol,),
        )
    except sqlite3.Error:
        return pd.DataFrame()


def _stock_ohlc(conn: sqlite3.Connection, symbol: str) -> pd.DataFrame:
    try:
        return pd.read_sql_query(
            "SELECT date, open, adjusted_close AS close FROM market_daily_bars "
            "WHERE symbol=? AND adjust_type='qfq' ORDER BY date",
            conn, params=(symbol,),
        )
    except sqlite3.Error:
        return pd.DataFrame()


def _benchmark_ohlc(conn: sqlite3.Connection) -> pd.DataFrame:
    return _load_ohlc(conn, BENCHMARK, "market_index_bars", "date, close")


def _calendar(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT DISTINCT date FROM market_daily_bars ORDER BY date").fetchall()
    return [r[0] for r in rows]


def _market_cap(conn: sqlite3.Connection, symbol: str, date: str) -> float:
    row = conn.execute(
        "SELECT market_cap FROM market_daily_basic WHERE symbol=? AND date<=? ORDER BY date DESC LIMIT 1",
        (symbol, date),
    ).fetchone()
    return float(row[0]) if row and row[0] else float("nan")


def _build_event_windows(events: pd.DataFrame, calendar: list[str], horizon: int) -> pd.DataFrame:
    """Return per-event holding windows: symbol, buy_date(T+1), sell_date(T+N), direction."""
    date_idx = {d: i for i, d in enumerate(calendar)}
    rows = []
    for _, ev in events.iterrows():
        event_day = map_event_to_trading_day(pd.DataFrame({"date": calendar}), str(ev["published_at"]))
        if event_day is None or event_day not in date_idx:
            continue
        t = date_idx[event_day]
        buy_i = t + 1  # T+1 open
        sell_i = t + horizon  # T+N close
        if sell_i >= len(calendar) or buy_i >= len(calendar):
            continue
        rows.append({
            "symbol": ev["symbol"],
            "direction": ev["direction"],
            "buy_date": calendar[buy_i],
            "sell_date": calendar[sell_i],
        })
    return pd.DataFrame(rows)


def _holding_returns(windows: pd.DataFrame, conn: sqlite3.Connection, horizon: int) -> pd.DataFrame:
    """Compute per-event holding return (T+1 open → T+N close) and daily calendar exposure."""
    records = []
    for _, w in windows.iterrows():
        px = _stock_ohlc(conn, w["symbol"])
        if px.empty:
            continue
        buy = px[px["date"] == w["buy_date"]]
        sell = px[px["date"] == w["sell_date"]]
        if buy.empty or sell.empty:
            continue
        open_px = float(buy["open"].iloc[0])
        close_px = float(sell["close"].iloc[0])
        if open_px <= 0 or close_px <= 0:
            continue
        ret = close_px / open_px - 1.0
        records.append({
            "symbol": w["symbol"],
            "direction": w["direction"],
            "buy_date": w["buy_date"],
            "sell_date": w["sell_date"],
            "ret": ret,
        })
    return pd.DataFrame(records)


def _build_daily_portfolio(holdings: pd.DataFrame, calendar: list[str]) -> pd.DataFrame:
    """Build a daily equal-weight long-short return series.

    Each trading day d, the portfolio is long all 预增 events with buy_date <= d <= sell_date,
    short all 首亏 events in window.  Daily return = mean(long rets) - mean(short rets).
    The per-event return is spread over its holding days (1/horizon per day, geometric).
    """
    if holdings.empty:
        return pd.DataFrame()
    n = len(calendar)
    long_w = np.zeros(n)
    short_w = np.zeros(n)
    long_r = np.zeros(n)
    short_r = np.zeros(n)
    date_idx = {d: i for i, d in enumerate(calendar)}
    horizon = 0
    for _, h in holdings.iterrows():
        b = date_idx.get(h["buy_date"])
        s = date_idx.get(h["sell_date"])
        if b is None or s is None:
            continue
        # per-day geometric return over holding window
        days = s - b + 1
        horizon = max(horizon, days)
        daily = (1.0 + h["ret"]) ** (1.0 / days) - 1.0
        if h["direction"] == "预增":
            long_w[b : s + 1] += 1.0
            long_r[b : s + 1] += daily
        else:
            short_w[b : s + 1] += 1.0
            short_r[b : s + 1] += daily
    long_ret = np.divide(long_r, long_w, out=np.zeros_like(long_r), where=long_w > 0)
    short_ret = np.divide(short_r, short_w, out=np.zeros_like(short_r), where=short_w > 0)
    # market-neutral: only count days where BOTH legs are present, so the spread
    # is beta-neutral by construction (long 预增 minus short 首亏 on the same day)
    both = (long_w > 0) & (short_w > 0)
    ls = np.where(both, long_ret - short_ret, np.nan)
    return pd.DataFrame({"date": calendar, "long_short": ls, "both_legs": both})


def _load_benchmark_daily(conn: sqlite3.Connection, calendar: list[str]) -> pd.Series:
    b = _benchmark_ohlc(conn)
    if b.empty:
        return pd.Series(dtype=float)
    b = b.set_index("date")["close"].astype(float)
    ret = b.pct_change().fillna(0.0)
    return ret.reindex(calendar).fillna(0.0)


def _build_size_factor(conn: sqlite3.Connection, holdings: pd.DataFrame, calendar: list[str]) -> pd.Series:
    """Size factor SMB = mean return of small-cap holdings - large-cap holdings (per day)."""
    # approximation: for the universe of event stocks, split by median market cap each day
    rows = []
    for _, h in holdings.iterrows():
        mc = _market_cap(conn, h["symbol"], h["buy_date"])
        rows.append({"symbol": h["symbol"], "date": h["buy_date"], "ret": h["ret"], "mcap": mc})
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rows)
    df = df.dropna(subset=["mcap"])
    daily = {}
    for date, grp in df.groupby("date"):
        if len(grp) < 4:
            continue
        median = grp["mcap"].median()
        small = grp[grp["mcap"] <= median]["ret"].mean()
        large = grp[grp["mcap"] > median]["ret"].mean()
        daily[date] = small - large
    return pd.Series(daily).reindex(calendar).fillna(0.0)


@dataclass
class CalendarTimeResult:
    n_events: int
    ls_mean_daily: float
    ls_annualized: float
    ls_sharpe: float
    alpha_ff1: float
    alpha_t: float
    alpha_p: float
    beta_mkt: float
    correlation_with_calendar: float


def run_calendar_time(
    *,
    horizon: int = 10,
    corpus_db: Path = CORPUS_DB,
    market_db: Path = MARKET_DB,
) -> CalendarTimeResult:
    events = _load_forecast_events(corpus_db)
    conn = sqlite3.connect(market_db)
    calendar = _calendar(conn)
    windows = _build_event_windows(events, calendar, horizon)
    holdings = _holding_returns(windows, conn, horizon)
    daily_ls = _build_daily_portfolio(holdings, calendar)
    bench = _load_benchmark_daily(conn, calendar)
    size = _build_size_factor(conn, holdings, calendar)
    conn.close()

    if daily_ls.empty:
        raise ValueError("no calendar-time portfolio built")

    merged = pd.DataFrame({
        "ls": daily_ls["long_short"],
        "mkt": bench,
        "smb": size,
    })
    merged = merged.dropna(subset=["ls"])  # keep only both-leg days
    merged = merged.replace([np.inf, -np.inf], np.nan).dropna(subset=["ls", "mkt"])

    # FF1 regression (market only) — cleanest alpha estimate, via explicit OLS
    y = merged["ls"].values.astype(float)
    mkt = merged["mkt"].values.astype(float)
    X = np.column_stack([np.ones(len(merged)), mkt])
    beta = np.linalg.pinv(X) @ y  # pinv handles rank-deficiency/NaN-free
    alpha_ff1, beta_mkt = beta[0], beta[1]
    resid = y - X @ beta
    n = len(merged)
    # t-stat of alpha (daily), using OLS standard error
    dof = n - 2
    sigma2 = float((resid @ resid) / dof) if dof > 0 else float("nan")
    XtX_inv = np.linalg.pinv(X.T @ X)
    se_alpha = np.sqrt(sigma2 * XtX_inv[0, 0]) if np.isfinite(sigma2) else float("nan")
    alpha_t = alpha_ff1 / se_alpha if se_alpha and np.isfinite(se_alpha) and se_alpha > 0 else float("nan")
    alpha_p = float(1.0 - __import__("math").erf(abs(alpha_t) / __import__("math").sqrt(2.0))) if np.isfinite(alpha_t) else float("nan")

    ls_mean_daily = float(merged["ls"].mean())
    ls_annualized = (1.0 + ls_mean_daily) ** 252 - 1.0
    ls_sharpe = float(merged["ls"].mean() / merged["ls"].std() * np.sqrt(252)) if merged["ls"].std() > 0 else float("nan")

    # correlation of long-short returns with calendar quarter indicator (seasonality probe)
    merged["month"] = pd.to_datetime(merged.index).month
    merged["season"] = merged["month"].isin([1, 4, 7, 10]).astype(float)
    corr_cal = float(merged["ls"].corr(merged["season"])) if len(merged) > 2 else float("nan")

    return CalendarTimeResult(
        n_events=int(len(holdings)),
        ls_mean_daily=ls_mean_daily,
        ls_annualized=ls_annualized,
        ls_sharpe=ls_sharpe,
        alpha_ff1=float(alpha_ff1),
        alpha_t=float(alpha_t),
        alpha_p=alpha_p,
        beta_mkt=float(beta_mkt),
        correlation_with_calendar=corr_cal,
    )


if __name__ == "__main__":
    for horizon in (5, 10):
        r = run_calendar_time(horizon=horizon)
        print(f"=== 日历时间回归 (持有 {horizon} 交易日) ===")
        print(f"事件数: {r.n_events}")
        print(f"多空日频均值: {r.ls_mean_daily*100:.4f}%/日")
        print(f"多空年化: {r.ls_annualized*100:.2f}%")
        print(f"多空夏普: {r.ls_sharpe:.2f}")
        print(f"FF1 alpha(日频): {r.alpha_ff1*100:.4f}%/日 → 年化 {(1+r.alpha_ff1)**252-1:.2%}")
        print(f"alpha t={r.alpha_t:.2f}, p={r.alpha_p:.4f}")
        print(f"beta_mkt={r.beta_mkt:.3f} (应接近 0 = 市场中性)")
        print(f"与财报季指示变量的相关性: {r.correlation_with_calendar:.3f}")
        print()
