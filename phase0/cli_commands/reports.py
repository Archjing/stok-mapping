from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from rich.console import Console

from phase0.reporting.exports import (
    export_phase0_execution_gate,
    export_phase0_financial_pti,
    export_phase0_low_turnover_bill,
    export_phase0_market_regime_report,
    export_phase0_oos_report,
    export_phase0_premarket,
    export_phase0_universe_pit,
)


REPORT_EXPORT_COMMANDS = frozenset(
    {
        "bill",
        "market-regime",
        "oos-report",
        "financial-pti",
        "universe-pti",
        "premarket",
        "execution-gate",
    }
)


def register_report_export_commands(subparsers: argparse._SubParsersAction) -> None:
    bill_parser = subparsers.add_parser("bill", help="Export selected phase0 strategy bill artifacts")
    bill_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    bill_parser.add_argument("--strategy-id", default=None, help="Registered strategy ID; defaults to strategy_reports.default_strategy_id")
    bill_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    bill_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")

    market_regime_parser = subparsers.add_parser("market-regime", help="Export phase0 market-regime validation report")
    market_regime_parser.add_argument("--config", default="config.yaml", help="Path to config file")

    oos_parser = subparsers.add_parser("oos-report", help="Export phase0 continuous OOS report with execution profile")
    oos_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    oos_parser.add_argument("--strategy-id", default=None, help="Registered strategy ID; defaults to strategy_reports.default_strategy_id")
    _add_execution_profile_args(oos_parser, output_help="Optional standalone output directory for OOS artifacts")
    oos_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    oos_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")

    financial_pti_parser = subparsers.add_parser("financial-pti", help="Audit financial factor point-in-time validity")
    financial_pti_parser.add_argument("--config", default="config.yaml", help="Path to config file")

    universe_pti_parser = subparsers.add_parser("universe-pti", help="Audit point-in-time universe listing and industry boundaries")
    universe_pti_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    universe_pti_parser.add_argument("--date", required=True, help="As-of date in YYYY-MM-DD")

    premarket_parser = subparsers.add_parser("premarket", help="Export phase0 07:30 premarket watchlist")
    premarket_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    premarket_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    premarket_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")

    execution_gate_parser = subparsers.add_parser("execution-gate", help="Run phase0 account execution effectiveness gate")
    execution_gate_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    execution_gate_parser.add_argument("--strategy-id", default=None, help="Registered strategy ID; defaults to strategy_reports.default_strategy_id")
    _add_execution_profile_args(execution_gate_parser, output_help="Optional standalone output directory for live execution backtest artifacts")
    execution_gate_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    execution_gate_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")


def handle_report_export_command(args: argparse.Namespace, *, parser: argparse.ArgumentParser, console: Any | None = None) -> int:
    report_console = console or Console()
    if args.cmd == "bill":
        config_path = Path(args.config).resolve()
        report_console.print("[bold]Phase 0 bill export started[/bold]")
        result = export_phase0_low_turnover_bill(
            config_path=config_path,
            strategy_id=args.strategy_id,
            refresh_cache=bool(args.refresh_cache),
            no_panel_cache=bool(args.no_panel_cache),
        )
        report_console.print("[green]Bill export complete[/green]")
        report_console.print(f"Strategy: {result.get('strategy_id', '')}")
        report_console.print(f"Bill: {result['bill']}")
        report_console.print(f"Daily assets: {result['daily']}")
        report_console.print(f"Preview: {result['preview']}")
        report_console.print(f"Rows: {result['rows']}")
        return 0
    if args.cmd == "market-regime":
        report_console.print("[bold]Phase 0 market-regime report started[/bold]")
        result = export_phase0_market_regime_report()
        report_console.print("[green]Market-regime report complete[/green]")
        report_console.print(f"Summary: {result['summary']}")
        report_console.print(f"Segments: {result['segments']}")
        report_console.print(f"HTML: {result['html']}")
        report_console.print(f"Rows: {result['rows']}")
        return 0
    if args.cmd == "oos-report":
        config_path = Path(args.config).resolve()
        report_console.print("[bold]Phase 0 OOS report started[/bold]")
        result = export_phase0_oos_report(
            config_path=config_path,
            strategy_id=args.strategy_id,
            profile=args.profile,
            output_dir=args.output_dir,
            refresh_cache=bool(args.refresh_cache),
            no_panel_cache=bool(args.no_panel_cache),
            slippage=args.slippage,
            commission=args.commission,
            stamp_duty_sell=args.stamp_duty_sell,
            price_mode=args.price_mode,
            lot_size=args.lot_size,
            max_participation_rate=args.max_participation_rate,
            enable_limit_check=args.enable_limit_check,
            enable_suspension_check=args.enable_suspension_check,
        )
        report_console.print("[green]OOS report complete[/green]")
        report_console.print(f"Strategy: {result.get('strategy_id', '')}")
        report_console.print(f"Profile: {result['profile']}")
        report_console.print(f"Daily assets: {result['daily_assets']}")
        report_console.print(f"Report: {result['report']}")
        report_console.print(f"Curve: {result['curve']}")
        report_console.print(f"Fold: {result['fold']}")
        return 0
    if args.cmd == "financial-pti":
        config_path = Path(args.config).resolve()
        report_console.print("[bold]Phase 0 financial PTI audit started[/bold]")
        result = export_phase0_financial_pti(config_path)
        report_console.print("[green]Financial PTI audit complete[/green]")
        report_console.print(f"Verdict: {result['verdict']}")
        report_console.print(f"Summary: {result['summary']}")
        report_console.print(f"Samples: {result['samples']}")
        report_console.print(f"HTML: {result['html']}")
        return 0
    if args.cmd == "universe-pti":
        config_path = Path(args.config).resolve()
        report_console.print("[bold]Phase 0 universe PTI audit started[/bold]")
        result = export_phase0_universe_pit(config_path, as_of_date=str(args.date))
        report_console.print("[green]Universe PTI audit complete[/green]")
        report_console.print(f"Report: {result['report']}")
        report_console.print(f"Selected count: {result['selected_count']}")
        report_console.print(f"Boundary violations: {result['boundary_violations']}")
        report_console.print(f"Historical industry constraint effective: {result['industry_effective']}")
        return 0
    if args.cmd == "premarket":
        config_path = Path(args.config).resolve()
        report_console.print("[bold]Phase 0 premarket watchlist started[/bold]")
        result = export_phase0_premarket(
            config_path=config_path,
            refresh_cache=bool(args.refresh_cache),
            no_panel_cache=bool(args.no_panel_cache),
        )
        report_console.print("[green]Premarket watchlist complete[/green]")
        report_console.print(f"Watchlist: {result['watchlist']}")
        report_console.print(f"Report: {result['report']}")
        report_console.print(f"Rows: {result['rows']}")
        report_console.print(f"Signal date: {result['signal_date']}")
        report_console.print(f"Check time: {result['check_time']}")
        return 0
    if args.cmd == "execution-gate":
        config_path = Path(args.config).resolve()
        report_console.print("[bold]Phase 0 account execution gate started[/bold]")
        result = export_phase0_execution_gate(
            config_path=config_path,
            strategy_id=args.strategy_id,
            profile=args.profile,
            output_dir=args.output_dir,
            refresh_cache=bool(args.refresh_cache),
            no_panel_cache=bool(args.no_panel_cache),
            slippage=args.slippage,
            commission=args.commission,
            stamp_duty_sell=args.stamp_duty_sell,
            price_mode=args.price_mode,
            lot_size=args.lot_size,
            max_participation_rate=args.max_participation_rate,
            enable_limit_check=args.enable_limit_check,
            enable_suspension_check=args.enable_suspension_check,
        )
        report_console.print("[green]Account execution gate complete[/green]")
        report_console.print(f"Strategy: {result.get('strategy_id', '')}")
        report_console.print(f"Verdict: {result['verdict']}")
        report_console.print(f"Folds: {result['folds']}")
        report_console.print(f"Report: {result['report']}")
        return 0
    parser.error(
        "report export command expected one of: "
        + ", ".join(sorted(REPORT_EXPORT_COMMANDS))
    )
    return 2


def _add_execution_profile_args(parser: argparse.ArgumentParser, *, output_help: str) -> None:
    parser.add_argument("--profile", choices=["research", "live"], default=None, help="Execution parameter profile: research or live")
    parser.add_argument("--output-dir", default=None, help=output_help)
    parser.add_argument("--slippage", type=float, default=None, help="Override profile slippage for this run")
    parser.add_argument("--commission", type=float, default=None, help="Override profile commission for this run")
    parser.add_argument("--stamp-duty-sell", type=float, default=None, help="Override profile sell stamp duty for this run")
    parser.add_argument("--price-mode", choices=["close", "next_open", "conservative"], default=None, help="Override profile execution price mode")
    parser.add_argument("--lot-size", type=int, default=None, help="Override profile lot size")
    parser.add_argument("--max-participation-rate", type=float, default=None, help="Override profile max market-volume participation rate")
    parser.add_argument("--enable-limit-check", action=argparse.BooleanOptionalAction, default=None, help="Override profile limit-up/down check")
    parser.add_argument("--enable-suspension-check", action=argparse.BooleanOptionalAction, default=None, help="Override profile suspension check")
