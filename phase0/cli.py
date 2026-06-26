from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from phase0.config import load_config
from phase0.cli_commands.data_governance import (
    DATA_GOVERNANCE_COMMANDS,
    handle_data_governance_command,
    register_data_governance_commands,
)
from phase0.cli_commands.dashboard import handle_dashboard_command, register_dashboard_commands
from phase0.cli_commands.intelligence import handle_intelligence_command, register_intelligence_commands
from phase0.cli_commands.maintenance import handle_maintenance_command, register_maintenance_commands
from phase0.cli_commands.output import print_manual_history_update_result
from phase0.cli_commands.reports import REPORT_EXPORT_COMMANDS, handle_report_export_command, register_report_export_commands
from phase0.cli_commands.research import RESEARCH_COMMANDS, handle_research_command, register_research_commands
from phase0.cli_commands.strategy_research import (
    STRATEGY_RESEARCH_COMMANDS,
    _print_walk_forward_trace,
    _run_db_health_gate,
    handle_strategy_research_command,
    register_strategy_research_commands,
)
from phase0.cli_commands.system import (
    handle_system_command,
    register_system_commands,
    summarize_system_maintenance_status,
)
from phase0.data_sources import ConnectivityResult, check_connectivity, fetch_yf_daily
from phase0.data_governance.quality import aggregate_quality, audit_quality
from phase0.cli_commands.delivery import (
    DELIVERY_COMMANDS,
    handle_delivery_command,
    register_delivery_commands,
    run_daily_brief_pipeline,
    run_watchlist_pipeline,
)
from phase0.cli_commands.data_update import (
    DATA_UPDATE_COMMANDS,
    _format_duration,
    _print_tushare_financial_progress,
    handle_data_update_command,
    register_data_update_commands,
)
from phase0.external_market_history import (
    load_us_daily_from_history,
    update_us_market_history_from_config,
)
from phase0.local_history import configure_local_history
from phase0.reporting import (
    write_cost_sensitivity_report,
    write_data_source_report,
    write_effectiveness_gate_report,
    write_walk_forward_report,
)
from phase0.reporting.exports import (
    export_brief_account_bill as _export_brief_account_bill,
    export_phase0_execution_gate as _export_phase0_execution_gate,
    export_phase0_financial_pti as _export_phase0_financial_pti,
    export_phase0_low_turnover_bill as _export_phase0_low_turnover_bill,
    export_phase0_market_regime_report as _export_phase0_market_regime_report,
    export_phase0_oos_report as _export_phase0_oos_report,
    export_phase0_premarket as _export_phase0_premarket,
    export_phase0_universe_pit as _export_phase0_universe_pit,
)
from phase0.reporting.paths import report_category_dir, report_path
from phase0.throttle import configure_akshare_throttle
from phase0.update_history import update_manual_history_from_config
from phase0.walk_forward import describe_walk_forward_presets, run_cost_sensitivity, run_walk_forward, save_walk_forward_csv


_print_manual_history_update_result = print_manual_history_update_result


def run_phase0(config_path: Path) -> int:
    console = Console()
    root = config_path.parent
    cfg = load_config(config_path)
    configure_local_history(cfg.get("local_history", {}), root)
    configure_akshare_throttle(cfg.get("data_sources", {}).get("akshare", {}))

    console.print("[bold]Phase 0 started[/bold]")
    years = int(cfg["years"])

    history_result = None
    update_cfg = cfg.get("manual_history_update", {})
    if bool(update_cfg.get("enabled", False)) and bool(update_cfg.get("run_before_phase0", True)):
        console.print("0) Checking/updating local A-share history through configured primary source...")
        history_result = update_manual_history_from_config(cfg, root, check_only=False)
        color = "green" if history_result.ok else "red"
        console.print(
            f"[{color}]Manual history status: {history_result.status}[/{color}] "
            f"latest={history_result.after_latest_date or history_result.before_latest_date or 'N/A'} "
            f"coverage={history_result.after_coverage:.4f} "
            f"source={history_result.primary_source or 'N/A'}"
        )

    us_result = None
    us_cfg = cfg.get("us_market_history", {})
    if bool(us_cfg.get("enabled", False)) and bool(us_cfg.get("run_before_phase0", True)):
        console.print("0b) Checking/updating US market history...")
        us_result = update_us_market_history_from_config(cfg, root, check_only=False)
        color = "green" if us_result.ok else "red"
        console.print(
            f"[{color}]US market history status: {us_result.status}[/{color}] "
            f"latest={us_result.latest_date or 'N/A'} "
            f"coverage={us_result.coverage:.4f} "
            f"source={us_result.source or 'N/A'}"
        )

    console.print("1) Checking data-source connectivity...")
    connectivity = check_connectivity(cfg["data_sources"], years=years)
    if history_result is not None:
        latest = history_result.after_latest_date or history_result.before_latest_date
        message = "; ".join(history_result.warnings[-3:])
        if history_result.primary_source:
            message = f"primary_source={history_result.primary_source}" + (f"; {message}" if message else "")
        connectivity.append(
            ConnectivityResult(
                source="manual-history",
                target="pre_run_update",
                ok=history_result.ok,
                rows=history_result.fetched_rows,
                latest_date=latest,
                error=history_result.status if not message else f"{history_result.status}; {message}",
            )
        )
    if us_result is not None:
        message = "; ".join(us_result.warnings[-3:])
        connectivity.append(
            ConnectivityResult(
                source="us-market-history",
                target="pre_run_update",
                ok=us_result.ok,
                rows=us_result.fetched_rows,
                latest_date=us_result.latest_date,
                error=us_result.status if not message else f"{us_result.status}; {message}",
            )
        )

    console.print("2) Running quality audit on US market history targets...")
    quality_results = []
    us_symbols = [str(item) for item in cfg.get("us_market_history", {}).get("symbols", [])]
    if us_symbols:
        from datetime import date, timedelta

        end = date.today()
        start = end - timedelta(days=365 * years + 20)
        us_bars = load_us_daily_from_history(us_symbols, start, end)
        for sym in us_symbols:
            df = us_bars[us_bars["symbol"] == sym].copy() if not us_bars.empty else us_bars
            if not df.empty:
                quality_results.append(audit_quality(sym, df))
    if not quality_results:
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

    report_dir = report_category_dir(root=root, config=cfg, category="phase0")
    write_data_source_report(
        report_path(root=root, config=cfg, category="phase0", parts=("phase0_data_source_report.md",)),
        connectivity=connectivity,
        quality=quality_results,
        quality_summary=quality_summary,
    )

    console.print("3) Running walk-forward backtest baseline...")
    for line in describe_walk_forward_presets(cfg.get("walk_forward", {})):
        console.print(f"[cyan]{line}[/cyan]")
    wf = run_walk_forward(cfg)
    folds_df = wf["folds"]
    candidate_folds_df = wf.get("candidate_folds")
    summary = wf["summary"]

    if not folds_df.empty:
        save_walk_forward_csv(folds_df, report_path(root=root, config=cfg, category="phase0", parts=("phase0_walk_forward_folds.csv",)))
    if candidate_folds_df is not None and not candidate_folds_df.empty:
        save_walk_forward_csv(candidate_folds_df, report_path(root=root, config=cfg, category="phase0", parts=("phase0_walk_forward_candidates.csv",)))
    universe_audit_df = wf.get("universe_audit")
    if universe_audit_df is not None and not universe_audit_df.empty:
        save_walk_forward_csv(universe_audit_df, report_path(root=root, config=cfg, category="phase0", parts=("phase0_walk_forward_universe_audit.csv",)))
    write_walk_forward_report(
        report_path(root=root, config=cfg, category="phase0", parts=("phase0_walk_forward_report.md",)),
        summary=summary,
        folds_df=folds_df,
    )
    write_effectiveness_gate_report(
        report_path(root=root, config=cfg, category="phase0", parts=("phase0_effectiveness_report.md",)),
        wf_summary=summary,
        gate_cfg=cfg.get("walk_forward", {}).get("gate", {}),
    )

    console.print("4) Exporting selected strategy bill and daily assets...")
    bill_result = _export_phase0_low_turnover_bill(config_path=config_path)
    console.print(f"Bill: {bill_result['bill']}")
    console.print(f"Daily assets: {bill_result['daily']}")
    console.print(f"Bill preview: {bill_result['preview']}")
    console.print(f"Bill rows: {bill_result['rows']}")

    console.print("[green]Phase 0 complete[/green]")
    console.print(f"Reports: {report_dir}")
    return 0


def run_phase0_cost_sensitivity(config_path: Path, scenarios: list[dict[str, float | str]]) -> int:
    console = Console()
    root = config_path.parent
    cfg = load_config(config_path)
    configure_local_history(cfg.get("local_history", {}), root)
    configure_akshare_throttle(cfg.get("data_sources", {}).get("akshare", {}))

    cfg["cost_sensitivity"] = {
        "enabled": True,
        "scenarios": scenarios,
    }
    report_dir = report_category_dir(root=root, config=cfg, category="phase0")
    console.print("[bold]Phase 0 cost sensitivity started[/bold]")
    console.print("Scenarios:")
    for scenario in scenarios:
        console.print(
            f"- {scenario['name']}: "
            f"slippage={float(scenario['slippage']):.5f}, "
            f"commission={float(scenario['commission']):.5f}, "
            f"stamp_duty_sell={float(scenario['stamp_duty_sell']):.5f}"
        )

    sensitivity_df = run_cost_sensitivity(cfg)
    if not sensitivity_df.empty:
        save_walk_forward_csv(sensitivity_df, report_path(root=root, config=cfg, category="phase0", parts=("phase0_cost_sensitivity.csv",)))
    write_cost_sensitivity_report(
        report_path(root=root, config=cfg, category="phase0", parts=("phase0_cost_sensitivity_report.md",)),
        sensitivity_df,
    )

    console.print("[green]Phase 0 cost sensitivity complete[/green]")
    console.print(f"Reports: {report_dir}")
    return 0


def _parse_cost_scenario(text: str, cfg: dict) -> dict[str, float | str]:
    parts = [part.strip() for part in text.split(":")]
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"invalid cost scenario '{text}', expected name:slippage")
    wcfg = cfg.get("walk_forward", {})
    return {
        "name": parts[0],
        "slippage": float(parts[1]),
        "commission": float(wcfg.get("commission", 0.0)),
        "stamp_duty_sell": float(wcfg.get("stamp_duty_sell", 0.0)),
    }


def _configured_cost_scenarios(cfg: dict) -> list[dict[str, float | str]]:
    scenarios = cfg.get("cost_sensitivity", {}).get("scenarios", [])
    return [
        {
            "name": str(item["name"]),
            "slippage": float(item["slippage"]),
            "commission": float(item.get("commission", cfg.get("walk_forward", {}).get("commission", 0.0))),
            "stamp_duty_sell": float(item.get("stamp_duty_sell", cfg.get("walk_forward", {}).get("stamp_duty_sell", 0.0))),
        }
        for item in scenarios
    ]


def main() -> int:
    top_level_groups = {
        "Data Import & Update": [
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
        ],
        "Delivery & Reports": [
            "bill",
            "brief",
            "daily-brief",
            "market-regime",
            "oos-report",
            "premarket",
        ],
        "Governance & Research": [
            "adjustment-audit",
            "cost-sensitivity",
            "db-health",
            "execution-gate",
            "factor-effectiveness",
            "financial-pti",
            "index-asof-audit",
            "intelligence",
            "overfit-diagnostic",
            "run",
            "strategy-admission",
            "strategy-core-reachability-diagnostic",
            "strategy-csi300-attribution",
            "strategy-exposure-diagnostic",
            "strategy-failure-attribution",
            "strategy-filter-diagnostic",
            "strategy-fold-attribution",
            "strategy-holdings-exposure",
            "strategy-market-context",
            "strategy-missing-core-audit",
            "strategy-participation-overlay",
            "strategy-role-card",
            "universe-pti",
        ],
        "Operations": [
            "dashboard",
            "maintain",
            "system",
        ],
    }
    grouped_help_lines = ["Top-level command index by category:"]
    for group_name in sorted(top_level_groups):
        grouped_help_lines.append(f"  {group_name}:")
        grouped_help_lines.extend([f"    - {name}" for name in sorted(top_level_groups[group_name])])
    parser = argparse.ArgumentParser(
        description="Run Phase 0 pipeline",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "\n".join(grouped_help_lines)
            + "\n\n"
            "Nested command groups:\n"
            "  brief: account-bill, daily, daily-brief, premarket, watchlist\n"
            "  dashboard: scan\n"
            "  intelligence: collect, import-local, review-candidates, validate\n"
            "  maintain: resume, run, status, stop, supervise, tick\n"
            "  system: status\n"
        ),
    )
    sub = parser.add_subparsers(dest="cmd")
    run_parser = sub.add_parser("run", help="Run phase0 pipeline")
    run_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    cost_parser = sub.add_parser("cost-sensitivity", help="Run explicit phase0 cost sensitivity scenarios")
    cost_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    cost_parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Scenario in name:slippage format. Repeatable, e.g. --scenario base:0.001 --scenario stress:0.003",
    )
    cost_parser.add_argument(
        "--use-config-scenarios",
        action="store_true",
        help="Use cost_sensitivity.scenarios from config.yaml. Required when --scenario is omitted.",
    )
    register_report_export_commands(sub)
    register_data_governance_commands(sub)
    register_strategy_research_commands(sub)
    register_research_commands(sub)
    register_dashboard_commands(sub)
    register_intelligence_commands(sub)
    register_maintenance_commands(sub)
    register_system_commands(sub)
    register_delivery_commands(sub)
    register_data_update_commands(sub)

    args = parser.parse_args()
    if args.cmd in REPORT_EXPORT_COMMANDS:
        return handle_report_export_command(args, parser=parser)
    if args.cmd in DATA_GOVERNANCE_COMMANDS:
        return handle_data_governance_command(args, parser=parser)
    if args.cmd in STRATEGY_RESEARCH_COMMANDS:
        return handle_strategy_research_command(args, parser=parser)
    if args.cmd in RESEARCH_COMMANDS:
        return handle_research_command(args, parser=parser)
    if args.cmd == "dashboard":
        return handle_dashboard_command(args, parser=parser)
    if args.cmd == "intelligence":
        return handle_intelligence_command(args, parser=parser)
    if args.cmd == "maintain":
        return handle_maintenance_command(args, parser=parser)
    if args.cmd == "system":
        return handle_system_command(args, parser=parser)
    if args.cmd in DELIVERY_COMMANDS:
        return handle_delivery_command(args, parser=parser)
    if args.cmd in DATA_UPDATE_COMMANDS:
        return handle_data_update_command(args, parser=parser)
    if args.cmd == "cost-sensitivity":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        scenarios = [_parse_cost_scenario(text, cfg) for text in args.scenario]
        if args.use_config_scenarios:
            scenarios = _configured_cost_scenarios(cfg)
        if not scenarios:
            console = Console()
            console.print(
                "[red]No cost sensitivity scenarios specified.[/red] "
                "Use --scenario name:slippage or --use-config-scenarios."
            )
            return 2
        return run_phase0_cost_sensitivity(config_path, scenarios)
    if args.cmd != "run":
        parser.print_help()
        return 1

    config_path = Path(args.config).resolve()
    cfg = load_config(config_path)
    console = Console()
    gate_exit = _run_db_health_gate(
        console=console,
        config=cfg.get("phase0", cfg),
        root=config_path.parent,
        scope="cn",
        fail_on="error",
        label="Phase 0 run",
    )
    if gate_exit != 0:
        return gate_exit
    return run_phase0(config_path)


if __name__ == "__main__":
    raise SystemExit(main())
