from __future__ import annotations

import phase0.adjustment_backfill as legacy_adjustment
import phase0.daily_basic_backfill as legacy_daily_basic
import phase0.tushare_history_backfill as legacy_tushare_history
from phase0.data_governance.backfills import adjustment, daily_basic, tushare_history
from phase0.data_governance.backfills.adjustment import AdjustmentBackfillResult, backfill_adjustment_factors_from_config
from phase0.data_governance.backfills.daily_basic import DailyBasicBackfillResult, backfill_daily_basic_from_config
from phase0.data_governance.backfills.tushare_history import (
    TushareFinancialBackfillResult,
    TushareHistoryBackfillResult,
    backfill_tushare_financials_from_config,
    backfill_tushare_history_from_config,
)


def test_backfill_new_imports_are_available() -> None:
    assert DailyBasicBackfillResult.__name__ == "DailyBasicBackfillResult"
    assert AdjustmentBackfillResult.__name__ == "AdjustmentBackfillResult"
    assert TushareHistoryBackfillResult.__name__ == "TushareHistoryBackfillResult"
    assert TushareFinancialBackfillResult.__name__ == "TushareFinancialBackfillResult"
    assert callable(backfill_daily_basic_from_config)
    assert callable(backfill_adjustment_factors_from_config)
    assert callable(backfill_tushare_history_from_config)
    assert callable(backfill_tushare_financials_from_config)


def test_legacy_backfill_imports_alias_new_modules() -> None:
    assert legacy_daily_basic is daily_basic
    assert legacy_adjustment is adjustment
    assert legacy_tushare_history is tushare_history
    assert legacy_daily_basic.backfill_daily_basic_from_config is backfill_daily_basic_from_config
    assert legacy_adjustment.backfill_adjustment_factors_from_config is backfill_adjustment_factors_from_config
    assert legacy_tushare_history.backfill_tushare_history_from_config is backfill_tushare_history_from_config
    assert legacy_tushare_history.backfill_tushare_financials_from_config is backfill_tushare_financials_from_config
