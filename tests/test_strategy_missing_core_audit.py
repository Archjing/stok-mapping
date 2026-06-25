from __future__ import annotations

import pandas as pd

from phase0.strategy_missing_core_audit import _classify_reason, _symbol_summary


def test_missing_core_classification_distinguishes_universe_stages() -> None:
    base = {
        "in_snapshot": True,
        "in_filtered": False,
        "in_scored": False,
        "in_selected_before_limit": False,
        "in_universe": False,
        "missing_days": 2,
        "snapshot_bfq_rows": 20,
        "snapshot_basic_rows": 20,
        "valid_bfq_rows": 20,
        "valid_adj_factor_rows": 20,
        "missing_dates_present_in_valid_bfq": 2,
        "missing_dates_present_in_valid_adj": 2,
        "db_daily_rows": 10,
        "db_basic_rows": 10,
        "db_adj_rows": 10,
    }

    assert _classify_reason(**base) == "filtered_out_before_universe_selection"
    assert _classify_reason(**{**base, "in_filtered": True}) == "ranked_out_or_balanced_out_of_pit_universe"
    assert _classify_reason(**{**base, "in_selected_before_limit": True}) == "beyond_walk_forward_limit"
    assert _classify_reason(**{**base, "in_universe": True}) == "universe_member_but_panel_missing"
    assert _classify_reason(**{**base, "in_universe": True, "valid_bfq_rows": 0}) == "universe_member_with_valid_window_data_gap"


def test_missing_core_classification_reports_database_gaps() -> None:
    base = {
        "in_snapshot": False,
        "in_filtered": False,
        "in_scored": False,
        "in_selected_before_limit": False,
        "in_universe": False,
        "missing_days": 2,
        "snapshot_bfq_rows": 20,
        "snapshot_basic_rows": 20,
        "valid_bfq_rows": 20,
        "valid_adj_factor_rows": 20,
        "missing_dates_present_in_valid_bfq": 2,
        "missing_dates_present_in_valid_adj": 2,
        "db_daily_rows": 10,
        "db_basic_rows": 10,
        "db_adj_rows": 10,
    }

    assert _classify_reason(**base) == "available_in_db_but_absent_from_pit_snapshot"
    assert _classify_reason(**{**base, "snapshot_bfq_rows": 0}) == "snapshot_window_price_gap"
    assert _classify_reason(**{**base, "snapshot_basic_rows": 0}) == "snapshot_window_basic_gap"
    assert _classify_reason(**{**base, "db_daily_rows": 0}) == "missing_daily_history"
    assert _classify_reason(**{**base, "db_basic_rows": 0}) == "missing_daily_basic"
    assert _classify_reason(**{**base, "db_adj_rows": 0}) == "missing_adjustment_factor"


def test_symbol_summary_preserves_total_missing_weight_order() -> None:
    events = pd.DataFrame(
        [
            {
                "symbol": "B",
                "name": "Beta",
                "industry": "Bank",
                "fold": 1,
                "missing_days": 2,
                "avg_rank": 10.0,
                "min_rank": 8.0,
                "avg_weight": 0.01,
                "total_missing_weight": 0.02,
                "in_pit_snapshot": True,
                "in_pit_filtered": True,
                "in_pit_selected_before_limit": False,
                "in_pit_universe": False,
                "missing_dates_present_in_valid_bfq": 0,
                "missing_dates_present_in_valid_adj": 0,
                "snapshot_bfq_rows": 20,
                "snapshot_basic_rows": 20,
                "valid_bfq_rows": 20,
                "valid_adj_factor_rows": 20,
                "db_daily_rows": 100,
                "db_daily_basic_rows": 90,
                "db_adj_factor_rows": 90,
                "classification": "ranked_out_or_balanced_out_of_pit_universe",
            },
            {
                "symbol": "A",
                "name": "Alpha",
                "industry": "Tech",
                "fold": 1,
                "missing_days": 1,
                "avg_rank": 3.0,
                "min_rank": 3.0,
                "avg_weight": 0.05,
                "total_missing_weight": 0.05,
                "in_pit_snapshot": False,
                "in_pit_filtered": False,
                "in_pit_selected_before_limit": False,
                "in_pit_universe": False,
                "missing_dates_present_in_valid_bfq": 0,
                "missing_dates_present_in_valid_adj": 0,
                "snapshot_bfq_rows": 20,
                "snapshot_basic_rows": 20,
                "valid_bfq_rows": 20,
                "valid_adj_factor_rows": 20,
                "db_daily_rows": 100,
                "db_daily_basic_rows": 90,
                "db_adj_factor_rows": 90,
                "classification": "available_in_db_but_absent_from_pit_snapshot",
            },
        ]
    )

    out = _symbol_summary(events, pd.DataFrame())

    assert out["symbol"].tolist() == ["A", "B"]
    assert out.loc[0, "total_missing_weight"] == 0.05
