"""仓位设计对比回测: 全仓 1.0 vs 单档 55% vs 强60%/弱50%.

直接复用 cross_market_semiconductor_timing_etf_v1 的执行引擎路径, 用
不同仓位参数跑三组全历史模拟 (2019-06-12 ~ 2026-08-11), 输出对比。

用法: .venv/bin/python3 scripts/backtest_position_sizing.py
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
from quant.research.metrics import annualized_return, max_drawdown, sharpe
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


def run_scenario(
    panel: pd.DataFrame,
    intraday: pd.DataFrame,
    *,
    label: str,
    position_size: float,
    strong_position_size: float | None = None,
    weak_position_size: float | None = None,
) -> dict:
    account = SimulatedAccountConfig(
        account_id=f"poscmp_{label}",
        name=label,
        initial_cash=100_000.0,
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
        position_size=position_size,
        strong_position_size=strong_position_size,
        weak_position_size=weak_position_size,
    )
    result = run_single_etf_intraday_account_execution(
        signal_frame=panel, intraday_bars=intraday, account=account, policy=policy
    )
    returns = result.daily_assets.set_index("date")["daily_return"]
    trades = result.trades
    buys = int((trades["side"] == "buy").sum())
    sells = int((trades["side"] == "sell").sum())
    avg_exposure = float(result.daily_assets["exposure"].mean())
    avg_cash = float((result.daily_assets["cash_asset"] / result.daily_assets["total_asset"]).mean())
    return {
        "label": label,
        "total": float((1.0 + returns).prod() - 1.0),
        "annual": float(annualized_return(returns)),
        "sharpe": float(sharpe(returns)),
        "mdd": float(max_drawdown(returns)),
        "round_trips": sells,
        "buys": buys,
        "avg_exposure": avg_exposure,
        "avg_cash": avg_cash,
    }


def main() -> int:
    cfg = load_config(Path("config.yaml"))
    strategy = get_strategy("cross_market_semiconductor_timing_etf_v1")
    sc = cfg["walk_forward"]["strategy_v2"]
    print("构建面板 + 5min ...")
    panel = build_full_panel(strategy, sc)
    intraday = strategy._load_5min_bars(panel["date"].min(), panel["date"].max(), DEFAULT_TARGET_SYMBOL)

    scenarios = [
        ("全仓 1.0 (当前)", dict(position_size=1.0)),
        ("单档 55%", dict(position_size=0.55)),
        ("强60%/弱50%", dict(position_size=1.0, strong_position_size=0.6, weak_position_size=0.5)),
    ]
    rows = []
    for label, kwargs in scenarios:
        print(f"  跑 {label} ...")
        rows.append(run_scenario(panel, intraday, label=label, **kwargs))

    out = pd.DataFrame(rows)
    print()
    print(out.to_string(index=False, formatters={
        "total": lambda v: f"{v:+.1%}",
        "annual": lambda v: f"{v:+.1%}",
        "sharpe": lambda v: f"{v:.2f}",
        "mdd": lambda v: f"{v:.1%}",
        "avg_exposure": lambda v: f"{v:.1%}",
        "avg_cash": lambda v: f"{v:.1%}",
    }))
    out.to_csv(Path("reports/position_sizing_comparison.csv"), index=False, encoding="utf-8-sig")
    print()
    print("对比表: reports/position_sizing_comparison.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
