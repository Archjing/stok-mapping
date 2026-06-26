from __future__ import annotations

from pathlib import Path

import phase0.strategy_admission as admission
from phase0.research.admission import reports


def test_admission_report_helpers_are_reexported_from_runner() -> None:
    assert admission._write_report is reports.write_report
    assert admission._write_governance_report is reports.write_governance_report
    assert admission._admission_command_hint is reports.admission_command_hint
    assert admission._config_command_arg is reports.config_command_arg
    assert admission._required_artifact_names is reports.required_artifact_names
    assert admission._md_table is reports._md_table
    assert admission._format_status_float is reports._format_status_float
    assert admission._format_benchmark_float is reports._format_benchmark_float
    assert admission._format_status_int is reports._format_status_int
    assert admission._value_counts is reports._value_counts
    assert admission._format_count_map is reports._format_count_map
    assert admission._load_quality_factor_evidence is reports._load_quality_factor_evidence
    assert admission._quality_factor_evidence_label is reports._quality_factor_evidence_label
    assert admission._quality_failure_attribution is reports._quality_failure_attribution
    assert admission._safe_float is reports.safe_float
    assert admission._safe_int is reports.safe_int
    assert admission._safe_str is reports.safe_str


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
