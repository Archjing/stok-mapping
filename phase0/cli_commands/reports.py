from __future__ import annotations

import argparse


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
