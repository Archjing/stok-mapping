from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from rich.console import Console

from quant.maintenance_orchestrator import (
    maintenance_resume,
    maintenance_run_long_task,
    maintenance_status,
    maintenance_stop,
    maintenance_supervise,
    maintenance_tick,
)


def register_maintenance_commands(subparsers: argparse._SubParsersAction) -> None:
    maintain_parser = subparsers.add_parser("maintain", help="Maintenance orchestrator commands")
    maintain_sub = maintain_parser.add_subparsers(dest="maintain_cmd")
    maintain_tick_parser = maintain_sub.add_parser("tick", help="Evaluate scheduled maintenance tasks")
    maintain_tick_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    maintain_tick_parser.add_argument("--dry-run", action="store_true", help="Only evaluate scheduling decisions, do not start tasks")
    maintain_tick_parser.add_argument("--as-of", default=None, help="Optional local time in YYYY-MM-DD HH:MM")
    maintain_status_parser = maintain_sub.add_parser("status", help="Show maintenance orchestrator task status")
    maintain_status_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    maintain_status_parser.add_argument("--write-report", action="store_true", help="Write the default Markdown maintenance report")
    maintain_status_parser.add_argument("--output-md", default=None, help="Optional Markdown report path")
    maintain_supervise_parser = maintain_sub.add_parser(
        "supervise",
        help="Refresh long-running shard status without starting or stopping tasks",
    )
    maintain_supervise_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    maintain_supervise_parser.add_argument("--task", choices=["tushare_financial_backfill"], default="tushare_financial_backfill", help="Task name")
    maintain_supervise_parser.add_argument("--run-id", type=int, default=None, help="Optional run id")
    maintain_supervise_parser.add_argument("--dry-run", action="store_true", help="Show candidate status updates without writing them")
    maintain_run_parser = maintain_sub.add_parser("run", help="Start an orchestrated maintenance task")
    maintain_run_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    maintain_run_parser.add_argument("--task", required=True, choices=["tushare_financial_backfill"], help="Task name")
    maintain_run_parser.add_argument("--start-period", default="2018-06-30", help="Financial start period in YYYY-MM-DD")
    maintain_run_parser.add_argument("--end-period", default="2026-03-31", help="Financial end period in YYYY-MM-DD")
    maintain_run_parser.add_argument("--shard-count", type=int, default=3, help="Number of shards. Default: 3")
    maintain_run_parser.add_argument("--max-requests-per-minute", type=int, default=67, help="Per-shard request throttle. Default: 67")
    maintain_run_parser.add_argument("--retry-failed", action=argparse.BooleanOptionalAction, default=True, help="Retry failed backfill tasks")
    maintain_run_parser.add_argument("--missing-fields-only", action="store_true", help="Only patch rows that have missing fields")
    maintain_run_parser.add_argument("--limit-tasks", type=int, default=None, help="Optional per-shard task limit")
    maintain_run_parser.add_argument("--dry-run", action="store_true", help="Register shard commands without starting processes")
    maintain_stop_parser = maintain_sub.add_parser("stop", help="Stop an orchestrated long-running task")
    maintain_stop_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    maintain_stop_parser.add_argument("--task", choices=["tushare_financial_backfill"], default="tushare_financial_backfill", help="Task name")
    maintain_stop_parser.add_argument("--run-id", type=int, default=None, help="Optional run id")
    maintain_stop_parser.add_argument("--dry-run", action="store_true", help="Show matched shards without stopping them")
    maintain_resume_parser = maintain_sub.add_parser("resume", help="Resume non-running, non-succeeded shards")
    maintain_resume_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    maintain_resume_parser.add_argument("--task", choices=["tushare_financial_backfill"], default="tushare_financial_backfill", help="Task name")
    maintain_resume_parser.add_argument("--run-id", type=int, default=None, help="Optional run id")
    maintain_resume_parser.add_argument("--dry-run", action="store_true", help="Show matched shards without restarting them")


def handle_maintenance_command(args: argparse.Namespace, *, parser: argparse.ArgumentParser, console: Any | None = None) -> int:
    maintenance_console = console or Console()
    if args.maintain_cmd == "tick":
        config_path = Path(args.config).resolve()
        maintenance_console.print("[bold]Maintenance tick started[/bold]")
        result = maintenance_tick(
            config_path,
            as_of=args.as_of,
            dry_run=bool(args.dry_run),
        )
        maintenance_console.print("[green]Maintenance tick complete[/green]")
        maintenance_console.print(f"State DB: {result.state_db}")
        maintenance_console.print(f"As of: {result.as_of}")
        maintenance_console.print(f"Dry run: {result.dry_run}")
        maintenance_console.print(f"Executed runs: {result.executed_runs}")
        for item in result.decisions:
            color = "green" if item.decision == "will_run" else ("yellow" if item.decision == "skipped" else "red")
            maintenance_console.print(
                f"[{color}]{item.task_name}[/{color}] "
                f"{item.decision} at {item.scheduled_time} | {item.reason}"
            )
        return 0
    if args.maintain_cmd == "status":
        config_path = Path(args.config).resolve()
        maintenance_console.print("[bold]Maintenance status started[/bold]")
        result = maintenance_status(
            config_path,
            output_md=Path(args.output_md).resolve() if args.output_md else None,
            write_report=bool(args.write_report),
        )
        maintenance_console.print("[green]Maintenance status complete[/green]")
        maintenance_console.print(f"State DB: {result.state_db}")
        maintenance_console.print(f"Generated at: {result.generated_at}")
        if result.report_path:
            maintenance_console.print(f"Report: {result.report_path}")
        for row in result.rows:
            maintenance_console.print(
                f"{row.task_name}: enabled={row.enabled}, schedule={row.schedule_value}, "
                f"last_decision={row.last_decision}, last_reason={row.last_reason}, "
                f"last_run={row.last_run_status}, log={row.log_path}"
            )
        if result.shards:
            maintenance_console.print("[bold]Maintenance shards[/bold]")
            for shard in result.shards[:20]:
                maintenance_console.print(
                    f"run={shard.run_id} task={shard.task_name} shard={shard.shard_index}/{shard.shard_count} "
                    f"status={shard.status} pid={shard.pid} log={shard.log_path}"
                )
                if shard.report_path or shard.error_summary or shard.key_conclusion:
                    maintenance_console.print(
                        f"  report={shard.report_path or 'N/A'} error={shard.error_summary or 'N/A'} "
                        f"conclusion={shard.key_conclusion or 'N/A'}"
                    )
        return 0
    if args.maintain_cmd == "supervise":
        config_path = Path(args.config).resolve()
        result = maintenance_supervise(
            config_path,
            task_name=args.task,
            run_id=args.run_id,
            dry_run=bool(args.dry_run),
        )
        maintenance_console.print(f"Maintenance supervise status: {result.status}")
        maintenance_console.print(f"State DB: {result.state_db}")
        if result.message:
            maintenance_console.print(f"Message: {result.message}")
        for shard in result.shard_rows[:20]:
            maintenance_console.print(
                f"run={shard.run_id} shard={shard.shard_index}/{shard.shard_count} "
                f"status={shard.status} pid={shard.pid} log={shard.log_path}"
            )
            if shard.report_path or shard.error_summary or shard.key_conclusion:
                maintenance_console.print(
                    f"  report={shard.report_path or 'N/A'} error={shard.error_summary or 'N/A'} "
                    f"conclusion={shard.key_conclusion or 'N/A'}"
                )
        return 0
    if args.maintain_cmd == "run":
        config_path = Path(args.config).resolve()
        result = maintenance_run_long_task(
            config_path,
            task_name=args.task,
            start_period=args.start_period,
            end_period=args.end_period,
            shard_count=args.shard_count,
            max_requests_per_minute=args.max_requests_per_minute,
            retry_failed=bool(args.retry_failed),
            missing_fields_only=bool(args.missing_fields_only),
            limit_tasks=args.limit_tasks,
            dry_run=bool(args.dry_run),
        )
        maintenance_console.print(f"Maintenance run status: {result.status}")
        maintenance_console.print(f"State DB: {result.state_db}")
        maintenance_console.print(f"Run ID: {result.run_id}")
        if result.message:
            maintenance_console.print(f"Message: {result.message}")
        for shard in result.shard_rows:
            maintenance_console.print(
                f"shard={shard.shard_index}/{shard.shard_count} status={shard.status} "
                f"pid={shard.pid} log={shard.log_path}"
            )
        return 0 if result.status not in {"blocked"} else 2
    if args.maintain_cmd == "stop":
        config_path = Path(args.config).resolve()
        result = maintenance_stop(
            config_path,
            task_name=args.task,
            run_id=args.run_id,
            dry_run=bool(args.dry_run),
        )
        maintenance_console.print(f"Maintenance stop status: {result.status}")
        maintenance_console.print(f"State DB: {result.state_db}")
        if result.message:
            maintenance_console.print(f"Message: {result.message}")
        for shard in result.shard_rows[:20]:
            maintenance_console.print(
                f"run={shard.run_id} shard={shard.shard_index}/{shard.shard_count} "
                f"status={shard.status} pid={shard.pid} log={shard.log_path}"
            )
        return 0
    if args.maintain_cmd == "resume":
        config_path = Path(args.config).resolve()
        result = maintenance_resume(
            config_path,
            task_name=args.task,
            run_id=args.run_id,
            dry_run=bool(args.dry_run),
        )
        maintenance_console.print(f"Maintenance resume status: {result.status}")
        maintenance_console.print(f"State DB: {result.state_db}")
        if result.message:
            maintenance_console.print(f"Message: {result.message}")
        for shard in result.shard_rows[:20]:
            maintenance_console.print(
                f"run={shard.run_id} shard={shard.shard_index}/{shard.shard_count} "
                f"status={shard.status} pid={shard.pid} log={shard.log_path}"
            )
        return 0
    parser.error("maintain requires a subcommand: tick, status, supervise, run, stop, or resume")
    return 2
