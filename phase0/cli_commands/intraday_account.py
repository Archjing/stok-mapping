from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rich.console import Console

from phase0.execution.intraday_account_runner import (
    IntradayAccountRunError,
    run_configured_intraday_account,
)


INTRADAY_ACCOUNT_COMMANDS = {"intraday-account"}


def register_intraday_account_commands(subparsers: argparse._SubParsersAction) -> None:
    command = subparsers.add_parser(
        "intraday-account",
        help="Replay one configured 5-minute single-ETF simulated account",
    )
    command.add_argument("--account-id", required=True, help="Configured simulated account id")
    command.add_argument("--config", default="config.yaml", help="Path to config file")
    command.add_argument(
        "--as-of",
        default=None,
        help="Replay data visible through YYYY-MM-DD. Defaults to the current date.",
    )
    command.add_argument(
        "--write-state",
        action="store_true",
        help="Replace this account's local SQLite replay snapshot after a complete run",
    )
    command.add_argument("--json", action="store_true", help="Print the summary as JSON")


def handle_intraday_account_command(
    args: argparse.Namespace,
    *,
    parser: argparse.ArgumentParser,
    console: Any | None = None,
) -> int:
    if args.cmd not in INTRADAY_ACCOUNT_COMMANDS:
        parser.error("intraday account command expected")
        return 2

    output = console or Console()
    try:
        run = run_configured_intraday_account(
            config_path=Path(args.config),
            account_id=str(args.account_id),
            as_of_date=str(args.as_of) if args.as_of else None,
            write_state=bool(args.write_state),
        )
    except (IntradayAccountRunError, ValueError) as exc:
        output.print(f"[red]Intraday account replay failed:[/red] {exc}")
        return 2

    summary = run.summary()
    if bool(args.json):
        output.print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        output.print("[bold]5-minute single-ETF account replay complete[/bold]")
        output.print(f"Account: {summary['account_id']} ({summary['strategy_id']})")
        output.print(
            f"Window: {summary['panel_start_date']} -> {summary['panel_end_date']} "
            f"({summary['panel_sessions']} sessions, as-of {summary['as_of_date']})"
        )
        output.print(
            f"Signals: {summary['raw_signal_count']}; entries: {summary['entry_count']}; "
            f"completed round trips: {summary['completed_round_trip_count']}; "
            f"cancelled/unfilled: {summary['unfilled_order_count']}"
        )
        output.print(
            f"Annualized return: {summary['annualized_return']:.2%}; "
            f"Sharpe: {summary['sharpe']:.3f}; "
            f"max drawdown: {summary['max_drawdown']:.2%}; "
            f"final assets: {summary['final_assets']:,.2f}"
        )
        output.print(
            f"State: {summary['state_status']}; missing 5-minute days: "
            f"{summary['intraday_data_missing_days']}; SQLite written: {summary['state_written']}"
        )
        output.print(
            "Execution boundary: completed-bar, post-close replay. "
            "This command is not a live intraday order scheduler."
        )
    return 0 if summary["execution_complete"] else 2
