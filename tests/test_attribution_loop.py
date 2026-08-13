"""Tests for the failure-attribution closed loop."""
from __future__ import annotations

import pandas as pd

from quant.research.diagnostics.attribution_loop import (
    build_repair_hypotheses,
    build_verification_plan,
    run_attribution_loop,
)


def _context_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "strategy_id": ["quality_low_turnover_monthly_v1"] * 5,
        "walk_forward_preset": ["baseline_2y_1y_5fold"] * 5,
        "fold": [1, 2, 3, 4, 5],
        "valid_start": ["2023-01-01", "2024-01-01", "2024-04-01", "2025-04-01", "2025-04-01"],
        "valid_end": ["2023-12-31", "2024-12-31", "2025-03-31", "2026-03-31", "2026-03-31"],
        "primary_fold_failure": ["relative_failure_benchmark_strong"] * 5,
        "market_context_label": [
            "relative_lag_in_strong_benchmark_context",
            "risk_context_pressure",
            "risk_context_pressure",
            "clean_positive_context",
            "benchmark_context_unavailable",
        ],
    })


def test_build_repair_hypotheses_expands_each_label() -> None:
    hypotheses = build_repair_hypotheses(_context_frame())
    assert not hypotheses.empty
    # relative lag -> 1 hypothesis; risk pressure -> 2; control -> 1; missing -> 1
    assert set(hypotheses["hypothesis_code"]) >= {
        "H-relative-lag", "H-risk-scaling", "H-trend-gate",
        "H-control-fold", "H-context-data-gap",
    }
    # P0 hypotheses come first
    priorities = hypotheses["priority"].tolist()
    assert priorities == sorted(priorities, key=lambda p: {"P0": 0, "P1": 1, "P2": 2}[p])


def test_verification_plan_upgrades_repeated_hypothesis_to_proven() -> None:
    hypotheses = build_repair_hypotheses(_context_frame())
    plan = build_verification_plan(hypotheses)
    # risk_context_pressure appears in folds 2 and 3 -> H-risk-scaling proven (>=2 folds)
    risk_row = plan[(plan["hypothesis_code"] == "H-risk-scaling")]
    assert len(risk_row) == 1
    assert risk_row.iloc[0]["distinct_folds"] == 2
    assert risk_row.iloc[0]["evidence_class"] == "proven"
    # H-relative-lag appears once -> weak
    lag_row = plan[(plan["hypothesis_code"] == "H-relative-lag")]
    assert lag_row.iloc[0]["evidence_class"] == "weak"


def test_attribution_loop_writes_csvs(tmp_path) -> None:
    context = _context_frame()
    context_path = tmp_path / "strategy_market_context_diagnostic.csv"
    context.to_csv(context_path, index=False)
    hypotheses, plan, hypo_path, plan_path = run_attribution_loop(market_context_csv=context_path)
    assert hypo_path.exists() and plan_path.exists()
    assert len(hypotheses) > 0
    assert len(plan) > 0
    # Verification plan ranks P0 before P1 before P2.
    priorities = plan["priority"].tolist()
    assert priorities == sorted(priorities, key=lambda p: {"P0": 0, "P1": 1, "P2": 2}[p])


def test_empty_context_is_safe() -> None:
    empty = pd.DataFrame(columns=["market_context_label"])
    hypotheses = build_repair_hypotheses(empty)
    plan = build_verification_plan(hypotheses)
    assert hypotheses.empty and plan.empty
