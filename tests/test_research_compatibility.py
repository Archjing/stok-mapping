from __future__ import annotations

from importlib import import_module

import pytest


@pytest.mark.parametrize(
    ("legacy_module_name", "new_module_name", "symbols"),
    [
        (
            "phase0.strategy_market_context",
            "phase0.research.diagnostics.market_context",
            ["run_strategy_market_context"],
        ),
        (
            "phase0.strategy_exposure_diagnostic",
            "phase0.research.diagnostics.exposure",
            ["run_strategy_exposure_diagnostic"],
        ),
        (
            "phase0.strategy_filter_diagnostic",
            "phase0.research.diagnostics.filter",
            ["run_strategy_filter_diagnostic", "_daily_filter_rows", "_fold_summary_row"],
        ),
        (
            "phase0.factor_effectiveness",
            "phase0.research.diagnostics.factor_effectiveness",
            ["FactorEffectivenessResult", "FactorSpec", "FACTOR_SPECS", "run_factor_effectiveness_report"],
        ),
        (
            "phase0.overfit",
            "phase0.research.diagnostics.overfit",
            ["OverfitDiagnosticResult", "run_overfit_diagnostic", "_metrics", "_score"],
        ),
        (
            "phase0.strategy_role_card",
            "phase0.research.summaries.role_card",
            ["StrategyRoleCardResult", "run_strategy_role_card", "ADMISSION_PASS_ACTIONS"],
        ),
        (
            "phase0.strategy_participation_overlay",
            "phase0.research.participation.overlay",
            ["StrategyParticipationOverlayResult", "run_strategy_participation_overlay", "_overlay_daily_rows"],
        ),
        (
            "phase0.strategy_participation_path_audit",
            "phase0.research.participation.path_audit",
            ["StrategyParticipationPathAuditResult", "run_strategy_participation_path_audit"],
        ),
        (
            "phase0.strategy_holdings_exposure",
            "phase0.research.holdings.exposure",
            [
                "StrategyHoldingsExposureResult",
                "run_strategy_holdings_exposure",
                "_coverage_summary",
                "_holding_rows_from_signal",
            ],
        ),
        (
            "phase0.strategy_alpha_source_audit",
            "phase0.research.attribution.alpha_source",
            ["StrategyAlphaSourceAuditResult", "run_strategy_alpha_source_audit"],
        ),
        (
            "phase0.strategy_csi300_attribution",
            "phase0.research.attribution.csi300",
            ["DEFAULT_BENCHMARK", "StrategyCsi300AttributionResult", "run_strategy_csi300_attribution"],
        ),
        (
            "phase0.strategy_fold_attribution",
            "phase0.research.attribution.fold",
            ["StrategyFoldAttributionResult", "run_strategy_fold_attribution"],
        ),
        (
            "phase0.strategy_core_reachability",
            "phase0.research.core_coverage.core_reachability",
            [
                "StrategyCoreReachabilityResult",
                "_diagnose_fold",
                "_seed_benchmark_panel",
                "run_strategy_core_reachability_diagnostic",
            ],
        ),
        (
            "phase0.strategy_missing_core_audit",
            "phase0.research.core_coverage.missing_core_audit",
            ["MissingCoreAuditResult", "run_missing_core_audit"],
        ),
        (
            "phase0.strategy_failure_attribution",
            "phase0.research.admission.failure_attribution",
            ["SEVERITY_RANK", "StrategyFailureAttributionResult", "run_strategy_failure_attribution"],
        ),
    ],
)
def test_research_legacy_imports_alias_split_modules(
    legacy_module_name: str,
    new_module_name: str,
    symbols: list[str],
) -> None:
    legacy_module = import_module(legacy_module_name)
    new_module = import_module(new_module_name)

    assert legacy_module is new_module
    for symbol in symbols:
        assert getattr(legacy_module, symbol) is getattr(new_module, symbol)


@pytest.mark.parametrize(
    ("package_name", "module_name", "symbols"),
    [
        (
            "phase0.research.summaries",
            "phase0.research.summaries.role_card",
            ["StrategyRoleCardResult", "run_strategy_role_card"],
        ),
        (
            "phase0.research.participation",
            "phase0.research.participation.overlay",
            ["StrategyParticipationOverlayResult", "run_strategy_participation_overlay"],
        ),
        (
            "phase0.research.participation",
            "phase0.research.participation.path_audit",
            ["StrategyParticipationPathAuditResult", "run_strategy_participation_path_audit"],
        ),
        (
            "phase0.research.holdings",
            "phase0.research.holdings.exposure",
            ["StrategyHoldingsExposureResult", "run_strategy_holdings_exposure"],
        ),
        (
            "phase0.research.attribution",
            "phase0.research.attribution.alpha_source",
            ["StrategyAlphaSourceAuditResult", "run_strategy_alpha_source_audit"],
        ),
        (
            "phase0.research.attribution",
            "phase0.research.attribution.csi300",
            ["StrategyCsi300AttributionResult", "run_strategy_csi300_attribution"],
        ),
        (
            "phase0.research.attribution",
            "phase0.research.attribution.fold",
            ["StrategyFoldAttributionResult", "run_strategy_fold_attribution"],
        ),
        (
            "phase0.research.core_coverage",
            "phase0.research.core_coverage.core_reachability",
            ["StrategyCoreReachabilityResult", "run_strategy_core_reachability_diagnostic"],
        ),
        (
            "phase0.research.core_coverage",
            "phase0.research.core_coverage.missing_core_audit",
            ["MissingCoreAuditResult", "run_missing_core_audit"],
        ),
        (
            "phase0.research.admission",
            "phase0.research.admission.failure_attribution",
            ["StrategyFailureAttributionResult", "run_strategy_failure_attribution"],
        ),
    ],
)
def test_research_package_exports_alias_split_modules(
    package_name: str,
    module_name: str,
    symbols: list[str],
) -> None:
    package = import_module(package_name)
    split_module = import_module(module_name)

    for symbol in symbols:
        assert getattr(package, symbol) is getattr(split_module, symbol)


@pytest.mark.parametrize(
    ("legacy_module_name", "new_module_name", "symbol_pairs"),
    [
        (
            "phase0.strategy_admission",
            "phase0.research.admission.strategy_scope",
            [
                ("_force_strategy_set_enabled_for_admission", "_force_strategy_set_enabled_for_admission"),
                ("_resolve_strategy_scope", "_resolve_strategy_scope"),
            ],
        ),
        (
            "phase0.strategy_admission",
            "phase0.research.admission.gate",
            [
                ("_overfit_blocks_admission", "overfit_blocks_admission"),
                ("_resolve_admission_gate", "resolve_admission_gate"),
                ("_resolve_diagnostic_suites", "resolve_diagnostic_suites"),
            ],
        ),
        (
            "phase0.strategy_admission",
            "phase0.research.admission.review",
            [
                ("_admission_action", "admission_action"),
                ("_build_constraint_review", "build_constraint_review"),
                ("_build_window_matrix", "build_window_matrix"),
                ("_price_adjustment_fail_window_count", "price_adjustment_fail_window_count"),
            ],
        ),
    ],
)
def test_strategy_admission_helpers_export_split_modules(
    legacy_module_name: str,
    new_module_name: str,
    symbol_pairs: list[tuple[str, str]],
) -> None:
    legacy_module = import_module(legacy_module_name)
    new_module = import_module(new_module_name)

    for symbol, new_symbol in symbol_pairs:
        assert getattr(legacy_module, symbol) is getattr(new_module, new_symbol)
