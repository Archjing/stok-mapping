from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from rich.console import Console

from quant.config import load_config
from quant.data_access.local_history import configure_local_history
from quant.research.admission.failure_attribution import run_strategy_failure_attribution
from quant.research.attribution.csi300 import run_strategy_csi300_attribution
from quant.research.attribution.fold import run_strategy_fold_attribution
from quant.research.core_coverage.core_reachability import run_strategy_core_reachability_diagnostic
from quant.research.core_coverage.missing_core_audit import run_missing_core_audit
from quant.research.diagnostics.exposure import run_strategy_exposure_diagnostic
from quant.research.diagnostics.filter import run_strategy_filter_diagnostic
from quant.research.diagnostics.market_context import run_strategy_market_context
from quant.research.holdings.exposure import run_strategy_holdings_exposure
from quant.research.participation.overlay import run_strategy_participation_overlay
from quant.research.summaries.role_card import run_strategy_role_card


RESEARCH_COMMANDS = frozenset(
    {
        "strategy-csi300-attribution",
        "strategy-core-reachability-diagnostic",
        "strategy-exposure-diagnostic",
        "strategy-failure-attribution",
        "strategy-filter-diagnostic",
        "strategy-fold-attribution",
        "strategy-holdings-exposure",
        "strategy-market-context",
        "strategy-missing-core-audit",
        "strategy-participation-overlay",
        "strategy-role-card",
    }
)


def register_research_commands(subparsers: argparse._SubParsersAction) -> None:
    attribution_parser = subparsers.add_parser(
        "strategy-failure-attribution",
        help="Attribute failed strategy admission decisions from existing CSV artifacts",
    )
    attribution_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    attribution_parser.add_argument("--admission-dir", default=None, help="Directory containing existing strategy admission CSV artifacts")
    attribution_parser.add_argument("--folds", default=None, help="Path to strategy_admission_candidate_folds.csv")
    attribution_parser.add_argument("--matrix", default=None, help="Path to strategy_admission_window_matrix.csv")
    attribution_parser.add_argument("--constraints", default=None, help="Path to strategy_admission_constraint_review.csv")
    attribution_parser.add_argument("--overfit", default=None, help="Path to overfit_diagnostic/strategy_overfit_diagnostic.csv")
    attribution_parser.add_argument("--output-dir", default=None, help="Output directory for failure attribution artifacts")

    market_context_parser = subparsers.add_parser(
        "strategy-market-context",
        help="Overlay benchmark market context onto strategy fold attribution",
    )
    market_context_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    market_context_parser.add_argument("--fold-attribution", required=True, help="Path to strategy_failure_fold_attribution.csv")
    market_context_parser.add_argument("--output-dir", default=None, help="Output directory for market context artifacts")
    market_context_parser.add_argument("--benchmark-symbol", default=None, help="Benchmark symbol; defaults to quant.benchmark_symbol")
    market_context_parser.add_argument("--trend-window", type=int, default=120, help="Benchmark trend moving-average window")
    market_context_parser.add_argument("--vol-window", type=int, default=20, help="Benchmark volatility window")
    market_context_parser.add_argument("--vol-quantile", type=float, default=0.70, help="Rolling volatility quantile for high-vol context")

    exposure_parser = subparsers.add_parser(
        "strategy-exposure-diagnostic",
        help="Diagnose strong-benchmark lag exposure proxies from existing strategy artifacts",
    )
    exposure_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    exposure_parser.add_argument("--candidate-folds", required=True, help="Path to strategy_admission_candidate_folds.csv")
    exposure_parser.add_argument("--market-context", required=True, help="Path to strategy_market_context_diagnostic.csv")
    exposure_parser.add_argument("--universe", default=None, help="Optional universe metadata CSV; defaults to data/universe/local_factor_universe.csv")
    exposure_parser.add_argument("--output-dir", default=None, help="Output directory for exposure diagnostic artifacts")

    filter_parser = subparsers.add_parser(
        "strategy-filter-diagnostic",
        help="Diagnose strategy empty-exposure and hard-filter bottlenecks",
    )
    filter_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    filter_parser.add_argument("--candidate-folds", required=True, help="Path to strategy_admission_candidate_folds.csv")
    filter_parser.add_argument("--strategy", required=True, help="Strategy ID to diagnose")
    filter_parser.add_argument("--presets", nargs="+", default=None, help="Optional walk-forward preset names to include")
    filter_parser.add_argument("--folds", nargs="+", type=int, default=None, help="Optional fold numbers to include")
    filter_parser.add_argument("--output-dir", default=None, help="Output directory for filter diagnostic artifacts")

    core_reach_parser = subparsers.add_parser(
        "strategy-core-reachability-diagnostic",
        help="Diagnose complete CSI300 core-weight reachability from as-of benchmark weights",
    )
    core_reach_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    core_reach_parser.add_argument("--candidate-folds", required=True, help="Path to strategy_admission_candidate_folds.csv")
    core_reach_parser.add_argument("--output-dir", required=True, help="Output directory for core reachability artifacts")
    core_reach_parser.add_argument("--benchmark-symbol", default=None, help="Benchmark symbol; defaults to quant.benchmark_symbol")
    core_reach_parser.add_argument("--presets", nargs="+", default=None, help="Optional walk-forward preset names to include")
    core_reach_parser.add_argument("--folds", nargs="+", type=int, default=None, help="Optional fold numbers to include")
    core_reach_parser.add_argument("--core-top-n", type=int, default=60, help="Benchmark rank cutoff for core constituents")
    core_reach_parser.add_argument("--core-cumulative-weight", type=float, default=0.60, help="Cumulative benchmark weight cutoff for core constituents")
    core_reach_parser.add_argument("--top-n", type=int, default=20, help="Complete benchmark top-weight constituent count to audit")
    core_reach_parser.add_argument("--min-amount", type=float, default=0.0, help="Minimum daily amount required for reachability")
    core_reach_parser.add_argument("--min-amount-ratio20", type=float, default=0.0, help="Minimum amount_ratio20 required for reachability")
    core_reach_parser.add_argument("--weight-date-lag-days", type=int, default=1, help="Calendar-day lag before looking up benchmark weights")
    core_reach_parser.add_argument(
        "--seed-benchmark-core",
        action="store_true",
        help="Read-only experiment: append missing benchmark core/top members into the diagnostic panel",
    )
    core_reach_parser.add_argument("--seed-top-n", type=int, default=None, help="Benchmark top-N members to seed when --seed-benchmark-core is used; defaults to --top-n")
    core_reach_parser.add_argument("--seed-core-top-n", type=int, default=None, help="Benchmark core rank cutoff to seed; defaults to --core-top-n")
    core_reach_parser.add_argument("--seed-core-cumulative-weight", type=float, default=None, help="Benchmark cumulative core weight to seed; defaults to --core-cumulative-weight")

    missing_core_parser = subparsers.add_parser(
        "strategy-missing-core-audit",
        help="Audit why benchmark core members are missing from PIT panels",
    )
    missing_core_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    missing_core_parser.add_argument("--missing-reasons", required=True, help="Path to strategy_core_reachability_failure_reasons.csv")
    missing_core_parser.add_argument("--candidate-folds", required=True, help="Path to strategy_admission_candidate_folds.csv")
    missing_core_parser.add_argument("--output-dir", required=True, help="Output directory for missing-core audit artifacts")
    missing_core_parser.add_argument("--top-symbols", type=int, default=30, help="Number of missing symbols to audit by total missing weight")

    holdings_parser = subparsers.add_parser(
        "strategy-holdings-exposure",
        help="Rebuild research-only daily holdings and industry exposure for strategy folds",
    )
    holdings_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    holdings_parser.add_argument("--candidate-folds", required=True, help="Path to strategy_admission_candidate_folds.csv")
    holdings_parser.add_argument("--market-context", required=True, help="Path to strategy_market_context_diagnostic.csv")
    holdings_parser.add_argument("--strategy", required=True, help="Strategy ID to rebuild")
    holdings_parser.add_argument("--presets", nargs="+", default=None, help="Optional walk-forward preset names to include")
    holdings_parser.add_argument("--folds", nargs="+", type=int, default=None, help="Optional fold numbers to include")
    holdings_parser.add_argument("--benchmark-symbol", default=None, help="Benchmark symbol; defaults to quant.benchmark_symbol")
    holdings_parser.add_argument("--output-dir", default=None, help="Output directory for holdings exposure artifacts")

    fold_attr_parser = subparsers.add_parser(
        "strategy-fold-attribution",
        help="Assemble read-only paired fold attribution from existing diagnostics",
    )
    fold_attr_parser.add_argument("--quality-fold-attribution", required=True, help="Path to quality strategy_failure_fold_attribution.csv")
    fold_attr_parser.add_argument("--price-volume-fold-attribution", required=True, help="Path to price-volume strategy_failure_fold_attribution.csv")
    fold_attr_parser.add_argument("--quality-market-context", required=True, help="Path to quality strategy_market_context_diagnostic.csv")
    fold_attr_parser.add_argument("--price-volume-market-context", required=True, help="Path to price-volume strategy_market_context_diagnostic.csv")
    fold_attr_parser.add_argument("--quality-holdings", required=True, help="Path to quality strategy_daily_holdings.csv")
    fold_attr_parser.add_argument("--price-volume-holdings", required=True, help="Path to price-volume strategy_daily_holdings.csv")
    fold_attr_parser.add_argument("--quality-daily-exposure", required=True, help="Path to quality strategy_daily_exposure.csv")
    fold_attr_parser.add_argument("--price-volume-daily-exposure", required=True, help="Path to price-volume strategy_daily_exposure.csv")
    fold_attr_parser.add_argument("--output-dir", required=True, help="Output directory for paired fold attribution artifacts")

    participation_parser = subparsers.add_parser(
        "strategy-participation-overlay",
        help="Run research-only minimum-exposure counterfactual on daily holdings",
    )
    participation_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    participation_parser.add_argument("--holdings", required=True, help="Path to strategy_daily_holdings.csv")
    participation_parser.add_argument("--daily-exposure", required=True, help="Path to strategy_daily_exposure.csv")
    participation_parser.add_argument("--output-dir", required=True, help="Output directory for participation overlay artifacts")
    participation_parser.add_argument("--min-exposure", type=float, default=0.65, help="Minimum gross exposure target for scoped rows")
    participation_parser.add_argument("--max-symbol-weight", type=float, default=0.10, help="Per-symbol live weight cap after scaling")
    participation_parser.add_argument("--max-scale", type=float, default=2.0, help="Maximum per-day scaling factor")
    participation_parser.add_argument("--context-label", default="relative_lag_in_strong_benchmark_context", help="Market context label to rescale; use 'all' for no filter")

    csi300_attr_parser = subparsers.add_parser(
        "strategy-csi300-attribution",
        help="Attribute strong CSI300 lag using as-of benchmark weights",
    )
    csi300_attr_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    csi300_attr_parser.add_argument("--holdings", default=None, help="Optional path to strategy_daily_holdings.csv")
    csi300_attr_parser.add_argument("--daily-exposure", default=None, help="Optional path to strategy_daily_exposure.csv")
    csi300_attr_parser.add_argument("--candidate-folds", default=None, help="Optional strategy_admission_candidate_folds.csv for fold date scaffolding")
    csi300_attr_parser.add_argument("--market-context", default=None, help="Optional strategy_market_context_diagnostic.csv for context filtering")
    csi300_attr_parser.add_argument("--output-dir", required=True, help="Output directory for CSI300 attribution artifacts")
    csi300_attr_parser.add_argument("--benchmark-symbol", default=None, help="Benchmark symbol; defaults to quant.benchmark_symbol")
    csi300_attr_parser.add_argument("--context-label", default="relative_lag_in_strong_benchmark_context", help="Market context label to diagnose; use 'all' for no filter")
    csi300_attr_parser.add_argument("--top-n", type=int, default=20, help="Benchmark top-weight constituent count to audit")
    csi300_attr_parser.add_argument("--weight-date-lag-days", type=int, default=1, help="Calendar-day lag before looking up benchmark weights; default avoids same-day close as pre-trade visible")

    role_card_parser = subparsers.add_parser(
        "strategy-role-card",
        help="Build a research-only strategy role card from existing diagnostics",
    )
    role_card_parser.add_argument("--strategy", required=True, help="Strategy ID to summarize")
    role_card_parser.add_argument("--matrix", required=True, help="Path to strategy_admission_window_matrix.csv")
    role_card_parser.add_argument("--constraints", required=True, help="Path to strategy_admission_constraint_review.csv")
    role_card_parser.add_argument("--fold-attribution", default=None, help="Optional strategy_failure_fold_attribution.csv")
    role_card_parser.add_argument("--market-context", default=None, help="Optional strategy_market_context_diagnostic.csv")
    role_card_parser.add_argument("--holdings-summary", default=None, help="Optional strategy_holdings_exposure_summary.csv")
    role_card_parser.add_argument("--overlay-summary", default=None, help="Optional strategy_participation_overlay_summary.csv")
    role_card_parser.add_argument("--output-dir", required=True, help="Output directory for role-card artifacts")


def handle_research_command(args: argparse.Namespace, *, parser: argparse.ArgumentParser, console: Any | None = None) -> int:
    research_console = console or Console()
    if args.cmd == "strategy-failure-attribution":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        research_console.print("[bold]Strategy failure attribution started[/bold]")
        result = run_strategy_failure_attribution(
            config=cfg,
            root=config_path.parent,
            admission_dir=Path(args.admission_dir).resolve() if args.admission_dir else None,
            folds_path=Path(args.folds).resolve() if args.folds else None,
            matrix_path=Path(args.matrix).resolve() if args.matrix else None,
            constraint_path=Path(args.constraints).resolve() if args.constraints else None,
            overfit_path=Path(args.overfit).resolve() if args.overfit else None,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
        )
        research_console.print("[green]Strategy failure attribution complete[/green]")
        research_console.print(f"Strategies: {result.strategies}")
        research_console.print(f"Rows: {result.rows}")
        research_console.print(f"CSV: {result.csv_path}")
        research_console.print(f"Markdown: {result.md_path}")
        if result.fold_csv_path is not None:
            research_console.print(f"Fold CSV: {result.fold_csv_path}")
        if result.fold_md_path is not None:
            research_console.print(f"Fold Markdown: {result.fold_md_path}")
        return 0
    if args.cmd == "strategy-market-context":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg
        configure_local_history(phase_cfg.get("local_history", {}), config_path.parent)
        research_console.print("[bold]Strategy market context diagnostic started[/bold]")
        result = run_strategy_market_context(
            config=phase_cfg,
            root=config_path.parent,
            fold_attribution_path=Path(args.fold_attribution).resolve(),
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
            benchmark_symbol=args.benchmark_symbol,
            trend_window=args.trend_window,
            vol_window=args.vol_window,
            vol_quantile=args.vol_quantile,
        )
        research_console.print("[green]Strategy market context diagnostic complete[/green]")
        research_console.print(f"Benchmark: {result.benchmark_symbol}")
        research_console.print(f"Rows: {result.rows}")
        research_console.print(f"CSV: {result.csv_path}")
        research_console.print(f"Summary CSV: {result.summary_csv_path}")
        research_console.print(f"Coverage CSV: {result.coverage_csv_path}")
        research_console.print(f"Markdown: {result.md_path}")
        return 0
    if args.cmd == "strategy-exposure-diagnostic":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg
        research_console.print("[bold]Strategy exposure diagnostic started[/bold]")
        result = run_strategy_exposure_diagnostic(
            config=phase_cfg,
            root=config_path.parent,
            config_path=config_path,
            candidate_folds_path=Path(args.candidate_folds).resolve(),
            market_context_path=Path(args.market_context).resolve(),
            universe_path=Path(args.universe).resolve() if args.universe else None,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
            command=" ".join(os.sys.argv),
        )
        research_console.print("[green]Strategy exposure diagnostic complete[/green]")
        research_console.print(f"Rows: {result.rows}")
        research_console.print(f"Strong lag rows: {result.strong_lag_rows}")
        research_console.print(f"CSV: {result.csv_path}")
        research_console.print(f"Summary CSV: {result.summary_csv_path}")
        research_console.print(f"Run log: {result.run_log_md_path}")
        research_console.print(f"Markdown: {result.md_path}")
        return 0
    if args.cmd == "strategy-filter-diagnostic":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg
        research_console.print("[bold]Strategy filter diagnostic started[/bold]")
        result = run_strategy_filter_diagnostic(
            config=phase_cfg,
            root=config_path.parent,
            config_path=config_path,
            candidate_folds_path=Path(args.candidate_folds).resolve(),
            strategy_id=args.strategy,
            presets=args.presets,
            folds=args.folds,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
            command=" ".join(os.sys.argv),
        )
        research_console.print("[green]Strategy filter diagnostic complete[/green]")
        research_console.print(f"Rows: {result.rows}")
        research_console.print(f"Folds: {result.folds}")
        research_console.print(f"Fold summary CSV: {result.fold_summary_csv_path}")
        research_console.print(f"Daily CSV: {result.daily_csv_path}")
        research_console.print(f"Funnel CSV: {result.funnel_csv_path}")
        research_console.print(f"Markdown: {result.md_path}")
        return 0
    if args.cmd == "strategy-core-reachability-diagnostic":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg
        research_console.print("[bold]Strategy core reachability diagnostic started[/bold]")
        result = run_strategy_core_reachability_diagnostic(
            config=phase_cfg,
            root=config_path.parent,
            config_path=config_path,
            candidate_folds_path=Path(args.candidate_folds).resolve(),
            output_dir=Path(args.output_dir).resolve(),
            benchmark_symbol=args.benchmark_symbol,
            presets=args.presets,
            folds=args.folds,
            core_top_n=args.core_top_n,
            core_cumulative_weight=args.core_cumulative_weight,
            top_n=args.top_n,
            min_amount=args.min_amount,
            min_amount_ratio20=args.min_amount_ratio20,
            weight_date_lag_days=args.weight_date_lag_days,
            seed_benchmark_core=args.seed_benchmark_core,
            seed_top_n=args.seed_top_n,
            seed_core_top_n=args.seed_core_top_n,
            seed_core_cumulative_weight=args.seed_core_cumulative_weight,
            command=" ".join(os.sys.argv),
        )
        research_console.print("[green]Strategy core reachability diagnostic complete[/green]")
        research_console.print(f"Status: {result.status}")
        research_console.print(f"Daily rows: {result.daily_rows}")
        research_console.print(f"Fold rows: {result.fold_rows}")
        research_console.print(f"Daily CSV: {result.daily_csv_path}")
        research_console.print(f"Fold summary CSV: {result.fold_summary_csv_path}")
        research_console.print(f"Failure reasons CSV: {result.failure_reason_csv_path}")
        research_console.print(f"Markdown: {result.report_md_path}")
        research_console.print(f"Run log: {result.run_log_md_path}")
        return 0
    if args.cmd == "strategy-missing-core-audit":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg
        research_console.print("[bold]Strategy missing-core audit started[/bold]")
        result = run_missing_core_audit(
            config=phase_cfg,
            root=config_path.parent,
            config_path=config_path,
            missing_reasons_path=Path(args.missing_reasons).resolve(),
            candidate_folds_path=Path(args.candidate_folds).resolve(),
            output_dir=Path(args.output_dir).resolve(),
            top_symbols=args.top_symbols,
            command=" ".join(os.sys.argv),
        )
        research_console.print("[green]Strategy missing-core audit complete[/green]")
        research_console.print(f"Symbol rows: {result.symbol_rows}")
        research_console.print(f"Event rows: {result.event_rows}")
        research_console.print(f"Symbol CSV: {result.symbol_csv_path}")
        research_console.print(f"Event CSV: {result.event_csv_path}")
        research_console.print(f"Markdown: {result.report_md_path}")
        research_console.print(f"Run log: {result.run_log_md_path}")
        return 0
    if args.cmd == "strategy-holdings-exposure":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg
        research_console.print("[bold]Strategy holdings exposure diagnostic started[/bold]")
        result = run_strategy_holdings_exposure(
            config=phase_cfg,
            root=config_path.parent,
            config_path=config_path,
            candidate_folds_path=Path(args.candidate_folds).resolve(),
            market_context_path=Path(args.market_context).resolve(),
            strategy_id=args.strategy,
            presets=args.presets,
            folds=args.folds,
            benchmark_symbol=args.benchmark_symbol,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
            command=" ".join(os.sys.argv),
        )
        research_console.print("[green]Strategy holdings exposure diagnostic complete[/green]")
        research_console.print(f"Holdings rows: {result.holdings_rows}")
        research_console.print(f"Daily rows: {result.daily_rows}")
        research_console.print(f"Summary rows: {result.summary_rows}")
        research_console.print(f"Holdings CSV: {result.holdings_csv_path}")
        research_console.print(f"Daily exposure CSV: {result.daily_exposure_csv_path}")
        research_console.print(f"Industry exposure CSV: {result.industry_exposure_csv_path}")
        research_console.print(f"Summary CSV: {result.summary_csv_path}")
        research_console.print(f"Coverage CSV: {result.coverage_csv_path}")
        research_console.print(f"Run log: {result.run_log_md_path}")
        research_console.print(f"Markdown: {result.md_path}")
        return 0
    if args.cmd == "strategy-fold-attribution":
        research_console.print("[bold]Strategy fold attribution assembly started[/bold]")
        result = run_strategy_fold_attribution(
            quality_fold_attribution_path=Path(args.quality_fold_attribution).resolve(),
            price_volume_fold_attribution_path=Path(args.price_volume_fold_attribution).resolve(),
            quality_market_context_path=Path(args.quality_market_context).resolve(),
            price_volume_market_context_path=Path(args.price_volume_market_context).resolve(),
            quality_holdings_path=Path(args.quality_holdings).resolve(),
            price_volume_holdings_path=Path(args.price_volume_holdings).resolve(),
            quality_daily_exposure_path=Path(args.quality_daily_exposure).resolve(),
            price_volume_daily_exposure_path=Path(args.price_volume_daily_exposure).resolve(),
            output_dir=Path(args.output_dir).resolve(),
        )
        research_console.print("[green]Strategy fold attribution assembly complete[/green]")
        research_console.print(f"Paired rows: {result.paired_rows}")
        research_console.print(f"Paired fold CSV: {result.paired_fold_csv_path}")
        research_console.print(f"Daily exposure CSV: {result.daily_exposure_csv_path}")
        research_console.print(f"Top holdings CSV: {result.top_holding_csv_path}")
        research_console.print(f"Quality bucket CSV: {result.quality_bucket_csv_path}")
        research_console.print(f"Turnover cost CSV: {result.turnover_cost_csv_path}")
        research_console.print(f"Markdown: {result.md_path}")
        return 0
    if args.cmd == "strategy-participation-overlay":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg
        research_console.print("[bold]Strategy participation overlay counterfactual started[/bold]")
        result = run_strategy_participation_overlay(
            config=phase_cfg,
            root=config_path.parent,
            config_path=config_path,
            holdings_path=Path(args.holdings).resolve(),
            daily_exposure_path=Path(args.daily_exposure).resolve(),
            output_dir=Path(args.output_dir).resolve(),
            min_exposure=args.min_exposure,
            max_symbol_weight=args.max_symbol_weight,
            max_scale=args.max_scale,
            context_label=args.context_label,
            command=" ".join(os.sys.argv),
        )
        research_console.print("[green]Strategy participation overlay counterfactual complete[/green]")
        research_console.print(f"Daily rows: {result.daily_rows}")
        research_console.print(f"Summary rows: {result.summary_rows}")
        research_console.print(f"Daily CSV: {result.daily_csv_path}")
        research_console.print(f"Summary CSV: {result.summary_csv_path}")
        research_console.print(f"Markdown: {result.report_md_path}")
        research_console.print(f"Run log: {result.run_log_md_path}")
        return 0
    if args.cmd == "strategy-csi300-attribution":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg
        research_console.print("[bold]Strategy CSI300 attribution started[/bold]")
        result = run_strategy_csi300_attribution(
            config=phase_cfg,
            root=config_path.parent,
            holdings_path=Path(args.holdings).resolve() if args.holdings else None,
            daily_exposure_path=Path(args.daily_exposure).resolve() if args.daily_exposure else None,
            candidate_folds_path=Path(args.candidate_folds).resolve() if args.candidate_folds else None,
            market_context_path=Path(args.market_context).resolve() if args.market_context else None,
            output_dir=Path(args.output_dir).resolve(),
            benchmark_symbol=args.benchmark_symbol,
            context_label=args.context_label,
            top_n=args.top_n,
            weight_date_lag_days=args.weight_date_lag_days,
            command=" ".join(os.sys.argv),
        )
        research_console.print("[green]Strategy CSI300 attribution complete[/green]")
        research_console.print(f"Status: {result.status}")
        research_console.print(f"Daily rows: {result.daily_rows}")
        research_console.print(f"Fold rows: {result.fold_rows}")
        research_console.print(f"Daily CSV: {result.daily_csv_path}")
        research_console.print(f"Fold CSV: {result.fold_csv_path}")
        research_console.print(f"Missed top weights CSV: {result.missed_top_csv_path}")
        research_console.print(f"Industry CSV: {result.industry_csv_path}")
        research_console.print(f"Markdown: {result.report_md_path}")
        research_console.print(f"Run log: {result.run_log_md_path}")
        return 0
    if args.cmd == "strategy-role-card":
        research_console.print("[bold]Strategy role card generation started[/bold]")
        result = run_strategy_role_card(
            strategy_id=args.strategy,
            matrix_path=Path(args.matrix).resolve(),
            constraints_path=Path(args.constraints).resolve(),
            fold_attribution_path=Path(args.fold_attribution).resolve() if args.fold_attribution else None,
            market_context_path=Path(args.market_context).resolve() if args.market_context else None,
            holdings_summary_path=Path(args.holdings_summary).resolve() if args.holdings_summary else None,
            overlay_summary_path=Path(args.overlay_summary).resolve() if args.overlay_summary else None,
            output_dir=Path(args.output_dir).resolve(),
        )
        research_console.print("[green]Strategy role card generation complete[/green]")
        research_console.print(f"Strategy: {result.strategy_id}")
        research_console.print(f"Admission action: {result.admission_action}")
        research_console.print(f"Rows: {result.rows}")
        research_console.print(f"Rule CSV: {result.rule_csv_path}")
        research_console.print(f"Markdown: {result.report_md_path}")
        return 0
    parser.error(
        "research command expected one of: "
        + ", ".join(sorted(RESEARCH_COMMANDS))
    )
    return 2
