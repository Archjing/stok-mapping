from __future__ import annotations

import phase0.strategy_admission as admission
from phase0.research.admission import gate


def test_admission_gate_helpers_are_reexported_from_runner() -> None:
    assert admission._resolve_admission_gate is gate.resolve_admission_gate
    assert admission._resolve_diagnostic_suites is gate.resolve_diagnostic_suites
    assert admission._overfit_blocks_admission is gate.overfit_blocks_admission
