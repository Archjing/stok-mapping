from __future__ import annotations

import pandas as pd
import pytest

from phase0.research.core_coverage import core_reachability
from phase0.research.holdings import exposure


def test_legacy_strategy_holdings_exposure_monkeypatch_hits_new_module(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_legacy_strategy_core_reachability_monkeypatch_hits_new_module(monkeypatch: pytest.MonkeyPatch) -> None:
    panel = pd.DataFrame(
        [
            {
                "date": "2024-01-10",
                "symbol": "A",
                "close": 10.0,
                "amount": 1000.0,
                "amount_ratio20": 1.2,
                "industry": "Bank",
            }
        ]
    )
    benchmark_weights = pd.DataFrame(
        [
            {"trade_date_dt": pd.Timestamp("2024-01-09"), "symbol": "A", "benchmark_weight": 0.40, "benchmark_rank": 1},
            {"trade_date_dt": pd.Timestamp("2024-01-09"), "symbol": "B", "benchmark_weight": 0.35, "benchmark_rank": 2},
        ]
    )

    def fake_load_daily(symbol, start, end, price_adjustment=None, as_of_date=None):
        return pd.DataFrame(
            [
                {
                    "date": "2024-01-10",
                    "close": 20.5,
                    "amount": 2000.0,
                    "amount_ratio20": 1.1,
                }
            ]
        )

    monkeypatch.setattr("phase0.strategy_core_reachability.load_daily_from_local_history", fake_load_daily)
    monkeypatch.setattr("phase0.strategy_core_reachability._lookup_stock_industry", lambda symbol: "Tech")

    seeded = core_reachability._seed_benchmark_panel(
        panel=panel,
        candidate_row=pd.Series({"valid_start": "2024-01-10", "valid_end": "2024-01-10"}),
        benchmark_weights=benchmark_weights,
        years=1,
        strategy_cfg={"price_adjustment": "qfq_asof"},
        seed_benchmark_core=True,
        seed_top_n=2,
        seed_core_top_n=2,
        seed_core_cumulative_weight=1.0,
        weight_date_lag_days=1,
    )

    added = seeded[seeded["symbol"].eq("B")].iloc[0]
    assert bool(added["benchmark_seeded"]) is True
    assert added["industry"] == "Tech"
