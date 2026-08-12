from __future__ import annotations

import copy
import shlex
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import quant.research.admission.runner as admission_runner
from quant.config import load_config
from quant.research.admission.reports import (
    admission_command_hint as _admission_command_hint,
    config_command_arg as _config_command_arg,
    write_governance_report as _write_governance_report,
    write_report as _write_report,
)
from quant.research.admission.runner import run_strategy_admission
from quant.research.admission.gate import (
    overfit_blocks_admission as _overfit_blocks_admission,
    resolve_admission_gate as _resolve_admission_gate,
    resolve_diagnostic_suites as _resolve_diagnostic_suites,
)
from quant.research.admission.review import (
    admission_action as _admission_action,
    attach_price_adjustment_status as _attach_price_adjustment_status,
    industry_missing_window_count as _industry_missing_window_count,
    price_adjustment_fail_window_count as _price_adjustment_fail_window_count,
    turnover_fail_window_count as _turnover_fail_window_count,
    window_metrics as _window_metrics,
)
from quant.research.admission.strategy_scope import (
    _force_strategy_set_enabled_for_admission,
    _resolve_strategy_scope,
)
from quant.research.diagnostics.overfit import _metrics, _score, run_overfit_diagnostic
from quant.walk_forward import FINANCIAL_DIAGNOSTIC_STRATEGIES, describe_walk_forward_presets


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


def test_strategy_scope_rejects_unknown_strategy_set() -> None:
    with pytest.raises(ValueError, match="unknown admission strategy_set: missing"):
        _resolve_strategy_scope(
            {"compare_strategies": ["legacy"]},
            {"strategy_sets": {"known": ["a"]}},
            strategy_set="missing",
            strategies=None,
        )


def test_admission_command_hint_records_actual_config_path(tmp_path) -> None:
    config_path = tmp_path / "config.main_strategy_i7_price_volume_industry_relative_20260624.yaml"
    config_path.write_text("quant: {}\n", encoding="utf-8")

    hint = _admission_command_hint(
        config_arg=_config_command_arg(config_path, tmp_path),
        presets=["baseline_2y_1y_5fold", "quality_4y_1y"],
        strategy_scope={
            "source": "cli_strategies",
            "strategy_set": "",
            "strategies": ["price_volume_low_turnover_v1"],
        },
        output_dir=tmp_path / "admission",
    )

    assert "--config config.main_strategy_i7_price_volume_industry_relative_20260624.yaml" in hint
    assert "--config config.yaml" not in hint


def test_admission_command_hint_records_only_non_default_cost_multiplier(tmp_path) -> None:
    kwargs = {
        "config_arg": "config.yaml",
        "presets": ["baseline"],
        "strategy_scope": {"strategy_set": "", "strategies": ["demo_strategy"]},
        "output_dir": tmp_path / "admission",
    }

    default_hint = _admission_command_hint(**kwargs)
    sensitivity_hint = _admission_command_hint(**kwargs, cost_multiplier=1.5)
    integer_sensitivity_hint = _admission_command_hint(**kwargs, cost_multiplier=2.0)

    assert "--cost-multiplier" not in default_hint
    assert "--cost-multiplier 1.5" in sensitivity_hint
    assert "--cost-multiplier 2.0" in integer_sensitivity_hint


def test_admission_command_hint_round_trips_paths_with_spaces_and_cost_multiplier(tmp_path) -> None:
    output_dir = tmp_path / "admission results"

    hint = _admission_command_hint(
        config_arg="configs/research config.yaml",
        presets=["baseline", "quality"],
        strategy_scope={"strategy_set": "", "strategies": ["demo_strategy"]},
        output_dir=output_dir,
        cost_multiplier=1.5,
    )

    assert shlex.split(hint) == [
        "python",
        "-m",
        "quant.cli",
        "strategy-admission",
        "--config",
        "configs/research config.yaml",
        "--presets",
        "baseline",
        "quality",
        "--strategies",
        "demo_strategy",
        "--output-dir",
        str(output_dir),
        "--cost-multiplier",
        "1.5",
    ]


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), float("-inf")])
def test_admission_command_hint_rejects_invalid_cost_multiplier(value: float, tmp_path) -> None:
    with pytest.raises(ValueError, match="cost_multiplier must be finite and greater than zero"):
        _admission_command_hint(
            config_arg="config.yaml",
            presets=["baseline"],
            strategy_scope={"strategy_set": "", "strategies": ["demo_strategy"]},
            output_dir=tmp_path / "admission",
            cost_multiplier=value,
        )


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


def test_strategy_set_forces_benchmark_core_alpha_overlay_switch() -> None:
    strategy_cfg = {
        "local_factor": {
            "benchmark_core_alpha_overlay": {"enabled": False},
        },
    }

    _force_strategy_set_enabled_for_admission(strategy_cfg, ["benchmark_core_alpha_overlay_v1"])

    assert strategy_cfg["local_factor"]["benchmark_core_alpha_overlay"]["enabled"] is True


def test_strategy_set_forces_low_churn_v2_enabled_in_runtime_copy() -> None:
    strategy_cfg = {"sleeve_composite_low_churn_v2": {"enabled": False}}

    _force_strategy_set_enabled_for_admission(
        strategy_cfg,
        ["sleeve_composite_low_churn_v2"],
    )

    assert strategy_cfg["sleeve_composite_low_churn_v2"]["enabled"] is True


def test_low_churn_v2_config_is_complete_and_isolated_for_research() -> None:
    config = load_config(Path("config.yaml"))
    walk_forward_cfg = config["walk_forward"]
    admission_cfg = walk_forward_cfg["admission"]
    strategy_cfg = walk_forward_cfg["strategy_v2"]

    assert strategy_cfg["sleeve_composite_low_churn_v2"] == {
        "enabled": False,
        "market": "CN",
        "daily_basic_table": "market_daily_basic",
        "min_available_factors": 4,
        "top_n": 30,
        "hold_top_n": 50,
        "rebalance_days": 20,
        "min_hold_days": 20,
        "max_symbol_weight": 0.04,
        "max_names_per_industry": 3,
        "factor_weights": {
            "slow_quality_score": 0.30,
            "slow_value_score": 0.20,
            "slow_low_vol_score": 0.20,
            "slow_earnings_score": 0.15,
            "slow_residual_momentum_score": 0.15,
        },
    }
    assert admission_cfg["strategy_sets"]["sleeve_low_churn_v2_research_v1"] == {
        "description": "低换手慢因子 v2 专项研究；不代表准入、模拟或实盘资格。",
        "strategies": [
            "sleeve_composite_low_churn_v1",
            "sleeve_composite_low_churn_v2",
        ],
    }
    assert admission_cfg["default_strategy_set"] == "baseline_admission_all_v1"
    assert "sleeve_composite_low_churn_v2" not in admission_cfg["strategy_sets"][
        "baseline_admission_all_v1"
    ]["strategies"]
    assert "sleeve_composite_low_churn_v2" not in strategy_cfg["compare_strategies"]


def test_low_churn_v2_is_added_to_financial_diagnostics_without_dropping_existing_members() -> None:
    assert FINANCIAL_DIAGNOSTIC_STRATEGIES == {
        "core_selection_quality_momentum_v1",
        "low_vol_low_turnover_quality_v1",
        "multifactor_volume_price_filter_v1",
        "quality_growth_price_v1",
        "quality_low_turnover_monthly_v1",
        "quality_low_turnover_regime_gate_v1",
        "sleeve_composite_v1",
        "sleeve_composite_low_churn_v2",
    }


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


def test_turnover_fail_counts_max_turnover_gate() -> None:
    group = pd.DataFrame(
        [
            {
                "turnover_annual_mean": 1.56,
                "turnover_annual_max": 5.73,
            }
        ]
    )

    assert (
        _turnover_fail_window_count(
            group,
            {
                "turnover_annual_mean_max": 3.0,
                "turnover_annual_max_max": 5.0,
            },
        )
        == 1
    )


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


def test_window_metrics_preserves_research_only_strategy_metadata() -> None:
    metrics = _window_metrics(
        "demo_strategy",
        "baseline",
        pd.DataFrame(
            [
                {
                    "fold": 1,
                    "annualized_return": 0.10,
                    "sharpe": 1.0,
                    "max_drawdown": -0.05,
                    "turnover_annual": 1.0,
                    "trades": 5,
                    "selected_params": "p1",
                    "supports_paper_trade": False,
                    "walk_forward_start_date": "2020-04-01",
                    "walk_forward_end_date": "2021-03-31",
                }
            ]
        ),
        {
            "annualized_return_min": 0.0,
            "sharpe_min": 0.5,
            "max_drawdown_min": -0.25,
            "positive_fold_ratio_min": 0.75,
            "turnover_annual_mean_max": 3.0,
            "turnover_annual_max_max": 5.0,
        },
    )

    assert metrics["is_window_pass"] is True
    assert metrics["supports_paper_trade"] is False


def test_window_metrics_summarizes_positive_excess_and_negative_fold_attribution() -> None:
    group = pd.DataFrame(
        [
            {
                "fold": 1,
                "annualized_return": -0.05,
                "benchmark_status": "available",
                "benchmark_annualized_return": -0.10,
                "excess_annualized_return": 0.05,
                "negative_fold_attribution": "negative_absolute_but_positive_excess: market_down_or_benchmark_weaker",
                "sharpe": 0.2,
                "max_drawdown": -0.10,
                "turnover_annual": 1.0,
                "trades": 3,
                "selected_params": "p1",
            },
            {
                "fold": 2,
                "annualized_return": 0.02,
                "benchmark_status": "available",
                "benchmark_annualized_return": 0.03,
                "excess_annualized_return": -0.01,
                "negative_fold_attribution": "positive_fold",
                "sharpe": 0.8,
                "max_drawdown": -0.04,
                "turnover_annual": 1.1,
                "trades": 4,
                "selected_params": "p1",
            },
            {
                "fold": 3,
                "annualized_return": -0.04,
                "benchmark_status": "available",
                "benchmark_annualized_return": 0.01,
                "excess_annualized_return": -0.05,
                "negative_fold_attribution": "negative_absolute_and_negative_excess: strategy_specific_underperformance",
                "sharpe": -0.3,
                "max_drawdown": -0.11,
                "turnover_annual": 0.9,
                "trades": 2,
                "selected_params": "p2",
            },
        ]
    )
    gate = {
        "annualized_return_min": -0.10,
        "sharpe_min": -1.0,
        "max_drawdown_min": -0.25,
        "positive_fold_ratio_min": 0.25,
        "turnover_annual_mean_max": 3.0,
        "turnover_annual_max_max": 5.0,
    }

    metrics = _window_metrics("demo_strategy", "baseline", group, gate)

    assert metrics["benchmark_status"] == "available"
    assert metrics["benchmark_available_fold_count"] == 3
    assert metrics["positive_fold_ratio"] == pytest.approx(1 / 3)
    assert metrics["positive_excess_fold_ratio"] == pytest.approx(1 / 3)
    assert metrics["excess_annualized_return_mean"] == pytest.approx((-0.01) / 3)
    assert metrics["negative_absolute_fold_count"] == 2
    assert metrics["negative_absolute_positive_excess_count"] == 1
    assert metrics["negative_absolute_negative_excess_count"] == 1
    assert metrics["negative_absolute_benchmark_unavailable_count"] == 0


def test_positive_excess_ratio_does_not_override_absolute_admission_gate() -> None:
    group = pd.DataFrame(
        [
            {
                "fold": 1,
                "annualized_return": -0.02,
                "benchmark_status": "available",
                "benchmark_annualized_return": -0.10,
                "excess_annualized_return": 0.08,
                "negative_fold_attribution": "negative_absolute_but_positive_excess: market_down_or_benchmark_weaker",
                "sharpe": 1.0,
                "max_drawdown": -0.05,
                "turnover_annual": 1.0,
                "trades": 3,
                "selected_params": "p1",
            },
            {
                "fold": 2,
                "annualized_return": -0.01,
                "benchmark_status": "available",
                "benchmark_annualized_return": -0.08,
                "excess_annualized_return": 0.07,
                "negative_fold_attribution": "negative_absolute_but_positive_excess: market_down_or_benchmark_weaker",
                "sharpe": 1.1,
                "max_drawdown": -0.04,
                "turnover_annual": 1.0,
                "trades": 4,
                "selected_params": "p1",
            },
        ]
    )
    gate = {
        "annualized_return_min": -0.10,
        "sharpe_min": 0.5,
        "max_drawdown_min": -0.25,
        "positive_fold_ratio_min": 0.75,
        "turnover_annual_mean_max": 3.0,
        "turnover_annual_max_max": 5.0,
        "require_parameter_stability": True,
        "require_industry_concentration_check": True,
    }

    metrics = _window_metrics("demo_strategy", "baseline", group, gate)
    action, reasons = _admission_action(
        pass_count=0,
        preset_count=1,
        turnover_fail_count=0,
        missing_window_count=0,
        parameter_unstable_count=0,
        industry_concentration_count=0,
        industry_missing_count=0,
        factor_missing_count=0,
        price_adjustment_fail_count=0,
        overfit_level="low",
        supports_paper_trade=True,
        group=pd.DataFrame([metrics]),
        gate_cfg=gate,
    )

    assert metrics["positive_excess_fold_ratio"] == pytest.approx(1.0)
    assert metrics["positive_fold_ratio"] == pytest.approx(0.0)
    assert metrics["is_positive_fold_pass"] is False
    assert metrics["is_window_pass"] is False
    assert action == "reject"
    assert "positive fold ratio below 75% in one or more windows" in reasons


def test_admission_report_shows_paper_trade_capability(tmp_path) -> None:
    report_path = tmp_path / "strategy_admission_report.md"
    matrix = pd.DataFrame(
        [
            {
                "strategy_id": "demo_strategy",
                "walk_forward_preset": "baseline",
                "status": "ok",
                "fold_count": 1,
                "walk_forward_start_date": "2020-04-01",
                "walk_forward_end_date": "2021-03-31",
                "walk_forward_expected_folds": 1,
                "walk_forward_actual_folds": 1,
                "walk_forward_fold_generation_warning": "",
                "price_adjustment_status": "qfq_asof",
                "annualized_return_mean": 0.10,
                "sharpe_mean": 1.0,
                "max_drawdown_worst": -0.05,
                "turnover_annual_mean": 1.0,
                "industry_diagnostic_status": "enabled:audited",
                "top_industry_avg_share_mean": 0.10,
                "top3_industries_avg_share_mean": 0.30,
                "account_execution_status": "not_enabled",
                "account_annualized_return_mean": 0.0,
                "account_sharpe_mean": 0.0,
                "account_executed_order_count_total": 0,
                "financial_diagnostic_status": "not_applicable",
                "benchmark_status": "available",
                "benchmark_available_fold_count": 1,
                "benchmark_annualized_return_mean": 0.05,
                "excess_annualized_return_mean": 0.05,
                "excess_annualized_return_min": 0.05,
                "positive_fold_ratio": 1.0,
                "positive_excess_fold_ratio": 1.0,
                "negative_absolute_fold_count": 0,
                "negative_absolute_positive_excess_count": 0,
                "negative_absolute_negative_excess_count": 0,
                "negative_absolute_benchmark_unavailable_count": 0,
                "is_window_pass": True,
            }
        ]
    )
    review = pd.DataFrame(
        [
            {
                "strategy_id": "demo_strategy",
                "admission_action": "research_only",
                "window_pass_count": 1,
                "window_count": 1,
                "turnover_fail_count": 0,
                "parameter_unstable_window_count": 0,
                "industry_diagnostic_missing_window_count": 0,
                "industry_concentration_window_count": 0,
                "factor_diagnostic_missing_window_count": 0,
                "price_adjustment_fail_window_count": 0,
                "supports_paper_trade": False,
                "overfit_risk_level": "low",
                "main_reasons": "strategy does not support paper trade review",
            }
        ]
    )

    _write_report(
        report_path,
        matrix,
        review,
        ["baseline"],
        ["demo_strategy"],
        root=tmp_path,
        strategy_scope={"source": "cli_strategies", "strategy_set": ""},
        gate_cfg={"require_qfq_asof": True},
        diagnostics_suites=[],
    )

    text = report_path.read_text(encoding="utf-8")
    assert "paper_trade" in text
    assert "Benchmark / Excess Diagnostics" in text
    assert "Supplemental only" in text
    assert "| demo_strategy | research_only | 1/1 | 0 | 0 | 0 | 0 | 0 | 0 | False | low |" in text


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
        command_hint="quant.cli strategy-admission --strategy-set baseline_admission_all_v1",
    )

    text = output_path.read_text(encoding="utf-8")

    assert "# Strategy Admission Governance Report" in text
    assert "baseline_admission_all_v1" in text
    assert "quant.cli strategy-admission --strategy-set baseline_admission_all_v1" in text
    assert "`qfq_asof`" in text
    assert "research_only" in text
    assert "不得进入 paper review / 模拟账户 / 日报 / watchlist" in text
    assert "strategy_admission_window_matrix.csv" in text
    assert "strategy_admission_constraint_review.csv" in text


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), float("-inf")])
def test_strategy_admission_rejects_invalid_cost_multiplier(value: float, tmp_path) -> None:
    with pytest.raises(ValueError, match="cost_multiplier must be finite and greater than zero"):
        run_strategy_admission(config={}, root=tmp_path, cost_multiplier=value)


def test_strategy_admission_applies_cost_multiplier_without_mutating_config(
    monkeypatch, tmp_path
) -> None:
    original_config = {
        "local_history": {"price_adjustment_for_backtest": "qfq_asof"},
        "walk_forward": {
            "commission": 0.00025,
            "stamp_duty_sell": 0.0005,
            "slippage": 0.00246,
            "execution": {
                "commission": 9.0,
                "stamp_duty_sell": 8.0,
                "slippage": 7.0,
                "transfer_fee": 0.00001,
                "minimum_commission": 5.0,
            },
            "presets": {"baseline": {"train_years": 2, "validate_years": 1}},
            "admission": {},
            "strategy_v2": {"compare_strategies": ["demo_strategy"]},
        },
        "unrelated": {"nested": [1, 2, 3]},
    }
    expected_original = copy.deepcopy(original_config)
    runtime_configs: list[dict] = []
    walk_forward_configs: list[dict] = []
    overfit_configs: list[dict] = []

    def fake_create_walk_forward_runtime(config, root):
        runtime_configs.append(config)
        return SimpleNamespace(name="cost-sensitive-runtime")

    def fake_run_walk_forward(config, trace_callback=None, runtime=None):
        walk_forward_configs.append(config)
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
        overfit_configs.append(config)
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / "strategy_overfit_diagnostic.csv"
        pd.DataFrame(
            [{"strategy_id": "demo_strategy", "overfit_risk_level": "low", "overfit_score": 0}]
        ).to_csv(csv_path, index=False)
        return SimpleNamespace(csv_path=csv_path)

    monkeypatch.setattr(admission_runner, "create_walk_forward_runtime", fake_create_walk_forward_runtime)
    monkeypatch.setattr(admission_runner, "run_walk_forward", fake_run_walk_forward)
    monkeypatch.setattr(admission_runner, "run_overfit_diagnostic", fake_overfit)

    result = run_strategy_admission(
        config=original_config,
        root=tmp_path,
        presets=["baseline"],
        output_dir=tmp_path / "admission",
        cost_multiplier=1.5,
    )

    assert original_config == expected_original
    assert len(runtime_configs) == len(walk_forward_configs) == len(overfit_configs) == 1
    for effective_config in [runtime_configs[0], walk_forward_configs[0], overfit_configs[0]]:
        walk_forward = effective_config["walk_forward"]
        assert walk_forward["commission"] == pytest.approx(0.000375)
        assert walk_forward["stamp_duty_sell"] == pytest.approx(0.00075)
        assert walk_forward["slippage"] == pytest.approx(0.00369)
        execution = walk_forward["execution"]
        assert execution["commission"] == 9.0
        assert execution["stamp_duty_sell"] == 8.0
        assert execution["slippage"] == 7.0
        assert execution["transfer_fee"] == 0.00001
        assert execution["minimum_commission"] == 5.0
        assert effective_config["unrelated"] == {"nested": [1, 2, 3]}

    folds = pd.read_csv(result.folds_csv)
    matrix = pd.read_csv(result.matrix_csv)
    assert folds["research_cost_multiplier"].tolist() == [1.5]
    assert matrix["research_cost_multiplier"].tolist() == [1.5]
    governance_text = result.governance_md.read_text(encoding="utf-8")
    assert "Research cost multiplier: `1.5`" in governance_text
    assert "--cost-multiplier 1.5" in governance_text


def test_strategy_admission_default_output_uses_standard_run_paths(monkeypatch, tmp_path) -> None:
    def fake_run_walk_forward(config, trace_callback=None, runtime=None):
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

    monkeypatch.setattr(admission_runner, "run_walk_forward", fake_run_walk_forward)
    monkeypatch.setattr(admission_runner, "run_overfit_diagnostic", fake_overfit)

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

    folds = pd.read_csv(result.folds_csv)
    matrix = pd.read_csv(result.matrix_csv)
    assert folds["research_cost_multiplier"].tolist() == [1.0]
    assert matrix["research_cost_multiplier"].tolist() == [1.0]

    governance_text = result.governance_md.read_text(encoding="utf-8")
    assert "strategy_admission__candidate_folds.csv" in governance_text
    assert "strategy_admission__window_matrix.csv" in governance_text
    assert "strategy_admission__constraint_review.csv" in governance_text
    assert "strategy_admission__report.md" in governance_text
    assert "overfit__diagnostic.csv" in governance_text
    assert "--output-dir" not in governance_text
    assert "Research cost multiplier: `1.0`" in governance_text
    assert "--cost-multiplier" not in governance_text


def test_strategy_admission_default_output_uses_standard_overfit_path_when_no_folds(
    monkeypatch, tmp_path
) -> None:
    def fake_run_walk_forward(config, trace_callback=None, runtime=None):
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

    monkeypatch.setattr(admission_runner, "run_walk_forward", fake_run_walk_forward)
    monkeypatch.setattr(admission_runner, "run_overfit_diagnostic", fail_overfit)

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
    governance_text = result.governance_md.read_text(encoding="utf-8")
    assert "overfit__diagnostic.csv" in governance_text
    empty_folds = pd.read_csv(result.folds_csv)
    empty_overfit = pd.read_csv(result.overfit_csv)
    matrix = pd.read_csv(result.matrix_csv)
    assert empty_folds.empty
    assert {
        "strategy_id",
        "candidate",
        "walk_forward_preset",
        "fold",
        "status",
        "failure_reason",
        "research_cost_multiplier",
    }.issubset(empty_folds.columns)
    assert empty_overfit.empty
    assert {
        "strategy_id",
        "overfit_risk_level",
        "overfit_score",
        "status",
        "failure_reason",
    }.issubset(empty_overfit.columns)
    assert matrix["research_cost_multiplier"].tolist() == [1.0]

    artifact_paths = {
        result.folds_csv,
        result.matrix_csv,
        result.constraint_csv,
        result.report_md,
        result.overfit_csv,
    }
    assert all(path.exists() for path in artifact_paths)
    required_section = governance_text.split("## Required Artifacts", 1)[1].split("## Summary", 1)[0]
    required_names = [
        line.removeprefix("- `").removesuffix("`")
        for line in required_section.splitlines()
        if line.startswith("- `")
    ]
    assert required_names
    assert all((result.output_dir / name).exists() for name in required_names)


def test_strategy_admission_forwards_walk_forward_runtime_overrides(monkeypatch, tmp_path) -> None:
    seen_configs: list[dict] = []

    def fake_run_walk_forward(config, trace_callback=None, runtime=None):
        seen_configs.append(config)
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

    monkeypatch.setattr(admission_runner, "run_walk_forward", fake_run_walk_forward)
    monkeypatch.setattr(
        admission_runner,
        "run_overfit_diagnostic",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("overfit diagnostic should not run without folds")),
    )

    run_strategy_admission(
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
        profile_run=True,
        no_wf_cache=True,
        refresh_wf_cache=True,
    )

    assert len(seen_configs) == 1
    walk_forward_cfg = seen_configs[0]["walk_forward"]
    assert walk_forward_cfg["execution"]["profile"] is True
    assert walk_forward_cfg["cache"]["enabled"] is False
    assert walk_forward_cfg["cache"]["refresh"] is True


def test_strategy_admission_reuses_walk_forward_runtime_across_presets(monkeypatch, tmp_path) -> None:
    runtimes: list[object] = []
    created: list[dict] = []

    def fake_create_walk_forward_runtime(config, root):
        created.append({"config": config, "root": root})
        return SimpleNamespace(name="shared-runtime")

    def fake_run_walk_forward(config, trace_callback=None, runtime=None):
        runtimes.append(runtime)
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

    monkeypatch.setattr(admission_runner, "create_walk_forward_runtime", fake_create_walk_forward_runtime)
    monkeypatch.setattr(admission_runner, "run_walk_forward", fake_run_walk_forward)

    run_strategy_admission(
        config={
            "local_history": {"price_adjustment_for_backtest": "qfq_asof"},
            "walk_forward": {
                "presets": {
                    "baseline": {"train_years": 2, "validate_years": 1},
                    "quality": {"train_years": 3, "validate_years": 1},
                },
                "admission": {},
                "strategy_v2": {"compare_strategies": ["demo_strategy"]},
            },
        },
        root=tmp_path,
        presets=["baseline", "quality"],
    )

    assert len(created) == 1
    assert len(runtimes) == 2
    assert runtimes[0] is runtimes[1]
    assert runtimes[0] is not None


def test_force_strategy_set_enabled_supports_regime_gate_strategy() -> None:
    strategy_cfg = {"local_factor": {"quality_low_turnover_regime_gate": {"enabled": False}}}

    _force_strategy_set_enabled_for_admission(strategy_cfg, ["quality_low_turnover_regime_gate_v1"])

    assert strategy_cfg["local_factor"]["quality_low_turnover_regime_gate"]["enabled"] is True


def test_force_strategy_set_enabled_supports_price_volume_low_turnover_strategy() -> None:
    strategy_cfg = {"local_factor": {"price_volume_low_turnover": {"enabled": False}}}

    _force_strategy_set_enabled_for_admission(strategy_cfg, ["price_volume_low_turnover_v1"])

    assert strategy_cfg["local_factor"]["price_volume_low_turnover"]["enabled"] is True


def test_force_strategy_set_enabled_supports_strong_index_participation_strategy() -> None:
    strategy_cfg = {"local_factor": {"strong_index_participation": {"enabled": False}}}

    _force_strategy_set_enabled_for_admission(strategy_cfg, ["strong_index_participation_v1"])

    assert strategy_cfg["local_factor"]["strong_index_participation"]["enabled"] is True


def test_force_strategy_set_enabled_supports_strong_index_dynamic_trigger_strategy() -> None:
    strategy_cfg = {"local_factor": {"strong_index_participation": {"enabled": False}}}

    _force_strategy_set_enabled_for_admission(strategy_cfg, ["strong_index_participation_dynamic_trigger_v1"])

    assert strategy_cfg["local_factor"]["strong_index_participation"]["enabled"] is True


def test_force_strategy_set_enabled_supports_strong_market_liquid_breadth_strategy() -> None:
    strategy_cfg = {"local_factor": {"strong_market_liquid_breadth_participation": {"enabled": False}}}

    _force_strategy_set_enabled_for_admission(strategy_cfg, ["strong_market_liquid_breadth_participation_v1"])

    assert strategy_cfg["local_factor"]["strong_market_liquid_breadth_participation"]["enabled"] is True


def test_force_strategy_set_enabled_supports_strong_market_stable_core_base_strategy() -> None:
    strategy_cfg = {"local_factor": {"strong_market_stable_core_base": {"enabled": False}}}

    _force_strategy_set_enabled_for_admission(strategy_cfg, ["strong_market_stable_core_base_v1"])

    assert strategy_cfg["local_factor"]["strong_market_stable_core_base"]["enabled"] is True


def test_force_strategy_set_enabled_supports_strong_market_benchmark_aware_core_strategy() -> None:
    strategy_cfg = {"local_factor": {"strong_market_benchmark_aware_core": {"enabled": False}}}

    _force_strategy_set_enabled_for_admission(strategy_cfg, ["strong_market_benchmark_aware_core_v1"])

    assert strategy_cfg["local_factor"]["strong_market_benchmark_aware_core"]["enabled"] is True


def test_force_strategy_set_enabled_supports_strong_benchmark_participation_boost_strategy() -> None:
    strategy_cfg = {"local_factor": {"strong_benchmark_participation_boost": {"enabled": False}}}

    _force_strategy_set_enabled_for_admission(strategy_cfg, ["strong_benchmark_participation_boost_v1"])

    assert strategy_cfg["local_factor"]["strong_benchmark_participation_boost"]["enabled"] is True


def test_force_strategy_set_enabled_supports_strong_benchmark_recovery_participation_strategy() -> None:
    strategy_cfg = {"local_factor": {"strong_benchmark_recovery_participation": {"enabled": False}}}

    _force_strategy_set_enabled_for_admission(strategy_cfg, ["strong_benchmark_recovery_participation_v1"])

    assert strategy_cfg["local_factor"]["strong_benchmark_recovery_participation"]["enabled"] is True


def test_force_strategy_set_enabled_supports_strong_benchmark_recovery_quality_strategy() -> None:
    strategy_cfg = {"local_factor": {"strong_benchmark_recovery_quality": {"enabled": False}}}

    _force_strategy_set_enabled_for_admission(strategy_cfg, ["strong_benchmark_recovery_quality_v1"])

    assert strategy_cfg["local_factor"]["strong_benchmark_recovery_quality"]["enabled"] is True


def test_force_strategy_set_enabled_supports_strong_benchmark_recovery_tradable_strategy() -> None:
    strategy_cfg = {"local_factor": {"strong_benchmark_recovery_tradable": {"enabled": False}}}

    _force_strategy_set_enabled_for_admission(strategy_cfg, ["strong_benchmark_recovery_tradable_v1"])

    assert strategy_cfg["local_factor"]["strong_benchmark_recovery_tradable"]["enabled"] is True


def test_force_strategy_set_enabled_supports_strong_benchmark_recovery_leadership_strategy() -> None:
    strategy_cfg = {"local_factor": {"strong_benchmark_recovery_leadership": {"enabled": False}}}

    _force_strategy_set_enabled_for_admission(strategy_cfg, ["strong_benchmark_recovery_leadership_v1"])

    assert strategy_cfg["local_factor"]["strong_benchmark_recovery_leadership"]["enabled"] is True


def test_i48_attribution_variants_only_enable_scoped_evidence_runs() -> None:
    strategy_cfg = {"local_factor": {"strong_market_stable_core_base": {"enabled": False}}}

    _force_strategy_set_enabled_for_admission(
        strategy_cfg,
        ["strong_market_stable_core_only_v1", "strong_market_stable_satellite_only_v1"],
    )

    assert strategy_cfg["local_factor"]["strong_market_stable_core_base"]["enabled"] is True
    scope = _resolve_strategy_scope(
        {"compare_strategies": ["legacy_momentum", "strong_market_stable_core_base_v1"]},
        {
            "default_strategy_set": "baseline_admission_all_v1",
            "strategy_sets": {
                "baseline_admission_all_v1": {
                    "strategies": ["legacy_momentum", "strong_market_stable_core_base_v1"]
                }
            },
        },
        strategy_set="baseline_admission_all_v1",
        strategies=None,
    )
    assert "strong_market_stable_core_only_v1" not in scope["strategies"]
    assert "strong_market_stable_satellite_only_v1" not in scope["strategies"]


def test_force_strategy_set_enabled_supports_sleeve_low_churn_strategy() -> None:
    strategy_cfg = {"sleeve_composite_low_churn": {"enabled": False}}

    _force_strategy_set_enabled_for_admission(strategy_cfg, ["sleeve_composite_low_churn_v1"])

    assert strategy_cfg["sleeve_composite_low_churn"]["enabled"] is True
