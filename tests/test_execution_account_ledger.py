from __future__ import annotations

import sqlite3
from pathlib import Path
from dataclasses import replace

import pandas as pd

from phase0.execution.accounts import SimulatedAccountConfig, build_account_ledger, collect_watchlist_frames, load_simulated_accounts


def _account(tmp_path: Path) -> SimulatedAccountConfig:
    return SimulatedAccountConfig(
        account_id="default",
        name="默认模拟账户",
        initial_cash=100000.0,
        simulation_start_date="2026-06-30",
        ledger_path=tmp_path / "data" / "simulated_trading" / "phase0_daily_account_ledger.csv",
        database_path=tmp_path / "data" / "simulated_trading" / "simulated_accounts.sqlite",
        execution_price_mode="next_open",
        max_participation_rate=0.0,
        lot_size=100,
        enable_limit_check=False,
        enable_suspension_check=False,
    )


def _write_history_db(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "a_share_history.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE market_daily_bars (
                market TEXT NOT NULL,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                adjust_type TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL
            );
            CREATE TABLE market_stocks (
                market TEXT NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT,
                list_date TEXT
            );
            """
        )
        conn.execute(
            """
            INSERT INTO market_daily_bars
            (market, symbol, date, adjust_type, open, high, low, close, volume, amount)
            VALUES ('CN', 'SH.600000', '2026-06-30', 'bfq', 10.0, 10.2, 9.8, 10.0, 1000000, 10000000.0)
            """
        )
        conn.execute(
            "INSERT INTO market_stocks (market, symbol, name, list_date) VALUES ('CN', 'SH.600000', '浦发银行', '1999-11-10')"
        )


def _watchlist(*, signal_date: str, check_time: str, target_weight: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "信号日期": signal_date,
                "盘前检查时间": check_time,
                "动作": "关注买入" if target_weight != "0.00%" else "关注卖出",
                "信号动作": "继续持有" if target_weight != "0.00%" else "候选观察",
                "股票代码": "SH.600000",
                "股票名称": "浦发银行",
                "收盘价": "10.00",
                "当前权重": "0.00%",
                "目标权重": target_weight,
                "权重变化": target_weight,
            }
        ]
    )


def _daily_asset_dates(database_path: Path) -> list[str]:
    with sqlite3.connect(database_path) as conn:
        return [
            str(row[0])
            for row in conn.execute(
                "SELECT brief_date FROM account_daily_assets ORDER BY brief_date"
            ).fetchall()
        ]


def _daily_asset_start_dates(database_path: Path) -> list[str]:
    with sqlite3.connect(database_path) as conn:
        return [
            str(row[0])
            for row in conn.execute(
                "SELECT start_date FROM account_daily_assets ORDER BY brief_date"
            ).fetchall()
        ]


def test_load_simulated_accounts_keeps_account_strategy_id(tmp_path: Path) -> None:
    accounts = load_simulated_accounts(
        {
            "strategy_reports": {"default_strategy_id": "legacy_momentum_low_turnover_v1"},
            "accounts": {
                "simulated": [
                    {
                        "account_id": "default",
                        "name": "默认模拟账户",
                        "initial_cash": 100000.0,
                    },
                    {
                        "account_id": "quality",
                        "name": "质量账户",
                        "initial_cash": 200000.0,
                        "strategy_id": "low_vol_low_turnover_quality_v1",
                    },
                ]
            },
        },
        tmp_path,
    )

    assert [account.account_id for account in accounts] == ["default", "quality"]
    assert accounts[0].strategy_id == "legacy_momentum_low_turnover_v1"
    assert accounts[1].strategy_id == "low_vol_low_turnover_quality_v1"


def test_load_simulated_accounts_keeps_account_local_strategy_params_isolated(tmp_path: Path) -> None:
    accounts = load_simulated_accounts(
        {
            "accounts": {
                "simulated": [
                    {
                        "account_id": "semiconductor_512480",
                        "name": "512480",
                        "initial_cash": 100000.0,
                        "strategy_id": "cross_market_semiconductor_timing_etf_v1",
                        "strategy_params": {"target_symbol": "SH.512480"},
                    },
                    {
                        "account_id": "semiconductor_512760",
                        "name": "512760",
                        "initial_cash": 100000.0,
                        "strategy_id": "cross_market_semiconductor_timing_etf_v1",
                        "strategy_params": {"target_symbol": "SH.512760"},
                    },
                ]
            }
        },
        tmp_path,
    )

    assert accounts[0].strategy_params == {"target_symbol": "SH.512480"}
    assert accounts[1].strategy_params == {"target_symbol": "SH.512760"}


def test_collect_watchlist_frames_filters_by_account_and_strategy(tmp_path: Path) -> None:
    run_root = tmp_path / "reports" / "runs" / "2026-06-30"
    default_path = run_root / "20260630_080000__premarket__default" / "premarket__watchlist.csv"
    quality_path = run_root / "20260630_081000__premarket__quality" / "premarket__watchlist.csv"
    default_path.parent.mkdir(parents=True, exist_ok=True)
    quality_path.parent.mkdir(parents=True, exist_ok=True)
    default_watchlist = _watchlist(signal_date="2026-06-29", check_time="2026-06-30 07:30", target_weight="20.00%")
    default_watchlist["账户ID"] = "default"
    default_watchlist["策略ID"] = "legacy_momentum_low_turnover_v1"
    quality_watchlist = _watchlist(signal_date="2026-06-29", check_time="2026-06-30 07:30", target_weight="60.00%")
    quality_watchlist["账户ID"] = "quality"
    quality_watchlist["策略ID"] = "low_vol_low_turnover_quality_v1"
    default_watchlist.to_csv(default_path, index=False, encoding="utf-8-sig")
    quality_watchlist.to_csv(quality_path, index=False, encoding="utf-8-sig")
    current = _watchlist(signal_date="2026-06-30", check_time="2026-07-01 07:30", target_weight="0.00%")
    current["账户ID"] = "quality"
    current["策略ID"] = "low_vol_low_turnover_quality_v1"

    frames = collect_watchlist_frames(
        tmp_path,
        current,
        "2026-07-01",
        simulation_start_date="2026-06-30",
        account_id="quality",
        strategy_id="low_vol_low_turnover_quality_v1",
    )

    assert frames["2026-06-30"]["target_weight"].tolist() == [0.6]
    assert frames["2026-07-01"]["target_weight"].tolist() == [0.0]


def test_collect_watchlist_frames_does_not_apply_unscoped_history_to_non_default_account(tmp_path: Path) -> None:
    run_path = (
        tmp_path
        / "reports"
        / "runs"
        / "2026-06-30"
        / "20260630_080000__premarket__watchlist"
        / "premarket__watchlist.csv"
    )
    run_path.parent.mkdir(parents=True, exist_ok=True)
    _watchlist(signal_date="2026-06-29", check_time="2026-06-30 07:30", target_weight="80.00%").to_csv(
        run_path,
        index=False,
        encoding="utf-8-sig",
    )
    current = _watchlist(signal_date="2026-06-30", check_time="2026-07-01 07:30", target_weight="0.00%")
    current["账户ID"] = "quality"
    current["策略ID"] = "low_vol_low_turnover_quality_v1"

    frames = collect_watchlist_frames(
        tmp_path,
        current,
        "2026-07-01",
        simulation_start_date="2026-06-30",
        account_id="quality",
        strategy_id="low_vol_low_turnover_quality_v1",
    )

    assert list(frames) == ["2026-07-01"]


def test_missing_future_execution_price_does_not_clear_existing_account_database(tmp_path: Path) -> None:
    _write_history_db(tmp_path)
    account = _account(tmp_path)
    local_history_cfg = {"path": "data/a_share_history.sqlite"}

    build_account_ledger(
        root=tmp_path,
        current_watchlist=_watchlist(signal_date="2026-06-29", check_time="2026-06-30 07:30", target_weight="50.00%"),
        current_brief_date="2026-06-30",
        account=account,
        local_history_cfg=local_history_cfg,
    )
    assert _daily_asset_dates(account.database_path) == ["2026-06-30"]
    assert _daily_asset_start_dates(account.database_path) == ["2026-06-30"]

    ledger, latest = build_account_ledger(
        root=tmp_path,
        current_watchlist=_watchlist(signal_date="2026-06-30", check_time="2026-07-01 07:30", target_weight="0.00%"),
        current_brief_date="2026-07-01",
        account=account,
        local_history_cfg=local_history_cfg,
    )

    assert ledger.empty
    assert latest == {}
    assert _daily_asset_dates(account.database_path) == ["2026-06-30"]


def test_account_ledger_collects_standard_run_watchlists(tmp_path: Path) -> None:
    _write_history_db(tmp_path)
    account = _account(tmp_path)
    local_history_cfg = {"path": "data/a_share_history.sqlite"}
    run_watchlist = tmp_path / "reports" / "runs" / "2026-06-30" / "20260630_090000__premarket__watchlist" / "premarket__watchlist.csv"
    run_watchlist.parent.mkdir(parents=True, exist_ok=True)
    _watchlist(signal_date="2026-06-29", check_time="2026-06-30 07:30", target_weight="50.00%").to_csv(
        run_watchlist,
        index=False,
        encoding="utf-8-sig",
    )

    ledger, latest = build_account_ledger(
        root=tmp_path,
        current_watchlist=_watchlist(signal_date="2026-06-30", check_time="2026-07-01 07:30", target_weight="0.00%"),
        current_brief_date="2026-07-01",
        account=account,
        local_history_cfg=local_history_cfg,
    )

    assert ledger["brief_date"].tolist() == ["2026-06-30"]
    assert latest["brief_date"] == "2026-06-30"
    assert _daily_asset_dates(account.database_path) == ["2026-06-30"]


def test_account_ledger_collects_historical_brief_ledger_when_run_watchlists_were_pruned(tmp_path: Path) -> None:
    _write_history_db(tmp_path)
    with sqlite3.connect(tmp_path / "data" / "a_share_history.sqlite") as conn:
        conn.execute(
            """
            INSERT INTO market_daily_bars
            (market, symbol, date, adjust_type, open, high, low, close, volume, amount)
            VALUES ('CN', 'SH.600000', '2026-07-01', 'bfq', 11.0, 11.2, 10.8, 11.0, 1000000, 11000000.0)
            """
        )
    brief_ledger = tmp_path / "data" / "simulated_trading" / "phase0_daily_brief_ledger.csv"
    brief_ledger.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "brief_date": "2026-06-30",
                "signal_date": "2026-06-29",
                "symbol": "SH.600000",
                "name": "浦发银行",
                "action": "关注买入",
                "current_weight": 0.0,
                "target_weight": 0.5,
                "weight_change": 0.5,
                "account_id": "",
                "strategy_id": "",
            },
            {
                "brief_date": "2026-07-01",
                "signal_date": "2026-06-30",
                "symbol": "SH.600000",
                "name": "浦发银行",
                "action": "关注卖出",
                "current_weight": 0.5,
                "target_weight": 0.0,
                "weight_change": -0.5,
                "account_id": "default",
                "strategy_id": "legacy_momentum_low_turnover_v1",
            },
        ]
    ).to_csv(brief_ledger, index=False, encoding="utf-8-sig")
    account = _account(tmp_path)
    local_history_cfg = {"path": "data/a_share_history.sqlite"}

    frames = collect_watchlist_frames(
        tmp_path,
        _watchlist(signal_date="2026-06-30", check_time="2026-07-01 07:30", target_weight="0.00%"),
        "2026-07-01",
        simulation_start_date="2026-06-30",
        account_id="default",
        strategy_id="legacy_momentum_low_turnover_v1",
    )
    ledger, latest = build_account_ledger(
        root=tmp_path,
        current_watchlist=_watchlist(signal_date="2026-06-30", check_time="2026-07-01 07:30", target_weight="0.00%"),
        current_brief_date="2026-07-01",
        account=account,
        local_history_cfg=local_history_cfg,
    )

    assert list(frames) == ["2026-06-30", "2026-07-01"]
    assert ledger["brief_date"].tolist() == ["2026-06-30", "2026-07-01"]
    assert latest["brief_date"] == "2026-07-01"
    assert _daily_asset_dates(account.database_path) == ["2026-06-30", "2026-07-01"]
    with sqlite3.connect(account.database_path) as conn:
        trade_dates = [
            str(row[0])
            for row in conn.execute("SELECT DISTINCT brief_date FROM account_trades ORDER BY brief_date").fetchall()
        ]
    assert trade_dates == ["2026-06-30", "2026-07-01"]


def test_account_ledger_persists_unfilled_order_events(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "a_share_history.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE market_daily_bars (
                market TEXT NOT NULL,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                adjust_type TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL
            );
            CREATE TABLE market_stocks (
                market TEXT NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT,
                list_date TEXT
            );
            """
        )
        conn.execute(
            """
            INSERT INTO market_daily_bars
            (market, symbol, date, adjust_type, open, high, low, close, volume, amount)
            VALUES ('CN', 'SH.600000', '2026-06-30', 'bfq', 10.0, 10.0, 10.0, 10.0, 1000000, 10000000.0)
            """
        )
        conn.execute(
            """
            INSERT INTO market_daily_bars
            (market, symbol, date, adjust_type, open, high, low, close, volume, amount)
            VALUES ('CN', 'SH.600000', '2026-07-01', 'bfq', 10.0, 10.0, 10.0, 10.0, 1, 10.0)
            """
        )
        conn.execute(
            "INSERT INTO market_stocks (market, symbol, name, list_date) VALUES ('CN', 'SH.600000', '浦发银行', '1999-11-10')"
        )
    account = replace(_account(tmp_path), max_participation_rate=0.05)
    local_history_cfg = {"path": "data/a_share_history.sqlite"}
    run_watchlist = tmp_path / "reports" / "runs" / "2026-06-30" / "20260630_090000__premarket__watchlist" / "premarket__watchlist.csv"
    run_watchlist.parent.mkdir(parents=True, exist_ok=True)
    _watchlist(signal_date="2026-06-29", check_time="2026-06-30 07:30", target_weight="50.00%").to_csv(
        run_watchlist,
        index=False,
        encoding="utf-8-sig",
    )

    ledger, latest = build_account_ledger(
        root=tmp_path,
        current_watchlist=_watchlist(signal_date="2026-06-30", check_time="2026-07-01 07:30", target_weight="0.00%"),
        current_brief_date="2026-07-01",
        account=account,
        local_history_cfg=local_history_cfg,
    )

    assert ledger["unfilled_orders"].tolist() == [0, 1]
    assert latest["block_reason_counts"] == '{"成交股数为0": 1}'
    with sqlite3.connect(account.database_path) as conn:
        rows = conn.execute(
            """
            SELECT brief_date, symbol, side, event_type, trade_status, requested_shares, filled_shares, block_reasons
            FROM account_order_events
            ORDER BY brief_date, symbol
            """
        ).fetchall()
    assert rows == [("2026-07-01", "SH.600000", "sell", "unfilled", "未成交", 5000.0, 0.0, "成交股数为0")]
