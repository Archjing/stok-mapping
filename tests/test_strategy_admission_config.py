from __future__ import annotations

import pandas as pd

from phase0.strategy_admission import (
    _attach_price_adjustment_status,
    _force_strategy_set_enabled_for_admission,
    _industry_missing_window_count,
    _overfit_blocks_admission,
    _price_adjustment_fail_window_count,
    _resolve_admission_gate,
    _resolve_diagnostic_suites,
    _resolve_strategy_scope,
    _window_metrics,
)
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
        ],
    )

    assert strategy_cfg["core_selection_quality_momentum"]["enabled"] is True
    assert strategy_cfg["theme_exposure_momentum"]["enabled"] is True
    assert strategy_cfg["local_factor"]["quality_low_turnover_monthly"]["enabled"] is True


def test_overfit_gate_uses_configured_max_level() -> None:
    gate = {"overfit_risk_max": "medium"}

    assert _overfit_blocks_admission("medium", gate) is False
    assert _overfit_blocks_admission("high", gate) is True
    assert _overfit_blocks_admission("critical", gate) is True


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
