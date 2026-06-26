from __future__ import annotations

from phase0.execution import strategy_ledger
import phase0.reporting.strategy_bill as strategy_bill
from phase0.execution.strategy_ledger import (
    append_order_record,
    execution_settings,
    ledger_for_fold,
    limit_pct,
    lot_floor,
    prepare_execution_frame,
    trade_block_reasons,
)


def test_strategy_ledger_execution_imports_are_available() -> None:
    assert callable(execution_settings)
    assert callable(limit_pct)
    assert callable(lot_floor)
    assert callable(prepare_execution_frame)
    assert callable(trade_block_reasons)
    assert callable(append_order_record)
    assert callable(ledger_for_fold)


def test_strategy_bill_reexports_execution_ledger_helpers() -> None:
    assert strategy_bill._execution_settings is strategy_ledger.execution_settings
    assert strategy_bill._limit_pct is strategy_ledger.limit_pct
    assert strategy_bill._lot_floor is strategy_ledger.lot_floor
    assert strategy_bill._prepare_execution_frame is strategy_ledger.prepare_execution_frame
    assert strategy_bill._trade_block_reasons is strategy_ledger.trade_block_reasons
    assert strategy_bill._append_order_record is strategy_ledger.append_order_record
    assert strategy_bill._ledger_for_fold is strategy_ledger.ledger_for_fold
