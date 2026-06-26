from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from phase0.research.admission.gate import resolve_admission_gate, resolve_diagnostic_suites
from phase0.research.admission.reports import (
    admission_command_hint,
    config_command_arg,
    required_artifact_names,
    write_governance_report,
    write_report,
)
from phase0.research.admission.review import attach_price_adjustment_status, build_constraint_review, build_window_matrix
from phase0.research.admission.strategy_scope import (
    _force_strategy_set_enabled_for_admission,
    _resolve_strategy_scope,
)
from phase0.research.diagnostics.overfit import run_overfit_diagnostic
from phase0.reporting.paths import create_report_run
from phase0.walk_forward import run_walk_forward


@dataclass(frozen=True)
class StrategyAdmissionResult:
    output_dir: Path
    matrix_csv: Path
    constraint_csv: Path
    report_md: Path
    governance_md: Path
    folds_csv: Path
    overfit_csv: Path
    strategies: int
    presets: int
    rows: int


def run_strategy_admission(
    *,
    config: dict[str, Any],
    root: Path,
    config_path: Path | None = None,
    presets: list[str] | None = None,
    strategy_set: str | None = None,
    strategies: list[str] | None = None,
    output_dir: Path | None = None,
    trace_callback: Any | None = None,
) -> StrategyAdmissionResult:
    wcfg = config.get("walk_forward", {})
    available_presets = wcfg.get("presets", {}) or {}
    preset_names = presets or list(available_presets.keys())
    if not preset_names:
        raise ValueError("strategy-admission requires at least one walk_forward preset")
    missing_presets = [name for name in preset_names if name not in available_presets]
    if missing_presets:
        raise ValueError(f"unknown walk_forward presets: {missing_presets}")

    admission_cfg = wcfg.get("admission", {}) or {}
    gate_cfg = resolve_admission_gate(wcfg)
    diagnostics_suites = resolve_diagnostic_suites(admission_cfg)
    strategy_cfg = wcfg.get("strategy_v2", {})
    strategy_scope = _resolve_strategy_scope(strategy_cfg, admission_cfg, strategy_set=strategy_set, strategies=strategies)
    strategy_names = strategy_scope["strategies"]
    if not strategy_names:
        raise ValueError("strategy-admission requires at least one strategy")

    explicit_output_dir = output_dir is not None
    if output_dir is None:
        scope_name = strategy_scope.get("strategy_set") or "_".join(strategy_names[:3]) or "default"
        report_run = create_report_run(root=root, config=config, command="strategy-admission", scope=str(scope_name))
        output_dir = report_run.run_dir
    else:
        report_run = None
    output_dir.mkdir(parents=True, exist_ok=True)

    all_folds: list[pd.DataFrame] = []
    failure_rows: list[dict[str, Any]] = []
    for preset_name in preset_names:
        scenario_cfg = copy.deepcopy(config)
        scenario_wcfg = scenario_cfg.setdefault("walk_forward", {})
        scenario_wcfg["preset_name"] = preset_name
        scenario_strategy_cfg = scenario_wcfg.setdefault("strategy_v2", {})
        scenario_strategy_cfg["compare_strategies"] = strategy_names
        _force_strategy_set_enabled_for_admission(scenario_strategy_cfg, strategy_names)
        result = run_walk_forward(scenario_cfg, trace_callback=trace_callback)
        summary = result.get("summary", {}) or {}
        folds = result.get("candidate_folds", pd.DataFrame())
        if folds is None or folds.empty:
            reason = str(summary.get("reason", "no valid folds"))
            for strategy_name in strategy_names:
                failure_rows.append(
                    {
                        "strategy_id": strategy_name,
                        "candidate": strategy_name,
                        "walk_forward_preset": preset_name,
                        "status": "failed",
                        "failure_reason": reason,
                    }
                )
            continue
        folds = folds.copy()
        folds["walk_forward_preset"] = preset_name
        folds["walk_forward_train_years"] = int(
            summary.get("walk_forward_train_years", available_presets[preset_name].get("train_years", 0))
        )
        folds["walk_forward_validate_years"] = int(
            summary.get("walk_forward_validate_years", available_presets[preset_name].get("validate_years", 0))
        )
        folds["walk_forward_start_date"] = str(
            summary.get("walk_forward_start_date", available_presets[preset_name].get("start_date", ""))
        )
        folds["walk_forward_end_date"] = str(
            summary.get("walk_forward_end_date", available_presets[preset_name].get("end_date", ""))
        )
        folds["walk_forward_expected_folds"] = summary.get(
            "walk_forward_expected_folds", available_presets[preset_name].get("expected_folds", "")
        )
        folds["walk_forward_actual_folds"] = summary.get(
            "walk_forward_actual_folds", folds["fold"].nunique() if "fold" in folds.columns else 0
        )
        folds["walk_forward_fold_generation_warning"] = str(summary.get("walk_forward_fold_generation_warning", ""))
        folds["status"] = "ok"
        folds["failure_reason"] = ""
        all_folds.append(folds)

    folds_df = pd.concat(all_folds, ignore_index=True) if all_folds else pd.DataFrame()
    failures_df = pd.DataFrame(failure_rows)
    matrix_df = build_window_matrix(folds_df, failures_df, strategy_names, preset_names, gate_cfg)
    attach_price_adjustment_status(matrix_df, config, gate_cfg)

    folds_csv = (
        output_dir / "strategy_admission_candidate_folds.csv"
        if explicit_output_dir
        else report_run.artifact("strategy_admission", "candidate_folds", "csv")
    )
    if folds_df.empty:
        pd.DataFrame().to_csv(folds_csv, index=False)
    else:
        folds_df.to_csv(folds_csv, index=False)

    overfit_output_dir = output_dir / "overfit_diagnostic" if explicit_output_dir else output_dir
    overfit_csv = (
        overfit_output_dir / "strategy_overfit_diagnostic.csv"
        if explicit_output_dir
        else report_run.artifact("overfit", "diagnostic", "csv")
    )
    overfit_df = pd.DataFrame()
    if not folds_df.empty:
        overfit_result = run_overfit_diagnostic(
            config=config,
            root=root,
            candidates_path=folds_csv,
            folds_path=folds_csv,
            output_dir=overfit_output_dir,
            standard_names=not explicit_output_dir,
        )
        overfit_csv = overfit_result.csv_path
        overfit_df = pd.read_csv(overfit_csv)

    constraint_df = build_constraint_review(matrix_df, overfit_df, preset_names, gate_cfg)

    if explicit_output_dir:
        matrix_csv = output_dir / "strategy_admission_window_matrix.csv"
        constraint_csv = output_dir / "strategy_admission_constraint_review.csv"
        report_md = output_dir / "strategy_admission_report.md"
        governance_md = output_dir / "strategy_admission_governance_report.md"
    else:
        matrix_csv = report_run.artifact("strategy_admission", "window_matrix", "csv")
        constraint_csv = report_run.artifact("strategy_admission", "constraint_review", "csv")
        report_md = report_run.artifact("strategy_admission", "report", "md")
        governance_md = report_run.artifact("strategy_admission", "governance", "md")
    matrix_df.to_csv(matrix_csv, index=False)
    constraint_df.to_csv(constraint_csv, index=False)
    write_report(
        report_md,
        matrix_df,
        constraint_df,
        preset_names,
        strategy_names,
        root=root,
        strategy_scope=strategy_scope,
        gate_cfg=gate_cfg,
        diagnostics_suites=diagnostics_suites,
    )
    write_governance_report(
        governance_md,
        matrix_df,
        constraint_df,
        preset_names,
        strategy_names,
        strategy_scope=strategy_scope,
        gate_cfg=gate_cfg,
        diagnostics_suites=diagnostics_suites,
        required_artifacts=required_artifact_names(
            output_dir=output_dir,
            folds_csv=folds_csv,
            matrix_csv=matrix_csv,
            constraint_csv=constraint_csv,
            report_md=report_md,
            overfit_csv=overfit_csv,
        ),
        command_hint=admission_command_hint(
            config_arg=config_command_arg(config_path, root),
            presets=preset_names,
            strategy_scope=strategy_scope,
            output_dir=output_dir if explicit_output_dir else None,
        ),
    )

    return StrategyAdmissionResult(
        output_dir=output_dir,
        matrix_csv=matrix_csv,
        constraint_csv=constraint_csv,
        report_md=report_md,
        governance_md=governance_md,
        folds_csv=folds_csv,
        overfit_csv=overfit_csv,
        strategies=len(strategy_names),
        presets=len(preset_names),
        rows=len(matrix_df),
    )
