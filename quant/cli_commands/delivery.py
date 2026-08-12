from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console

from quant.cli_commands.output import print_manual_history_update_result
from quant.config import load_config
from quant.data_governance.update_history import update_manual_history_from_config
from quant.execution.accounts import build_account_ledger, load_simulated_accounts
from quant.reporting.exports import export_brief_account_bill, export_premarket
from quant.reporting.paths import latest_dir, slug
from quant.reporting.quant_static_site import build_quant_static_site, sync_quant_static_site


DELIVERY_COMMANDS = frozenset({"brief", "daily-brief"})
BRIEF_TODAY_MIRROR = Path("/mnt/d/ZJ/Dev/brief_today/index.html")
ACCOUNT_BILL_TODAY_DIR = "reports/account_bill_today"
WATCHLIST_STATIC_ASSETS = ("style.css",)
ACCOUNT_BILL_STATIC_ASSETS = ("style.css",)
WATCHLIST_RSYNC_EXCLUDES = ("ui-test/",)


def _sync_target(remote_env: str, remote_dir_env: str, *, default_remote: str, default_remote_dir: str) -> tuple[str, str]:
    remote = os.environ.get(remote_env) or default_remote
    remote_dir = os.environ.get(remote_dir_env) or default_remote_dir
    return remote, remote_dir


def _sync_watchlist_to_remote(console: Console, local_dir: Path) -> None:
    # Watchlist remote mirror. This intentionally lives in the watchlist
    # program instead of a separate script so cron/manual reruns share one path.
    remote = os.environ.get("BRIEF_SYNC_REMOTE")
    remote_dir = os.environ.get("BRIEF_SYNC_REMOTE_DIR")
    if not remote or not remote_dir:
        console.print("[yellow]Warning:[/yellow] skip watchlist sync; BRIEF_SYNC_REMOTE/_DIR is not configured")
        return
    if not local_dir.exists() or not (local_dir / "index.html").exists():
        console.print(f"[yellow]Warning:[/yellow] skip watchlist sync; missing {local_dir / 'index.html'}")
        return
    try:
        subprocess.run(
            [
                "rsync",
                "-avz",
                "--delete",
                *[f"--exclude={pattern}" for pattern in WATCHLIST_RSYNC_EXCLUDES],
                f"{local_dir}/",
                f"{remote}:{remote_dir}",
            ],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        console.print(f"[yellow]Warning:[/yellow] watchlist sync failed: {exc}")
        return
    console.print(f"Watchlist remote: {remote}:{remote_dir}")


_sync_watchlist_to_ecs = _sync_watchlist_to_remote


def _publish_quant_site(console: Console, *, root: Path, config: dict[str, Any]) -> None:
    accounts = load_simulated_accounts(config, root)
    build_result = build_quant_static_site(root=root, config=config, accounts=accounts)
    try:
        sync_result = sync_quant_static_site(root=root, site_root=Path(build_result["site_root"]))
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        console.print(f"[yellow]Warning:[/yellow] quant site sync failed: {exc}")
        return
    console.print(f"Quant site remote: {sync_result['remote']}:{sync_result['remote_dir']}")


def _copy_watchlist_report_bundle(report_path: Path, target_html_path: Path) -> None:
    target_html_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(report_path, target_html_path)
    for asset_name in WATCHLIST_STATIC_ASSETS:
        asset_path = report_path.parent / asset_name
        if asset_path.exists():
            shutil.copyfile(asset_path, target_html_path.parent / asset_name)


def _watchlist_today_paths(*, root: Path, config: dict[str, Any]) -> list[Path]:
    return [
        latest_dir(root=root, config=config, channel="watchlist") / "index.html",
        root / "reports" / "watchlist_today" / "index.html",
        BRIEF_TODAY_MIRROR,
    ]


def _account_watchlist_latest_path(*, root: Path, config: dict[str, Any], account_id: str) -> Path:
    return latest_dir(root=root, config=config, channel="accounts") / slug(str(account_id)) / "watchlist" / "index.html"


def _copy_account_watchlist_latest(*, root: Path, config: dict[str, Any], account_id: str, report_path: Path) -> Path:
    target = _account_watchlist_latest_path(root=root, config=config, account_id=account_id)
    _copy_watchlist_report_bundle(report_path, target)
    return target


def publish_watchlist_static_assets(
    *,
    root: Path,
    config: dict[str, Any],
    source_dir: Path,
    console: Console | None = None,
    sync_remote: bool = True,
) -> list[Path]:
    """Publish watchlist CSS/assets without regenerating the watchlist report."""
    published: list[Path] = []
    for target_html_path in _watchlist_today_paths(root=root, config=config):
        if not target_html_path.exists():
            continue
        target_html_path.parent.mkdir(parents=True, exist_ok=True)
        for asset_name in WATCHLIST_STATIC_ASSETS:
            asset_path = source_dir / asset_name
            if asset_path.exists():
                target_asset_path = target_html_path.parent / asset_name
                shutil.copyfile(asset_path, target_asset_path)
                published.append(target_asset_path)
    if sync_remote and published:
        _sync_watchlist_to_remote(console or Console(), root / "reports" / "watchlist_today")
    return published


def _sync_account_bill_to_cloud(console: Console, local_dir: Path) -> None:
    remote = os.environ.get("ACCOUNT_BILL_SYNC_REMOTE")
    remote_dir = os.environ.get("ACCOUNT_BILL_SYNC_REMOTE_DIR")
    if not remote or not remote_dir:
        console.print("[yellow]Warning:[/yellow] skip legacy account bill sync; ACCOUNT_BILL_SYNC_REMOTE/_DIR is not configured")
        return
    if not local_dir.exists() or not (local_dir / "index.html").exists():
        console.print(f"[yellow]Warning:[/yellow] skip account bill sync; missing {local_dir / 'index.html'}")
        return
    try:
        subprocess.run(
            ["rsync", "-avz", "--delete", f"{local_dir}/", f"{remote}:{remote_dir}"],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        console.print(f"[yellow]Warning:[/yellow] account bill sync failed: {exc}")
        return
    console.print(f"Account bill cloud: {remote}:{remote_dir}")


def _copy_account_bill_latest(
    *,
    root: Path,
    config: dict[str, Any],
    account_bill: Any,
    account_id: str | None = None,
    include_global: bool = True,
) -> list[Path]:
    account_bill_path = Path(account_bill) if account_bill else Path("")
    if not str(account_bill or "").strip() or not account_bill_path.is_file():
        return []
    account_bill_today_paths: list[Path] = []
    if include_global:
        account_bill_today_paths.extend(
            [
                latest_dir(root=root, config=config, channel="account_bill") / "index.html",
                root / ACCOUNT_BILL_TODAY_DIR / "index.html",
            ]
        )
    if account_id:
        account_bill_today_paths.append(
            latest_dir(root=root, config=config, channel="accounts") / slug(str(account_id)) / "account_bill" / "index.html"
        )
    for account_bill_today_path in account_bill_today_paths:
        account_bill_today_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(account_bill_path, account_bill_today_path)
        for asset_name in ACCOUNT_BILL_STATIC_ASSETS:
            asset_path = account_bill_path.parent / asset_name
            if asset_path.exists():
                shutil.copyfile(asset_path, account_bill_today_path.parent / asset_name)
    return account_bill_today_paths


def _brief_date_from_watchlist_frame(frame: pd.DataFrame, fallback: str) -> str:
    if "盘前检查时间" not in frame.columns or frame.empty:
        return fallback
    values = frame["盘前检查时间"].dropna().astype(str)
    for value in values:
        text = value.strip()
        if len(text) >= 10 and text[4] == "-" and text[7] == "-":
            return text[:10]
    return fallback


def _watchlist_matches_account(frame: pd.DataFrame, account: Any) -> bool:
    account_id = str(getattr(account, "account_id", "") or "")
    strategy_id = str(getattr(account, "strategy_id", "") or "")
    if account_id and "账户ID" in frame.columns:
        account_values = {str(value) for value in frame["账户ID"].dropna().astype(str).unique()}
        if account_values and account_id not in account_values:
            return False
    elif account_id and account_id != "default":
        return False
    if strategy_id and "策略ID" in frame.columns:
        strategy_values = {str(value) for value in frame["策略ID"].dropna().astype(str).unique()}
        if strategy_values and strategy_id not in strategy_values:
            return False
    return True


def _candidate_watchlist_paths(root: Path, target_date: str) -> list[Path]:
    report_root = root / "reports"
    if not report_root.exists():
        return []
    paths = list(report_root.glob(f"runs/{target_date}/*/premarket__watchlist.csv"))
    paths.extend(report_root.glob(f"{target_date}/phase0_premarket_watchlist*.csv"))
    paths.extend(report_root.glob(f"{target_date}/premarket__watchlist*.csv"))
    return sorted({path for path in paths if path.is_file()}, key=lambda item: item.as_posix())


def _latest_watchlist_for_account(root: Path, account: Any, target_date: str) -> tuple[Path, pd.DataFrame] | None:
    matches: list[tuple[float, Path, pd.DataFrame]] = []
    for path in _candidate_watchlist_paths(root, target_date):
        try:
            frame = pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            continue
        if _brief_date_from_watchlist_frame(frame, target_date) != target_date:
            continue
        if not _watchlist_matches_account(frame, account):
            continue
        matches.append((path.stat().st_mtime, path, frame))
    if not matches:
        return None
    _, path, frame = max(matches, key=lambda item: (item[0], item[1].as_posix()))
    return path, frame


def _select_delivery_accounts(config: dict[str, Any], root: Path, *, account_id: str | None, all_accounts: bool) -> list[Any]:
    accounts = load_simulated_accounts(config, root)
    if all_accounts:
        return accounts
    if account_id:
        selected = [account for account in accounts if str(account.account_id) == str(account_id)]
        if not selected:
            available = ", ".join(str(account.account_id) for account in accounts) or "<none>"
            raise ValueError(f"simulated account {account_id!r} is not configured; available accounts: {available}")
        return selected
    return accounts[:1]


def confirm_account_bills_pipeline(
    *,
    config_path: Path,
    account_id: str | None = None,
    all_accounts: bool = False,
    target_date: str | None = None,
) -> int:
    console = Console()
    root = config_path.parent
    cfg = load_config(config_path)
    bill_date = target_date or date.today().isoformat()
    accounts = _select_delivery_accounts(cfg, root, account_id=account_id, all_accounts=all_accounts)
    if not accounts:
        console.print("[yellow]Warning:[/yellow] no enabled simulated accounts configured")
        _publish_quant_site(console, root=root, config=cfg)
        return 0

    console.print("[bold]Post-close account bill confirmation started[/bold]")
    console.print(f"Target date: {bill_date}")
    confirmed_accounts: list[str] = []
    failed_accounts: list[str] = []
    synced_legacy_bill = False
    legacy_account_id = "default" if any(str(getattr(account, "account_id", "")) == "default" for account in accounts) else str(
        getattr(accounts[0], "account_id", "")
    )

    for index, account in enumerate(accounts):
        account_label = str(getattr(account, "account_id", ""))
        selected = _latest_watchlist_for_account(root, account, bill_date)
        if selected is None:
            console.print(f"[yellow]Warning:[/yellow] {account_label}: no watchlist CSV found for {bill_date}")
            failed_accounts.append(account_label)
            continue
        watchlist_path, watchlist = selected
        account_ledger, _ = build_account_ledger(
            root=root,
            current_watchlist=watchlist,
            current_brief_date=bill_date,
            account=account,
            local_history_cfg=cfg.get("local_history", {}),
        )
        has_confirmed_bill = (
            not account_ledger.empty
            and "brief_date" in account_ledger.columns
            and bill_date in {str(value)[:10] for value in account_ledger["brief_date"].dropna().astype(str)}
        )
        if not has_confirmed_bill:
            console.print(
                "[yellow]Warning:[/yellow] "
                f"{account_label}: account ledger was not confirmed for {bill_date}; "
                "check execution price OHLCV coverage."
            )
            failed_accounts.append(account_label)
            continue

        result = export_brief_account_bill(config_path=config_path, brief_date=bill_date, account_id=account_label)
        include_global = not synced_legacy_bill and (account_label == legacy_account_id or (not all_accounts and index == 0))
        account_bill_today_paths = _copy_account_bill_latest(
            root=root,
            config=cfg,
            account_bill=result.get("account_bill"),
            account_id=account_label,
            include_global=include_global,
        )
        if include_global and account_bill_today_paths:
            _sync_account_bill_to_cloud(console, root / ACCOUNT_BILL_TODAY_DIR)
            synced_legacy_bill = True
        confirmed_accounts.append(account_label)
        console.print(f"{account_label}: confirmed from {watchlist_path}")
        for account_bill_today_path in account_bill_today_paths:
            console.print(f"{account_label}: account bill latest: {account_bill_today_path}")

    _publish_quant_site(console, root=root, config=cfg)
    console.print(
        f"Confirmed account bills: {len(confirmed_accounts)}/{len(accounts)} "
        f"({', '.join(confirmed_accounts) if confirmed_accounts else 'none'})"
    )
    if failed_accounts:
        console.print(f"[red]Failed accounts:[/red] {', '.join(failed_accounts)}")
        return 1
    console.print("[green]Post-close account bill confirmation complete[/green]")
    return 0


def run_watchlist_pipeline(
    *,
    config_path: Path,
    skip_update: bool = False,
    check_only: bool = False,
    refresh_cache: bool = False,
    no_panel_cache: bool = False,
    account_id: str | None = None,
    all_accounts: bool = False,
    as_of_date: str | None = None,
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

    selected_account_ids: list[str | None]
    if all_accounts:
        selected_account_ids = [account.account_id for account in load_simulated_accounts(cfg, config_path.parent)]
        if not selected_account_ids:
            console.print("[yellow]Warning:[/yellow] no enabled simulated accounts configured")
            return 0
    else:
        selected_account_ids = [account_id]

    results: list[dict[str, Any]] = []
    for selected_account_id in selected_account_ids:
        premarket_kwargs: dict[str, Any] = {
            "config_path": config_path,
            "refresh_cache": should_refresh_cache,
            "no_panel_cache": bool(no_panel_cache),
            "as_of_date": as_of_date,
        }
        if selected_account_id:
            premarket_kwargs["account_id"] = selected_account_id
        result = export_premarket(**premarket_kwargs)
        results.append(result)
        resolved_account_id = str(result.get("account_id") or selected_account_id or "")
        if resolved_account_id:
            _copy_account_watchlist_latest(
                root=config_path.parent,
                config=cfg,
                account_id=resolved_account_id,
                report_path=Path(result["report"]),
            )
            _copy_account_bill_latest(
                root=config_path.parent,
                config=cfg,
                account_bill=result.get("account_bill"),
                account_id=resolved_account_id,
                include_global=False,
            )
    result = results[0]
    report_path = Path(result["report"])
    watchlist_today_paths = _watchlist_today_paths(root=config_path.parent, config=cfg)
    for watchlist_today_path in watchlist_today_paths:
        _copy_watchlist_report_bundle(report_path, watchlist_today_path)
    _sync_watchlist_to_remote(console, config_path.parent / "reports" / "watchlist_today")
    account_bill_today_paths = _copy_account_bill_latest(root=config_path.parent, config=cfg, account_bill=result.get("account_bill"))
    if account_bill_today_paths:
        _sync_account_bill_to_cloud(console, config_path.parent / ACCOUNT_BILL_TODAY_DIR)
    _publish_quant_site(console, root=config_path.parent, config=cfg)
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
    for account_bill_today_path in account_bill_today_paths:
        console.print(f"Account bill today: {account_bill_today_path}")
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
    account_id: str | None = None,
    all_accounts: bool = False,
    as_of_date: str | None = None,
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
        account_id=account_id,
        all_accounts=all_accounts,
        as_of_date=as_of_date,
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
    brief_daily_parser.add_argument("--account-id", default=None, help="Simulated account ID; defaults to the first enabled account")
    brief_daily_parser.add_argument("--all-accounts", action="store_true", help="Run watchlist and simulated account ledger for every enabled simulated account")
    brief_daily_parser.add_argument("--as-of-date", default=None, help="Replay premarket generation with data capped at this signal date YYYY-MM-DD")
    brief_daily_compat_parser = brief_sub.add_parser("daily-brief", help="Compatibility alias for brief daily")
    brief_daily_compat_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    brief_daily_compat_parser.add_argument("--skip-update", action="store_true", help="Skip A-share history update")
    brief_daily_compat_parser.add_argument("--check-only", action="store_true", help="Only check A-share history freshness; do not export")
    brief_daily_compat_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    brief_daily_compat_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
    brief_daily_compat_parser.add_argument("--account-id", default=None, help="Simulated account ID; defaults to the first enabled account")
    brief_daily_compat_parser.add_argument("--all-accounts", action="store_true", help="Run watchlist and simulated account ledger for every enabled simulated account")
    brief_daily_compat_parser.add_argument("--as-of-date", default=None, help="Replay premarket generation with data capped at this signal date YYYY-MM-DD")
    brief_watchlist_parser = brief_sub.add_parser("watchlist", help="Generate the phase0 watchlist trial brief")
    brief_watchlist_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    brief_watchlist_parser.add_argument("--skip-update", action="store_true", help="Skip A-share history update")
    brief_watchlist_parser.add_argument("--check-only", action="store_true", help="Only check A-share history freshness; do not export")
    brief_watchlist_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    brief_watchlist_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
    brief_watchlist_parser.add_argument("--account-id", default=None, help="Simulated account ID; defaults to the first enabled account")
    brief_watchlist_parser.add_argument("--all-accounts", action="store_true", help="Run watchlist and simulated account ledger for every enabled simulated account")
    brief_watchlist_parser.add_argument("--as-of-date", default=None, help="Replay premarket generation with data capped at this signal date YYYY-MM-DD")
    brief_premarket_parser = brief_sub.add_parser("premarket", help="Export the raw 07:30 premarket watchlist without updating history")
    brief_premarket_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    brief_premarket_parser.add_argument("--account-id", default=None, help="Simulated account ID; defaults to the first enabled account")
    brief_premarket_parser.add_argument("--as-of-date", default=None, help="Replay premarket generation with data capped at this signal date YYYY-MM-DD")
    brief_premarket_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    brief_premarket_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
    brief_account_bill_parser = brief_sub.add_parser("account-bill", help="Export simulated account bill HTML from SQLite")
    brief_account_bill_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    brief_account_bill_parser.add_argument("--account-id", default=None, help="Simulated account ID; defaults to the first enabled account")
    brief_account_bill_parser.add_argument("--date", default=None, help="Brief/account date in YYYY-MM-DD. Defaults to latest account date.")
    brief_confirm_account_bills_parser = brief_sub.add_parser(
        "confirm-account-bills",
        help="Rebuild post-close simulated account ledgers and publish the quant site",
    )
    brief_confirm_account_bills_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    brief_confirm_account_bills_parser.add_argument("--account-id", default=None, help="Simulated account ID; defaults to the first enabled account")
    brief_confirm_account_bills_parser.add_argument(
        "--all-accounts",
        action="store_true",
        help="Confirm account bills for every enabled simulated account",
    )
    brief_confirm_account_bills_parser.add_argument(
        "--date",
        default=None,
        help="Account bill date in YYYY-MM-DD. Defaults to today.",
    )
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
    daily_brief_parser.add_argument("--account-id", default=None, help="Simulated account ID; defaults to the first enabled account")
    daily_brief_parser.add_argument("--all-accounts", action="store_true", help="Run watchlist and simulated account ledger for every enabled simulated account")
    daily_brief_parser.add_argument("--as-of-date", default=None, help="Replay premarket generation with data capped at this signal date YYYY-MM-DD")


def handle_delivery_command(args: argparse.Namespace, *, parser: argparse.ArgumentParser, console: Any | None = None) -> int:
    delivery_console = console or Console()
    account_id = getattr(args, "account_id", None)
    all_accounts = bool(getattr(args, "all_accounts", False))
    as_of_date = getattr(args, "as_of_date", None)
    if args.cmd == "brief":
        if args.brief_cmd in {"daily", "daily-brief", "watchlist"}:
            return run_daily_brief_pipeline(
                config_path=Path(args.config).resolve(),
                watchlist=True,
                skip_update=bool(args.skip_update),
                check_only=bool(args.check_only),
                refresh_cache=bool(args.refresh_cache),
                no_panel_cache=bool(args.no_panel_cache),
                account_id=account_id,
                all_accounts=all_accounts,
                as_of_date=as_of_date,
            )
        if args.brief_cmd == "premarket":
            config_path = Path(args.config).resolve()
            delivery_console.print("[bold]Phase 0 premarket watchlist started[/bold]")
            premarket_kwargs = {
                "config_path": config_path,
                "refresh_cache": bool(args.refresh_cache),
                "no_panel_cache": bool(args.no_panel_cache),
                "as_of_date": as_of_date,
            }
            if account_id:
                premarket_kwargs["account_id"] = account_id
            result = export_premarket(**premarket_kwargs)
            delivery_console.print("[green]Premarket watchlist complete[/green]")
            delivery_console.print(f"Watchlist: {result['watchlist']}")
            delivery_console.print(f"Report: {result['report']}")
            delivery_console.print(f"Rows: {result['rows']}")
            delivery_console.print(f"Signal date: {result['signal_date']}")
            delivery_console.print(f"Check time: {result['check_time']}")
            return 0
        if args.brief_cmd == "account-bill":
            config_path = Path(args.config).resolve()
            cfg = load_config(config_path)
            account_bill_kwargs = {
                "config_path": config_path,
                "brief_date": args.date,
            }
            if account_id:
                account_bill_kwargs["account_id"] = account_id
            result = export_brief_account_bill(**account_bill_kwargs)
            account_bill_today_paths = _copy_account_bill_latest(
                root=config_path.parent,
                config=cfg,
                account_bill=result.get("account_bill"),
            )
            if account_bill_today_paths:
                _sync_account_bill_to_cloud(delivery_console, config_path.parent / ACCOUNT_BILL_TODAY_DIR)
            delivery_console.print("[green]Account bill export complete[/green]")
            delivery_console.print(f"Account: {result['account']}")
            delivery_console.print(f"Date: {result['brief_date']}")
            delivery_console.print(f"Account bill: {result['account_bill']}")
            for account_bill_today_path in account_bill_today_paths:
                delivery_console.print(f"Account bill today: {account_bill_today_path}")
            return 0
        if args.brief_cmd == "confirm-account-bills":
            return confirm_account_bills_pipeline(
                config_path=Path(args.config).resolve(),
                account_id=account_id,
                all_accounts=all_accounts,
                target_date=args.date,
            )
        parser.error("brief requires a subcommand: daily, watchlist, premarket, account-bill, or confirm-account-bills")
    if args.cmd == "daily-brief":
        return run_daily_brief_pipeline(
            config_path=Path(args.config).resolve(),
            watchlist=bool(args.watchlist),
            skip_update=bool(args.skip_update),
            check_only=bool(args.check_only),
            refresh_cache=bool(args.refresh_cache),
            no_panel_cache=bool(args.no_panel_cache),
            account_id=account_id,
            all_accounts=all_accounts,
            as_of_date=as_of_date,
        )
    parser.error("delivery command expected one of: " + ", ".join(sorted(DELIVERY_COMMANDS)))
    return 2
