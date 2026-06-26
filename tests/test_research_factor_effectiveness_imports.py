from __future__ import annotations

import phase0.factor_effectiveness as legacy_factor_effectiveness
import phase0.research.diagnostics.factor_effectiveness as research_factor_effectiveness


def test_factor_effectiveness_legacy_import_aliases_research_diagnostic_module() -> None:
    assert legacy_factor_effectiveness is research_factor_effectiveness
    assert (
        legacy_factor_effectiveness.FactorEffectivenessResult
        is research_factor_effectiveness.FactorEffectivenessResult
    )
    assert legacy_factor_effectiveness.FactorSpec is research_factor_effectiveness.FactorSpec
    assert legacy_factor_effectiveness.FACTOR_SPECS is research_factor_effectiveness.FACTOR_SPECS
    assert (
        legacy_factor_effectiveness.run_factor_effectiveness_report
        is research_factor_effectiveness.run_factor_effectiveness_report
    )
