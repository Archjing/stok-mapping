from __future__ import annotations

import phase0.overfit as legacy_overfit
import phase0.research.diagnostics.overfit as research_overfit


def test_overfit_legacy_import_aliases_research_diagnostic_module() -> None:
    assert legacy_overfit is research_overfit
    assert legacy_overfit.OverfitDiagnosticResult is research_overfit.OverfitDiagnosticResult
    assert legacy_overfit.run_overfit_diagnostic is research_overfit.run_overfit_diagnostic
    assert legacy_overfit._metrics is research_overfit._metrics
    assert legacy_overfit._score is research_overfit._score
