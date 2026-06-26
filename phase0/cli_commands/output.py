from __future__ import annotations

from typing import Any

from rich.console import Console


def print_manual_history_update_result(console: Console, result: Any) -> None:
    color = "green" if result.ok else "red"
    console.print(f"[{color}]Manual history update status: {result.status}[/{color}]")
    console.print(f"Database: {result.db_path}")
    console.print(f"Calendar latest trade date: {result.calendar_trade_date}")
    console.print(f"Target trade date: {result.target_trade_date}")
    console.print(f"Before latest: {result.before_latest_date or 'N/A'} coverage={result.before_coverage:.4f}")
    console.print(f"After latest: {result.after_latest_date or 'N/A'} coverage={result.after_coverage:.4f}")
    console.print(f"Fetched rows: {result.fetched_rows}")
    console.print(f"Inserted rows: {result.inserted_rows}")
    console.print(f"Metadata updated rows: {result.metadata_updated_rows}")
    console.print(f"Primary source: {result.primary_source or 'N/A'}")
    if result.metadata_coverage:
        console.print(
            "Metadata coverage: "
            f"market_cap={result.metadata_coverage.get('market_cap', 0.0):.4f}, "
            f"pe={result.metadata_coverage.get('pe_ratio', 0.0):.4f}, "
            f"pb={result.metadata_coverage.get('pb_ratio', 0.0):.4f}, "
            f"turnover={result.metadata_coverage.get('turnover_rate', 0.0):.4f}"
        )
    if result.warnings:
        for warning in result.warnings:
            console.print(f"[yellow]Warning:[/yellow] {warning}")
