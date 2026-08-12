"""512480 全历史回测: SOX半导体择时策略 vs 512480/沪深300 buy&hold.

从 512480 创建日 (2019-06-12) 开始。US 信号数据自 2021-05 起可用,
此前策略无信号 → 空仓(现金)。

用法: .venv/bin/python3 scripts/backtest_512480_full_history.py
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quant.config import load_config
from quant.research.metrics import annualized_return, max_drawdown, sharpe
from quant.strategies import get_strategy

ETF_DB = Path("data/etf_history.sqlite")
US_DB = Path("data/us_market_history.sqlite")
CN_DB = Path("data/a_share_history.sqlite")

# 固定参数(研究验证的最优组合)
PARAMS = {
    "sox_threshold": 0.005,
    "vix_threshold": 19.0,
    "position_size": 1.0,
    "target_symbol": "SH.512480",
    "strong_signal_threshold": 0.01,
    "limit_order_discount": 0.01,
    "trailing_stop_ratio": 0.98,
    "weak_unfilled_action": "cancel",
    "fallback_time": "14:55",
}


def load_512480_daily() -> pd.DataFrame:
    with sqlite3.connect(ETF_DB) as conn:
        df = pd.read_sql_query(
            "SELECT date, open, high, low, close FROM market_etf_daily_bars "
            "WHERE symbol='SH.512480' ORDER BY date", conn,
        )
        adj = pd.read_sql_query(
            "SELECT date, adj_factor FROM market_etf_adj_factors "
            "WHERE symbol='SH.512480' ORDER BY date", conn,
        )
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if not adj.empty:
        adj["date"] = pd.to_datetime(adj["date"]).dt.normalize()
        adj["adj_factor"] = pd.to_numeric(adj["adj_factor"], errors="coerce")
        adj = adj.dropna(subset=["adj_factor"]).drop_duplicates("date", keep="last")
        df = df.merge(adj, on="date", how="left")
    if "adj_factor" not in df.columns:
        df["adj_factor"] = 1.0
    df["adj_factor"] = df["adj_factor"].fillna(1.0)
    # 后复权价: 连续价格序列, 用于 buy&hold 基准(消除份额折算缺口)
    df["hfq_close"] = df["close"] * df["adj_factor"]
    return df.dropna(subset=["open", "close"]).sort_values("date").reset_index(drop=True)


def load_hs300_daily() -> pd.DataFrame:
    with sqlite3.connect(CN_DB) as conn:
        df = pd.read_sql_query(
            "SELECT date, close FROM market_index_bars "
            "WHERE symbol='SH.000300' ORDER BY date", conn,
        )
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df.dropna().sort_values("date").reset_index(drop=True)


def metrics(ret: pd.Series) -> dict[str, float]:
    return {
        "total": float((1 + ret).prod() - 1),
        "ann": annualized_return(ret),
        "sharpe": sharpe(ret),
        "mdd": max_drawdown(ret),
    }


def fmt(label: str, m: dict[str, float], trades: int | None = None) -> str:
    line = (
        f"{label:<28} {m['total']:>+10.1%} {m['ann']:>+10.1%} "
        f"{m['sharpe']:>7.2f} {m['mdd']:>9.1%}"
    )
    if trades is not None:
        line += f" {trades:>6}"
    return line


def build_full_panel(strategy, sc: dict) -> pd.DataFrame:
    """构建从 512480 创建日 (2019-06-12) 起的完整面板。

    与 prepare_panel 不同: 保留全部 A 股交易日(创建日至今)。
    US 信号可用前 (2021-05 之前) sox_ret=0 / vix_close=999 → 无信号空仓。
    """
    import numpy as np

    tc = dict(sc.get("cross_market_semiconductor_timing", {}))
    tc["target_symbol"] = "SH.512480"
    # 必须覆盖 512480 创建日 2019-06-12; config 的 years=7 只回溯到 2019-07 中旬
    years = max(int(tc.get("years", 7)), 8)
    as_of = date.today()

    etf = strategy._load_etf_daily(years=years, symbol="SH.512480", as_of_date=as_of)
    if etf.empty:
        return pd.DataFrame()
    us = strategy._load_us_features(
        years=years,
        cn_trading_dates=etf["date"],
        as_of_date=as_of,
    )
    merged = etf.merge(us, on="date", how="left")
    merged["sox_ret"] = merged["sox_ret"].fillna(0.0)
    merged["vix_close"] = merged["vix_close"].fillna(999.0)
    merged["timing_ret"] = (merged["close"].shift(-1) / merged["open"] - 1.0).fillna(0.0)
    merged["vol20"] = merged["ret"].rolling(20).std() * np.sqrt(252)
    for w in [3, 5, 10, 20, 60]:
        merged[f"mom{w}"] = merged["close"].pct_change(w)
        merged[f"ma{w}"] = merged["close"].rolling(w).mean()
    return merged.dropna(
        subset=["date", "symbol", "open", "close", "sox_ret", "vix_close"]
    ).reset_index(drop=True)


def main() -> int:
    cfg = load_config(Path("config.yaml"))
    strategy = get_strategy("cross_market_semiconductor_timing_etf_v1")
    sc = cfg["walk_forward"]["strategy_v2"]

    print("构建策略面板 (512480 创建日 2019-06-12 起, 保留全历史)...")
    panel = build_full_panel(strategy, sc)
    print(f"  面板: {len(panel)} 行, {panel['date'].min().date()} ~ {panel['date'].max().date()}")
    us_available = int(panel["vix_close"].lt(900).sum())
    print(f"  US信号可用日: {us_available} (2005 起全量)")
    print(f"  信号日: {int(((panel['sox_ret'] > 0.005) & (panel['vix_close'] < 19)).sum())}")

    # 策略回测 (盘中模拟, 含成本)
    print("运行策略盘中模拟...")
    output = strategy.apply(
        panel, PARAMS,
        slippage=0.0001, commission=0.00025, stamp_duty_sell=0.0,
    )
    strat_ret = output.returns
    strat_m = metrics(strat_ret)
    meta = output.metadata.get("account_execution_metrics", {})
    trades = int(meta.get("account_completed_round_trip_count", 0))
    missing_days = int(meta.get("account_intraday_data_missing_days", 0))

    # 512480 buy&hold (从创建日, 用后复权连续价)
    etf = load_512480_daily()
    etf = etf[etf["date"] <= panel["date"].max()].copy()
    bh_ret = etf.set_index("date")["hfq_close"].pct_change().fillna(0)
    bh_ret = bh_ret[bh_ret.index >= panel["date"].min()]
    bh_m = metrics(bh_ret)

    # 沪深300 buy&hold (同期)
    hs = load_hs300_daily()
    hs = hs[(hs["date"] >= panel["date"].min()) & (hs["date"] <= panel["date"].max())].copy()
    hs_ret = hs.set_index("date")["close"].pct_change().fillna(0)
    hs_m = metrics(hs_ret)

    # ── 报告 ──
    print()
    print("=" * 78)
    print("512480 全历史回测: SOX+VIX 半导体择时策略 vs 基准")
    print("=" * 78)
    print(f"回测区间:   {panel['date'].min().date()} ~ {panel['date'].max().date()} "
          f"({len(panel)} 交易日)")
    print(f"策略参数:   SOX>0.5% + VIX<19, 强信号>1%开盘追/弱信号挂单0.99, "
          f"追踪止损2%, T+1收盘平仓")
    print(f"US信号可用: 2005 起全量 (512480 创建日即有信号)")
    print()
    print(f"{'策略/基准':<28} {'总收益':>10} {'年化':>10} {'夏普':>7} {'最大回撤':>9} {'交易数':>6}")
    print("-" * 78)
    print(fmt("策略 (SOX+VIX择时)", strat_m, trades))
    print(fmt("512480 buy&hold", bh_m))
    print(fmt("沪深300 buy&hold", hs_m))
    print("-" * 78)

    print()
    print("── 对比分析 ──")
    print(f"策略 vs 512480 BH:  收益 {(strat_m['total']-bh_m['total']):+.1%}, "
          f"夏普 {strat_m['sharpe']-bh_m['sharpe']:+.2f}, "
          f"回撤 {strat_m['mdd']-bh_m['mdd']:+.1%}")
    print(f"策略 vs 沪深300 BH:  收益 {(strat_m['total']-hs_m['total']):+.1%}, "
          f"夏普 {strat_m['sharpe']-hs_m['sharpe']:+.2f}, "
          f"回撤 {strat_m['mdd']-hs_m['mdd']:+.1%}")
    if missing_days:
        print(f"注意: {missing_days} 个交易日缺少盘中数据(可能因当日无5分钟线)")
    print()
    print("说明: 512480 于 2019-06-12 上市。策略依赖美股 SOX/VIX 信号,")
    print("      本地 US 历史自 2005 年起全量可用, 信号从创建日即生效。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
