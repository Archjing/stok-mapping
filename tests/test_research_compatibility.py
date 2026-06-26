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
