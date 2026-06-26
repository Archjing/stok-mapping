from __future__ import annotations

import phase0.strategy_alpha_source_audit as legacy_alpha_source_module
import phase0.strategy_csi300_attribution as legacy_csi300_module
import phase0.strategy_fold_attribution as legacy_fold_module
from phase0.research.attribution import (
    StrategyAlphaSourceAuditResult,
    StrategyCsi300AttributionResult,
    StrategyFoldAttributionResult,
    run_strategy_alpha_source_audit as new_alpha_source_runner,
    run_strategy_csi300_attribution as new_csi300_runner,
    run_strategy_fold_attribution as new_fold_runner,
)
from phase0.research.attribution import alpha_source, csi300, fold
from phase0.research.attribution.alpha_source import StrategyAlphaSourceAuditResult as NewAlphaSourceResult
from phase0.research.attribution.alpha_source import run_strategy_alpha_source_audit
from phase0.research.attribution.csi300 import DEFAULT_BENCHMARK
from phase0.research.attribution.csi300 import StrategyCsi300AttributionResult as NewCsi300Result
from phase0.research.attribution.csi300 import run_strategy_csi300_attribution
from phase0.research.attribution.fold import StrategyFoldAttributionResult as NewFoldResult
from phase0.research.attribution.fold import run_strategy_fold_attribution
from phase0.strategy_alpha_source_audit import run_strategy_alpha_source_audit as legacy_alpha_source_runner
from phase0.strategy_csi300_attribution import DEFAULT_BENCHMARK as legacy_default_benchmark
from phase0.strategy_csi300_attribution import run_strategy_csi300_attribution as legacy_csi300_runner
from phase0.strategy_fold_attribution import run_strategy_fold_attribution as legacy_fold_runner


def test_legacy_strategy_attribution_imports_reexport_new_runners() -> None:
    assert legacy_alpha_source_module is alpha_source
    assert legacy_csi300_module is csi300
    assert legacy_fold_module is fold
    assert legacy_alpha_source_runner is run_strategy_alpha_source_audit
    assert legacy_csi300_runner is run_strategy_csi300_attribution
    assert legacy_fold_runner is run_strategy_fold_attribution
    assert new_alpha_source_runner is run_strategy_alpha_source_audit
    assert new_csi300_runner is run_strategy_csi300_attribution
    assert new_fold_runner is run_strategy_fold_attribution
    assert StrategyAlphaSourceAuditResult is NewAlphaSourceResult
    assert StrategyCsi300AttributionResult is NewCsi300Result
    assert StrategyFoldAttributionResult is NewFoldResult
    assert legacy_default_benchmark is DEFAULT_BENCHMARK
