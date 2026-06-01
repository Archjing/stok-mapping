from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from phase0.config import load_config
from phase0.data_sources import ConnectivityResult, check_connectivity, fetch_yf_daily
from phase0.external_market_history import (
    load_us_daily_from_history,
    update_hk_market_history_from_config,
    update_us_market_history_from_config,
)
from phase0.financial_factors import update_financial_factors_from_config
from phase0.import_history import import_from_config, import_index_history_from_config
from phase0.local_history import configure_local_history
from phase0.quality import aggregate_quality, audit_quality
from phase0.reporting import (
    write_cost_sensitivity_report,
    write_data_source_report,
    write_effectiveness_gate_report,
    write_walk_forward_report,
)
from phase0.throttle import configure_akshare_throttle
from phase0.universe import build_local_factor_universe
from phase0.update_history import update_manual_history_from_config
from phase0.walk_forward import run_cost_sensitivity, run_walk_forward, save_walk_forward_csv


def _export_phase0_low_turnover_bill(
    *,
    config_path: Path,
    refresh_cache: bool = False,
    no_panel_cache: bool = False,
) -> dict:
    from scripts.export_low_turnover_bill import export_low_turnover_bill

    return export_low_turnover_bill(
        config_path=config_path,
        refresh_cache=refresh_cache,
        no_panel_cache=no_panel_cache,
    )


def _export_phase0_market_regime_report() -> dict:
    from scripts.export_market_regime_report import export_market_regime_report

    return export_market_regime_report(
        input_path=Path("reports/phase0_low_turnover_oos_curve.csv"),
        summary_output=Path("reports/phase0_market_regime_summary.csv"),
        segment_output=Path("reports/phase0_market_regime_segments.csv"),
        html_output=Path("reports/phase0_market_regime_report.html"),
    )


def _export_phase0_oos_report(
    *,
    config_path: Path,
    profile: str | None = None,
    output_dir: str | None = None,
    refresh_cache: bool = False,
    no_panel_cache: bool = False,
    slippage: float | None = None,
    commission: float | None = None,
    stamp_duty_sell: float | None = None,
    price_mode: str | None = None,
    lot_size: int | None = None,
    max_participation_rate: float | None = None,
    enable_limit_check: bool | None = None,
    enable_suspension_check: bool | None = None,
) -> dict:
    from scripts.export_low_turnover_oos_report import export_low_turnover_oos_report

    return export_low_turnover_oos_report(
        config_path=config_path,
        profile=profile,
        output_dir=output_dir,
        refresh_cache=refresh_cache,
        no_panel_cache=no_panel_cache,
        slippage=slippage,
        commission=commission,
        stamp_duty_sell=stamp_duty_sell,
        price_mode=price_mode,
        lot_size=lot_size,
        max_participation_rate=max_participation_rate,
        enable_limit_check=enable_limit_check,
        enable_suspension_check=enable_suspension_check,
    )


def _export_phase0_financial_pti(config_path: Path) -> dict:
    from scripts.audit_financial_pti import audit_financial_pti

    return audit_financial_pti(
        config_path=config_path,
        summary_output=Path("reports/phase0_financial_pti_summary.csv"),
        sample_output=Path("reports/phase0_financial_pti_problem_samples.csv"),
        html_output=Path("reports/phase0_financial_pti_report.html"),
    )


def _export_phase0_premarket(
    *,
    config_path: Path,
    refresh_cache: bool = False,
    no_panel_cache: bool = False,
) -> dict:
    from scripts.export_premarket_watchlist import export_premarket_watchlist

    return export_premarket_watchlist(
        config_path=config_path,
        refresh_cache=refresh_cache,
        no_panel_cache=no_panel_cache,
    )


def _export_phase0_execution_gate(
    *,
    config_path: Path,
    profile: str | None = None,
    output_dir: str | None = None,
    refresh_cache: bool = False,
    no_panel_cache: bool = False,
    slippage: float | None = None,
    commission: float | None = None,
    stamp_duty_sell: float | None = None,
    price_mode: str | None = None,
    lot_size: int | None = None,
    max_participation_rate: float | None = None,
    enable_limit_check: bool | None = None,
    enable_suspension_check: bool | None = None,
) -> dict:
    from scripts.export_execution_effectiveness_report import export_execution_effectiveness_report

    return export_execution_effectiveness_report(
        config_path=config_path,
        profile=profile,
        output_dir=output_dir,
        refresh_cache=refresh_cache,
        no_panel_cache=no_panel_cache,
        slippage=slippage,
        commission=commission,
        stamp_duty_sell=stamp_duty_sell,
        price_mode=price_mode,
        lot_size=lot_size,
        max_participation_rate=max_participation_rate,
        enable_limit_check=enable_limit_check,
        enable_suspension_check=enable_suspension_check,
    )


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

    console.print("4) Exporting selected low-turnover bill and daily assets...")
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
    report_dir = root / "reports"
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
        save_walk_forward_csv(sensitivity_df, report_dir / "phase0_cost_sensitivity.csv")
    write_cost_sensitivity_report(report_dir / "phase0_cost_sensitivity_report.md", sensitivity_df)

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
    parser = argparse.ArgumentParser(description="Run Phase 0 pipeline")
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
    bill_parser = sub.add_parser("bill", help="Export selected phase0 low-turnover bill artifacts")
    bill_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    bill_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    bill_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
    market_regime_parser = sub.add_parser("market-regime", help="Export phase0 market-regime validation report")
    market_regime_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    oos_parser = sub.add_parser("oos-report", help="Export phase0 continuous OOS report with execution profile")
    oos_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    oos_parser.add_argument("--profile", choices=["research", "live"], default=None, help="Execution parameter profile: research or live")
    oos_parser.add_argument("--output-dir", default=None, help="Optional standalone output directory for OOS artifacts")
    oos_parser.add_argument("--slippage", type=float, default=None, help="Override profile slippage for this run")
    oos_parser.add_argument("--commission", type=float, default=None, help="Override profile commission for this run")
    oos_parser.add_argument("--stamp-duty-sell", type=float, default=None, help="Override profile sell stamp duty for this run")
    oos_parser.add_argument("--price-mode", choices=["close", "next_open", "conservative"], default=None, help="Override profile execution price mode")
    oos_parser.add_argument("--lot-size", type=int, default=None, help="Override profile lot size")
    oos_parser.add_argument("--max-participation-rate", type=float, default=None, help="Override profile max market-volume participation rate")
    oos_parser.add_argument("--enable-limit-check", action=argparse.BooleanOptionalAction, default=None, help="Override profile limit-up/down check")
    oos_parser.add_argument("--enable-suspension-check", action=argparse.BooleanOptionalAction, default=None, help="Override profile suspension check")
    oos_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    oos_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
    financial_pti_parser = sub.add_parser("financial-pti", help="Audit financial factor point-in-time validity")
    financial_pti_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    premarket_parser = sub.add_parser("premarket", help="Export phase0 07:30 premarket watchlist")
    premarket_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    premarket_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    premarket_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
    execution_gate_parser = sub.add_parser("execution-gate", help="Run phase0 account execution effectiveness gate")
    execution_gate_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    execution_gate_parser.add_argument("--profile", choices=["research", "live"], default=None, help="Execution parameter profile: research or live")
    execution_gate_parser.add_argument("--output-dir", default=None, help="Optional standalone output directory for live execution backtest artifacts")
    execution_gate_parser.add_argument("--slippage", type=float, default=None, help="Override profile slippage for this run")
    execution_gate_parser.add_argument("--commission", type=float, default=None, help="Override profile commission for this run")
    execution_gate_parser.add_argument("--stamp-duty-sell", type=float, default=None, help="Override profile sell stamp duty for this run")
    execution_gate_parser.add_argument("--price-mode", choices=["close", "next_open", "conservative"], default=None, help="Override profile execution price mode")
    execution_gate_parser.add_argument("--lot-size", type=int, default=None, help="Override profile lot size")
    execution_gate_parser.add_argument("--max-participation-rate", type=float, default=None, help="Override profile max market-volume participation rate")
    execution_gate_parser.add_argument("--enable-limit-check", action=argparse.BooleanOptionalAction, default=None, help="Override profile limit-up/down check")
    execution_gate_parser.add_argument("--enable-suspension-check", action=argparse.BooleanOptionalAction, default=None, help="Override profile suspension check")
    execution_gate_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    execution_gate_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
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
    us_history_parser = sub.add_parser("update-us-market-history", help="Incrementally update US market history database")
    us_history_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    us_history_parser.add_argument("--check-only", action="store_true", help="Only check freshness, do not fetch or write")
    hk_history_parser = sub.add_parser("update-hk-market-history", help="Incrementally update HK market history database")
    hk_history_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    hk_history_parser.add_argument("--check-only", action="store_true", help="Only check freshness, do not fetch or write")
    financial_parser = sub.add_parser("update-financials", help="Update A-share quarterly financial factors")
    financial_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    financial_parser.add_argument("--periods", type=int, default=None, help="Override number of recent quarters to fetch")
    financial_parser.add_argument(
        "--no-build-universe",
        action="store_true",
        help="Do not rebuild local factor universe after a successful update",
    )

    args = parser.parse_args()
    if args.cmd == "bill":
        config_path = Path(args.config).resolve()
        console = Console()
        console.print("[bold]Phase 0 bill export started[/bold]")
        result = _export_phase0_low_turnover_bill(
            config_path=config_path,
            refresh_cache=bool(args.refresh_cache),
            no_panel_cache=bool(args.no_panel_cache),
        )
        console.print("[green]Bill export complete[/green]")
        console.print(f"Bill: {result['bill']}")
        console.print(f"Daily assets: {result['daily']}")
        console.print(f"Preview: {result['preview']}")
        console.print(f"Rows: {result['rows']}")
        return 0
    if args.cmd == "market-regime":
        console = Console()
        console.print("[bold]Phase 0 market-regime report started[/bold]")
        result = _export_phase0_market_regime_report()
        console.print("[green]Market-regime report complete[/green]")
        console.print(f"Summary: {result['summary']}")
        console.print(f"Segments: {result['segments']}")
        console.print(f"HTML: {result['html']}")
        console.print(f"Rows: {result['rows']}")
        return 0
    if args.cmd == "oos-report":
        config_path = Path(args.config).resolve()
        console = Console()
        console.print("[bold]Phase 0 OOS report started[/bold]")
        result = _export_phase0_oos_report(
            config_path=config_path,
            profile=args.profile,
            output_dir=args.output_dir,
            refresh_cache=bool(args.refresh_cache),
            no_panel_cache=bool(args.no_panel_cache),
            slippage=args.slippage,
            commission=args.commission,
            stamp_duty_sell=args.stamp_duty_sell,
            price_mode=args.price_mode,
            lot_size=args.lot_size,
            max_participation_rate=args.max_participation_rate,
            enable_limit_check=args.enable_limit_check,
            enable_suspension_check=args.enable_suspension_check,
        )
        console.print("[green]OOS report complete[/green]")
        console.print(f"Profile: {result['profile']}")
        console.print(f"Daily assets: {result['daily_assets']}")
        console.print(f"Report: {result['report']}")
        console.print(f"Curve: {result['curve']}")
        console.print(f"Fold: {result['fold']}")
        return 0
    if args.cmd == "financial-pti":
        config_path = Path(args.config).resolve()
        console = Console()
        console.print("[bold]Phase 0 financial PTI audit started[/bold]")
        result = _export_phase0_financial_pti(config_path)
        console.print("[green]Financial PTI audit complete[/green]")
        console.print(f"Verdict: {result['verdict']}")
        console.print(f"Summary: {result['summary']}")
        console.print(f"Samples: {result['samples']}")
        console.print(f"HTML: {result['html']}")
        return 0
    if args.cmd == "premarket":
        config_path = Path(args.config).resolve()
        console = Console()
        console.print("[bold]Phase 0 premarket watchlist started[/bold]")
        result = _export_phase0_premarket(
            config_path=config_path,
            refresh_cache=bool(args.refresh_cache),
            no_panel_cache=bool(args.no_panel_cache),
        )
        console.print("[green]Premarket watchlist complete[/green]")
        console.print(f"Watchlist: {result['watchlist']}")
        console.print(f"Report: {result['report']}")
        console.print(f"Rows: {result['rows']}")
        console.print(f"Signal date: {result['signal_date']}")
        console.print(f"Check time: {result['check_time']}")
        return 0
    if args.cmd == "execution-gate":
        config_path = Path(args.config).resolve()
        console = Console()
        console.print("[bold]Phase 0 account execution gate started[/bold]")
        result = _export_phase0_execution_gate(
            config_path=config_path,
            profile=args.profile,
            output_dir=args.output_dir,
            refresh_cache=bool(args.refresh_cache),
            no_panel_cache=bool(args.no_panel_cache),
            slippage=args.slippage,
            commission=args.commission,
            stamp_duty_sell=args.stamp_duty_sell,
            price_mode=args.price_mode,
            lot_size=args.lot_size,
            max_participation_rate=args.max_participation_rate,
            enable_limit_check=args.enable_limit_check,
            enable_suspension_check=args.enable_suspension_check,
        )
        console.print("[green]Account execution gate complete[/green]")
        console.print(f"Verdict: {result['verdict']}")
        console.print(f"Folds: {result['folds']}")
        console.print(f"Report: {result['report']}")
        return 0
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
        console.print(f"Primary source: {result.primary_source or 'N/A'}")
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
    if args.cmd == "update-us-market-history":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = update_us_market_history_from_config(cfg, config_path.parent, check_only=args.check_only)
        console = Console()
        color = "green" if result.ok else "red"
        console.print(f"[{color}]US market history update status: {result.status}[/{color}]")
        console.print(f"Database: {result.db_path}")
        console.print(f"Latest date: {result.latest_date or 'N/A'}")
        console.print(f"Coverage: {result.coverage:.4f} ({result.covered_symbols}/{result.symbol_count})")
        console.print(f"Fetched rows: {result.fetched_rows}")
        console.print(f"Inserted rows: {result.inserted_rows}")
        console.print(f"Updated rows: {result.updated_rows}")
        console.print(f"Source: {result.source or 'N/A'}")
        if result.warnings:
            for warning in result.warnings:
                console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0 if result.ok else 2
    if args.cmd == "update-hk-market-history":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = update_hk_market_history_from_config(cfg, config_path.parent, check_only=args.check_only)
        console = Console()
        color = "green" if result.ok else "red"
        console.print(f"[{color}]HK market history update status: {result.status}[/{color}]")
        console.print(f"Database: {result.db_path}")
        console.print(f"Latest date: {result.latest_date or 'N/A'}")
        console.print(f"Coverage: {result.coverage:.4f} ({result.covered_symbols}/{result.symbol_count})")
        console.print(f"Fetched rows: {result.fetched_rows}")
        console.print(f"Inserted rows: {result.inserted_rows}")
        console.print(f"Updated rows: {result.updated_rows}")
        console.print(f"Source: {result.source or 'N/A'}")
        if result.warnings:
            for warning in result.warnings:
                console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0 if result.ok else 2
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
