from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from phase0.config import load_config
from phase0.data_sources import check_connectivity, fetch_yf_daily
from phase0.quality import aggregate_quality, audit_quality
from phase0.reporting import (
    write_data_source_report,
    write_effectiveness_gate_report,
    write_walk_forward_report,
)
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
    summary = wf["summary"]

    if not folds_df.empty:
        save_walk_forward_csv(folds_df, report_dir / "phase0_walk_forward_folds.csv")
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

    args = parser.parse_args()
    if args.cmd != "run":
        parser.print_help()
        return 1

    config_path = Path(args.config).resolve()
    return run_phase0(config_path)


if __name__ == "__main__":
    raise SystemExit(main())
