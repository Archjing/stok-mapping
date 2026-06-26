from __future__ import annotations

import phase0.strategy_missing_core_audit as legacy_missing_core_audit
from phase0.research.core_coverage import MissingCoreAuditResult, run_missing_core_audit as new_missing_core_runner
from phase0.research.core_coverage import missing_core_audit
from phase0.research.core_coverage.missing_core_audit import MissingCoreAuditResult as NewMissingCoreResult
from phase0.research.core_coverage.missing_core_audit import run_missing_core_audit
from phase0.strategy_missing_core_audit import run_missing_core_audit as legacy_missing_core_runner


def test_legacy_strategy_missing_core_audit_import_aliases_new_module() -> None:
    assert legacy_missing_core_audit is missing_core_audit
    assert legacy_missing_core_runner is run_missing_core_audit
    assert new_missing_core_runner is run_missing_core_audit
    assert MissingCoreAuditResult is NewMissingCoreResult
