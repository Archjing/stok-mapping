from __future__ import annotations

from pathlib import Path

import pytest

import phase0.strategy_admission as admission
from phase0.research.admission import gate, reports, review, runner
from phase0.research.admission.runner import StrategyAdmissionResult, run_strategy_admission


@pytest.mark.parametrize(
    ("legacy_name", "new_value"),
    [
        ("_resolve_admission_gate", gate.resolve_admission_gate),
        ("_resolve_diagnostic_suites", gate.resolve_diagnostic_suites),
        ("_overfit_blocks_admission", gate.overfit_blocks_admission),
        ("_write_report", reports.write_report),
        ("_write_governance_report", reports.write_governance_report),
        ("_admission_command_hint", reports.admission_command_hint),
        ("_config_command_arg", reports.config_command_arg),
        ("_required_artifact_names", reports.required_artifact_names),
        ("_md_table", reports._md_table),
        ("_format_status_float", reports._format_status_float),
        ("_format_benchmark_float", reports._format_benchmark_float),
        ("_format_status_int", reports._format_status_int),
        ("_value_counts", reports._value_counts),
        ("_format_count_map", reports._format_count_map),
        ("_load_quality_factor_evidence", reports._load_quality_factor_evidence),
        ("_quality_factor_evidence_label", reports._quality_factor_evidence_label),
        ("_quality_failure_attribution", reports._quality_failure_attribution),
        ("_safe_float", reports.safe_float),
        ("_safe_int", reports.safe_int),
        ("_safe_str", reports.safe_str),
        ("_attach_price_adjustment_status", review.attach_price_adjustment_status),
        ("_build_window_matrix", review.build_window_matrix),
        ("_window_metrics", review.window_metrics),
        ("_build_constraint_review", review.build_constraint_review),
        ("_admission_action", review.admission_action),
        ("_parameter_unstable_window_count", review.parameter_unstable_window_count),
        ("_industry_concentration_window_count", review.industry_concentration_window_count),
        ("_industry_missing_window_count", review.industry_missing_window_count),
        ("_factor_missing_window_count", review.factor_missing_window_count),
        ("_price_adjustment_fail_window_count", review.price_adjustment_fail_window_count),
        ("_turnover_fail_window_count", review.turnover_fail_window_count),
        ("run_strategy_admission", run_strategy_admission),
        ("StrategyAdmissionResult", StrategyAdmissionResult),
    ],
)
def test_strategy_admission_reexports_split_admission_helpers(legacy_name: str, new_value: object) -> None:
    assert getattr(admission, legacy_name) is new_value


def test_admission_runner_is_packaged_under_research_admission() -> None:
    assert runner.run_strategy_admission is run_strategy_admission
    assert runner.StrategyAdmissionResult is StrategyAdmissionResult


def test_report_helpers_keep_command_and_artifact_contract(tmp_path: Path) -> None:
    hint = reports.admission_command_hint(
        config_arg="config.demo.yaml",
        presets=["baseline_2y_1y_5fold", "quality_4y_1y"],
        strategy_scope={"strategy_set": "baseline_admission_all_v1", "strategies": ["ignored_when_set"]},
        output_dir=tmp_path / "admission",
    )

    artifacts = reports.required_artifact_names(
        output_dir=tmp_path / "admission",
        folds_csv=tmp_path / "admission" / "strategy_admission_candidate_folds.csv",
        matrix_csv=tmp_path / "admission" / "strategy_admission_window_matrix.csv",
        constraint_csv=tmp_path / "admission" / "strategy_admission_constraint_review.csv",
        report_md=tmp_path / "admission" / "strategy_admission_report.md",
        overfit_csv=tmp_path / "admission" / "overfit_diagnostic" / "strategy_overfit_diagnostic.csv",
    )

    assert hint == (
        "phase0.cli strategy-admission --config config.demo.yaml "
        "--presets baseline_2y_1y_5fold quality_4y_1y "
        "--strategy-set baseline_admission_all_v1 "
        f"--output-dir {tmp_path / 'admission'}"
    )
    assert artifacts == [
        "strategy_admission_candidate_folds.csv",
        "strategy_admission_window_matrix.csv",
        "strategy_admission_constraint_review.csv",
        "strategy_admission_report.md",
        "overfit_diagnostic/strategy_overfit_diagnostic.csv",
    ]
