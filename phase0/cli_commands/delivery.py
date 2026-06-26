from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console

from phase0.cli_commands.output import print_manual_history_update_result
from phase0.config import load_config
from phase0.data_governance.update_history import update_manual_history_from_config
from phase0.reporting.exports import export_brief_account_bill, export_phase0_premarket
from phase0.reporting.paths import latest_dir


DELIVERY_COMMANDS = frozenset({"brief", "daily-brief"})
BRIEF_TODAY_MIRROR = Path("/mnt/d/ZJ/Dev/brief_today/index.html")


def _sync_watchlist_to_ecs(console: Console, local_dir: Path) -> None:
    # Watchlist remote mirror. This intentionally lives in the watchlist
    # program instead of a separate script so cron/manual reruns share one path.
    # The ECS target can be overridden by environment if the host/path changes.
    remote = os.environ.get("BRIEF_SYNC_REMOTE", "root@39.105.102.5")
    remote_dir = os.environ.get("BRIEF_SYNC_REMOTE_DIR", "/brief/")
    if not local_dir.exists() or not (local_dir / "index.html").exists():
        console.print(f"[yellow]Warning:[/yellow] skip ECS watchlist sync; missing {local_dir / 'index.html'}")
        return
    try:
        subprocess.run(
            ["rsync", "-avz", "--delete", f"{local_dir}/", f"{remote}:{remote_dir}"],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        console.print(f"[yellow]Warning:[/yellow] ECS watchlist sync failed: {exc}")
        return
    console.print(f"Watchlist ECS: {remote}:{remote_dir}")


def run_watchlist_pipeline(
    *,
    config_path: Path,
    skip_update: bool = False,
    check_only: bool = False,
    refresh_cache: bool = False,
    no_panel_cache: bool = False,
) -> int:
    console = Console()
    cfg = load_config(config_path)
    console.print("[bold]Phase 0 watchlist pipeline started[/bold]")

    history_result = None
    if skip_update:
        console.print("[yellow]1) Skipping A-share history update[/yellow]")
    else:
        console.print("1) Updating A-share history...")
        history_result = update_manual_history_from_config(cfg, config_path.parent, check_only=check_only)
        print_manual_history_update_result(console, history_result)
        if not history_result.ok:
            console.print("[red]Watchlist stopped because A-share history update failed.[/red]")
            return 2
        if check_only:
            console.print("[yellow]Watchlist stopped after freshness check because --check-only was set.[/yellow]")
            return 0

    should_refresh_cache = bool(refresh_cache)
    if history_result is not None and int(history_result.inserted_rows) > 0:
        should_refresh_cache = True
        console.print("[yellow]2) New A-share rows inserted; refreshing strategy panel cache[/yellow]")
    else:
        console.print("2) Generating premarket watchlist...")

    result = export_phase0_premarket(
        config_path=config_path,
        refresh_cache=should_refresh_cache,
        no_panel_cache=bool(no_panel_cache),
    )
    report_path = Path(result["report"])
    watchlist_today_paths = [
        latest_dir(root=config_path.parent, config=cfg, channel="watchlist") / "index.html",
        config_path.parent / "reports" / "watchlist_today" / "index.html",
        BRIEF_TODAY_MIRROR,
    ]
    for watchlist_today_path in watchlist_today_paths:
        watchlist_today_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(report_path, watchlist_today_path)
    _sync_watchlist_to_ecs(console, config_path.parent / "reports" / "watchlist_today")
    console.print("[green]Watchlist pipeline complete[/green]")
    console.print(f"Watchlist: {result['watchlist']}")
    console.print(f"Report: {result['report']}")
    for watchlist_today_path in watchlist_today_paths:
        console.print(f"Watchlist today: {watchlist_today_path}")
    if "ledger" in result:
        console.print(f"Simulation ledger: {result['ledger']}")
    if "account_ledger" in result:
        console.print(f"Account ledger: {result['account_ledger']}")
    if "account_bill" in result:
        console.print(f"Account bill: {result['account_bill']}")
    console.print(f"Rows: {result['rows']}")
    console.print(f"Signal date: {result['signal_date']}")
    console.print(f"Check time: {result['check_time']}")

    if history_result is not None and history_result.after_latest_date and result.get("signal_date"):
        if str(history_result.after_latest_date) != str(result["signal_date"]):
            console.print(
                "[yellow]Warning:[/yellow] "
                f"history latest date is {history_result.after_latest_date}, "
                f"but strategy signal date is {result['signal_date']}."
            )
    return 0


def run_daily_brief_pipeline(
    *,
    config_path: Path,
    watchlist: bool = False,
    skip_update: bool = False,
    check_only: bool = False,
    refresh_cache: bool = False,
    no_panel_cache: bool = False,
) -> int:
    console = Console()
    if not watchlist:
        console.print(
            "[yellow]Warning:[/yellow] full daily brief is not implemented yet; "
            "running --watchlist compatibility mode."
        )
    return run_watchlist_pipeline(
        config_path=config_path,
        skip_update=skip_update,
        check_only=check_only,
        refresh_cache=refresh_cache,
        no_panel_cache=no_panel_cache,
    )


def register_delivery_commands(subparsers: argparse._SubParsersAction) -> None:
    brief_parser = subparsers.add_parser("brief", help="Brief delivery commands")
    brief_sub = brief_parser.add_subparsers(dest="brief_cmd")
    brief_daily_parser = brief_sub.add_parser("daily", help="Generate the daily brief; currently uses watchlist output")
    brief_daily_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    brief_daily_parser.add_argument("--skip-update", action="store_true", help="Skip A-share history update")
    brief_daily_parser.add_argument("--check-only", action="store_true", help="Only check A-share history freshness; do not export")
    brief_daily_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    brief_daily_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
    brief_daily_compat_parser = brief_sub.add_parser("daily-brief", help="Compatibility alias for brief daily")
    brief_daily_compat_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    brief_daily_compat_parser.add_argument("--skip-update", action="store_true", help="Skip A-share history update")
    brief_daily_compat_parser.add_argument("--check-only", action="store_true", help="Only check A-share history freshness; do not export")
    brief_daily_compat_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    brief_daily_compat_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
    brief_watchlist_parser = brief_sub.add_parser("watchlist", help="Generate the phase0 watchlist trial brief")
    brief_watchlist_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    brief_watchlist_parser.add_argument("--skip-update", action="store_true", help="Skip A-share history update")
    brief_watchlist_parser.add_argument("--check-only", action="store_true", help="Only check A-share history freshness; do not export")
    brief_watchlist_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    brief_watchlist_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
    brief_premarket_parser = brief_sub.add_parser("premarket", help="Export the raw 07:30 premarket watchlist without updating history")
    brief_premarket_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    brief_premarket_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    brief_premarket_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
    brief_account_bill_parser = brief_sub.add_parser("account-bill", help="Export simulated account bill HTML from SQLite")
    brief_account_bill_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    brief_account_bill_parser.add_argument("--date", default=None, help="Brief/account date in YYYY-MM-DD. Defaults to latest account date.")
    daily_brief_parser = subparsers.add_parser("daily-brief", help="Run the daily delivery pipeline")
    daily_brief_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    daily_brief_parser.add_argument(
        "--watchlist",
        action="store_true",
        help="Export the phase0 watchlist trial brief; the full daily brief is reserved for later product stages",
    )
    daily_brief_parser.add_argument("--skip-update", action="store_true", help="Skip A-share history update and only export the watchlist")
    daily_brief_parser.add_argument("--check-only", action="store_true", help="Only check A-share history freshness; do not export the watchlist")
    daily_brief_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    daily_brief_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")


def handle_delivery_command(args: argparse.Namespace, *, parser: argparse.ArgumentParser, console: Any | None = None) -> int:
    delivery_console = console or Console()
    if args.cmd == "brief":
        if args.brief_cmd in {"daily", "daily-brief", "watchlist"}:
            return run_daily_brief_pipeline(
                config_path=Path(args.config).resolve(),
                watchlist=True,
                skip_update=bool(args.skip_update),
                check_only=bool(args.check_only),
                refresh_cache=bool(args.refresh_cache),
                no_panel_cache=bool(args.no_panel_cache),
            )
        if args.brief_cmd == "premarket":
            config_path = Path(args.config).resolve()
            delivery_console.print("[bold]Phase 0 premarket watchlist started[/bold]")
            result = export_phase0_premarket(
                config_path=config_path,
                refresh_cache=bool(args.refresh_cache),
                no_panel_cache=bool(args.no_panel_cache),
            )
            delivery_console.print("[green]Premarket watchlist complete[/green]")
            delivery_console.print(f"Watchlist: {result['watchlist']}")
            delivery_console.print(f"Report: {result['report']}")
            delivery_console.print(f"Rows: {result['rows']}")
            delivery_console.print(f"Signal date: {result['signal_date']}")
            delivery_console.print(f"Check time: {result['check_time']}")
            return 0
        if args.brief_cmd == "account-bill":
            result = export_brief_account_bill(
                config_path=Path(args.config).resolve(),
                brief_date=args.date,
            )
            delivery_console.print("[green]Account bill export complete[/green]")
            delivery_console.print(f"Account: {result['account']}")
            delivery_console.print(f"Date: {result['brief_date']}")
            delivery_console.print(f"Account bill: {result['account_bill']}")
            return 0
        parser.error("brief requires a subcommand: daily, watchlist, premarket, or account-bill")
    if args.cmd == "daily-brief":
        return run_daily_brief_pipeline(
            config_path=Path(args.config).resolve(),
            watchlist=bool(args.watchlist),
            skip_update=bool(args.skip_update),
            check_only=bool(args.check_only),
            refresh_cache=bool(args.refresh_cache),
            no_panel_cache=bool(args.no_panel_cache),
        )
    parser.error("delivery command expected one of: " + ", ".join(sorted(DELIVERY_COMMANDS)))
    return 2
