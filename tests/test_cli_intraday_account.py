from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from phase0.cli_commands import intraday_account as intraday_cli
from phase0.execution import intraday_account_runner as account_runner


class CaptureConsole:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def print(self, value: object) -> None:
        self.lines.append(str(value))


def test_register_intraday_account_command() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    intraday_cli.register_intraday_account_commands(subparsers)

    args = parser.parse_args(
        [
            "intraday-account",
            "--account-id",
            "semiconductor_timing",
            "--as-of",
            "2026-08-11",
            "--recover-missing",
            "--json",
        ]
    )

    assert args.account_id == "semiconductor_timing"
    assert args.as_of == "2026-08-11"
    assert args.recover_missing is True
    assert args.json is True


def test_handler_runs_replay_and_prints_machine_readable_summary(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []
    summary = {
        "account_id": "semiconductor_timing",
        "strategy_id": "cross_market_semiconductor_timing_etf_v1",
        "execution_model": "single_etf_intraday",
        "execution_scope": "post_close_5min_replay",
        "as_of_date": "2026-08-11",
        "panel_start_date": "2021-08-09",
        "panel_end_date": "2026-08-11",
        "panel_sessions": 1257,
        "target_symbol": "SH.512480",
        "raw_signal_count": 339,
        "entry_count": 213,
        "exit_count": 213,
        "completed_round_trip_count": 213,
        "trade_count": 426,
        "unfilled_order_count": 25,
        "intraday_data_missing_days": 0,
        "intraday_data_missing_dates": [],
        "state_status": "complete_flat",
        "execution_complete": True,
        "open_position_shares": 0.0,
        "planned_exit_date": "",
        "annualized_return": 0.1196,
        "sharpe": 0.668,
        "max_drawdown": -0.2835,
        "final_assets": 337891.27,
        "trade_reason_counts": {},
        "state_written": False,
        "state_database_path": "accounts.sqlite",
        "intraday_database_path": "etf.sqlite",
    }

    def fake_run(**kwargs: object) -> SimpleNamespace:
        calls.append(kwargs)
        return SimpleNamespace(summary=lambda: summary)

    monkeypatch.setattr(intraday_cli, "run_configured_intraday_account", fake_run)
    console = CaptureConsole()
    args = SimpleNamespace(
        cmd="intraday-account",
        account_id="semiconductor_timing",
        config=str(tmp_path / "config.yaml"),
        as_of="2026-08-11",
        recover_missing=False,
        json=True,
    )

    exit_code = intraday_cli.handle_intraday_account_command(
        args,
        parser=argparse.ArgumentParser(),
        console=console,
    )

    assert exit_code == 0
    assert calls == [
        {
            "config_path": Path(tmp_path / "config.yaml"),
            "account_id": "semiconductor_timing",
            "as_of_date": "2026-08-11",
            "recover_missing": False,
        }
    ]
    assert json.loads(console.lines[0]) == summary


def test_handler_returns_two_for_incomplete_replay(monkeypatch, tmp_path: Path) -> None:
    summary = {
        "execution_complete": False,
        "account_id": "test",
        "strategy_id": "test",
        "panel_start_date": "2026-08-11",
        "panel_end_date": "2026-08-11",
        "panel_sessions": 1,
        "as_of_date": "2026-08-11",
        "raw_signal_count": 1,
        "entry_count": 1,
        "completed_round_trip_count": 0,
        "unfilled_order_count": 0,
        "annualized_return": 0.0,
        "sharpe": 0.0,
        "max_drawdown": 0.0,
        "final_assets": 100000.0,
        "state_status": "blocked_missing_exit_data",
        "intraday_data_missing_days": 1,
        "state_written": False,
    }
    monkeypatch.setattr(
        intraday_cli,
        "run_configured_intraday_account",
        lambda **kwargs: SimpleNamespace(summary=lambda: summary),
    )

    exit_code = intraday_cli.handle_intraday_account_command(
        SimpleNamespace(
            cmd="intraday-account",
            account_id="test",
            config=str(tmp_path / "config.yaml"),
            as_of=None,
            recover_missing=False,
            json=False,
        ),
        parser=argparse.ArgumentParser(),
        console=CaptureConsole(),
    )

    assert exit_code == 2


def test_configured_accounts_with_shared_strategy_keep_target_symbols_isolated(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    etf_db = tmp_path / "etf.sqlite"
    us_db = tmp_path / "data" / "us_market_history.sqlite"
    us_db.parent.mkdir(parents=True)
    etf_db.touch()
    us_db.touch()
    calls: list[str] = []

    class Strategy:
        account_execution_model = "single_etf_intraday"

        def account_execution_params(self, strategy_cfg):
            return {"target_symbol": strategy_cfg["cross_market_semiconductor_timing"]["target_symbol"]}

        def build_metadata(self, params):
            return {
                "account_execution_policy": {
                    "target_symbol": params["target_symbol"],
                    "return_threshold": 0.005,
                    "volatility_threshold": 19.0,
                    "strong_signal_threshold": 0.01,
                    "trailing_drawdown": 0.02,
                }
            }

        def prepare_panel(self, _panel, strategy_cfg):
            calls.append(strategy_cfg["cross_market_semiconductor_timing"]["target_symbol"])
            return pd.DataFrame(
                {
                    "date": pd.to_datetime(["2026-08-11"]),
                    "symbol": [calls[-1]],
                    "open": [1.0],
                    "close": [1.0],
                    "sox_ret": [0.0],
                    "vix_close": [20.0],
                }
            )

    config = {
        "walk_forward": {"strategy_v2": {"cross_market_semiconductor_timing": {"target_symbol": "SH.512480"}}},
        "accounts": {
            "simulated": [
                {
                    "account_id": "etf_512480",
                    "name": "512480",
                    "initial_cash": 100000,
                    "strategy_id": "cross_market_semiconductor_timing_etf_v1",
                    "execution_model": "single_etf_intraday",
                    "intraday_data_path": "etf.sqlite",
                    "strategy_params": {"target_symbol": "SH.512480"},
                },
                {
                    "account_id": "etf_512760",
                    "name": "512760",
                    "initial_cash": 100000,
                    "strategy_id": "cross_market_semiconductor_timing_etf_v1",
                    "execution_model": "single_etf_intraday",
                    "intraday_data_path": "etf.sqlite",
                    "strategy_params": {"target_symbol": "SH.512760"},
                },
            ]
        },
    }
    monkeypatch.setattr(account_runner, "load_config", lambda _path: config)
    monkeypatch.setattr(account_runner, "get_strategy", lambda _strategy_id: Strategy())
    monkeypatch.setattr(
        account_runner,
        "run_single_etf_intraday_account_execution",
        lambda **_kwargs: SimpleNamespace(metrics={"account_execution_complete": True}),
    )

    first = account_runner.run_configured_intraday_account(
        config_path=config_path, account_id="etf_512480", as_of_date="2026-08-11"
    )
    second = account_runner.run_configured_intraday_account(
        config_path=config_path, account_id="etf_512760", as_of_date="2026-08-11"
    )

    assert calls == ["SH.512480", "SH.512760"]
    assert first.policy.target_symbol == "SH.512480"
    assert second.policy.target_symbol == "SH.512760"


def test_intraday_account_includes_as_of_session_when_daily_panel_lags(monkeypatch, tmp_path: Path) -> None:
    """A first account session must not wait for the daily-bar importer."""
    config_path = tmp_path / "config.yaml"
    etf_db = tmp_path / "etf.sqlite"
    us_db = tmp_path / "data" / "us_market_history.sqlite"
    etf_db.touch()
    us_db.parent.mkdir(parents=True)
    us_db.touch()
    captured: dict[str, pd.DataFrame] = {}

    class Strategy:
        account_execution_model = "single_etf_intraday"

        def account_execution_params(self, _strategy_cfg):
            return {"target_symbol": "SH.512480"}

        def build_metadata(self, _params):
            return {
                "account_execution_policy": {
                    "target_symbol": "SH.512480",
                    "return_threshold": 0.005,
                    "volatility_threshold": 19.0,
                    "strong_signal_threshold": 0.01,
                    "trailing_drawdown": 0.02,
                }
            }

        def prepare_panel(self, _panel, _strategy_cfg):
            return pd.DataFrame(
                {
                    "date": pd.to_datetime(["2026-08-11"]),
                    "symbol": ["SH.512480"],
                    "open": [1.07],
                    "close": [1.07],
                    "sox_ret": [0.0],
                    "vix_close": [20.0],
                }
            )

        def prepare_intraday_account_session(self, _strategy_cfg):
            return pd.DataFrame(
                {
                    "date": pd.to_datetime(["2026-08-12"]),
                    "symbol": ["SH.512480"],
                    "open": [1.073],
                    "close": [1.088],
                    "sox_ret": [0.00872],
                    "vix_close": [15.28],
                }
            )

    config = {
        "walk_forward": {"strategy_v2": {"cross_market_semiconductor_timing": {}}},
        "accounts": {
            "simulated": [
                {
                    "account_id": "semiconductor_timing",
                    "name": "Semiconductor timing",
                    "initial_cash": 200000,
                    "strategy_id": "cross_market_semiconductor_timing_etf_v1",
                    "execution_model": "single_etf_intraday",
                    "intraday_data_path": "etf.sqlite",
                    "simulation_start_date": "2026-08-12",
                }
            ]
        },
    }
    monkeypatch.setattr(account_runner, "load_config", lambda _path: config)
    monkeypatch.setattr(account_runner, "get_strategy", lambda _strategy_id: Strategy())

    def fake_execute(*, signal_frame, **_kwargs):
        captured["panel"] = signal_frame.copy()
        return SimpleNamespace(metrics={"account_execution_complete": True})

    monkeypatch.setattr(account_runner, "run_single_etf_intraday_account_execution", fake_execute)

    run = account_runner.run_configured_intraday_account(
        config_path=config_path,
        account_id="semiconductor_timing",
        as_of_date="2026-08-12",
    )

    assert captured["panel"]["date"].tolist() == [pd.Timestamp("2026-08-12")]
    assert captured["panel"].iloc[0]["sox_ret"] == 0.00872
    assert run.panel["date"].tolist() == [pd.Timestamp("2026-08-12")]


def test_intraday_account_appends_as_of_session_when_history_already_exists(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    etf_db = tmp_path / "etf.sqlite"
    us_db = tmp_path / "data" / "us_market_history.sqlite"
    etf_db.touch()
    us_db.parent.mkdir(parents=True)
    us_db.touch()
    captured: dict[str, pd.DataFrame] = {}

    class Strategy:
        account_execution_model = "single_etf_intraday"

        def account_execution_params(self, _strategy_cfg):
            return {"target_symbol": "SH.512480"}

        def build_metadata(self, _params):
            return {
                "account_execution_policy": {
                    "target_symbol": "SH.512480",
                    "return_threshold": 0.005,
                    "volatility_threshold": 19.0,
                    "strong_signal_threshold": 0.01,
                    "trailing_drawdown": 0.02,
                }
            }

        def prepare_panel(self, _panel, _strategy_cfg):
            return pd.DataFrame(
                {
                    "date": pd.to_datetime(["2026-08-11"]),
                    "symbol": ["SH.512480"],
                    "open": [1.07],
                    "close": [1.07],
                    "sox_ret": [0.0],
                    "vix_close": [20.0],
                }
            )

        def prepare_intraday_account_session(self, _strategy_cfg):
            return pd.DataFrame(
                {
                    "date": pd.to_datetime(["2026-08-12"]),
                    "symbol": ["SH.512480"],
                    "open": [1.073],
                    "close": [1.088],
                    "sox_ret": [0.00872],
                    "vix_close": [15.28],
                }
            )

    config = {
        "walk_forward": {"strategy_v2": {"cross_market_semiconductor_timing": {}}},
        "accounts": {
            "simulated": [
                {
                    "account_id": "semiconductor_timing",
                    "name": "Semiconductor timing",
                    "initial_cash": 200000,
                    "strategy_id": "cross_market_semiconductor_timing_etf_v1",
                    "execution_model": "single_etf_intraday",
                    "intraday_data_path": "etf.sqlite",
                    "simulation_start_date": "2026-08-11",
                }
            ]
        },
    }
    monkeypatch.setattr(account_runner, "load_config", lambda _path: config)
    monkeypatch.setattr(account_runner, "get_strategy", lambda _strategy_id: Strategy())
    def fake_execute(*, signal_frame, **_kwargs):
        captured["panel"] = signal_frame.copy()
        return SimpleNamespace(metrics={"account_execution_complete": True})

    monkeypatch.setattr(account_runner, "run_single_etf_intraday_account_execution", fake_execute)

    account_runner.run_configured_intraday_account(
        config_path=config_path,
        account_id="semiconductor_timing",
        as_of_date="2026-08-12",
    )

    assert captured["panel"]["date"].tolist() == [
        pd.Timestamp("2026-08-11"),
        pd.Timestamp("2026-08-12"),
    ]
