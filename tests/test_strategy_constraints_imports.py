from __future__ import annotations

import phase0.strategy_constraints as legacy_constraints
from phase0.strategies import constraints
from phase0.strategies.constraints import ConstraintEngineResult, apply_strategy_constraints
from phase0.strategies.constraints import _optional_int
from phase0.strategy_constraints import ConstraintEngineResult as LegacyConstraintEngineResult
from phase0.strategy_constraints import apply_strategy_constraints as legacy_apply_strategy_constraints
from phase0.strategy_constraints import _optional_int as legacy_optional_int


def test_legacy_strategy_constraints_import_aliases_domain_module() -> None:
    assert legacy_constraints is constraints
    assert legacy_apply_strategy_constraints is apply_strategy_constraints
    assert LegacyConstraintEngineResult is ConstraintEngineResult
    assert legacy_optional_int is _optional_int


def test_legacy_strategy_constraints_monkeypatch_hits_domain_module(monkeypatch) -> None:
    monkeypatch.setattr("phase0.strategy_constraints._optional_int", lambda value: 42)

    assert constraints._optional_int("ignored") == 42
