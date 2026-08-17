from __future__ import annotations

import argparse
import os
from datetime import date
from pathlib import Path
from typing import Any

from rich.console import Console

from quant.data_governance.adjustment import run_adjustment_audit
from quant.config import load_config
from quant.data_governance.db_health import run_database_health_check
from quant.data_governance.governance import run_governance_pass
from quant.data_governance.index_asof_audit import run_index_asof_audit
from quant.data_governance.sqlite_capacity import run_sqlite_capacity_audit


DATA_GOVERNANCE_COMMANDS = frozenset(
    {
        "adjustment-audit",
        "data-governance",
        "db-capacity",
        "db-health",
        "index-asof-audit",
    }
)


def register_data_governance_commands(subparsers: argparse._SubParsersAction) -> None:
    adjustment_parser = subparsers.add_parser(
        "adjustment-audit",
        help="Audit A-share price adjustment point-in-time readiness",
    )
    adjustment_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    adjustment_parser.add_argument("--output-csv", default=None, help="Optional CSV output path")
    adjustment_parser.add_argument("--output-md", default=None, help="Optional Markdown output path")

    index_asof_parser = subparsers.add_parser(
        "index-asof-audit",
        help="Audit benchmark constituent and weight as-of data readiness",
    )
    index_asof_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    index_asof_parser.add_argument(
        "--benchmark-symbol",
        default=None,
        help="Benchmark symbol; defaults to quant.benchmark_symbol",
    )
    index_asof_parser.add_argument(
        "--candidate-folds",
        default=None,
        help="Optional strategy_admission_candidate_folds.csv for fold-level coverage",
    )
    index_asof_parser.add_argument("--output-dir", default=None, help="Output directory for index as-of audit artifacts")

    db_health_parser = subparsers.add_parser("db-health", help="Run read-only SQLite database health checks")
    db_health_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    db_health_parser.add_argument(
        "--scope",
        choices=["all", "cn", "financial", "cross_market", "scheduler"],
        default="all",
        help="Health-check scope. Default: all",
    )
    db_health_parser.add_argument("--as-of", default=None, help="As-of date in YYYY-MM-DD. Defaults to today.")
    db_health_parser.add_argument("--output-dir", default=None, help="Output directory for health-check artifacts")
    db_health_parser.add_argument(
        "--fail-on",
        choices=["error", "warning", "never"],
        default="never",
        help="Exit with code 2 when result has errors, warnings, or never. Default: never.",
    )

    db_capacity_parser = subparsers.add_parser(
        "db-capacity",
        help="Run a read-only SQLite capacity, backup, and redundant-index audit",
    )
    db_capacity_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    db_capacity_parser.add_argument("--output-dir", default=None, help="Output directory for capacity artifacts")
    db_capacity_parser.add_argument(
        "--quick-check",
        action="store_true",
        help="Run PRAGMA quick_check for each database; slower for large files",
    )
    db_capacity_parser.add_argument(
        "--row-counts",
        action="store_true",
        help="Count rows in each user table; slower for large files",
    )

    governance_parser = subparsers.add_parser(
        "data-governance",
        help="Daily freshness check + automatic repair across local data databases",
    )
    governance_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    governance_parser.add_argument("--as-of", default=None, help="As-of date in YYYY-MM-DD. Defaults to today.")
    governance_parser.add_argument("--check-only", action="store_true", help="Report staleness without running repairs")
    governance_parser.add_argument("--no-journal-migration", action="store_true", help="Skip WAL journal-mode migration")


def handle_data_governance_command(args: argparse.Namespace, *, parser: argparse.ArgumentParser, console: Any | None = None) -> int:
    governance_console = console or Console()
    if args.cmd == "adjustment-audit":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        governance_console.print("[bold]A-share price adjustment audit started[/bold]")
        result = run_adjustment_audit(
            config=cfg,
            root=config_path.parent,
            output_csv=Path(args.output_csv).resolve() if args.output_csv else None,
            output_md=Path(args.output_md).resolve() if args.output_md else None,
        )
        color = "green" if result.can_build_qfq_asof else "yellow"
        governance_console.print(f"[{color}]Adjustment audit verdict: {result.verdict}[/{color}]")
        governance_console.print(f"Can build qfq_asof: {result.can_build_qfq_asof}")
        governance_console.print(f"CSV: {result.csv_path}")
        governance_console.print(f"Markdown: {result.md_path}")
        for warning in result.warnings[:10]:
            governance_console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0
    if args.cmd == "index-asof-audit":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg
        governance_console.print("[bold]Index as-of data audit started[/bold]")
        result = run_index_asof_audit(
            config=phase_cfg,
            root=config_path.parent,
            config_path=config_path,
            benchmark_symbol=args.benchmark_symbol,
            candidate_folds_path=Path(args.candidate_folds).resolve() if args.candidate_folds else None,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
            command=" ".join(os.sys.argv),
        )
        governance_console.print("[green]Index as-of data audit complete[/green]")
        governance_console.print(f"Benchmark: {result.benchmark_symbol}")
        governance_console.print(f"Database: {result.db_path}")
        governance_console.print(f"Constituents: {result.constituent_status}")
        governance_console.print(f"Weights: {result.weight_status}")
        governance_console.print(f"Fold rows: {result.fold_rows}")
        governance_console.print(f"Capability CSV: {result.capability_csv_path}")
        governance_console.print(f"Fold coverage CSV: {result.fold_coverage_csv_path}")
        governance_console.print(f"Markdown: {result.report_md_path}")
        governance_console.print(f"Run log: {result.run_log_md_path}")
        return 0
    if args.cmd == "db-capacity":
        config_path = Path(args.config).resolve()
        governance_console.print("[bold]SQLite capacity audit started[/bold]")
        result = run_sqlite_capacity_audit(
            root=config_path.parent,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
            quick_check=bool(args.quick_check),
            row_counts=bool(args.row_counts),
        )
        color = "green" if result.status == "pass" else ("yellow" if result.status == "warning" else "red")
        governance_console.print(f"[{color}]SQLite capacity audit status: {result.status}[/{color}]")
        governance_console.print(
            f"Databases: {result.database_count}; backups: {result.backup_count}; "
            f"warnings: {result.warning_count}; errors: {result.error_count}"
        )
        governance_console.print(f"JSON: {result.json_path}")
        governance_console.print(f"Markdown: {result.markdown_path}")
        return 2 if result.error_count else 0
    if args.cmd == "data-governance":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        governance_console.print("[bold]Data governance freshness pass started[/bold]")
        result = run_governance_pass(
            root=config_path.parent,
            cfg=cfg,
            as_of=date.fromisoformat(args.as_of) if args.as_of else None,
            repair=not args.check_only,
            check_only=bool(args.check_only),
        )
        color = "green" if result.repair_failed == 0 else "red"
        governance_console.print(
            f"[{color}]Governance: checked={result.checked} fresh={result.fresh} stale={result.stale} "
            f"empty={result.empty} errors={result.errors} repaired={result.repaired} repair_failed={result.repair_failed}[/{color}]"
        )
        for f in result.findings:
            if f.status != "fresh":
                governance_console.print(
                    f"  - {f.target.label}: {f.status} latest={f.latest or '-'} expected={f.expected} {f.detail}".rstrip()
                )
        if result.journal is not None:
            j = result.journal
            governance_console.print(
                f"Journal: scanned={j.scanned} migrated={len(j.migrated)} already_wal={len(j.already_wal)} failed={len(j.failed)}"
            )
            for rel in j.failed:
                governance_console.print(f"[red]  WAL failed: {rel}[/red]")
        return 2 if result.repair_failed else 0
    if args.cmd == "db-health":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        governance_console.print("[bold]Database health check started[/bold]")
        result = run_database_health_check(
            config=cfg,
            root=config_path.parent,
            scope=str(args.scope),
            as_of_date=str(args.as_of) if args.as_of else None,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
        )
        color = "green" if result.status == "pass" else ("yellow" if result.status == "warning" else "red")
        governance_console.print(f"[{color}]Database health status: {result.status}[/{color}]")
        governance_console.print(f"Summary rows: {result.summary_rows}")
        governance_console.print(
            f"Findings: errors={result.error_count}, warnings={result.warning_count}, info={result.info_count}"
        )
        governance_console.print(f"Summary CSV: {result.summary_csv}")
        governance_console.print(f"Findings CSV: {result.findings_csv}")
        governance_console.print(f"Markdown: {result.summary_md}")
        if args.fail_on == "error" and result.error_count > 0:
            return 2
        if args.fail_on == "warning" and (result.error_count > 0 or result.warning_count > 0):
            return 2
        return 0
    parser.error(
        "data governance command expected one of: "
        + ", ".join(sorted(DATA_GOVERNANCE_COMMANDS))
    )
    return 2
