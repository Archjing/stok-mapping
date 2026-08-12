from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from quant.execution.accounts import SimulatedAccountConfig, collect_watchlist_frames, ensure_account_tables
from quant.reporting.premarket_watchlist import (
    _load_account_holding_days,
    _load_confirmed_account_positions,
    _load_previous_sim_positions,
)


def test_load_account_holding_days_counts_confirmed_position_snapshots(tmp_path: Path) -> None:
    account = SimulatedAccountConfig(
        account_id="default",
        name="默认模拟账户",
        initial_cash=1_000_000.0,
        ledger_path=tmp_path / "ledger.csv",
        database_path=tmp_path / "simulated_accounts.sqlite",
        simulation_start_date="2026-06-27",
    )
    with sqlite3.connect(account.database_path) as conn:
        ensure_account_tables(conn)
        conn.executemany(
            """
            INSERT INTO account_daily_assets
            (account_id, brief_date, start_date, total_asset, stock_asset, cash_asset, daily_pnl, daily_return,
             target_exposure, estimated_trade_amount, estimated_volume, execution_price_mode, max_participation_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("default", "2026-06-27", "2026-06-27", 1_000_000.0, 0.0, 1_000_000.0, 0.0, 0.0, 0.0, 0.0, 0.0, "next_open", 0.05),
                ("default", "2026-06-28", "2026-06-27", 1_000_000.0, 10_000.0, 990_000.0, 0.0, 0.0, 0.01, 0.0, 0.0, "next_open", 0.05),
                ("default", "2026-06-29", "2026-06-27", 1_000_000.0, 20_000.0, 980_000.0, 0.0, 0.0, 0.02, 0.0, 0.0, "next_open", 0.05),
            ],
        )
        conn.executemany(
            """
            INSERT INTO account_positions
            (account_id, brief_date, symbol, name, close, target_weight, market_value, shares, lots, lot_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("default", "2026-06-28", "AAA", "Alpha", 10.0, 0.01, 10_000.0, 1_000.0, 10.0, 100),
                ("default", "2026-06-29", "AAA", "Alpha", 20.0, 0.02, 20_000.0, 1_000.0, 10.0, 100),
                ("default", "2026-06-27", "BBB", "Beta", 5.0, 0.01, 10_000.0, 2_000.0, 20.0, 100),
            ],
        )

    assert _load_account_holding_days(account, "2026-06-30") == {"AAA": 2}


def test_new_account_without_confirmed_positions_has_no_holding_days(tmp_path: Path) -> None:
    account = SimulatedAccountConfig(
        account_id="default",
        name="默认模拟账户",
        initial_cash=1_000_000.0,
        ledger_path=tmp_path / "ledger.csv",
        database_path=tmp_path / "simulated_accounts.sqlite",
        simulation_start_date="2026-06-30",
    )
    with sqlite3.connect(account.database_path) as conn:
        ensure_account_tables(conn)

    assert _load_account_holding_days(account, "2026-06-30") == {}


def test_confirmed_account_positions_are_authoritative_even_when_symbol_missing(tmp_path: Path) -> None:
    account = SimulatedAccountConfig(
        account_id="default",
        name="默认模拟账户",
        initial_cash=1_000_000.0,
        ledger_path=tmp_path / "ledger.csv",
        database_path=tmp_path / "simulated_accounts.sqlite",
        simulation_start_date="2026-06-30",
    )
    with sqlite3.connect(account.database_path) as conn:
        ensure_account_tables(conn)
        conn.execute(
            """
            INSERT INTO account_daily_assets
            (account_id, brief_date, start_date, total_asset, stock_asset, cash_asset, daily_pnl, daily_return,
             target_exposure, estimated_trade_amount, estimated_volume, execution_price_mode, max_participation_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("default", "2026-06-30", "2026-06-30", 1_000_000.0, 10_000.0, 990_000.0, 0.0, 0.0, 0.01, 0.0, 0.0, "next_open", 0.05),
        )
        conn.execute(
            """
            INSERT INTO account_positions
            (account_id, brief_date, symbol, name, close, target_weight, market_value, shares, lots, lot_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("default", "2026-06-30", "AAA", "Alpha", 10.0, 0.01, 10_000.0, 1_000.0, 10.0, 100),
        )

    positions, source, has_snapshot = _load_confirmed_account_positions(account, "2026-07-01")

    assert positions == {"AAA": 0.01}
    assert source == "确认账单2026-06-30"
    assert has_snapshot is True


def test_previous_sim_positions_respect_simulation_start_date(tmp_path: Path) -> None:
    ledger_path = tmp_path / "phase0_daily_brief_ledger.csv"
    pd.DataFrame(
        [
            {
                "brief_date": "2026-06-28",
                "signal_date": "2026-06-27",
                "symbol": "AAA",
                "name": "Alpha",
                "action": "继续持有",
                "current_weight": 0.05,
                "target_weight": 0.05,
                "weight_change": 0.0,
            }
        ]
    ).to_csv(ledger_path, index=False, encoding="utf-8-sig")

    positions, source = _load_previous_sim_positions(
        tmp_path,
        "2026-06-30",
        ledger_path,
        simulation_start_date="2026-06-30",
    )

    assert positions == {}
    assert source == ""


def test_collect_watchlist_frames_skips_reports_before_simulation_start(tmp_path: Path) -> None:
    old_report_dir = tmp_path / "reports" / "2026-06-28"
    old_report_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "股票代码": "AAA",
                "股票名称": "Alpha",
                "收盘价": "10.00",
                "模拟账户目标权重": "5.00%",
                "模拟账户权重变化": "5.00%",
            }
        ]
    ).to_csv(old_report_dir / "phase0_premarket_watchlist_2026-06-28.csv", index=False, encoding="utf-8-sig")
    current = pd.DataFrame(
        [
            {
                "股票代码": "BBB",
                "股票名称": "Beta",
                "收盘价": "20.00",
                "模拟账户目标权重": "0.00%",
                "模拟账户权重变化": "0.00%",
            }
        ]
    )

    frames = collect_watchlist_frames(
        tmp_path,
        current,
        "2026-06-30",
        simulation_start_date="2026-06-30",
    )

    assert list(frames) == ["2026-06-30"]
    assert frames["2026-06-30"]["symbol"].tolist() == ["BBB"]
