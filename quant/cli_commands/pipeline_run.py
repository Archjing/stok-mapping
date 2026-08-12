from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from rich.console import Console

from quant.cli_commands.gates import run_db_health_gate as _run_db_health_gate
from quant.config import load_config
from quant.data_access.connectivity import ConnectivityResult, check_connectivity, fetch_yf_daily
from quant.data_governance.quality import aggregate_quality, audit_quality
from quant.data_governance.external_market_history import load_us_daily_from_history, update_us_market_history_from_config
from quant.data_governance.cross_market_reference_history import (
    CrossMarketReferenceHistoryUpdateResult,
    configure_cross_market_reference_history_from_config,
    update_cross_market_reference_history_from_config,
)
from quant.data_access.local_history import configure_local_history
from quant.reporting import (
    write_cost_sensitivity_report,
    write_data_source_report,
    write_effectiveness_gate_report,
    write_walk_forward_report,
)
from quant.reporting.exports import export_low_turnover_bill
from quant.reporting.paths import report_category_dir, report_path
from quant.data_access.throttle import configure_akshare_throttle
from quant.data_governance.update_history import update_manual_history_from_config
from quant.walk_forward import describe_walk_forward_presets, run_cost_sensitivity, run_walk_forward, save_walk_forward_csv


PIPELINE_RUN_COMMANDS = frozenset({"cost-sensitivity", "run"})


def _apply_walk_forward_runtime_overrides(
    cfg: dict[str, Any],
    *,
    profile: bool = False,
    no_wf_cache: bool = False,
    refresh_wf_cache: bool = False,
) -> None:
    wcfg = cfg.setdefault("walk_forward", {})
    if profile:
        wcfg.setdefault("execution", {})["profile"] = True
    cache_cfg = wcfg.setdefault("cache", {})
    if no_wf_cache:
        cache_cfg["enabled"] = False
    if refresh_wf_cache:
        cache_cfg["refresh"] = True


def require_fresh_cross_market_reference(
    cfg: dict[str, Any],
    result: CrossMarketReferenceHistoryUpdateResult,
) -> None:
    reference_enabled = bool(cfg.get("cross_market_reference_history", {}).get("enabled", False))
    cross_market_enabled = bool(cfg.get("walk_forward", {}).get("strategy_v2", {}).get("cross_market", {}).get("enabled", False))
    if reference_enabled and cross_market_enabled and not result.ok:
        raise RuntimeError(
            "cross_market_reference_history_gate_failed:"
            f"status={result.status};coverage={result.coverage:.4f};latest_date={result.latest_date or 'N/A'}"
        )


def run_pipeline(
    config_path: Path,
    *,
    profile: bool = False,
    no_wf_cache: bool = False,
    refresh_wf_cache: bool = False,
) -> int:
    console = Console()
    root = config_path.parent
    cfg = load_config(config_path)
    _apply_walk_forward_runtime_overrides(
        cfg,
        profile=profile,
        no_wf_cache=no_wf_cache,
        refresh_wf_cache=refresh_wf_cache,
    )
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

    reference_result = None
    reference_cfg = cfg.get("cross_market_reference_history", {})
    configure_cross_market_reference_history_from_config(cfg, root)
    if bool(reference_cfg.get("enabled", False)):
        update_reference = bool(reference_cfg.get("run_before_phase0", True))
        console.print("0c) Checking/updating cross-market reference history..." if update_reference else "0c) Checking cross-market reference history...")
        reference_result = update_cross_market_reference_history_from_config(cfg, root, check_only=not update_reference)
        color = "green" if reference_result.ok else "red"
        console.print(
            f"[{color}]Cross-market reference history status: {reference_result.status}[/{color}] "
            f"latest={reference_result.latest_date or 'N/A'} "
            f"coverage={reference_result.coverage:.4f}"
        )
        require_fresh_cross_market_reference(cfg, reference_result)

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
    if reference_result is not None:
        message = "; ".join(reference_result.warnings[-3:])
        connectivity.append(
            ConnectivityResult(
                source="cross-market-reference-history",
                target="pre_run_update",
                ok=reference_result.ok,
                rows=reference_result.fetched_rows,
                latest_date=reference_result.latest_date,
                error=reference_result.status if not message else f"{reference_result.status}; {message}",
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

    # Keep Phase 0 useful when the online US fallback is empty or rate-limited.
    if not quality_results:
        from quant.walk_forward import _load_symbol

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
    wf = run_walk_forward(cfg, root=root)
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
    bill_result = export_low_turnover_bill(config_path=config_path)
    console.print(f"Bill: {bill_result['bill']}")
    console.print(f"Daily assets: {bill_result['daily']}")
    console.print(f"Bill preview: {bill_result['preview']}")
    console.print(f"Bill rows: {bill_result['rows']}")

    console.print("[green]Phase 0 complete[/green]")
    console.print(f"Reports: {report_dir}")
    return 0


def run_pipeline_cost_sensitivity(config_path: Path, scenarios: list[dict[str, float | str]]) -> int:
    console = Console()
    root = config_path.parent
    cfg = load_config(config_path)
    configure_local_history(cfg.get("local_history", {}), root)
    configure_cross_market_reference_history_from_config(cfg, root)
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

    sensitivity_df = run_cost_sensitivity(cfg, root=root)
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


def register_pipeline_run_commands(subparsers: argparse._SubParsersAction) -> None:
    run_parser = subparsers.add_parser("run", help="Run phase0 pipeline")
    run_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    run_parser.add_argument("--profile", action="store_true", help="Write walk-forward timing profile JSON under logs/perf")
    run_parser.add_argument("--no-wf-cache", action="store_true", help="Disable walk-forward runtime caches for this run")
    run_parser.add_argument("--refresh-wf-cache", action="store_true", help="Refresh walk-forward disk caches before use")
    cost_parser = subparsers.add_parser("cost-sensitivity", help="Run explicit phase0 cost sensitivity scenarios")
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


def handle_pipeline_run_command(args: argparse.Namespace, *, parser: argparse.ArgumentParser, console: Any | None = None) -> int:
    run_console = console or Console()
    if args.cmd == "cost-sensitivity":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        scenarios = [_parse_cost_scenario(text, cfg) for text in args.scenario]
        if args.use_config_scenarios:
            scenarios = _configured_cost_scenarios(cfg)
        if not scenarios:
            run_console.print(
                "[red]No cost sensitivity scenarios specified.[/red] "
                "Use --scenario name:slippage or --use-config-scenarios."
            )
            return 2
        return run_pipeline_cost_sensitivity(config_path, scenarios)
    if args.cmd == "run":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        gate_exit = _run_db_health_gate(
            console=run_console,
            config=cfg,
            root=config_path.parent,
            scope="cn",
            fail_on="error",
            label="Phase 0 run",
        )
        if gate_exit != 0:
            return gate_exit
        return run_pipeline(
            config_path,
            profile=bool(args.profile),
            no_wf_cache=bool(args.no_wf_cache),
            refresh_wf_cache=bool(args.refresh_wf_cache),
        )
    parser.error("phase0 run command expected one of: " + ", ".join(sorted(PIPELINE_RUN_COMMANDS)))
    return 2
