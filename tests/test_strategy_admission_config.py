from __future__ import annotations

import pandas as pd
from types import SimpleNamespace

import phase0.strategy_admission as admission
from phase0.strategy_admission import (
    _admission_action,
    _attach_price_adjustment_status,
    _force_strategy_set_enabled_for_admission,
    _write_governance_report,
    _industry_missing_window_count,
    _overfit_blocks_admission,
    _price_adjustment_fail_window_count,
    _resolve_admission_gate,
    _resolve_diagnostic_suites,
    _resolve_strategy_scope,
    _window_metrics,
    run_strategy_admission,
)
from phase0.overfit import _metrics, _score, run_overfit_diagnostic
from phase0.walk_forward import describe_walk_forward_presets


def test_strategy_scope_prefers_cli_strategies_over_strategy_set() -> None:
    scope = _resolve_strategy_scope(
        {"compare_strategies": ["legacy"]},
        {
            "default_strategy_set": "all",
            "strategy_sets": {"all": {"strategies": ["a", "b"]}},
        },
        strategy_set="all",
        strategies=["only_this"],
    )

    assert scope["source"] == "cli_strategies"
    assert scope["strategies"] == ["only_this"]


def test_strategy_scope_uses_default_strategy_set() -> None:
    scope = _resolve_strategy_scope(
        {"compare_strategies": ["legacy"]},
        {
            "default_strategy_set": "all",
            "strategy_sets": {"all": {"description": "default", "strategies": ["a", "b"]}},
        },
        strategy_set=None,
        strategies=None,
    )

    assert scope["source"] == "strategy_set"
    assert scope["strategy_set"] == "all"
    assert scope["description"] == "default"
    assert scope["strategies"] == ["a", "b"]


def test_strategy_scope_falls_back_to_legacy_compare_strategies() -> None:
    scope = _resolve_strategy_scope(
        {"compare_strategies": ["legacy"]},
        {},
        strategy_set=None,
        strategies=None,
    )

    assert scope["source"] == "legacy_compare_strategies"
    assert scope["strategies"] == ["legacy"]


def test_admission_gate_prefers_admission_config_and_falls_back_to_legacy_gate() -> None:
    gate = _resolve_admission_gate(
        {
            "gate": {"sharpe_min": 0.4, "min_positive_fold_ratio": 0.6},
            "admission": {"gate": {"sharpe_min": 0.7, "turnover_annual_mean_max": 2.0}},
        }
    )

    assert gate["sharpe_min"] == 0.7
    assert gate["positive_fold_ratio_min"] == 0.6
    assert gate["turnover_annual_mean_max"] == 2.0
    assert gate["require_qfq_asof"] is True


def test_diagnostic_suites_are_design_inputs() -> None:
    suites = _resolve_diagnostic_suites(
        {"diagnostics": {"suites": ["data_quality_v1", "overfit_v1"]}}
    )

    assert suites == ["data_quality_v1", "overfit_v1"]


def test_strategy_set_forces_legacy_enabled_switches_in_runtime_copy() -> None:
    strategy_cfg = {
        "core_selection_quality_momentum": {"enabled": False},
        "theme_exposure_momentum": {"enabled": False},
        "local_factor": {"quality_low_turnover_monthly": {"enabled": False}},
    }

    _force_strategy_set_enabled_for_admission(
        strategy_cfg,
        [
            "core_selection_quality_momentum_v1",
            "theme_exposure_momentum_v1",
            "quality_low_turnover_monthly_v1",
            "sleeve_composite_v1",
        ],
    )

    assert strategy_cfg["core_selection_quality_momentum"]["enabled"] is True
    assert strategy_cfg["theme_exposure_momentum"]["enabled"] is True
    assert strategy_cfg["local_factor"]["quality_low_turnover_monthly"]["enabled"] is True
    assert strategy_cfg["sleeve_composite"]["enabled"] is True


def test_overfit_gate_uses_configured_max_level() -> None:
    gate = {"overfit_risk_max": "medium"}

    assert _overfit_blocks_admission("medium", gate) is False
    assert _overfit_blocks_admission("high", gate) is True
    assert _overfit_blocks_admission("critical", gate) is True


def test_overfit_metrics_flag_last_fold_lift_risk() -> None:
    metrics = _metrics(
        pd.DataFrame(
            [
                {"walk_forward_preset": "baseline", "fold": 1, "annualized_return": -0.08, "sharpe": -0.5, "max_drawdown": -0.1, "turnover_annual": 1.0},
                {"walk_forward_preset": "baseline", "fold": 2, "annualized_return": -0.04, "sharpe": -0.2, "max_drawdown": -0.1, "turnover_annual": 1.0},
                {"walk_forward_preset": "baseline", "fold": 3, "annualized_return": 0.12, "sharpe": 0.8, "max_drawdown": -0.1, "turnover_annual": 1.0},
            ]
        )
    )
    score, reasons = _score(metrics)

    assert metrics["last_fold_lift_risk"] is True
    assert metrics["last_fold_lift_preset"] == "baseline"
    assert metrics["last_fold_lift"] == 0.18
    assert score >= 15
    assert "last fold materially lifts results" in reasons


def test_overfit_metrics_do_not_flag_stable_positive_folds_as_last_fold_lift() -> None:
    metrics = _metrics(
        pd.DataFrame(
            [
                {"walk_forward_preset": "quality", "fold": 1, "annualized_return": 0.05, "sharpe": 0.7, "max_drawdown": -0.1, "turnover_annual": 1.0},
                {"walk_forward_preset": "quality", "fold": 2, "annualized_return": 0.07, "sharpe": 0.8, "max_drawdown": -0.1, "turnover_annual": 1.0},
                {"walk_forward_preset": "quality", "fold": 3, "annualized_return": 0.16, "sharpe": 1.0, "max_drawdown": -0.1, "turnover_annual": 1.0},
            ]
        )
    )
    _, reasons = _score(metrics)

    assert metrics["last_fold_lift_risk"] is False
    assert "last fold materially lifts results" not in reasons


def test_overfit_diagnostic_can_use_standard_artifact_names(tmp_path) -> None:
    folds_path = tmp_path / "folds.csv"
    pd.DataFrame(
        [
            {
                "strategy_id": "demo_strategy",
                "fold": 1,
                "annualized_return": 0.03,
                "sharpe": 0.8,
                "max_drawdown": -0.08,
                "turnover_annual": 1.0,
                "selected_params": "p1",
            }
        ]
    ).to_csv(folds_path, index=False)

    result = run_overfit_diagnostic(
        config={},
        root=tmp_path,
        candidates_path=folds_path,
        folds_path=folds_path,
        output_dir=tmp_path / "reports" / "runs" / "2026-06-23" / "20260623_180000__strategy_admission__demo",
        standard_names=True,
    )

    assert result.csv_path.name == "overfit__diagnostic.csv"
    assert result.md_path.name == "overfit__diagnostic.md"
    assert result.csv_path.exists()
    assert result.md_path.exists()


def test_window_metrics_preserve_diagnostic_statuses_without_fake_zero_meaning() -> None:
    group = pd.DataFrame(
        [
            {
                "fold": 1,
                "annualized_return": 0.05,
                "sharpe": 0.6,
                "max_drawdown": -0.1,
                "turnover_annual": 1.2,
                "trades": 5,
                "selected_params": "p1",
                "account_execution_status": "not_enabled",
                "financial_diagnostic_status": "not_available",
                "walk_forward_start_date": "2020-04-01",
                "walk_forward_end_date": "2026-03-31",
                "walk_forward_expected_folds": 2,
                "walk_forward_actual_folds": 1,
                "walk_forward_fold_generation_warning": "",
            }
        ]
    )
    gate = {
        "annualized_return_min": 0.0,
        "sharpe_min": 0.5,
        "max_drawdown_min": -0.25,
        "positive_fold_ratio_min": 0.75,
        "turnover_annual_mean_max": 3.0,
        "turnover_annual_max_max": 5.0,
    }

    row = _window_metrics("demo", "quality_4y_1y", group, gate)

    assert row["account_execution_status"] == "not_enabled"
    assert row["industry_diagnostic_status"] == "not_enabled"
    assert row["financial_diagnostic_status"] == "not_available"
    assert row["account_executed_order_count_total"] == 0


def test_required_industry_check_counts_missing_status() -> None:
    ok_windows = pd.DataFrame(
        [
            {"industry_diagnostic_status": "not_enabled"},
            {"industry_diagnostic_status": "enabled:audited"},
        ]
    )

    assert _industry_missing_window_count(ok_windows) == 1


def test_research_only_strategy_cannot_be_eligible_for_paper_review() -> None:
    action, reasons = _admission_action(
        pass_count=2,
        preset_count=2,
        turnover_fail_count=0,
        missing_window_count=0,
        parameter_unstable_count=0,
        industry_concentration_count=0,
        industry_missing_count=0,
        factor_missing_count=0,
        price_adjustment_fail_count=0,
        overfit_level="low",
        supports_paper_trade=False,
        group=pd.DataFrame([{"positive_fold_ratio": 1.0}, {"positive_fold_ratio": 1.0}]),
        gate_cfg={
            "positive_fold_ratio_min": 0.75,
            "require_parameter_stability": True,
            "require_industry_concentration_check": True,
        },
    )

    assert action == "research_only"
    assert "strategy does not support paper trade review" in reasons


def test_admission_marks_non_qfq_asof_price_adjustment_as_gate_failure() -> None:
    matrix = pd.DataFrame([{"strategy_id": "demo", "status": "ok"}])
    gate = {"require_qfq_asof": True}

    _attach_price_adjustment_status(
        matrix,
        {"local_history": {"adjust_type": "qfq", "price_adjustment_for_backtest": "qfq_current"}},
        gate,
    )

    assert matrix.loc[0, "price_adjustment_for_backtest"] == "qfq_current"
    assert matrix.loc[0, "price_adjustment_status"] == "not_qfq_asof"
    assert _price_adjustment_fail_window_count(matrix) == 1


def test_walk_forward_preset_description_includes_natural_date_window() -> None:
    lines = describe_walk_forward_presets(
        {
            "presets": {
                "quality_4y_1y": {
                    "train_years": 4,
                    "validate_years": 1,
                    "start_date": "2020-04-01",
                    "end_date": "2026-03-31",
                    "expected_folds": 2,
                    "description": "质量/低换手策略严格复核窗口。",
                }
            }
        },
        ["quality_4y_1y"],
    )

    assert len(lines) == 1
    assert "quality_4y_1y" in lines[0]
    assert "2020-04-01 至 2026-03-31" in lines[0]
    assert "每折用 4 年训练选参" in lines[0]
    assert "预计 2 折" in lines[0]


def test_walk_forward_preset_description_can_default_to_all_presets_for_admission() -> None:
    lines = describe_walk_forward_presets(
        {
            "preset_name": "a",
            "presets": {
                "a": {"train_years": 2, "validate_years": 1},
                "b": {"train_years": 3, "validate_years": 1},
            },
        },
        default_all=True,
    )

    assert len(lines) == 2
    assert "`a`" in lines[0]
    assert "`b`" in lines[1]


def test_governance_report_records_scope_boundaries_and_required_artifacts(tmp_path) -> None:
    matrix = pd.DataFrame(
        [
            {
                "strategy_id": "sleeve_composite_v1",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "status": "ok",
                "price_adjustment_status": "qfq_asof",
                "is_window_pass": False,
                "annualized_return_mean": -0.01,
                "sharpe_mean": -0.2,
                "turnover_annual_mean": 1.2,
                "industry_diagnostic_status": "enabled:audited",
                "financial_diagnostic_status": "not_available",
                "account_execution_status": "not_enabled",
            }
        ]
    )
    review = pd.DataFrame(
        [
            {
                "strategy_id": "sleeve_composite_v1",
                "admission_action": "research_only",
                "window_pass_count": 0,
                "window_count": 1,
                "main_reasons": "strategy does not support paper trade review",
            }
        ]
    )
    output_path = tmp_path / "strategy_admission_governance_report.md"

    _write_governance_report(
        output_path,
        matrix,
        review,
        presets=["baseline_2y_1y_5fold"],
        strategies=["sleeve_composite_v1"],
        strategy_scope={
            "source": "strategy_set",
            "strategy_set": "baseline_admission_all_v1",
            "description": "full admission set",
        },
        gate_cfg={"require_qfq_asof": True, "overfit_risk_max": "medium"},
        diagnostics_suites=["data_quality_v1", "overfit_v1"],
        command_hint="phase0.cli strategy-admission --strategy-set baseline_admission_all_v1",
    )

    text = output_path.read_text(encoding="utf-8")

    assert "# Strategy Admission Governance Report" in text
    assert "baseline_admission_all_v1" in text
    assert "phase0.cli strategy-admission --strategy-set baseline_admission_all_v1" in text
    assert "`qfq_asof`" in text
    assert "research_only" in text
    assert "不得进入 paper review / 模拟账户 / 日报 / watchlist" in text
    assert "strategy_admission_window_matrix.csv" in text
    assert "strategy_admission_constraint_review.csv" in text


def test_strategy_admission_default_output_uses_standard_run_paths(monkeypatch, tmp_path) -> None:
    def fake_run_walk_forward(config, trace_callback=None):
        return {
            "summary": {
                "walk_forward_train_years": 2,
                "walk_forward_validate_years": 1,
                "walk_forward_start_date": "2020-04-01",
                "walk_forward_end_date": "2026-03-31",
                "walk_forward_expected_folds": 1,
                "walk_forward_actual_folds": 1,
            },
            "candidate_folds": pd.DataFrame(
                [
                    {
                        "strategy_id": "demo_strategy",
                        "candidate": "demo_strategy",
                        "fold": 1,
                        "annualized_return": 0.01,
                        "sharpe": 0.1,
                        "max_drawdown": -0.1,
                        "turnover_annual": 1.0,
                        "trades": 1,
                        "selected_params": "p1",
                        "supports_paper_trade": False,
                    }
                ]
            ),
        }

    def fake_overfit(*, config, root, candidates_path, folds_path, output_dir, standard_names=False):
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_name = "overfit__diagnostic.csv" if standard_names else "strategy_overfit_diagnostic.csv"
        csv_path = output_dir / csv_name
        pd.DataFrame(
            [
                {
                    "strategy_id": "demo_strategy",
                    "overfit_risk_level": "low",
                    "overfit_score": 0,
                }
            ]
        ).to_csv(csv_path, index=False)
        return SimpleNamespace(csv_path=csv_path)

    monkeypatch.setattr(admission, "run_walk_forward", fake_run_walk_forward)
    monkeypatch.setattr(admission, "run_overfit_diagnostic", fake_overfit)

    result = run_strategy_admission(
        config={
            "local_history": {"price_adjustment_for_backtest": "qfq_asof"},
            "walk_forward": {
                "presets": {"baseline": {"train_years": 2, "validate_years": 1}},
                "admission": {},
                "strategy_v2": {"compare_strategies": ["demo_strategy"]},
            },
        },
        root=tmp_path,
        presets=["baseline"],
    )

    assert "reports/runs/" in result.output_dir.as_posix()
    assert result.report_md.name == "strategy_admission__report.md"
    assert result.governance_md.name == "strategy_admission__governance.md"
    assert result.matrix_csv.name == "strategy_admission__window_matrix.csv"
    assert result.constraint_csv.name == "strategy_admission__constraint_review.csv"
    assert result.folds_csv.name == "strategy_admission__candidate_folds.csv"
    assert result.overfit_csv.name == "overfit__diagnostic.csv"

    governance_text = result.governance_md.read_text(encoding="utf-8")
    assert "strategy_admission__candidate_folds.csv" in governance_text
    assert "strategy_admission__window_matrix.csv" in governance_text
    assert "strategy_admission__constraint_review.csv" in governance_text
    assert "strategy_admission__report.md" in governance_text
    assert "overfit__diagnostic.csv" in governance_text
    assert "--output-dir" not in governance_text


def test_strategy_admission_default_output_uses_standard_overfit_path_when_no_folds(
    monkeypatch, tmp_path
) -> None:
    def fake_run_walk_forward(config, trace_callback=None):
        return {
            "summary": {
                "reason": "no eligible universe",
                "walk_forward_train_years": 2,
                "walk_forward_validate_years": 1,
                "walk_forward_start_date": "2020-04-01",
                "walk_forward_end_date": "2026-03-31",
                "walk_forward_expected_folds": 1,
                "walk_forward_actual_folds": 0,
            },
            "candidate_folds": pd.DataFrame(),
        }

    def fail_overfit(**kwargs):
        raise AssertionError("overfit diagnostic should not run without candidate folds")

    monkeypatch.setattr(admission, "run_walk_forward", fake_run_walk_forward)
    monkeypatch.setattr(admission, "run_overfit_diagnostic", fail_overfit)

    result = run_strategy_admission(
        config={
            "local_history": {"price_adjustment_for_backtest": "qfq_asof"},
            "walk_forward": {
                "presets": {"baseline": {"train_years": 2, "validate_years": 1}},
                "admission": {},
                "strategy_v2": {"compare_strategies": ["demo_strategy"]},
            },
        },
        root=tmp_path,
        presets=["baseline"],
    )

    assert result.overfit_csv.name == "overfit__diagnostic.csv"
    assert "overfit__diagnostic.csv" in result.governance_md.read_text(encoding="utf-8")
