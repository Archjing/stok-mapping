"""SOX半导体→512480 跨市场映射择时 — 完整周期回测。

固定参数、两档入场和 T+1 日内追踪止损的研究回测。

本脚本保留一个旧研究对照：弱信号全天未触及后，仍回填当天开盘成交。
只有这个回填动作属于事后情景；“开盘挂限价、触及成交、未触及收盘撤单”本身
是可执行规则，并由 phase0.execution.single_etf_intraday 提供 admission/模拟口径。

用法: .venv/bin/python3 scripts/backtest_sox_512480.py
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phase0.execution.accounts import (
    SimulatedAccountConfig,
    _affordable_buy_shares,
    _trade_cost,
)
from phase0.research.metrics import annualized_return, max_drawdown, sharpe
from phase0.strategies.cross_market_semiconductor_timing import (
    map_us_features_to_next_cn_trading_day,
)

# ── 参数 ────────────────────────────────────────────────────────────
SOX_THRESHOLD         = 0.005   # SOX 隔夜 > 0.5%
VIX_THRESHOLD         = 19.0    # VIX < 19
STRONG_SOX            = 0.01    # 强信号边界: SOX > 1.0% → 开盘追
LIMIT_DISCOUNT        = 0.01    # 弱信号限价折扣: open × 0.99
TRAIL_RATIO           = 0.98    # 追踪止损: running_high × 0.98
INITIAL_CASH          = 100_000
LOT_SIZE              = 100
SLIPPAGE              = 0.0001  # 0.01%
COMMISSION            = 0.00025 # 万分之 2.5
STAMP_DUTY            = 0.0     # ETF 免印花税
MIN_COMMISSION        = 5.0
PRICE_TICK            = 0.001

ETF_DB = Path("data/etf_history.sqlite")
US_DB  = Path("data/us_market_history.sqlite")
CN_DB  = Path("data/a_share_history.sqlite")

# ── 数据加载 ────────────────────────────────────────────────────────

def load_etf_daily():
    end = date.today()
    start = end - timedelta(days=365 * 7 + 30)
    with sqlite3.connect(ETF_DB) as conn:
        df = pd.read_sql_query(
            "SELECT date, open, high, low, close FROM market_etf_daily_bars "
            "WHERE symbol='SH.512480' AND date>=? AND date<=? ORDER BY date",
            conn, params=[start.isoformat(), end.isoformat()],
        )
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["open","close"])

def load_etf_5min(date_start, date_end):
    with sqlite3.connect(ETF_DB) as conn:
        df = pd.read_sql_query(
            "SELECT time, open, high, low, close FROM market_etf_5min_bars "
            "WHERE symbol='SH.512480' AND time>=? AND time<=? ORDER BY time",
            conn,
            params=[str(date_start), str(date_end) + " 23:59:59"],
        )
    if df.empty:
        return df
    df["time"] = pd.to_datetime(df["time"])
    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = df["time"].dt.strftime("%Y-%m-%d")
    return df.set_index("time").sort_index()

def load_us(cn_trading_dates: pd.Series | pd.DatetimeIndex):
    end = date.today()
    start = end - timedelta(days=365 * 7 + 30)
    with sqlite3.connect(US_DB) as conn:
        sox = pd.read_sql_query(
            "SELECT date, close FROM us_daily_bars WHERE symbol='^SOX' "
            "AND date>=? AND date<=? ORDER BY date",
            conn, params=[start.isoformat(), end.isoformat()],
        )
        vix = pd.read_sql_query(
            "SELECT date, close FROM us_daily_bars WHERE symbol='^VIX' "
            "AND date>=? AND date<=? ORDER BY date",
            conn, params=[start.isoformat(), end.isoformat()],
        )
    sox["date"] = pd.to_datetime(sox["date"]).dt.normalize()
    sox["sox_ret"] = pd.to_numeric(sox["close"], errors="coerce").pct_change()
    vix["date"] = pd.to_datetime(vix["date"]).dt.normalize()
    vix["vix"] = pd.to_numeric(vix["close"], errors="coerce")
    # SOX and VIX must come from the same completed US session.  The helper
    # maps it to the first actual later A-share session, including Mondays and
    # holiday-adjacent sessions rather than applying a calendar-day +1.
    merged = sox[["date","sox_ret"]].merge(vix[["date","vix"]], on="date", how="inner")
    merged = merged.dropna(subset=["sox_ret", "vix"])
    return map_us_features_to_next_cn_trading_day(merged, cn_trading_dates)

def load_hs300():
    with sqlite3.connect(CN_DB) as conn:
        return pd.read_sql_query(
            "SELECT date, close FROM market_index_bars "
            "WHERE symbol='SH.000300' ORDER BY date", conn,
        )

# ── 账户 ────────────────────────────────────────────────────────────

def account():
    return SimulatedAccountConfig(
        account_id="backtest", name="backtest",
        initial_cash=float(INITIAL_CASH),
        ledger_path="/dev/null", database_path="/dev/null",
        execution_price_mode="next_open",
        price_tick=PRICE_TICK, lot_size=LOT_SIZE,
        commission=COMMISSION, stamp_duty_sell=STAMP_DUTY,
        slippage=SLIPPAGE, min_commission=MIN_COMMISSION,
        transfer_fee_rate=0.0,
        enable_limit_check=False, enable_suspension_check=False,
        enable_t_plus_one=True, enable_special_limit_rules=False,
    )

# ── 回测 ────────────────────────────────────────────────────────────

def run(use_limit: bool) -> dict:
    """use_limit=True → 弱信号挂限价单; False → 全部开盘追"""
    daily = load_etf_daily()
    us    = load_us(daily["date"])
    m = daily.merge(us, on="date", how="inner")
    m["date"] = pd.to_datetime(m["date"]).dt.normalize()
    m = m.sort_values("date").reset_index(drop=True)
    # 固定样本边界，保证报告可复现。
    m = m[(m["date"] >= "2021-05-13") & (m["date"] <= "2025-12-31")]

    signal = (m["sox_ret"] > SOX_THRESHOLD) & (m["vix"] < VIX_THRESHOLD)

    # 加载全量 5 分钟线
    intra = load_etf_5min(m["date"].min(), m["date"].max())

    acct = account()
    cash = float(acct.initial_cash)
    shares: float = 0.0
    state = "idle"
    sell_on_date: pd.Timestamp | None = None
    nav_log: list[float] = []
    trade_log: list[dict] = []

    for i in range(len(m)):
        row = m.iloc[i]
        dt = row["date"]
        exited_today = False

        # ── 卖出 ──
        if state == "holding" and sell_on_date is not None and dt >= sell_on_date:
            # 入场时已锁定 T+1 的实际 A 股交易日；后续信号不能延长持仓。
            day_bars = intra[intra["date"] == dt.strftime("%Y-%m-%d")]
            exit_px = float(row["close"])
            if not day_bars.empty and len(day_bars) > 0:
                rh = float(day_bars.iloc[0]["open"])
                triggered = False
                for _, bar in day_bars.iterrows():
                    if float(bar["high"]) > rh:
                        rh = float(bar["high"])
                    if float(bar["low"]) <= rh * TRAIL_RATIO:
                        exit_px = rh * TRAIL_RATIO
                        triggered = True
                        break
                if not triggered:
                    exit_px = float(day_bars.iloc[-1]["close"])
            gross = shares * exit_px
            cost = _trade_cost(float(gross), "sell", acct)
            cash += gross - cost
            trade_log[-1]["exit_price"] = exit_px
            trade_log[-1]["exit_date"] = str(dt.date())
            trade_log[-1]["gross_ret"] = float(gross - cost) / trade_log[-1]["cost"] - 1
            shares = 0.0
            state = "idle"
            sell_on_date = None
            exited_today = True

        # ── 买入 ──
        # T+1 的退出发生在 14:55 附近，不能回填成同日 09:30 的新开仓。
        if state == "idle" and not exited_today and signal.iloc[i] and i + 1 < len(m):
            sox_val = float(row["sox_ret"])
            is_strong = sox_val > STRONG_SOX

            if is_strong or not use_limit:
                buy_px = float(row["open"])
            else:
                limit_px = float(row["open"]) * (1.0 - LIMIT_DISCOUNT)
                day_bars = intra[intra["date"] == dt.strftime("%Y-%m-%d")]
                if not day_bars.empty and float(day_bars["low"].min()) <= limit_px:
                    buy_px = limit_px
                else:
                    buy_px = float(row["open"])

            max_s = _affordable_buy_shares(
                cash_asset=cash, price=buy_px,
                requested_shares=1e9, account=acct,
            )
            if max_s > 0:
                gross = max_s * buy_px
                cost = _trade_cost(float(gross), "buy", acct)
                cash -= gross + cost
                shares = max_s
                state = "holding"
                sell_on_date = m.iloc[i + 1]["date"]
                trade_log.append({
                    "entry_date": str(dt.date()),
                    "entry_price": buy_px,
                    "shares": max_s,
                    "cost": gross + cost,
                    "sox_ret": sox_val,
                    "vix": float(row["vix"]),
                    "entry_type": "market" if is_strong else "limit",
                })

        nav = cash + shares * float(row["close"])
        nav_log.append(nav)

    # 如果末尾仍持仓, 按最后收盘价平仓
    if shares > 0:
        nav_log[-1] = cash + shares * float(m.iloc[-1]["close"])

    eq = np.array(nav_log)
    daily_ret = eq[1:] / eq[:-1] - 1.0

    return {
        "total_ret": eq[-1] / INITIAL_CASH - 1,
        "ann_ret": annualized_return(pd.Series(daily_ret)),
        "sharpe": sharpe(pd.Series(daily_ret)),
        "mdd": max_drawdown(pd.Series(daily_ret)),
        "trades": len(trade_log),
        "signals": int(signal.sum()),
        "final_eq": eq[-1],
        "trade_log": trade_log,
        "dates": m["date"],
        "nav": eq,
        "daily_ret": daily_ret,
    }

# ── 主程序 ──────────────────────────────────────────────────────────

def main():
    print("加载数据...")
    daily = load_etf_daily()
    us    = load_us(daily["date"])
    m = daily.merge(us, on="date", how="inner")
    m = m[(m["date"] >= "2021-05-13") & (m["date"] <= "2025-12-31")]
    m["date"] = pd.to_datetime(m["date"]).dt.normalize()

    signal = (m["sox_ret"] > SOX_THRESHOLD) & (m["vix"] < VIX_THRESHOLD)
    sig_count = signal.sum()

    print(f"\n数据: {len(m)} 天, {m['date'].min().date()} ~ {m['date'].max().date()}")
    print(f"信号: {sig_count} 次 ({sig_count/len(m):.1%}), ~{sig_count/(len(m)/252):.0f} 次/年")
    print(f"参数: SOX>{SOX_THRESHOLD:.1%} VIX<{VIX_THRESHOLD:.0f} "
          f"强信号>{STRONG_SOX:.1%} 限价折{LIMIT_DISCOUNT:.0%} 止损{TRAIL_RATIO:.0%}")

    print(f"\n{'='*65}")
    print(f"{'策略':<24} {'总收益':>10} {'年化':>10} {'夏普':>7} {'回撤':>9} {'交易':>6}")
    print("-"*65)

    # 开盘买入
    r_market = run(use_limit=False)
    print(f"{'开盘买入':<24} {r_market['total_ret']:>+9.1%} {r_market['ann_ret']:>+9.1%} "
          f"{r_market['sharpe']:>7.2f} {r_market['mdd']:>8.1%} {r_market['trades']:>6}")

    # 限价买入
    r_limit = run(use_limit=True)
    print(f"{'限价买入(弱信号挂单)':<24} {r_limit['total_ret']:>+9.1%} {r_limit['ann_ret']:>+9.1%} "
          f"{r_limit['sharpe']:>7.2f} {r_limit['mdd']:>8.1%} {r_limit['trades']:>6}")

    # 对标
    hs = load_hs300()
    hs["date"] = pd.to_datetime(hs["date"]).dt.normalize()
    hs = hs[(hs["date"] >= m["date"].min()) & (hs["date"] <= m["date"].max())]
    hs_ret = float(hs["close"].iloc[-1]) / float(hs["close"].iloc[0]) - 1
    hs_daily = hs.set_index("date")["close"].pct_change().dropna()
    hs_ann = annualized_return(hs_daily)
    hs_sh = sharpe(hs_daily)
    hs_mdd = max_drawdown(hs_daily)

    bh_daily = m["close"].pct_change().dropna()
    bh_ret = float(m["close"].iloc[-1]) / float(m["close"].iloc[0]) - 1
    bh_ann = annualized_return(bh_daily)
    bh_sh = sharpe(bh_daily)
    bh_mdd = max_drawdown(bh_daily)

    print(f"{'512480 buy&hold':<24} {bh_ret:>+9.1%} {bh_ann:>+9.1%} "
          f"{bh_sh:>7.2f} {bh_mdd:>8.1%} {'-':>6}")
    print(f"{'沪深300':<24} {hs_ret:>+9.1%} {hs_ann:>+9.1%} "
          f"{hs_sh:>7.2f} {hs_mdd:>8.1%} {'-':>6}")

    # ── 限价买入详细 ──
    print(f"\n── 限价买入 交易明细 (前10笔) ──")
    for i, t in enumerate(r_limit["trade_log"][:10]):
        gr = t.get("gross_ret", 0) or 0
        print(f"  {t['entry_date']} {t['entry_type']:6s} "
              f"¥{t['entry_price']:.3f} × {int(t['shares']):,}股 "
              f"SOX={t['sox_ret']:+.2%} VIX={t['vix']:.0f} "
              f"→ {t.get('exit_date','?'):10s} 收益={gr:+.2%}")

    # ── 年度 ──
    print(f"\n── 年度收益 ──")
    print(f"{'年份':<6} {'信号':>5} {'开盘买':>9} {'限价买':>9} {'BH':>9} {'HS300':>9}")
    for yr in range(2021, 2026):
        ym = m[m["date"].dt.year == yr]
        if len(ym) < 5:
            continue
        ysig = signal[ym.index[0]:ym.index[-1]+1].sum()
        ybh = float(ym["close"].iloc[-1]) / float(ym["close"].iloc[0]) - 1 if len(ym) > 1 else 0
        # 从 daily_ret 切片
        idx0 = list(m["date"]).index(ym["date"].iloc[0])
        idx1 = list(m["date"]).index(ym["date"].iloc[-1])
        y_mkt = (1 + pd.Series(r_market["daily_ret"][idx0:idx1])).prod() - 1
        y_lim = (1 + pd.Series(r_limit["daily_ret"][idx0:idx1])).prod() - 1
        yhs = float(hs[hs["date"].dt.year == yr]["close"].iloc[-1]) / float(hs[hs["date"].dt.year == yr]["close"].iloc[0]) - 1 if len(hs[hs["date"].dt.year == yr]) > 1 else 0
        print(f"{yr:<6} {int(ysig):>5} {y_mkt:>+8.1%} {y_lim:>+8.1%} {ybh:>+8.1%} {yhs:>+8.1%}")

    # ── 强弱信号分析 ──
    print(f"\n── 信号分布 ──")
    sig_df = m[signal].copy()
    strong = (sig_df["sox_ret"] > STRONG_SOX).sum()
    weak = sig_count - strong
    print(f"强信号(SOX>{STRONG_SOX:.0%}): {strong} 次")
    print(f"弱信号(SOX {SOX_THRESHOLD:.1%}-{STRONG_SOX:.0%}): {weak} 次")

    # 限价单触及率
    if use_limit_analysis := True:
        intra_all = load_etf_5min(m["date"].min(), m["date"].max())
        weak_sig = sig_df[sig_df["sox_ret"] <= STRONG_SOX]
        hit = 0
        for _, row in weak_sig.iterrows():
            dt = row["date"]
            limit_px = float(row["open"]) * (1.0 - LIMIT_DISCOUNT)
            day = intra_all[intra_all["date"] == dt.strftime("%Y-%m-%d")]
            if not day.empty and float(day["low"].min()) <= limit_px:
                hit += 1
        if weak > 0:
            print(f"限价单触及率: {hit}/{weak} = {hit/weak:.0%}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
