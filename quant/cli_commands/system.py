from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from rich.console import Console

from quant.maintenance_orchestrator import maintenance_status


def register_system_commands(subparsers: argparse._SubParsersAction) -> None:
    system_parser = subparsers.add_parser("system", help="System orchestrator commands")
    system_sub = system_parser.add_subparsers(dest="system_cmd")
    system_status_parser = system_sub.add_parser("status", help="Show read-only system status summary")
    system_status_parser.add_argument("--config", default="config.yaml", help="Path to config file")


def summarize_system_maintenance_status(result) -> dict[str, object]:
    last_run_status_counts = Counter(row.last_run_status or "not_available" for row in result.rows)
    last_decision_counts = Counter(row.last_decision or "not_available" for row in result.rows)
    shard_status_counts = Counter(shard.status or "not_available" for shard in result.shards)
    return {
        "task_count": len(result.rows),
        "last_run_status_counts": dict(sorted(last_run_status_counts.items())),
        "last_decision_counts": dict(sorted(last_decision_counts.items())),
        "running_shard_count": int(shard_status_counts.get("running", 0)),
        "shard_status_counts": dict(sorted(shard_status_counts.items())),
    }


def handle_system_command(args: argparse.Namespace, *, parser: argparse.ArgumentParser, console: Any | None = None) -> int:
    system_console = console or Console()
    if args.system_cmd == "status":
        config_path = Path(args.config).resolve()
        system_console.print("[bold]System status started[/bold]")
        maintenance_result = maintenance_status(config_path, refresh_state=False, read_only=True)
        summary = summarize_system_maintenance_status(maintenance_result)
        system_console.print("[green]System status complete[/green]")
        system_console.print(f"Maintenance state DB: {maintenance_result.state_db}")
        system_console.print(f"Maintenance generated at: {maintenance_result.generated_at}")
        system_console.print(f"Maintenance tasks: {summary['task_count']}")
        system_console.print(f"Maintenance last_run_status: {_format_counts(summary['last_run_status_counts'])}")
        system_console.print(f"Maintenance last_decision: {_format_counts(summary['last_decision_counts'])}")
        system_console.print(f"Maintenance running shards: {summary['running_shard_count']}")
        system_console.print(f"Maintenance shard_status: {_format_counts(summary['shard_status_counts'])}")
        return 0
    parser.error("system requires a subcommand: status")
    return 2


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
