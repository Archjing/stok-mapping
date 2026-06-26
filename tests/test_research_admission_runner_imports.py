from phase0.research.admission import runner
from phase0.research.admission.runner import StrategyAdmissionResult, run_strategy_admission
from phase0.strategy_admission import (
    StrategyAdmissionResult as legacy_strategy_admission_result,
)
from phase0.strategy_admission import (
    run_strategy_admission as legacy_run_strategy_admission,
)


def test_admission_runner_is_packaged_under_research_admission() -> None:
    assert runner.run_strategy_admission is run_strategy_admission
    assert runner.StrategyAdmissionResult is StrategyAdmissionResult


def test_legacy_strategy_admission_exports_runner_for_compatibility() -> None:
    assert legacy_run_strategy_admission is run_strategy_admission
    assert legacy_strategy_admission_result is StrategyAdmissionResult
