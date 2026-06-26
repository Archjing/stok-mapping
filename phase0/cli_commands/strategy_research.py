from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from rich.console import Console

import phase0.cli_commands.gates as gates
from phase0.config import load_config
from phase0.factor_effectiveness import run_factor_effectiveness_report
from phase0.overfit import run_overfit_diagnostic
from phase0.strategy_admission import run_strategy_admission
from phase0.walk_forward import describe_walk_forward_presets


STRATEGY_RESEARCH_COMMANDS = frozenset(
    {
        "factor-effectiveness",
        "overfit-diagnostic",
        "strategy-admission",
    }
)


def _print_walk_forward_trace(console: Console, payload: dict[str, object]) -> None:
    event = str(payload.get("event") or "")
    strategy_id = str(payload.get("strategy_id") or "")
    fold = int(payload.get("fold") or 0)
    if event == "fold_start":
        console.print(
            "WF fold start: "
            f"strategy={strategy_id} fold={fold} "
            f"train={payload.get('train_start')}..{payload.get('train_end')} "
            f"valid={payload.get('valid_start')}..{payload.get('valid_end')} "
            f"train_symbols={payload.get('train_symbols')} valid_symbols={payload.get('valid_symbols')}"
        )
        return
    if event == "fold_params":
        console.print(
            "WF fold params: "
            f"strategy={strategy_id} fold={fold} eligible={payload.get('eligible')} "
            f"params={payload.get('formatted_params')}"
        )
        return
    if event == "fold_result":
        first_symbols = payload.get("first_target_symbols") or []
        console.print(
            "WF fold result: "
            f"strategy={strategy_id} fold={fold} "
            f"ann={float(payload.get('annualized_return') or 0.0):.4f} "
            f"sharpe={float(payload.get('sharpe') or 0.0):.4f} "
            f"turnover={float(payload.get('turnover_annual') or 0.0):.2f} "
            f"trades={int(payload.get('trades') or 0)} "
            f"target_days={int(payload.get('target_days') or 0)} "
            f"live_days={int(payload.get('live_days') or 0)} "
            f"avg_target_holdings={float(payload.get('avg_target_holdings') or 0.0):.2f} "
            f"avg_live_holdings={float(payload.get('avg_live_holdings') or 0.0):.2f} "
            f"trade_days={int(payload.get('trade_days') or 0)} "
            f"first_target_date={payload.get('first_target_date') or ''} "
            f"first_target_symbols={','.join(str(item) for item in first_symbols)} "
            f"constraint={payload.get('constraint_mode') or ''}/{payload.get('constraint_status') or ''}"
        )


def _run_db_health_gate(
    *,
    console: Console,
    config: dict,
    root: Path,
    scope: str,
    fail_on: str,
    label: str,
) -> int:
    return gates.run_db_health_gate(
        console=console,
        config=config,
        root=root,
        scope=scope,
        fail_on=fail_on,
        label=label,
    )


def register_strategy_research_commands(subparsers: argparse._SubParsersAction) -> None:
    overfit_parser = subparsers.add_parser("overfit-diagnostic", help="Generate strategy overfitting diagnostic report")
    overfit_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    overfit_parser.add_argument("--candidates", default=None, help="Path to walk-forward candidates CSV")
    overfit_parser.add_argument("--folds", default=None, help="Path to walk-forward folds CSV")
    overfit_parser.add_argument("--output-dir", default=None, help="Output directory for diagnostic reports")

    admission_parser = subparsers.add_parser("strategy-admission", help="Run strategy admission window and constraint review")
    admission_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    admission_parser.add_argument("--presets", nargs="+", default=None, help="Walk-forward preset names to evaluate")
    admission_parser.add_argument("--strategy-set", default=None, help="Admission strategy set name from walk_forward.admission.strategy_sets")
    admission_parser.add_argument("--strategies", nargs="+", default=None, help="Strategy IDs to evaluate")
    admission_parser.add_argument("--output-dir", default=None, help="Output directory for admission reports")
    admission_parser.add_argument("--trace-run", action="store_true", help="Print fold-level walk-forward trace while running")

    factor_parser = subparsers.add_parser("factor-effectiveness", help="Generate point-in-time factor effectiveness report")
    factor_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    factor_parser.add_argument("--output-dir", default=None, help="Output directory for factor effectiveness artifacts")


def handle_strategy_research_command(
    args: argparse.Namespace,
    *,
    parser: argparse.ArgumentParser,
    console: Any | None = None,
) -> int:
    research_console = console or Console()
    if args.cmd == "overfit-diagnostic":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        research_console.print("[bold]Strategy overfit diagnostic started[/bold]")
        result = run_overfit_diagnostic(
            config=cfg.get("phase0", cfg),
            root=config_path.parent,
            candidates_path=Path(args.candidates).resolve() if args.candidates else None,
            folds_path=Path(args.folds).resolve() if args.folds else None,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
        )
        research_console.print("[green]Overfit diagnostic complete[/green]")
        research_console.print(f"Selected candidate: {result.selected_candidate}")
        research_console.print(f"Selected risk level: {result.selected_risk_level}")
        research_console.print(f"CSV: {result.csv_path}")
        research_console.print(f"Markdown: {result.md_path}")
        research_console.print(f"Rows: {result.rows}")
        return 0

    if args.cmd == "strategy-admission":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg.get("phase0", cfg)
        research_console.print("[bold]Strategy admission review started[/bold]")
        for line in describe_walk_forward_presets(phase_cfg.get("walk_forward", {}), args.presets, default_all=True):
            research_console.print(f"[cyan]{line}[/cyan]")
        result = run_strategy_admission(
            config=phase_cfg,
            root=config_path.parent,
            config_path=config_path,
            presets=args.presets,
            strategy_set=args.strategy_set,
            strategies=args.strategies,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
            trace_callback=(lambda payload: _print_walk_forward_trace(research_console, payload)) if args.trace_run else None,
        )
        research_console.print("[green]Strategy admission review complete[/green]")
        research_console.print(f"Strategies: {result.strategies}")
        research_console.print(f"Presets: {result.presets}")
        research_console.print(f"Rows: {result.rows}")
        research_console.print(f"Window matrix CSV: {result.matrix_csv}")
        research_console.print(f"Constraint review CSV: {result.constraint_csv}")
        research_console.print(f"Candidate folds CSV: {result.folds_csv}")
        research_console.print(f"Overfit CSV: {result.overfit_csv}")
        research_console.print(f"Markdown: {result.report_md}")
        research_console.print(f"Governance Markdown: {result.governance_md}")
        return 0

    if args.cmd == "factor-effectiveness":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg.get("phase0", cfg)
        gate_exit = _run_db_health_gate(
            console=research_console,
            config=phase_cfg,
            root=config_path.parent,
            scope="cn",
            fail_on="error",
            label="Factor effectiveness",
        )
        if gate_exit != 0:
            return gate_exit
        research_console.print("[bold]Factor effectiveness diagnostic started[/bold]")
        result = run_factor_effectiveness_report(
            config=phase_cfg,
            root=config_path.parent,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
        )
        research_console.print("[green]Factor effectiveness diagnostic complete[/green]")
        research_console.print(f"Factors: {result.factor_count}")
        research_console.print(f"Valid folds: {result.fold_count}")
        research_console.print(f"Summary CSV: {result.summary_csv}")
        research_console.print(f"Markdown: {result.summary_md}")
        research_console.print(f"Group returns: {result.group_returns_csv}")
        research_console.print(f"Yearly IC: {result.ic_by_year_csv}")
        research_console.print(f"Correlation: {result.correlation_csv}")
        for warning in result.warnings[:10]:
            research_console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0

    parser.error(
        "strategy research command expected one of: "
        + ", ".join(sorted(STRATEGY_RESEARCH_COMMANDS))
    )
    return 2
