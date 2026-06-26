from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from rich.console import Console

from phase0.adjustment_backfill import backfill_adjustment_factors_from_config
from phase0.cli_commands.output import print_manual_history_update_result
from phase0.config import load_config
from phase0.daily_basic_backfill import backfill_daily_basic_from_config
from phase0.data_governance.index_asof_backfill import backfill_index_asof_from_config
from phase0.external_market_history import update_hk_market_history_from_config, update_us_market_history_from_config
from phase0.financial_factors import update_financial_factors_from_config
from phase0.import_history import import_from_config, import_index_history_from_config
from phase0.tushare_history_backfill import backfill_tushare_financials_from_config, backfill_tushare_history_from_config
from phase0.universe import build_local_factor_universe
from phase0.update_history import update_manual_history_from_config


DATA_UPDATE_COMMANDS = frozenset(
    {
        "backfill-adjustment-factors",
        "backfill-daily-basic",
        "backfill-index-asof",
        "backfill-tushare-financials",
        "backfill-tushare-history",
        "build-universe",
        "import-history",
        "import-index-history",
        "update-financials",
        "update-hk-market-history",
        "update-history",
        "update-us-market-history",
    }
)


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def _print_tushare_financial_progress(console: Console, progress: dict) -> None:
    target = int(progress.get("target_tasks") or 0)
    processed = int(progress.get("processed_tasks") or 0)
    elapsed = float(progress.get("elapsed_seconds") or 0.0)
    remaining = max(target - processed, 0)
    percent = (processed / target * 100.0) if target else 100.0
    rate = (processed / elapsed * 60.0) if elapsed > 0 else 0.0
    eta = _format_duration(remaining / (processed / elapsed)) if processed > 0 and elapsed > 0 else "unknown"
    event = str(progress.get("event") or "progress")
    label = "selected" if event == "start" else "progress"
    console.print(
        "[cyan]Tushare financial backfill {label}:[/cyan] "
        "{processed}/{target} ({percent:.1f}%), "
        "fetched={fetched}, empty={empty}, failed={failed}, inserted_rows={inserted}, "
        "rate={rate:.1f}/min, elapsed={elapsed_text}, eta={eta}".format(
            label=label,
            processed=processed,
            target=target,
            percent=percent,
            fetched=int(progress.get("fetched_tasks") or 0),
            empty=int(progress.get("empty_tasks") or 0),
            failed=int(progress.get("failed_tasks") or 0),
            inserted=int(progress.get("inserted_rows") or 0),
            rate=rate,
            elapsed_text=_format_duration(elapsed),
            eta=eta,
        )
    )


def register_data_update_commands(subparsers: argparse._SubParsersAction) -> None:
    universe_parser = subparsers.add_parser("build-universe", help="Build local-factor A-share universe")
    universe_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    history_parser = subparsers.add_parser("import-history", help="Import manual A-share history zip files")
    history_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    index_history_parser = subparsers.add_parser("import-index-history", help="Rebuild manual A-share index history tables only")
    index_history_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    update_history_parser = subparsers.add_parser("update-history", help="Incrementally update manual A-share history database")
    update_history_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    update_history_parser.add_argument("--check-only", action="store_true", help="Only check freshness, do not fetch or write")
    update_history_parser.add_argument(
        "--no-build-universe",
        action="store_true",
        help="Do not rebuild local factor universe after a successful update",
    )
    daily_basic_backfill_parser = subparsers.add_parser("backfill-daily-basic", help="Backfill historical A-share daily_basic valuation rows")
    daily_basic_backfill_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    daily_basic_backfill_parser.add_argument("--start-date", required=True, help="Start date in YYYY-MM-DD")
    daily_basic_backfill_parser.add_argument("--end-date", required=True, help="End date in YYYY-MM-DD")
    daily_basic_backfill_parser.add_argument("--limit-dates", type=int, default=None, help="Optional cap for number of open dates to fetch")
    adjustment_backfill_parser = subparsers.add_parser("backfill-adjustment-factors", help="Backfill A-share Tushare adj_factor and dividend tables")
    adjustment_backfill_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    adjustment_backfill_parser.add_argument("--start-date", required=True, help="Start date in YYYY-MM-DD")
    adjustment_backfill_parser.add_argument("--end-date", required=True, help="End date in YYYY-MM-DD")
    adjustment_backfill_parser.add_argument("--limit-dates", type=int, default=None, help="Optional cap for number of open dates to fetch")
    adjustment_backfill_parser.add_argument("--no-skip-existing", action="store_true", help="Refetch dates already present in market_adj_factors")
    adjustment_backfill_parser.add_argument("--no-dividends", action="store_true", help="Only fetch adj_factor; skip dividend table")
    adjustment_backfill_parser.add_argument(
        "--max-requests-per-minute",
        type=int,
        default=180,
        help="Client-side Tushare request throttle. Default 180 is below the 2000-point 200/minute tier.",
    )
    index_asof_backfill_parser = subparsers.add_parser("backfill-index-asof", help="Backfill benchmark index constituent and weight as-of tables")
    index_asof_backfill_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    index_asof_backfill_parser.add_argument("--index-code", default=None, help="Project index code, defaults to benchmark_symbol")
    index_asof_backfill_parser.add_argument("--start-date", default="2016-01-01", help="Start date in YYYY-MM-DD")
    index_asof_backfill_parser.add_argument("--end-date", required=True, help="End date in YYYY-MM-DD")
    index_asof_backfill_parser.add_argument("--input-csv", default=None, help="Optional CSV with index_code, con_code, trade_date, weight")
    index_asof_backfill_parser.add_argument(
        "--max-requests-per-minute",
        type=int,
        default=180,
        help="Client-side Tushare request throttle. Default 180 is below the 2000-point 200/minute tier.",
    )
    index_asof_backfill_parser.add_argument("--weights-table", default="cn_index_weights_asof", help="Target SQLite weights table")
    index_asof_backfill_parser.add_argument("--constituents-table", default="cn_index_constituents_asof", help="Target SQLite constituents table")
    tushare_backfill_parser = subparsers.add_parser("backfill-tushare-history", help="Backfill Tushare historical A-share fields and audit coverage")
    tushare_backfill_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    tushare_backfill_parser.add_argument("--start-date", default="2016-01-01", help="Start date in YYYY-MM-DD")
    tushare_backfill_parser.add_argument("--end-date", required=True, help="End date in YYYY-MM-DD")
    tushare_backfill_parser.add_argument("--limit-dates", type=int, default=None, help="Optional cap for daily open dates to fetch")
    tushare_backfill_parser.add_argument("--limit-periods", type=int, default=None, help="Optional cap for financial periods to fetch")
    tushare_backfill_parser.add_argument("--no-skip-existing", action="store_true", help="Refetch dates/periods already present locally")
    tushare_backfill_parser.add_argument("--no-daily-basic", action="store_true", help="Skip Tushare daily_basic backfill")
    tushare_backfill_parser.add_argument("--no-adj-factor", action="store_true", help="Skip Tushare adj_factor backfill")
    tushare_backfill_parser.add_argument("--no-dividends", action="store_true", help="Skip Tushare dividend backfill")
    tushare_backfill_parser.add_argument("--no-financial", action="store_true", help="Skip Tushare financial factor backfill")
    tushare_backfill_parser.add_argument(
        "--max-requests-per-minute",
        type=int,
        default=180,
        help="Client-side Tushare request throttle. Default 180 is below the 2000-point 200/minute tier.",
    )
    tushare_financial_parser = subparsers.add_parser(
        "backfill-tushare-financials",
        help="Backfill Tushare financial factors by ts_code with resumable tasks",
    )
    tushare_financial_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    tushare_financial_parser.add_argument("--period", default=None, help="Single financial period in YYYY-MM-DD")
    tushare_financial_parser.add_argument("--start-period", default="2016-03-31", help="Start financial period in YYYY-MM-DD")
    tushare_financial_parser.add_argument("--end-period", default="2018-03-31", help="End financial period in YYYY-MM-DD")
    tushare_financial_parser.add_argument("--limit-symbols", type=int, default=None, help="Optional cap for target symbols per period")
    tushare_financial_parser.add_argument("--limit-tasks", type=int, default=None, help="Optional cap for selected task rows to process")
    tushare_financial_parser.add_argument("--retry-failed", action="store_true", help="Retry failed tasks in addition to pending tasks")
    tushare_financial_parser.add_argument("--replace-existing", action="store_true", help="Replace existing valid financial rows")
    tushare_financial_parser.add_argument(
        "--missing-fields-only",
        action="store_true",
        help="Only patch existing financial rows that have missing fields",
    )
    tushare_financial_parser.add_argument(
        "--missing-fields",
        default="roe,revenue_growth,profit_growth,operating_cash_flow_to_net_profit,debt_to_asset",
        help="Comma-separated financial fields to patch when --missing-fields-only is set",
    )
    tushare_financial_parser.add_argument("--shard-index", type=int, default=0, help="Shard index for distributed runs")
    tushare_financial_parser.add_argument("--shard-count", type=int, default=1, help="Total shard count for distributed runs")
    tushare_financial_parser.add_argument("--max-runtime-minutes", type=int, default=None, help="Stop gracefully after this many minutes")
    tushare_financial_parser.add_argument(
        "--max-requests-per-minute",
        type=int,
        default=120,
        help="Client-side Tushare request throttle. Default 120 is conservative for long financial backfills.",
    )
    us_history_parser = subparsers.add_parser("update-us-market-history", help="Incrementally update US market history database")
    us_history_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    us_history_parser.add_argument("--check-only", action="store_true", help="Only check freshness, do not fetch or write")
    hk_history_parser = subparsers.add_parser("update-hk-market-history", help="Incrementally update HK market history database")
    hk_history_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    hk_history_parser.add_argument("--check-only", action="store_true", help="Only check freshness, do not fetch or write")
    financial_parser = subparsers.add_parser("update-financials", help="Update A-share quarterly financial factors")
    financial_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    financial_parser.add_argument("--periods", type=int, default=None, help="Override number of recent quarters to fetch")
    financial_parser.add_argument(
        "--no-build-universe",
        action="store_true",
        help="Do not rebuild local factor universe after a successful update",
    )


def handle_data_update_command(args: argparse.Namespace, *, parser: argparse.ArgumentParser, console: Any | None = None) -> int:
    update_console = console or Console()
    if args.cmd == "update-financials":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = update_financial_factors_from_config(cfg, config_path.parent, periods=args.periods)
        color = "green" if result.ok else "red"
        update_console.print(f"[{color}]Financial factor update status: {result.status}[/{color}]")
        update_console.print(f"Database: {result.db_path}")
        update_console.print(f"Periods requested: {', '.join(result.periods_requested) or 'N/A'}")
        update_console.print(f"Periods updated: {', '.join(result.periods_updated) or 'N/A'}")
        update_console.print(f"Fetched rows: {result.fetched_rows}")
        update_console.print(f"Inserted rows: {result.inserted_rows}")
        if result.factor_coverage:
            update_console.print(
                "Financial factor coverage: "
                f"latest={result.factor_coverage.get('latest_factor', 0.0):.4f}, "
                f"roe={result.factor_coverage.get('roe', 0.0):.4f}, "
                f"revenue_growth={result.factor_coverage.get('revenue_growth', 0.0):.4f}, "
                f"profit_growth={result.factor_coverage.get('profit_growth', 0.0):.4f}, "
                f"cash_flow_quality={result.factor_coverage.get('cash_flow_quality', 0.0):.4f}, "
                f"debt_to_asset={result.factor_coverage.get('debt_to_asset', 0.0):.4f}"
            )
        if result.warnings:
            for warning in result.warnings:
                update_console.print(f"[yellow]Warning:[/yellow] {warning}")
        if not result.ok:
            return 2
        if (
            not args.no_build_universe
            and result.inserted_rows > 0
            and bool(cfg.get("financial_factors", {}).get("rebuild_universe_after", True))
        ):
            universe_result = build_local_factor_universe(cfg, config_path.parent)
            update_console.print("[green]Universe rebuild complete[/green]")
            update_console.print(f"Source: {universe_result.source}")
            update_console.print(f"Selected: {universe_result.selected_count}/{universe_result.target_size}")
            if universe_result.warnings:
                for warning in universe_result.warnings:
                    update_console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0
    if args.cmd == "update-history":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = update_manual_history_from_config(cfg, config_path.parent, check_only=args.check_only)
        print_manual_history_update_result(update_console, result)
        if not result.ok:
            return 2
        if (
            not args.check_only
            and not args.no_build_universe
            and result.status in {"updated", "metadata_updated"}
            and bool(cfg.get("manual_history_update", {}).get("rebuild_universe_after", False))
        ):
            universe_result = build_local_factor_universe(cfg, config_path.parent)
            update_console.print("[green]Universe rebuild complete[/green]")
            update_console.print(f"Source: {universe_result.source}")
            update_console.print(f"Selected: {universe_result.selected_count}/{universe_result.target_size}")
            if universe_result.warnings:
                for warning in universe_result.warnings:
                    update_console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0
    if args.cmd == "backfill-daily-basic":
        config_path = Path(args.config).resolve()
        update_console.print("[bold]A-share daily_basic backfill started[/bold]")
        result = backfill_daily_basic_from_config(
            config_path,
            start_date=str(args.start_date),
            end_date=str(args.end_date),
            limit_dates=args.limit_dates,
        )
        update_console.print("[green]A-share daily_basic backfill complete[/green]")
        update_console.print(f"Database: {result.db_path}")
        update_console.print(f"Table: {result.table_name}")
        update_console.print(f"Status: {result.status}")
        update_console.print(f"Target dates: {result.target_dates}")
        update_console.print(f"Fetched dates: {result.fetched_dates}")
        update_console.print(f"Inserted rows: {result.inserted_rows}")
        update_console.print(f"Skipped existing dates: {result.skipped_existing_dates}")
        if result.warnings:
            update_console.print("Warnings:")
            for item in result.warnings[:20]:
                update_console.print(f"- {item}")
        return 0
    if args.cmd == "backfill-adjustment-factors":
        config_path = Path(args.config).resolve()
        update_console.print("[bold]A-share adjustment factor backfill started[/bold]")
        result = backfill_adjustment_factors_from_config(
            config_path,
            start_date=str(args.start_date),
            end_date=str(args.end_date),
            limit_dates=args.limit_dates,
            skip_existing=not bool(args.no_skip_existing),
            include_dividends=not bool(args.no_dividends),
            max_requests_per_minute=int(args.max_requests_per_minute),
        )
        color = "green" if result.status in {"ok", "empty"} else "red"
        update_console.print(f"[{color}]Adjustment factor backfill status: {result.status}[/{color}]")
        update_console.print(f"Database: {result.db_path}")
        update_console.print(f"Target dates: {result.target_dates}")
        update_console.print(f"Fetched dates: {result.fetched_dates}")
        update_console.print(f"Inserted adj_factor rows: {result.inserted_adj_factor_rows}")
        update_console.print(f"Inserted dividend rows: {result.inserted_dividend_rows}")
        update_console.print(f"Skipped existing dates: {result.skipped_existing_dates}")
        if result.warnings:
            update_console.print("Warnings:")
            for item in result.warnings[:20]:
                update_console.print(f"- {item}")
        return 0 if result.status != "missing_tushare_token" else 2
    if args.cmd == "backfill-tushare-history":
        config_path = Path(args.config).resolve()
        update_console.print("[bold]Tushare historical backfill started[/bold]")
        result = backfill_tushare_history_from_config(
            config_path,
            start_date=str(args.start_date),
            end_date=str(args.end_date),
            max_requests_per_minute=int(args.max_requests_per_minute),
            limit_dates=args.limit_dates,
            limit_periods=args.limit_periods,
            skip_existing=not bool(args.no_skip_existing),
            include_daily_basic=not bool(args.no_daily_basic),
            include_adj_factor=not bool(args.no_adj_factor),
            include_dividends=not bool(args.no_dividends),
            include_financial=not bool(args.no_financial),
        )
        color = "green" if result.status == "ok" else "yellow"
        update_console.print(f"[{color}]Tushare historical backfill status: {result.status}[/{color}]")
        update_console.print(f"Database: {result.db_path}")
        update_console.print(
            f"Daily basic: fetched {result.daily_basic_fetched_dates}/{result.daily_basic_target_dates}, "
            f"rows {result.daily_basic_inserted_rows}"
        )
        update_console.print(
            f"Adj factor: fetched {result.adj_factor_fetched_dates}/{result.adj_factor_target_dates}, "
            f"rows {result.adj_factor_inserted_rows}"
        )
        update_console.print(f"Dividends rows: {result.dividend_inserted_rows}")
        update_console.print(f"Financial: fetched {result.financial_fetched_periods}/{result.financial_target_periods}, rows {result.financial_inserted_rows}")
        update_console.print(f"Audit CSV: {result.audit_csv}")
        update_console.print(f"Audit Markdown: {result.audit_md}")
        if result.warnings:
            update_console.print("Warnings:")
            for item in result.warnings[:30]:
                update_console.print(f"- {item}")
        return 0 if result.status != "missing_tushare_token" else 2
    if args.cmd == "backfill-index-asof":
        config_path = Path(args.config).resolve()
        update_console.print("[bold]Index as-of backfill started[/bold]")
        result = backfill_index_asof_from_config(
            config_path,
            index_code=str(args.index_code) if args.index_code else None,
            start_date=str(args.start_date),
            end_date=str(args.end_date),
            input_csv=Path(args.input_csv).resolve() if args.input_csv else None,
            max_requests_per_minute=int(args.max_requests_per_minute),
            weights_table=str(args.weights_table),
            constituents_table=str(args.constituents_table),
        )
        color = "green" if result.status == "ok" else "yellow"
        update_console.print(f"[{color}]Index as-of backfill status: {result.status}[/{color}]")
        update_console.print(f"Database: {result.db_path}")
        update_console.print(f"Index: {result.index_code} ({result.vendor_index_code})")
        update_console.print(f"Source: {result.source}")
        update_console.print(f"Fetched rows: {result.fetched_rows}")
        update_console.print(f"Inserted weight rows: {result.inserted_weight_rows}")
        update_console.print(f"Inserted constituent rows: {result.inserted_constituent_rows}")
        update_console.print(f"Trade dates: {result.distinct_trade_dates} ({result.min_trade_date or 'N/A'}..{result.max_trade_date or 'N/A'})")
        update_console.print(f"Audit CSV: {result.audit_csv}")
        update_console.print(f"Audit Markdown: {result.audit_md}")
        if result.warnings:
            update_console.print("Warnings:")
            for item in result.warnings[:30]:
                update_console.print(f"- {item}")
        return 0 if result.status not in {"missing_tushare_token"} else 2
    if args.cmd == "backfill-tushare-financials":
        config_path = Path(args.config).resolve()
        update_console.print("[bold]Tushare financial backfill started[/bold]")
        result = backfill_tushare_financials_from_config(
            config_path,
            start_period=str(args.start_period),
            end_period=str(args.end_period),
            period=str(args.period) if args.period else None,
            max_requests_per_minute=int(args.max_requests_per_minute),
            max_runtime_minutes=args.max_runtime_minutes,
            limit_symbols=args.limit_symbols,
            limit_tasks=args.limit_tasks,
            retry_failed=bool(args.retry_failed),
            replace_existing=bool(args.replace_existing),
            missing_fields_only=bool(args.missing_fields_only),
            missing_fields=[item.strip() for item in str(args.missing_fields).split(",") if item.strip()],
            shard_index=int(args.shard_index),
            shard_count=int(args.shard_count),
            progress_callback=lambda progress: _print_tushare_financial_progress(update_console, progress),
        )
        color = "green" if result.status == "ok" else "yellow"
        update_console.print(f"[{color}]Tushare financial backfill status: {result.status}[/{color}]")
        update_console.print(f"Database: {result.db_path}")
        update_console.print(f"Target tasks: {result.target_tasks}")
        update_console.print(f"Processed tasks: {result.processed_tasks}")
        update_console.print(f"Fetched: {result.fetched_tasks}")
        update_console.print(f"Empty: {result.empty_tasks}")
        update_console.print(f"Failed: {result.failed_tasks}")
        update_console.print(f"Inserted rows: {result.inserted_rows}")
        update_console.print(f"Audit CSV: {result.audit_csv}")
        update_console.print(f"Audit Markdown: {result.audit_md}")
        if result.warnings:
            update_console.print("Warnings:")
            for item in result.warnings[:30]:
                update_console.print(f"- {item}")
        return 0 if result.status != "missing_tushare_token" else 2
    if args.cmd == "update-us-market-history":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = update_us_market_history_from_config(cfg, config_path.parent, check_only=args.check_only)
        color = "green" if result.ok else "red"
        update_console.print(f"[{color}]US market history update status: {result.status}[/{color}]")
        update_console.print(f"Database: {result.db_path}")
        update_console.print(f"Latest date: {result.latest_date or 'N/A'}")
        update_console.print(f"Coverage: {result.coverage:.4f} ({result.covered_symbols}/{result.symbol_count})")
        update_console.print(f"Fetched rows: {result.fetched_rows}")
        update_console.print(f"Inserted rows: {result.inserted_rows}")
        update_console.print(f"Updated rows: {result.updated_rows}")
        update_console.print(f"Source: {result.source or 'N/A'}")
        if result.warnings:
            for warning in result.warnings:
                update_console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0 if result.ok else 2
    if args.cmd == "update-hk-market-history":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = update_hk_market_history_from_config(cfg, config_path.parent, check_only=args.check_only)
        color = "green" if result.ok else "red"
        update_console.print(f"[{color}]HK market history update status: {result.status}[/{color}]")
        update_console.print(f"Database: {result.db_path}")
        update_console.print(f"Latest date: {result.latest_date or 'N/A'}")
        update_console.print(f"Coverage: {result.coverage:.4f} ({result.covered_symbols}/{result.symbol_count})")
        update_console.print(f"Fetched rows: {result.fetched_rows}")
        update_console.print(f"Inserted rows: {result.inserted_rows}")
        update_console.print(f"Updated rows: {result.updated_rows}")
        update_console.print(f"Source: {result.source or 'N/A'}")
        if result.warnings:
            for warning in result.warnings:
                update_console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0 if result.ok else 2
    if args.cmd == "import-history":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = import_from_config(cfg, config_path.parent)
        update_console.print("[green]Manual history import complete[/green]")
        update_console.print(f"Database: {result.db_path}")
        update_console.print(f"Start date: {result.start_date}")
        update_console.print(f"QFQ: {result.qfq_files} files, {result.qfq_rows} rows")
        update_console.print(f"BFQ: {result.bfq_files} files, {result.bfq_rows} rows")
        update_console.print(f"Symbols: {result.symbols}")
        update_console.print(f"Stock meta rows: {result.stock_meta_rows}")
        update_console.print(f"Trading calendar rows: {result.calendar_rows}")
        update_console.print(f"Delisted stock rows: {result.delisted_rows}")
        update_console.print(f"Index meta rows: {result.index_meta_rows}")
        update_console.print(f"Index daily bars: {result.index_files} files, {result.index_rows} rows")
        return 0
    if args.cmd == "import-index-history":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = import_index_history_from_config(cfg, config_path.parent)
        update_console.print("[green]Manual index history import complete[/green]")
        update_console.print(f"Database: {result.db_path}")
        update_console.print(f"Start date: {result.start_date}")
        update_console.print(f"Index meta rows: {result.index_meta_rows}")
        update_console.print(f"Index daily bars: {result.index_files} files, {result.index_rows} rows")
        return 0
    if args.cmd == "build-universe":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = build_local_factor_universe(cfg, config_path.parent)
        update_console.print("[green]Universe build complete[/green]")
        update_console.print(f"Source: {result.source}")
        update_console.print(f"Selected: {result.selected_count}/{result.target_size}")
        update_console.print(f"Universe: {result.output_path}")
        update_console.print(f"Report: {result.report_path}")
        if result.warnings:
            for warning in result.warnings:
                update_console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0
    parser.error("data update command expected one of: " + ", ".join(sorted(DATA_UPDATE_COMMANDS)))
    return 2
