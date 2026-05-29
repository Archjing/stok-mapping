from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from phase0.config import load_config
from phase0.data_sources import check_connectivity, fetch_yf_daily
from phase0.financial_factors import update_financial_factors_from_config
from phase0.import_history import import_from_config, import_index_history_from_config
from phase0.quality import aggregate_quality, audit_quality
from phase0.reporting import (
    write_data_source_report,
    write_effectiveness_gate_report,
    write_walk_forward_report,
)
from phase0.universe import build_local_factor_universe
from phase0.update_history import update_manual_history_from_config
from phase0.walk_forward import run_walk_forward, save_walk_forward_csv


def run_phase0(config_path: Path) -> int:
    console = Console()
    root = config_path.parent
    cfg = load_config(config_path)

    console.print("[bold]Phase 0 started[/bold]")
    years = int(cfg["years"])

    console.print("1) Checking data-source connectivity...")
    connectivity = check_connectivity(cfg["data_sources"], years=years)

    console.print("2) Running quality audit on yfinance connectivity targets...")
    quality_results = []
    for r in connectivity:
        if r.source == "yfinance" and r.ok:
            df = fetch_yf_daily(r.target, years=years)
            quality_results.append(audit_quality(r.target, df))
    quality_summary = aggregate_quality(quality_results)

    # Fallback: if yfinance is unavailable/rate-limited, run quality audit on
    # walk-forward symbol pool through AkShare-backed loaders so Phase 0 still
    # produces a usable quality section.
    if not quality_results:
        from phase0.walk_forward import _load_symbol  # local import to avoid cycle

        for sym in cfg.get("symbols", []):
            try:
                df = _load_symbol(sym, years=years)
                quality_results.append(audit_quality(sym, df))
            except Exception:
                continue
        quality_summary = aggregate_quality(quality_results)

    report_dir = root / "reports"
    write_data_source_report(
        report_dir / "phase0_data_source_report.md",
        connectivity=connectivity,
        quality=quality_results,
        quality_summary=quality_summary,
    )

    console.print("3) Running walk-forward backtest baseline...")
    wf = run_walk_forward(cfg)
    folds_df = wf["folds"]
    candidate_folds_df = wf.get("candidate_folds")
    summary = wf["summary"]

    if not folds_df.empty:
        save_walk_forward_csv(folds_df, report_dir / "phase0_walk_forward_folds.csv")
    if candidate_folds_df is not None and not candidate_folds_df.empty:
        save_walk_forward_csv(candidate_folds_df, report_dir / "phase0_walk_forward_candidates.csv")
    write_walk_forward_report(report_dir / "phase0_walk_forward_report.md", summary=summary, folds_df=folds_df)
    write_effectiveness_gate_report(report_dir / "phase0_effectiveness_report.md", wf_summary=summary)

    console.print("[green]Phase 0 complete[/green]")
    console.print(f"Reports: {report_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 0 pipeline")
    sub = parser.add_subparsers(dest="cmd")
    run_parser = sub.add_parser("run", help="Run phase0 pipeline")
    run_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    universe_parser = sub.add_parser("build-universe", help="Build local-factor A-share universe")
    universe_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    history_parser = sub.add_parser("import-history", help="Import manual A-share history zip files")
    history_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    index_history_parser = sub.add_parser("import-index-history", help="Rebuild manual A-share index history tables only")
    index_history_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    update_history_parser = sub.add_parser("update-history", help="Incrementally update manual A-share history database")
    update_history_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    update_history_parser.add_argument("--check-only", action="store_true", help="Only check freshness, do not fetch or write")
    update_history_parser.add_argument(
        "--no-build-universe",
        action="store_true",
        help="Do not rebuild local factor universe after a successful update",
    )
    financial_parser = sub.add_parser("update-financials", help="Update A-share quarterly financial factors")
    financial_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    financial_parser.add_argument("--periods", type=int, default=None, help="Override number of recent quarters to fetch")
    financial_parser.add_argument(
        "--no-build-universe",
        action="store_true",
        help="Do not rebuild local factor universe after a successful update",
    )

    args = parser.parse_args()
    if args.cmd == "update-financials":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = update_financial_factors_from_config(cfg, config_path.parent, periods=args.periods)
        console = Console()
        color = "green" if result.ok else "red"
        console.print(f"[{color}]Financial factor update status: {result.status}[/{color}]")
        console.print(f"Database: {result.db_path}")
        console.print(f"Periods requested: {', '.join(result.periods_requested) or 'N/A'}")
        console.print(f"Periods updated: {', '.join(result.periods_updated) or 'N/A'}")
        console.print(f"Fetched rows: {result.fetched_rows}")
        console.print(f"Inserted rows: {result.inserted_rows}")
        if result.factor_coverage:
            console.print(
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
                console.print(f"[yellow]Warning:[/yellow] {warning}")
        if not result.ok:
            return 2
        if (
            not args.no_build_universe
            and result.inserted_rows > 0
            and bool(cfg.get("financial_factors", {}).get("rebuild_universe_after", True))
        ):
            universe_result = build_local_factor_universe(cfg, config_path.parent)
            console.print("[green]Universe rebuild complete[/green]")
            console.print(f"Source: {universe_result.source}")
            console.print(f"Selected: {universe_result.selected_count}/{universe_result.target_size}")
            if universe_result.warnings:
                for warning in universe_result.warnings:
                    console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0
    if args.cmd == "update-history":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = update_manual_history_from_config(cfg, config_path.parent, check_only=args.check_only)
        console = Console()
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
        if not result.ok:
            return 2
        if (
            not args.check_only
            and not args.no_build_universe
            and result.status in {"updated", "metadata_updated"}
            and bool(cfg.get("manual_history_update", {}).get("rebuild_universe_after", False))
        ):
            universe_result = build_local_factor_universe(cfg, config_path.parent)
            console.print("[green]Universe rebuild complete[/green]")
            console.print(f"Source: {universe_result.source}")
            console.print(f"Selected: {universe_result.selected_count}/{universe_result.target_size}")
            if universe_result.warnings:
                for warning in universe_result.warnings:
                    console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0
    if args.cmd == "import-history":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = import_from_config(cfg, config_path.parent)
        console = Console()
        console.print("[green]Manual history import complete[/green]")
        console.print(f"Database: {result.db_path}")
        console.print(f"Start date: {result.start_date}")
        console.print(f"QFQ: {result.qfq_files} files, {result.qfq_rows} rows")
        console.print(f"BFQ: {result.bfq_files} files, {result.bfq_rows} rows")
        console.print(f"Symbols: {result.symbols}")
        console.print(f"Stock meta rows: {result.stock_meta_rows}")
        console.print(f"Trading calendar rows: {result.calendar_rows}")
        console.print(f"Delisted stock rows: {result.delisted_rows}")
        console.print(f"Index meta rows: {result.index_meta_rows}")
        console.print(f"Index daily bars: {result.index_files} files, {result.index_rows} rows")
        return 0
    if args.cmd == "import-index-history":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = import_index_history_from_config(cfg, config_path.parent)
        console = Console()
        console.print("[green]Manual index history import complete[/green]")
        console.print(f"Database: {result.db_path}")
        console.print(f"Start date: {result.start_date}")
        console.print(f"Index meta rows: {result.index_meta_rows}")
        console.print(f"Index daily bars: {result.index_files} files, {result.index_rows} rows")
        return 0
    if args.cmd == "build-universe":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = build_local_factor_universe(cfg, config_path.parent)
        console = Console()
        console.print("[green]Universe build complete[/green]")
        console.print(f"Source: {result.source}")
        console.print(f"Selected: {result.selected_count}/{result.target_size}")
        console.print(f"Universe: {result.output_path}")
        console.print(f"Report: {result.report_path}")
        if result.warnings:
            for warning in result.warnings:
                console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0
    if args.cmd != "run":
        parser.print_help()
        return 1

    config_path = Path(args.config).resolve()
    return run_phase0(config_path)


if __name__ == "__main__":
    raise SystemExit(main())
