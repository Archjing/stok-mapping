from __future__ import annotations

import phase0.strategy_participation_overlay as legacy_overlay
import phase0.strategy_participation_path_audit as legacy_path_audit
from phase0.research.participation import (
    StrategyParticipationOverlayResult,
    StrategyParticipationPathAuditResult,
    run_strategy_participation_overlay as new_overlay_runner,
    run_strategy_participation_path_audit as new_path_audit_runner,
)
from phase0.research.participation import overlay, path_audit
from phase0.research.participation.overlay import StrategyParticipationOverlayResult as NewOverlayResult
from phase0.research.participation.overlay import _overlay_daily_rows
from phase0.research.participation.overlay import run_strategy_participation_overlay
from phase0.research.participation.path_audit import StrategyParticipationPathAuditResult as NewPathAuditResult
from phase0.research.participation.path_audit import run_strategy_participation_path_audit
from phase0.strategy_participation_overlay import _overlay_daily_rows as legacy_overlay_daily_rows
from phase0.strategy_participation_overlay import run_strategy_participation_overlay as legacy_overlay_runner
from phase0.strategy_participation_path_audit import run_strategy_participation_path_audit as legacy_path_audit_runner


def test_legacy_strategy_participation_imports_alias_new_modules() -> None:
    assert legacy_overlay is overlay
    assert legacy_path_audit is path_audit
    assert legacy_overlay_runner is run_strategy_participation_overlay
    assert legacy_path_audit_runner is run_strategy_participation_path_audit
    assert legacy_overlay_daily_rows is _overlay_daily_rows
    assert new_overlay_runner is run_strategy_participation_overlay
    assert new_path_audit_runner is run_strategy_participation_path_audit
    assert StrategyParticipationOverlayResult is NewOverlayResult
    assert StrategyParticipationPathAuditResult is NewPathAuditResult
