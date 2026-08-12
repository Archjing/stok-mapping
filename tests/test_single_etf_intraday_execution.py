from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from phase0.execution.accounts import SimulatedAccountConfig
from phase0.execution.single_etf_intraday import (
    SingleEtfIntradayPolicy,
    evaluate_trailing_exit,
    load_single_etf_intraday_state,
    run_single_etf_intraday_account_execution,
    write_single_etf_intraday_account_state,
)


def _account(tmp_path: Path) -> SimulatedAccountConfig:
    return SimulatedAccountConfig(
        account_id="single-etf",
        name="single ETF",
        initial_cash=100_000,
        ledger_path=tmp_path / "ledger.csv",
        database_path=tmp_path / "accounts.sqlite",
        strategy_id="cross_market_semiconductor_timing_etf_v1",
        execution_model="single_etf_intraday",
        price_tick=0.001,
        lot_size=100,
        commission=0.00025,
        min_commission=5.0,
        slippage=0.0,
        stamp_duty_sell=0.0,
        transfer_fee_rate=0.0,
        min_trade_amount=0.0,
    )


def _policy(**overrides: object) -> SingleEtfIntradayPolicy:
    values: dict[str, object] = {
        "target_symbol": "SH.512480",
        "return_symbol": "^SOX",
        "volatility_symbol": "^VIX",
        "return_threshold": 0.005,
        "volatility_threshold": 19.0,
        "strong_signal_threshold": 0.01,
        "weak_limit_discount": 0.01,
        "weak_unfilled_action": "cancel",
        "holding_sessions": 1,
        "trailing_drawdown": 0.02,
        "fallback_time": "14:55",
    }
    values.update(overrides)
    return SingleEtfIntradayPolicy(**values)


def _daily(sox_returns: list[float]) -> pd.DataFrame:
    dates = pd.to_datetime(["2024-06-10", "2024-06-11", "2024-06-12"])
    return pd.DataFrame(
        {
            "date": dates,
            "symbol": ["SH.512480"] * 3,
            "open": [1.000, 1.020, 1.010],
            "high": [1.020, 1.050, 1.030],
            "low": [0.980, 0.990, 0.990],
            "close": [1.010, 1.030, 1.000],
            "sox_ret": sox_returns,
            "vix_close": [18.0, 18.0, 18.0],
            "signal_us_date": pd.to_datetime(["2024-06-07", "2024-06-10", "2024-06-11"]),
        }
    )


def _bars() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": pd.to_datetime(
                [
                    "2024-06-10 09:35", "2024-06-10 14:55",
                    "2024-06-11 09:35", "2024-06-11 09:40", "2024-06-11 14:55",
                    "2024-06-12 09:35", "2024-06-12 14:55",
                ]
            ),
            "open": [1.000, 1.000, 1.020, 1.030, 1.025, 1.010, 1.000],
            "high": [1.010, 1.010, 1.040, 1.060, 1.030, 1.020, 1.010],
            "low": [0.980, 0.990, 1.010, 1.000, 1.010, 1.000, 0.990],
            "close": [1.000, 1.010, 1.030, 1.020, 1.020, 1.010, 1.000],
        }
    )


def test_strong_signal_buys_at_open_and_exits_next_session(tmp_path: Path) -> None:
    result = run_single_etf_intraday_account_execution(
        signal_frame=_daily([0.02, 0.0, 0.0]),
        intraday_bars=_bars(),
        account=_account(tmp_path),
        policy=_policy(),
    )

    assert result.trades["side"].tolist() == ["buy", "sell"]
    assert result.trades["date"].tolist() == ["2024-06-10", "2024-06-11"]
    assert result.trades.iloc[0]["price"] == 1.0
    assert result.metrics["account_execution_complete"] is True


def test_weak_signal_limit_fill_and_unfilled_cancel_are_executable(tmp_path: Path) -> None:
    filled = run_single_etf_intraday_account_execution(
        signal_frame=_daily([0.007, 0.0, 0.0]),
        intraday_bars=_bars(),
        account=_account(tmp_path),
        policy=_policy(),
    )
    assert filled.trades.iloc[0]["price"] == 0.99

    bars = _bars()
    bars.loc[bars["time"].dt.date == pd.Timestamp("2024-06-10").date(), "low"] = 0.995
    cancelled = run_single_etf_intraday_account_execution(
        signal_frame=_daily([0.007, 0.0, 0.0]),
        intraday_bars=bars,
        account=_account(tmp_path),
        policy=_policy(),
    )
    assert cancelled.trades.empty
    assert cancelled.metrics["account_unfilled_order_count"] == 1
    assert cancelled.metrics["account_execution_complete"] is True


def test_strong_and_weak_signals_use_separate_position_sizes(tmp_path: Path) -> None:
    strong = run_single_etf_intraday_account_execution(
        signal_frame=_daily([0.02, 0.0, 0.0]),
        intraday_bars=_bars(),
        account=_account(tmp_path),
        policy=_policy(strong_position_size=0.60, weak_position_size=0.50),
    )
    weak = run_single_etf_intraday_account_execution(
        signal_frame=_daily([0.007, 0.0, 0.0]),
        intraday_bars=_bars(),
        account=_account(tmp_path),
        policy=_policy(strong_position_size=0.60, weak_position_size=0.50),
    )

    assert strong.trades.iloc[0]["amount"] <= 60_000
    assert strong.trades.iloc[0]["amount"] > 59_000
    assert strong.daily_assets.iloc[0]["exposure"] == 0.60
    assert weak.trades.iloc[0]["amount"] <= 50_000
    assert weak.trades.iloc[0]["amount"] > 49_000
    assert weak.daily_assets.iloc[0]["exposure"] == 0.50


def test_exit_day_strong_signal_reenters_at_next_bar_open(tmp_path: Path) -> None:
    result = run_single_etf_intraday_account_execution(
        signal_frame=_daily([0.02, 0.02, 0.0]),
        intraday_bars=_bars(),
        account=_account(tmp_path),
        policy=_policy(strong_position_size=0.60, weak_position_size=0.50),
    )

    day_two = result.trades[result.trades["date"] == "2024-06-11"].reset_index(drop=True)
    assert day_two["side"].tolist() == ["sell", "buy"]
    assert day_two.iloc[0]["trade_time"] == "2024-06-11 09:40:00"
    assert day_two.iloc[1]["trade_time"] == "2024-06-11 14:55:00"
    assert day_two.iloc[1]["price"] == 1.025
    assert day_two.iloc[1]["amount"] <= result.daily_assets.iloc[0]["total_asset"] * 0.60


def test_exit_day_weak_signal_ignores_limit_touch_at_or_before_exit(tmp_path: Path) -> None:
    result = run_single_etf_intraday_account_execution(
        signal_frame=_daily([0.02, 0.007, 0.0]),
        intraday_bars=_bars(),
        account=_account(tmp_path),
        policy=_policy(strong_position_size=0.60, weak_position_size=0.50),
    )

    assert result.trades["side"].tolist() == ["buy", "sell"]
    assert result.metrics["account_unfilled_order_count"] == 1


def test_trailing_stop_uses_only_previous_completed_bar_high() -> None:
    bars = pd.DataFrame(
        {
            "time": pd.to_datetime(["2024-06-11 09:35", "2024-06-11 09:40", "2024-06-11 14:55"]),
            "open": [1.00, 1.08, 1.04],
            "high": [1.10, 1.08, 1.05],
            "low": [0.99, 1.04, 1.03],
            "close": [1.08, 1.05, 1.04],
        }
    )

    decision = evaluate_trailing_exit(
        bars=bars,
        entry_price=1.0,
        running_high=1.0,
        policy=_policy(),
        price_tick=0.001,
        slippage=0.0,
    )

    # The first bar cannot trigger from its own high.  Its completed high of
    # 1.10 sets a 1.078 stop that the next bar breaches.
    assert decision.status == "filled"
    assert decision.reason == "trailing_stop"
    assert decision.time == pd.Timestamp("2024-06-11 09:40")
    assert decision.price == 1.078


def test_missing_exit_bars_is_reported_and_never_uses_daily_close(tmp_path: Path) -> None:
    bars = _bars()
    bars = bars[bars["time"].dt.date != pd.Timestamp("2024-06-11").date()]

    result = run_single_etf_intraday_account_execution(
        signal_frame=_daily([0.02, 0.0, 0.0]),
        intraday_bars=bars,
        account=_account(tmp_path),
        policy=_policy(),
    )

    assert result.trades["side"].tolist() == ["buy"]
    assert result.metrics["account_execution_complete"] is False
    assert result.metrics["account_intraday_data_missing_days"] == 1


def test_last_session_signal_opens_position_and_marks_future_exit_pending(tmp_path: Path) -> None:
    one_day = _daily([0.02, 0.0, 0.0]).iloc[[0]].copy()
    one_day_bars = _bars()[
        _bars()["time"].dt.date == pd.Timestamp("2024-06-10").date()
    ].copy()

    result = run_single_etf_intraday_account_execution(
        signal_frame=one_day,
        intraday_bars=one_day_bars,
        account=_account(tmp_path),
        policy=_policy(),
    )

    assert result.trades["side"].tolist() == ["buy"]
    assert result.metrics["account_execution_complete"] is True
    assert result.metrics["account_state_status"] == "open_position_pending_exit"
    assert result.metrics["account_pending_exit_count"] == 1
    assert result.metrics["account_open_position_shares"] > 0
    assert result.metrics["account_planned_exit_date"] == ""


def test_state_write_is_idempotent(tmp_path: Path) -> None:
    account = _account(tmp_path)
    result = run_single_etf_intraday_account_execution(
        signal_frame=_daily([0.02, 0.0, 0.0]),
        intraday_bars=_bars(),
        account=account,
        policy=_policy(),
    )

    write_single_etf_intraday_account_state(account=account, policy=_policy(), result=result)
    write_single_etf_intraday_account_state(account=account, policy=_policy(), result=result)

    state = load_single_etf_intraday_state(account.database_path, account.account_id)
    assert len(state["trades"]) == 2
    with sqlite3.connect(account.database_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM single_etf_intraday_trades WHERE account_id = ?",
            (account.account_id,),
        ).fetchone()[0]
    assert count == 2
