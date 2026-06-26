from __future__ import annotations

import sqlite3

import pandas as pd

from phase0.research.holdings.exposure import (
    _coverage_summary,
    _daily_exposure_from_holdings,
    _ensure_optional_fold_metric_columns,
    _parse_selected_params,
    _holding_rows_from_signal,
    _industry_exposure_from_holdings,
    _summary_from_daily,
)
from phase0.strategy_admission import _force_strategy_set_enabled_for_admission


def test_holding_rows_and_daily_exposure_keep_target_and_live_weights() -> None:
    signal = pd.DataFrame(
        [
            {
                "date": "2024-04-01",
                "symbol": "AAA",
                "name": "A",
                "industry": "Bank",
                "weight_unshifted": 0.06,
                "weight": 0.00,
                "selected": 1.0,
                "rank": 1,
                "score": 0.90,
                "quality_growth_score": 0.88,
                "quality_rank_component": 0.75,
                "ret": 0.01,
                "position_ret": 0.0,
                "held_days": 0,
                "strong_index_context": True,
                "recovery_index_context": False,
                "recovery_quality_index_context": False,
                "review_day": True,
                "review_reason": "strong_context_stable_core",
                "strong_index_ret20": 0.03,
                "strong_index_ret60": 0.08,
                "strong_index_drawdown": -0.02,
            },
            {
                "date": "2024-04-02",
                "symbol": "AAA",
                "name": "A",
                "industry": "Bank",
                "weight_unshifted": 0.06,
                "weight": 0.06,
                "selected": 1.0,
                "rank": 1,
                "score": 0.91,
                "ret": 0.02,
                "position_ret": 0.0012,
                "held_days": 1,
                "strong_index_context": True,
                "recovery_index_context": False,
                "recovery_quality_index_context": False,
                "review_day": False,
                "review_reason": "strong_context_stable_core",
                "strong_index_ret20": 0.04,
                "strong_index_ret60": 0.09,
                "strong_index_drawdown": -0.01,
            },
            {
                "date": "2024-04-02",
                "symbol": "BBB",
                "name": "B",
                "industry": "Tech",
                "weight_unshifted": 0.04,
                "weight": 0.04,
                "selected": 1.0,
                "rank": 2,
                "score": 0.82,
                "ret": -0.01,
                "position_ret": -0.0004,
                "held_days": 1,
                "strong_index_context": True,
                "recovery_index_context": False,
                "recovery_quality_index_context": False,
                "review_day": False,
                "review_reason": "strong_context_stable_core",
                "strong_index_ret20": 0.04,
                "strong_index_ret60": 0.09,
                "strong_index_drawdown": -0.01,
            },
            {
                "date": "2024-04-02",
                "symbol": "CCC",
                "name": "C",
                "industry": "Health",
                "weight_unshifted": 0.00,
                "weight": 0.00,
                "selected": 0.0,
                "rank": 80,
                "score": 0.10,
                "ret": 0.00,
                "position_ret": 0.0,
                "held_days": 0,
            },
        ]
    )
    fold_row = {
        "strategy_id": "price_volume_low_turnover_v1",
        "walk_forward_preset": "baseline_2y_1y_5fold",
        "fold": 4,
        "valid_start": "2024-04-01",
        "valid_end": "2025-03-31",
        "universe_as_of_date": "2024-03-29",
    }
    context_row = {
        "market_context_label": "relative_lag_in_strong_benchmark_context",
        "benchmark_return_bucket": "strong_up",
        "benchmark_trend_bucket": "mostly_above_trend",
    }

    holdings = _holding_rows_from_signal(signal, fold_row=fold_row, context_row=context_row)

    assert list(holdings["symbol"]) == ["AAA", "AAA", "BBB"]
    assert set(holdings["market_context_label"]) == {"relative_lag_in_strong_benchmark_context"}
    assert "quality_growth_score" in holdings.columns
    assert "quality_rank_component" in holdings.columns
    assert "strong_index_context" in holdings.columns
    assert "recovery_index_context" in holdings.columns
    assert "recovery_quality_index_context" in holdings.columns
    assert "review_reason" in holdings.columns
    assert float(holdings.loc[holdings["date"] == pd.Timestamp("2024-04-02"), "live_weight"].sum()) == 0.10

    daily = _daily_exposure_from_holdings(holdings)
    day2 = daily[daily["date"] == pd.Timestamp("2024-04-02")].iloc[0]
    assert bool(day2["strong_index_context"]) is True
    assert bool(day2["recovery_index_context"]) is False
    assert bool(day2["recovery_quality_index_context"]) is False
    assert day2["review_reason"] == "strong_context_stable_core"
    assert day2["review_day_count"] == 0
    assert day2["strong_index_ret20"] == 0.04
    assert day2["live_holding_count"] == 2
    assert day2["target_holding_count"] == 2
    assert day2["live_top_industry"] == "Bank"
    assert day2["live_top_industry_share"] == 0.06
    assert day2["live_top3_industries_share"] == 0.10

    industry = _industry_exposure_from_holdings(holdings)
    day2_industries = industry[industry["date"] == pd.Timestamp("2024-04-02")]
    assert set(day2_industries["industry"]) == {"Bank", "Tech"}


def test_summary_and_coverage_make_benchmark_constituent_gap_explicit() -> None:
    daily = pd.DataFrame(
        [
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 4,
                "valid_start": "2024-04-01",
                "valid_end": "2025-03-31",
                "market_context_label": "relative_lag_in_strong_benchmark_context",
                "date": pd.Timestamp("2024-04-02"),
                "live_holding_count": 2,
                "target_holding_count": 2,
                "live_exposure": 0.10,
                "target_exposure": 0.10,
                "live_top_industry": "Bank",
                "live_top_industry_share": 0.06,
                "live_top3_industries_share": 0.10,
                "target_top_industry": "Bank",
                "target_top_industry_share": 0.06,
                "target_top3_industries_share": 0.10,
                "unknown_live_weight": 0.0,
            }
        ]
    )
    folds = pd.DataFrame(
        [
            {
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 4,
                "annualized_return": 0.075,
                "benchmark_annualized_return": 0.085,
                "excess_annualized_return": -0.010,
            }
        ]
    )

    summary = _summary_from_daily(daily, folds)

    assert summary.iloc[0]["fold_count"] == 1
    assert summary.iloc[0]["avg_excess_ann"] == -0.010
    assert summary.iloc[0]["dominant_live_top_industry"] == "Bank"
    assert "not a full CSI300 constituent attribution" in summary.iloc[0]["interpretation"]

    coverage = _coverage_summary(
        holdings_df=pd.DataFrame({"symbol": ["AAA"]}),
        daily_df=daily,
        fold_df=folds,
        audit_df=pd.DataFrame({"fold": [4]}),
        benchmark_symbol="SH.000300",
    )

    benchmark_constituents = coverage[coverage["artifact"] == "benchmark_constituents"].iloc[0]
    assert benchmark_constituents["status"] == "not_available"
    assert "local history sqlite is unavailable" in benchmark_constituents["note"]


def test_coverage_reports_available_benchmark_weights_when_asof_table_exists(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE cn_index_weights_asof (
                index_code TEXT,
                trade_date TEXT,
                symbol TEXT,
                weight REAL
            )
            """
        )
        conn.executemany(
            "INSERT INTO cn_index_weights_asof VALUES ('SH.000300', ?, ?, ?)",
            [
                ("2024-03-29", "SH.600000", 40.0),
                ("2024-03-29", "SH.600519", 30.0),
            ],
        )

    coverage = _coverage_summary(
        holdings_df=pd.DataFrame({"symbol": ["AAA"]}),
        daily_df=pd.DataFrame({"date": [pd.Timestamp("2024-04-02")]}),
        fold_df=pd.DataFrame({"fold": [4]}),
        audit_df=pd.DataFrame({"fold": [4]}),
        benchmark_symbol="SH.000300",
        local_history_db=db_path,
    )

    benchmark_constituents = coverage[coverage["artifact"] == "benchmark_constituents"].iloc[0]
    assert benchmark_constituents["status"] == "available"
    assert benchmark_constituents["rows"] == 2
    assert "cn_index_weights_asof is available" in benchmark_constituents["note"]


def test_parse_low_vol_quality_selected_params_for_replay() -> None:
    text = (
        "low_vol_low_turnover_quality@q0.6,"
        "vol_window=60,vol_q=0.5,turnover_q=0.5,mom20,"
        "buy_top=10,hold_top=20,rebalance=40d,min_hold=20d,"
        "max_w=0.1,target_vol=0.18,turnover_penalty=0.02"
    )
    strategy_cfg = {
        "local_factor": {
            "low_vol_low_turnover_quality": {
                "factor_weights": {
                    "quality": 0.25,
                    "low_volatility": 0.40,
                    "low_turnover": 0.25,
                    "medium_momentum": 0.10,
                },
                "use_xmarket_overlay": True,
            }
        },
        "constraints": {"industry": {"max_names_per_industry": 2}},
    }

    params = _parse_selected_params(text, strategy_cfg)

    assert params is not None
    assert params["quality_quantile"] == 0.6
    assert params["low_vol_window"] == 60
    assert params["momentum_window"] == 20
    assert params["buy_top_n"] == 10
    assert params["hold_top_n"] == 20
    assert params["use_xmarket_overlay"] is True
    assert params["max_names_per_industry"] == 2
    assert params["factor_weights"]["quality"] == 0.25


def test_optional_fold_metric_columns_are_backfilled_for_older_admission_outputs() -> None:
    folds = pd.DataFrame(
        [
            {
                "strategy_id": "low_vol_low_turnover_quality_v1",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 1,
                "valid_start": "2021-04-01",
                "valid_end": "2022-03-31",
                "annualized_return": -0.01,
            }
        ]
    )

    out = _ensure_optional_fold_metric_columns(folds)

    assert "benchmark_annualized_return" in out.columns
    assert "excess_annualized_return" in out.columns
    assert pd.isna(out.iloc[0]["benchmark_annualized_return"])


def test_holdings_exposure_force_enables_scoped_research_strategy() -> None:
    strategy_cfg = {"local_factor": {"strong_benchmark_recovery_leadership": {"enabled": False}}}

    _force_strategy_set_enabled_for_admission(strategy_cfg, ["strong_benchmark_recovery_leadership_v1"])

    assert strategy_cfg["local_factor"]["strong_benchmark_recovery_leadership"]["enabled"] is True
