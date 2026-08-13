"""生成 512480 全历史模拟交易台账 (含逐笔现金/仓位变动).

复用 cross_market_semiconductor_timing_etf_v1 的执行引擎路径
(run_single_etf_intraday_account_execution), 从 result.trades 重放
每笔成交, 记录:
  - 成交前/后现金 (cash_before / cash_after)
  - 成交前/后持仓份额 (shares_before / shares_after)
  - 成交后总资产 (total_asset_after)
  - 往返配对 (round_trip_no) 与单笔/单轮盈亏

输出: reports/512480_trade_ledger.csv
用法: .venv/bin/python3 scripts/build_trade_ledger_512480.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quant.config import load_config
from quant.execution.accounts import SimulatedAccountConfig
from quant.execution.single_etf_intraday import (
    SingleEtfIntradayPolicy,
    run_single_etf_intraday_account_execution,
)
from quant.strategies import get_strategy
from quant.strategies.cross_market_semiconductor_timing import (
    DEFAULT_TARGET_SYMBOL,
    LIMIT_ORDER_DISCOUNT,
    STRONG_SIGNAL_THRESHOLD,
    TRAILING_STOP_RATIO,
    US_SOX_SYMBOL,
    US_VIX_SYMBOL,
)
from scripts.backtest_512480_full_history import build_full_panel

OUTPUT_PATH = Path("reports/512480_trade_ledger.csv")
INITIAL_CASH = 100_000.0


def main() -> int:
    cfg = load_config(Path("config.yaml"))
    strategy = get_strategy("cross_market_semiconductor_timing_etf_v1")
    sc = cfg["walk_forward"]["strategy_v2"]

    print("构建面板 + 5 分钟线...")
    panel = build_full_panel(strategy, sc)
    intraday = strategy._load_5min_bars(
        panel["date"].min(), panel["date"].max(), DEFAULT_TARGET_SYMBOL
    )
    print(f"  面板 {len(panel)} 行, 5min {len(intraday)} 行")

    account = SimulatedAccountConfig(
        account_id="ledger_512480",
        name="512480 full-history ledger",
        initial_cash=INITIAL_CASH,
        ledger_path=Path("/dev/null"),
        database_path=Path("/dev/null"),
        execution_price_mode="next_open",
        price_tick=0.001,
        lot_size=100,
        commission=0.00025,
        stamp_duty_sell=0.0,
        slippage=0.0001,
        min_commission=5.0,
        transfer_fee_rate=0.0,
        enable_limit_check=False,
        enable_suspension_check=False,
        enable_t_plus_one=True,
        enable_special_limit_rules=False,
    )
    policy = SingleEtfIntradayPolicy(
        target_symbol=DEFAULT_TARGET_SYMBOL,
        return_symbol=US_SOX_SYMBOL,
        volatility_symbol=US_VIX_SYMBOL,
        return_threshold=0.005,
        volatility_threshold=19.0,
        strong_signal_threshold=STRONG_SIGNAL_THRESHOLD,
        weak_limit_discount=LIMIT_ORDER_DISCOUNT,
        weak_unfilled_action="cancel",
        holding_sessions=1,
        trailing_drawdown=1.0 - TRAILING_STOP_RATIO,
        fallback_time="14:55",
        position_size=1.0,
    )

    print("执行账户级模拟...")
    result = run_single_etf_intraday_account_execution(
        signal_frame=panel,
        intraday_bars=intraday,
        account=account,
        policy=policy,
    )
    trades = result.trades.copy()
    if trades.empty:
        print("无交易"); return 0
    trades = trades.sort_values(["trade_time"]).reset_index(drop=True)
    print(f"  成交 {len(trades)} 笔")

    # 逐笔重放: 计算现金/仓位变动
    cash = INITIAL_CASH
    shares = 0.0
    round_trip = 0
    open_leg: dict | None = None
    rows = []
    for _, t in trades.iterrows():
        side = t["side"]
        price = float(t["price"])
        qty = float(t["shares"])
        amount = float(t["amount"])
        cost = float(t["cost"])
        cash_before = cash
        shares_before = shares
        if side == "buy":
            cash -= amount + cost
            shares += qty
            open_leg = {"price": price, "shares": qty, "cost": cost}
        else:
            cash += amount - cost
            shares -= qty
            round_trip += 1
        # 成交后按成交价估值总资产
        total_asset_after = cash + shares * price
        rows.append({
            "trade_no": len(rows) + 1,
            "round_trip_no": round_trip if side == "sell" else "",
            "trade_date": t["date"],
            "trade_time": t["trade_time"],
            "signal_date": t["signal_date"],
            "side": side,
            "order_type": t["order_type"],
            "reason": t["reason"],
            "price": round(price, 4),
            "shares": qty,
            "amount": round(amount, 2),
            "cost": round(cost, 2),
            "cash_before": round(cash_before, 2),
            "cash_after": round(cash, 2),
            "shares_before": shares_before,
            "shares_after": shares,
            "total_asset_after": round(total_asset_after, 2),
        })
    ledger = pd.DataFrame(rows)

    # 往返配对盈亏
    buys = ledger[ledger["side"] == "buy"].reset_index(drop=True)
    sells = ledger[ledger["side"] == "sell"].reset_index(drop=True)
    pnl_rows = []
    for i in range(len(sells)):
        b = buys.iloc[i] if i < len(buys) else None
        s = sells.iloc[i]
        if b is None:
            break
        round_pnl = (float(s["amount"]) - float(s["cost"])) - (float(b["amount"]) + float(b["cost"]))
        pnl_rows.append({
            "round_trip_no": i + 1,
            "signal_date": b["signal_date"],
            "buy_date": b["trade_date"],
            "sell_date": s["trade_date"],
            "buy_price": b["price"],
            "sell_price": s["price"],
            "shares": b["shares"],
            "round_pnl": round(round_pnl, 2),
            "round_pnl_pct": round(round_pnl / (float(b["amount"]) + float(b["cost"])) * 100, 3),
        })
    pnl = pd.DataFrame(pnl_rows)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    pnl_path = OUTPUT_PATH.with_name("512480_round_trip_pnl.csv")
    pnl.to_csv(pnl_path, index=False, encoding="utf-8-sig")

    print(f"台账: {OUTPUT_PATH} ({len(ledger)} 行)")
    print(f"往返盈亏: {pnl_path} ({len(pnl)} 轮)")
    print()
    print("台账示例 (前 4 笔):")
    print(ledger.head(4).to_string(index=False))
    print()
    print(f"期末现金 {cash:,.2f} / 持仓 {shares:,.0f} 股")
    wins = int((pnl["round_pnl"] > 0).sum())
    total_pnl = pnl["round_pnl"].sum()
    print(f"往返: {len(pnl)} 轮, 盈利 {wins} 轮 ({wins/len(pnl):.1%}), 总盈亏 {total_pnl:+,.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
