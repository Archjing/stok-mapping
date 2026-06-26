from __future__ import annotations

import pandas as pd
import phase0.strategy_holdings_exposure as legacy_holdings_exposure
from phase0.research.holdings import StrategyHoldingsExposureResult, run_strategy_holdings_exposure as new_holdings_runner
from phase0.research.holdings import exposure
from phase0.research.holdings.exposure import StrategyHoldingsExposureResult as NewHoldingsResult
from phase0.research.holdings.exposure import _coverage_summary, _holding_rows_from_signal
from phase0.research.holdings.exposure import run_strategy_holdings_exposure
from phase0.strategy_holdings_exposure import _coverage_summary as legacy_coverage_summary
from phase0.strategy_holdings_exposure import _holding_rows_from_signal as legacy_holding_rows_from_signal
from phase0.strategy_holdings_exposure import run_strategy_holdings_exposure as legacy_holdings_runner


def test_legacy_strategy_holdings_exposure_import_aliases_new_module() -> None:
    assert legacy_holdings_exposure is exposure
    assert legacy_holdings_runner is run_strategy_holdings_exposure
    assert legacy_coverage_summary is _coverage_summary
    assert legacy_holding_rows_from_signal is _holding_rows_from_signal
    assert new_holdings_runner is run_strategy_holdings_exposure
    assert StrategyHoldingsExposureResult is NewHoldingsResult


def test_legacy_strategy_holdings_exposure_monkeypatch_hits_new_module(monkeypatch) -> None:
    def fake_load_index_daily(symbol, start, end):
        return pd.DataFrame(
            [
                {"date": "2024-04-01", "close": 100.0},
                {"date": "2024-04-02", "close": 101.0},
            ]
        )

    monkeypatch.setattr("phase0.strategy_holdings_exposure.load_index_daily_from_local_history", fake_load_index_daily)

    assert (
        exposure._benchmark_price_status(
            "SH.000300",
            pd.DataFrame({"date": [pd.Timestamp("2024-04-01"), pd.Timestamp("2024-04-02")]}),
        )
        == "available"
    )
