from __future__ import annotations

import json

import pandas as pd

from quant.execution.strategy_ledger import execution_settings, ledger_for_fold, trade_block_reasons


def _params() -> dict[str, int]:
    return {"buy_top_n": 1, "hold_top_n": 1}


def _ledger(signal_rows: list[dict[str, object]], price_rows: list[dict[str, object]], execution_cfg: dict[str, object]) -> tuple[pd.DataFrame, pd.DataFrame]:
    return ledger_for_fold(
        pd.DataFrame(signal_rows),
        price_frame=pd.DataFrame(price_rows),
        params=_params(),
        fold=1,
        initial_cash=100_000.0,
        names={},
        slippage=0.0,
        commission=0.00025,
        stamp_duty_sell=0.001,
        params_text="{}",
        execution_cfg=execution_cfg,
    )


def test_strategy_ledger_execution_settings_include_deterministic_constraints() -> None:
    cfg = execution_settings(
        {
            "execution": {
                "price_mode": "next_open",
                "price_tick": 0.01,
                "min_commission": 5.0,
                "transfer_fee_rate": 0.00001,
                "min_trade_amount": 1000.0,
                "enable_t_plus_one": True,
                "enable_special_limit_rules": True,
                "st_limit_pct": 0.05,
                "new_stock_no_limit_days": 5,
            }
        }
    )

    assert cfg["min_commission"] == 5.0
    assert cfg["price_tick"] == 0.01
    assert cfg["transfer_fee_rate"] == 0.00001
    assert cfg["min_trade_amount"] == 1000.0
    assert cfg["enable_t_plus_one"] is True
    assert cfg["enable_special_limit_rules"] is True
    assert cfg["st_limit_pct"] == 0.05
    assert cfg["new_stock_no_limit_days"] == 5


def test_strategy_ledger_uses_st_limit_rule_and_new_stock_exemption() -> None:
    execution_cfg = execution_settings({"execution": {"enable_limit_check": True, "enable_special_limit_rules": True, "st_limit_pct": 0.05, "new_stock_no_limit_days": 5}})
    st_row = pd.Series(
        {
            "date": "2024-01-10",
            "symbol": "SH.600001",
            "stock_name": "*ST Alpha",
            "open": 10.5,
            "close": 10.5,
            "volume": 1_000_000,
            "amount": 10_500_000.0,
            "previous_close": 10.0,
            "list_date": "2020-01-01",
        }
    )
    new_stock_row = st_row.copy()
    new_stock_row["stock_name"] = "Alpha"
    new_stock_row["list_date"] = "2024-01-08"

    assert "涨停不可买" in trade_block_reasons(st_row, "买", execution_cfg)
    assert "涨停不可买" not in trade_block_reasons(new_stock_row, "买", execution_cfg)


def test_strategy_ledger_applies_min_commission_and_transfer_fee_to_buy() -> None:
    execution_cfg = execution_settings({"execution": {"enable_limit_check": False, "enable_suspension_check": False, "min_commission": 5.0, "transfer_fee_rate": 0.00001}})
    signal = [
        {"date": "2024-01-02", "symbol": "AAA", "weight": 0.5, "score": 1.0, "rank": 1},
        {"date": "2024-01-03", "symbol": "AAA", "weight": 0.5, "score": 1.0, "rank": 1},
    ]
    prices = [
        {"date": "2024-01-02", "symbol": "AAA", "open": 10.0, "close": 10.0, "volume": 1_000_000, "amount": 10_000_000.0},
        {"date": "2024-01-03", "symbol": "AAA", "open": 10.0, "close": 10.0, "volume": 1_000_000, "amount": 10_000_000.0},
    ]

    bill, _daily = _ledger(signal, prices, execution_cfg)

    amount = float(bill.iloc[0]["成交金额"])
    assert float(bill.iloc[0]["交易成本"]) == max(5.0, amount * 0.00025) + amount * 0.00001


def test_strategy_ledger_blocks_min_trade_amount() -> None:
    execution_cfg = execution_settings({"execution": {"enable_limit_check": False, "enable_suspension_check": False, "min_trade_amount": 2000.0}})
    signal = [
        {"date": "2024-01-02", "symbol": "AAA", "weight": 0.01, "score": 1.0, "rank": 1},
        {"date": "2024-01-03", "symbol": "AAA", "weight": 0.01, "score": 1.0, "rank": 1},
    ]
    prices = [
        {"date": "2024-01-02", "symbol": "AAA", "open": 10.0, "close": 10.0, "volume": 1_000_000, "amount": 10_000_000.0},
        {"date": "2024-01-03", "symbol": "AAA", "open": 10.0, "close": 10.0, "volume": 1_000_000, "amount": 10_000_000.0},
    ]

    bill, daily = _ledger(signal, prices, execution_cfg)

    assert bill.iloc[0]["交易状态"] == "未成交"
    assert "低于最小成交金额" in str(bill.iloc[0]["未成交原因"])
    counts = json.loads(str(daily.iloc[0]["block_reason_counts"]))
    assert counts["低于最小成交金额"] == 1
