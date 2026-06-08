from __future__ import annotations

from phase0.strategy_admission import (
    _force_strategy_set_enabled_for_admission,
    _overfit_blocks_admission,
    _resolve_admission_gate,
    _resolve_diagnostic_suites,
    _resolve_strategy_scope,
)


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
