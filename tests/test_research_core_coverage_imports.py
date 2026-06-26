from __future__ import annotations

import pandas as pd
import phase0
import phase0.strategy_core_reachability as legacy_core_reachability
import phase0.strategy_missing_core_audit as legacy_missing_core_audit
import pytest
from phase0.research.core_coverage import (
    MissingCoreAuditResult,
    StrategyCoreReachabilityResult,
    run_missing_core_audit as new_missing_core_runner,
    run_strategy_core_reachability_diagnostic as new_core_reachability_runner,
)
from phase0.research.core_coverage import core_reachability, missing_core_audit
from phase0.research.core_coverage.core_reachability import StrategyCoreReachabilityResult as NewCoreReachabilityResult
from phase0.research.core_coverage.core_reachability import (
    _diagnose_fold,
    _seed_benchmark_panel,
    run_strategy_core_reachability_diagnostic,
)
from phase0.research.core_coverage.missing_core_audit import MissingCoreAuditResult as NewMissingCoreResult
from phase0.research.core_coverage.missing_core_audit import run_missing_core_audit
from phase0.strategy_core_reachability import (
    _diagnose_fold as legacy_diagnose_fold,
    _seed_benchmark_panel as legacy_seed_benchmark_panel,
    run_strategy_core_reachability_diagnostic as legacy_core_reachability_runner,
)
from phase0.strategy_missing_core_audit import run_missing_core_audit as legacy_missing_core_runner


def test_legacy_strategy_core_reachability_import_aliases_new_module() -> None:
    assert legacy_core_reachability is core_reachability
    assert phase0.strategy_core_reachability is core_reachability
    assert legacy_core_reachability_runner is run_strategy_core_reachability_diagnostic
    assert legacy_diagnose_fold is _diagnose_fold
    assert legacy_seed_benchmark_panel is _seed_benchmark_panel
    assert new_core_reachability_runner is run_strategy_core_reachability_diagnostic
    assert StrategyCoreReachabilityResult is NewCoreReachabilityResult


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


def test_legacy_strategy_missing_core_audit_import_aliases_new_module() -> None:
    assert legacy_missing_core_audit is missing_core_audit
    assert legacy_missing_core_runner is run_missing_core_audit
    assert new_missing_core_runner is run_missing_core_audit
    assert MissingCoreAuditResult is NewMissingCoreResult
