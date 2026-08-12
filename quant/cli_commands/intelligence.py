from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from rich.console import Console

from quant.intelligence import (
    collect_intelligence,
    import_local_intelligence,
    review_intelligence_candidates,
    validate_intelligence_ledger,
)


def register_intelligence_commands(subparsers: argparse._SubParsersAction) -> None:
    intelligence_parser = subparsers.add_parser(
        "intelligence",
        help="Collect, import, review, and validate strategy intelligence metadata",
    )
    intelligence_sub = intelligence_parser.add_subparsers(dest="intelligence_cmd")
    intelligence_collect_parser = intelligence_sub.add_parser(
        "collect",
        help="Collect configured intelligence metadata into an inbox CSV",
    )
    intelligence_collect_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    intelligence_collect_parser.add_argument("--output-csv", default=None, help="Optional candidate inbox CSV output path")
    intelligence_collect_parser.add_argument("--output-report", default=None, help="Optional Markdown report output path")
    intelligence_collect_parser.add_argument("--limit", type=int, default=None, help="Optional per-source row/file limit")
    intelligence_import_parser = intelligence_sub.add_parser(
        "import-local",
        help="Import local paper/report metadata into an inbox CSV",
    )
    intelligence_import_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    intelligence_import_parser.add_argument("--source-dir", default="refdocs/papers", help="Local source directory to scan")
    intelligence_import_parser.add_argument("--output-csv", default=None, help="Optional candidate inbox CSV output path")
    intelligence_import_parser.add_argument("--output-report", default=None, help="Optional Markdown report output path")
    intelligence_import_parser.add_argument("--limit", type=int, default=None, help="Optional file limit")
    intelligence_review_parser = intelligence_sub.add_parser(
        "review-candidates",
        help="Generate review suggestions for an intelligence inbox CSV",
    )
    intelligence_review_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    intelligence_review_parser.add_argument("--candidates-csv", required=True, help="Candidate inbox CSV to review")
    intelligence_review_parser.add_argument("--output-csv", default=None, help="Optional review suggestions CSV output path")
    intelligence_review_parser.add_argument("--output-report", default=None, help="Optional Markdown review report output path")
    intelligence_review_parser.add_argument("--limit", type=int, default=None, help="Optional candidate row limit")
    intelligence_review_parser.add_argument(
        "--excerpt-chars",
        type=int,
        default=2000,
        help="Maximum source excerpt chars per candidate",
    )
    intelligence_validate_parser = intelligence_sub.add_parser(
        "validate",
        help="Validate the strategy intelligence ledger CSV",
    )
    intelligence_validate_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    intelligence_validate_parser.add_argument("--ledger", default=None, help="Ledger CSV path. Defaults to config intelligence.ledger")
    intelligence_validate_parser.add_argument("--output-report", default=None, help="Optional Markdown validation report output path")


def handle_intelligence_command(args: argparse.Namespace, *, parser: argparse.ArgumentParser, console: Any | None = None) -> int:
    intelligence_console = console or Console()
    if args.intelligence_cmd == "collect":
        config_path = Path(args.config).resolve()
        intelligence_console.print("[bold]Strategy intelligence collect started[/bold]")
        result = collect_intelligence(
            config_path,
            output_csv=args.output_csv,
            output_report=args.output_report,
            limit=args.limit,
        )
        color = "green" if result.status == "ok" else "yellow"
        intelligence_console.print(f"[{color}]Intelligence collect status: {result.status}[/{color}]")
        intelligence_console.print(f"Candidate rows: {result.rows}")
        intelligence_console.print(f"Candidate CSV: {result.candidates_csv}")
        intelligence_console.print(f"Markdown: {result.report_md}")
        for warning in (result.warnings or [])[:10]:
            intelligence_console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0
    if args.intelligence_cmd == "import-local":
        config_path = Path(args.config).resolve()
        intelligence_console.print("[bold]Strategy intelligence local import started[/bold]")
        result = import_local_intelligence(
            config_path,
            source_dir=args.source_dir,
            output_csv=args.output_csv,
            output_report=args.output_report,
            limit=args.limit,
        )
        color = "green" if result.status == "ok" else "yellow"
        intelligence_console.print(f"[{color}]Intelligence import status: {result.status}[/{color}]")
        intelligence_console.print(f"Candidate rows: {result.rows}")
        intelligence_console.print(f"Candidate CSV: {result.candidates_csv}")
        intelligence_console.print(f"Markdown: {result.report_md}")
        for warning in (result.warnings or [])[:10]:
            intelligence_console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0
    if args.intelligence_cmd == "review-candidates":
        config_path = Path(args.config).resolve()
        intelligence_console.print("[bold]Strategy intelligence candidate review started[/bold]")
        result = review_intelligence_candidates(
            config_path,
            candidates_csv=args.candidates_csv,
            output_csv=args.output_csv,
            output_report=args.output_report,
            limit=args.limit,
            excerpt_chars=args.excerpt_chars,
        )
        color = "green" if result.status == "ok" else "yellow"
        intelligence_console.print(f"[{color}]Intelligence review status: {result.status}[/{color}]")
        intelligence_console.print(f"Rows: {result.row_count}")
        intelligence_console.print(f"Review CSV: {result.review_csv}")
        intelligence_console.print(f"Markdown: {result.report_md}")
        for warning in result.warnings[:10]:
            intelligence_console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0
    if args.intelligence_cmd == "validate":
        config_path = Path(args.config).resolve()
        intelligence_console.print("[bold]Strategy intelligence ledger validation started[/bold]")
        result = validate_intelligence_ledger(
            config_path,
            ledger=args.ledger,
            output_report=args.output_report,
        )
        color = "green" if result.status == "ok" else "red"
        intelligence_console.print(f"[{color}]Intelligence validation status: {result.status}[/{color}]")
        intelligence_console.print(f"Rows: {result.row_count}")
        intelligence_console.print(f"Errors: {result.error_count}")
        intelligence_console.print(f"Warnings: {result.warning_count}")
        intelligence_console.print(f"Markdown: {result.report_md}")
        for error in result.errors[:10]:
            intelligence_console.print(f"[red]Error:[/red] {error}")
        for warning in result.warnings[:10]:
            intelligence_console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 2 if result.error_count > 0 else 0
    parser.error("intelligence requires a subcommand: collect, import-local, review-candidates, or validate")
    return 2
