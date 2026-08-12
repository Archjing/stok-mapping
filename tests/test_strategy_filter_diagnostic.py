from __future__ import annotations

import pandas as pd
import pytest

from quant.research.diagnostics.filter import _daily_filter_rows, _fold_summary_row


def test_filter_diagnostic_marks_rare_strong_context_as_bottleneck() -> None:
    daily = pd.DataFrame(
        [
            {
                "date": f"2024-01-{day:02d}",
                "strong_index_context": day == 2,
                "hard_base_count": 8,
                "hard_base_share": 0.08,
                "eligible_for_new_buy_count": 4 if day == 2 else 0,
                "eligible_for_new_buy_share": 0.04 if day == 2 else 0.0,
            }
            for day in range(1, 29)
        ]
    )
    candidate = pd.Series(
        {
            "strategy_id": "strong_index_participation_v1",
            "walk_forward_preset": "baseline",
            "fold": 1,
            "valid_start": "2024-01-01",
            "valid_end": "2024-01-02",
            "trades": 0,
            "avg_live_holdings": 0,
        }
    )

    row = _fold_summary_row(daily, candidate)

    assert row["main_bottleneck"] == "strong_index_context_too_rare"
    assert "mostly stayed in cash" in row["interpretation"]


def test_filter_diagnostic_does_not_blame_empty_exposure_when_strategy_traded() -> None:
    daily = pd.DataFrame(
        [
            {
                "date": "2025-09-01",
                "strong_index_context": True,
                "hard_base_count": 35,
                "hard_base_share": 0.29,
                "eligible_for_new_buy_count": 35,
                "eligible_for_new_buy_share": 0.29,
            },
            {
                "date": "2025-09-02",
                "strong_index_context": True,
                "hard_base_count": 28,
                "hard_base_share": 0.23,
                "eligible_for_new_buy_count": 28,
                "eligible_for_new_buy_share": 0.23,
            },
        ]
    )
    candidate = pd.Series(
        {
            "strategy_id": "strong_index_participation_v1",
            "walk_forward_preset": "baseline",
            "fold": 5,
            "valid_start": "2025-04-01",
            "valid_end": "2026-03-31",
            "trades": 6,
            "avg_live_holdings": 5,
        }
    )

    row = _fold_summary_row(daily, candidate)

    assert row["main_bottleneck"] == "eligible_but_construction_or_hold_rules_limit_trades"
    assert "return quality" in row["interpretation"]


def test_filter_diagnostic_counts_dynamic_review_days() -> None:
    daily = pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "strong_index_context": False,
                "review_day": True,
                "review_reason": "fixed_rebalance",
                "hard_base_count": 8,
                "hard_base_share": 0.08,
                "eligible_for_new_buy_count": 0,
                "eligible_for_new_buy_share": 0.0,
            },
            {
                "date": "2024-01-02",
                "strong_index_context": True,
                "review_day": True,
                "review_reason": "dynamic_strong_context_on",
                "hard_base_count": 8,
                "hard_base_share": 0.08,
                "eligible_for_new_buy_count": 4,
                "eligible_for_new_buy_share": 0.04,
            },
            {
                "date": "2024-01-03",
                "strong_index_context": True,
                "review_day": False,
                "review_reason": "",
                "hard_base_count": 8,
                "hard_base_share": 0.08,
                "eligible_for_new_buy_count": 4,
                "eligible_for_new_buy_share": 0.04,
            },
        ]
    )
    candidate = pd.Series(
        {
            "strategy_id": "strong_index_participation_dynamic_trigger_v1",
            "walk_forward_preset": "baseline",
            "fold": 1,
            "valid_start": "2024-01-01",
            "valid_end": "2024-01-03",
            "trades": 1,
            "avg_live_holdings": 4,
        }
    )

    row = _fold_summary_row(daily, candidate)

    assert row["rebalance_day_count"] == 2
    assert row["fixed_rebalance_day_count"] == 1
    assert row["dynamic_review_day_count"] == 1
    assert row["strong_rebalance_day_count"] == 1
    assert row["candidate_rebalance_day_count"] == 1


def test_filter_diagnostic_reports_benchmark_weight_reachability() -> None:
    panel = pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "symbol": "A",
                "close": 12.0,
                "mom20": 0.10,
                "mom60": 0.20,
                "ma60": 10.0,
                "amount_ratio20": 1.5,
                "upper_shadow_pct": 0.5,
                "vol20": 0.10,
                "ret": 0.01,
                "industry": "Bank",
                "benchmark_weight": 0.30,
                "strong_index_context": True,
            },
            {
                "date": "2024-01-01",
                "symbol": "B",
                "close": 9.0,
                "mom20": 0.10,
                "mom60": 0.20,
                "ma60": 10.0,
                "amount_ratio20": 1.5,
                "upper_shadow_pct": 0.5,
                "vol20": 0.20,
                "ret": 0.01,
                "industry": "Tech",
                "benchmark_weight": 0.20,
                "strong_index_context": True,
            },
            {
                "date": "2024-01-02",
                "symbol": "A",
                "close": 12.0,
                "mom20": 0.10,
                "mom60": 0.20,
                "ma60": 10.0,
                "amount_ratio20": 1.5,
                "upper_shadow_pct": 0.5,
                "vol20": 0.10,
                "ret": 0.01,
                "industry": "Bank",
                "benchmark_weight": 0.30,
                "strong_index_context": False,
            },
        ]
    )
    candidate = pd.Series(
        {
            "strategy_id": "strong_market_effective_participation_v1",
            "walk_forward_preset": "baseline",
            "fold": 1,
            "valid_start": "2024-01-01",
            "valid_end": "2024-01-02",
            "trades": 1,
            "avg_live_holdings": 1,
        }
    )

    daily = _daily_filter_rows(
        panel,
        params={
            "amount_ratio_min": 1.0,
            "amount_ratio_max": 4.0,
            "upper_shadow_max": 1.3,
            "vol_cross_section_quantile": 1.0,
            "rebalance_days": 20,
        },
        strategy_id="strong_market_effective_participation_v1",
        preset_name="baseline",
        fold=1,
        candidate_row=candidate,
    )
    first_day = daily[daily["date"].eq("2024-01-01")].iloc[0]
    second_day = daily[daily["date"].eq("2024-01-02")].iloc[0]

    assert first_day["benchmark_member_count"] == 2
    assert first_day["hard_filter_benchmark_member_count"] == 1
    assert first_day["eligible_benchmark_member_count"] == 1
    assert first_day["eligible_benchmark_weight_sum"] == pytest.approx(0.30)
    assert first_day["panel_top20_eligible_benchmark_weight_sum"] == pytest.approx(0.30)
    assert second_day["eligible_benchmark_member_count"] == 0
    assert second_day["eligible_benchmark_weight_sum"] == pytest.approx(0.0)

    row = _fold_summary_row(daily, candidate)

    assert row["avg_benchmark_members"] == pytest.approx(1.5)
    assert row["avg_eligible_benchmark_members_on_strong_days"] == pytest.approx(1.0)
    assert row["avg_eligible_benchmark_weight_on_strong_days"] == pytest.approx(0.30)
    assert row["avg_panel_top20_eligible_benchmark_weight_on_strong_days"] == pytest.approx(0.30)


def test_filter_diagnostic_uses_daily_review_for_effective_participation_strategy() -> None:
    panel = pd.DataFrame(
        [
            {
                "date": f"2024-01-0{day}",
                "symbol": "A",
                "close": 12.0,
                "mom20": 0.10,
                "mom60": 0.20,
                "ma60": 10.0,
                "amount_ratio20": 1.5,
                "upper_shadow_pct": 0.5,
                "vol20": 0.10,
                "ret": 0.01,
                "industry": "Bank",
                "benchmark_weight": 0.30,
                "strong_index_context": day >= 2,
            }
            for day in range(1, 4)
        ]
    )
    candidate = pd.Series(
        {
            "strategy_id": "strong_market_effective_participation_v1",
            "walk_forward_preset": "baseline",
            "fold": 1,
            "valid_start": "2024-01-01",
            "valid_end": "2024-01-03",
            "trades": 1,
            "avg_live_holdings": 1,
        }
    )

    daily = _daily_filter_rows(
        panel,
        params={
            "amount_ratio_min": 1.0,
            "amount_ratio_max": 4.0,
            "upper_shadow_max": 1.3,
            "vol_cross_section_quantile": 1.0,
            "rebalance_days": 20,
        },
        strategy_id="strong_market_effective_participation_v1",
        preset_name="baseline",
        fold=1,
        candidate_row=candidate,
    )
    row = _fold_summary_row(daily, candidate)

    assert daily["review_day"].all()
    assert row["rebalance_day_count"] == 3
    assert row["strong_rebalance_day_count"] == 2
    assert row["candidate_rebalance_day_count"] == 2
