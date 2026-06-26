from __future__ import annotations

import pandas as pd

from phase0.execution import strategy_ledger
import phase0.reporting.strategy_bill as strategy_bill
from phase0.execution.strategy_ledger import (
    append_order_record,
    execution_settings,
    ledger_for_fold,
    limit_pct,
    load_bfq_execution_price_frame,
    lot_floor,
    prepare_execution_frame,
    trade_block_reasons,
)


def test_strategy_ledger_execution_imports_are_available() -> None:
    assert callable(execution_settings)
    assert callable(limit_pct)
    assert callable(load_bfq_execution_price_frame)
    assert callable(lot_floor)
    assert callable(prepare_execution_frame)
    assert callable(trade_block_reasons)
    assert callable(append_order_record)
    assert callable(ledger_for_fold)


def test_strategy_bill_reexports_execution_ledger_helpers() -> None:
    assert strategy_bill._execution_settings is strategy_ledger.execution_settings
    assert strategy_bill._load_bfq_execution_price_frame is strategy_ledger.load_bfq_execution_price_frame
    assert strategy_bill._limit_pct is strategy_ledger.limit_pct
    assert strategy_bill._lot_floor is strategy_ledger.lot_floor
    assert strategy_bill._prepare_execution_frame is strategy_ledger.prepare_execution_frame
    assert strategy_bill._trade_block_reasons is strategy_ledger.trade_block_reasons
    assert strategy_bill._append_order_record is strategy_ledger.append_order_record
    assert strategy_bill._ledger_for_fold is strategy_ledger.ledger_for_fold


def test_bfq_execution_price_frame_loads_raw_prices(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_load_daily_from_local_history(symbol, start, end, *, price_adjustment):
        calls.append({"symbol": symbol, "start": start, "end": end, "price_adjustment": price_adjustment})
        return pd.DataFrame(
            [
                {
                    "date": "2026-01-02",
                    "symbol": symbol,
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.5,
                    "close": 10.5,
                    "volume": 1000,
                    "amount": 10_500,
                }
            ]
        )

    monkeypatch.setattr(strategy_ledger, "load_daily_from_local_history", fake_load_daily_from_local_history)
    frame = pd.DataFrame(
        [
            {
                "date": "2026-01-02",
                "symbol": "SH.600000",
                "open": 20.0,
                "high": 21.0,
                "low": 19.5,
                "close": 20.5,
                "volume": 2000,
                "amount": 41_000,
                "score": 1.0,
            }
        ]
    )

    out = load_bfq_execution_price_frame(frame)

    assert calls == [
        {
            "symbol": "SH.600000",
            "start": pd.Timestamp("2026-01-02").date(),
            "end": pd.Timestamp("2026-01-02").date(),
            "price_adjustment": "bfq_raw",
        }
    ]
    assert out.loc[0, "open"] == 10.0
    assert out.loc[0, "close"] == 10.5
    assert out.loc[0, "execution_adjust_type"] == "bfq_raw"
    assert out.loc[0, "score"] == 1.0


def test_bfq_execution_price_frame_missing_required_columns_returns_copy() -> None:
    frame = pd.DataFrame([{"date": "2026-01-02", "open": 20.0}])

    out = load_bfq_execution_price_frame(frame)

    assert out.equals(frame)
    assert out is not frame


def test_bfq_execution_price_frame_no_raw_rows_preserves_original_frame(monkeypatch) -> None:
    monkeypatch.setattr(
        strategy_ledger,
        "load_daily_from_local_history",
        lambda *args, **kwargs: pd.DataFrame(),
    )
    frame = pd.DataFrame(
        [
            {
                "date": "2026-01-02",
                "symbol": "SH.600000",
                "open": 20.0,
                "close": 20.5,
            }
        ]
    )

    out = load_bfq_execution_price_frame(frame)

    assert out.loc[0, "date"] == pd.Timestamp("2026-01-02")
    assert out.loc[0, "open"] == 20.0
    assert out.loc[0, "close"] == 20.5
    assert "execution_adjust_type" not in out.columns
