from __future__ import annotations

import pandas as pd
from phase0.research.holdings import exposure


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
