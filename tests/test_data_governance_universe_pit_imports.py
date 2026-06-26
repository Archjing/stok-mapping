from __future__ import annotations

import scripts.audit_universe_pit as legacy_universe_pit
from phase0.data_governance import universe_pit
from phase0.data_governance.universe_pit import audit_universe_pit


def test_universe_pit_new_imports_are_available() -> None:
    assert callable(audit_universe_pit)


def test_legacy_universe_pit_script_aliases_data_governance_module() -> None:
    assert legacy_universe_pit is universe_pit
    assert legacy_universe_pit.audit_universe_pit is audit_universe_pit
