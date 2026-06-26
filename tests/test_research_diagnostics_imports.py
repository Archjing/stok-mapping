from __future__ import annotations

import phase0.strategy_exposure_diagnostic as legacy_exposure
import phase0.strategy_filter_diagnostic as legacy_filter
import phase0.strategy_market_context as legacy_market_context
from phase0.strategy_filter_diagnostic import _daily_filter_rows, _fold_summary_row
from phase0.research.diagnostics import exposure, filter, market_context


def test_legacy_strategy_diagnostic_imports_alias_new_modules() -> None:
    assert legacy_market_context is market_context
    assert legacy_exposure is exposure
    assert legacy_filter is filter
    assert legacy_market_context.run_strategy_market_context is market_context.run_strategy_market_context
    assert legacy_exposure.run_strategy_exposure_diagnostic is exposure.run_strategy_exposure_diagnostic
    assert legacy_filter.run_strategy_filter_diagnostic is filter.run_strategy_filter_diagnostic
    assert _daily_filter_rows is filter._daily_filter_rows
    assert _fold_summary_row is filter._fold_summary_row
