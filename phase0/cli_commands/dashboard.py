from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from rich.console import Console

from phase0.reporting.registry import scan_report_artifacts, write_report_manifest


def register_dashboard_commands(subparsers: argparse._SubParsersAction) -> None:
    dashboard_parser = subparsers.add_parser("dashboard", help="Report dashboard commands")
    dashboard_sub = dashboard_parser.add_subparsers(dest="dashboard_cmd")
    dashboard_scan_parser = dashboard_sub.add_parser("scan", help="Scan reports and write dashboard manifest")
    dashboard_scan_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    dashboard_scan_parser.add_argument("--manifest", default=None, help="Optional manifest output path")


def handle_dashboard_command(args: argparse.Namespace, *, parser: argparse.ArgumentParser, console: Any | None = None) -> int:
    dashboard_console = console or Console()
    if args.dashboard_cmd == "scan":
        config_path = Path(args.config).resolve()
        root = config_path.parent
        manifest_path = Path(args.manifest).resolve() if args.manifest else None
        dashboard_console.print("[bold]Report dashboard scan started[/bold]")
        manifest = write_report_manifest(root=root, manifest_path=manifest_path)
        artifacts = scan_report_artifacts(root)
        run_count = len({artifact.run_id for artifact in artifacts})
        type_counts = Counter(artifact.type for artifact in artifacts)
        category_counts = Counter(artifact.legacy_category for artifact in artifacts)
        dashboard_console.print("[green]Report dashboard scan complete[/green]")
        dashboard_console.print(f"Manifest: {manifest}")
        dashboard_console.print(f"Runs: {run_count}")
        dashboard_console.print(f"Artifacts: {len(artifacts)}")
        dashboard_console.print(f"Artifact types: {_format_counts(dict(type_counts))}")
        dashboard_console.print(f"Categories: {_format_counts(dict(category_counts))}")
        return 0
    parser.error("dashboard requires a subcommand: scan")
    return 2


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
