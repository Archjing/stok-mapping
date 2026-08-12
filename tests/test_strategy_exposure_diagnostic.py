from __future__ import annotations

import pandas as pd

from quant.research.diagnostics.exposure import run_strategy_exposure_diagnostic


def test_strategy_exposure_diagnostic_merges_existing_artifacts_and_writes_reports(tmp_path) -> None:
    folds_path = tmp_path / "strategy_admission_candidate_folds.csv"
    context_path = tmp_path / "strategy_market_context_diagnostic.csv"
    universe_path = tmp_path / "local_factor_universe.csv"
    output_dir = tmp_path / "out"

    pd.DataFrame(
        [
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 4,
                "valid_start": "2024-04-01",
                "valid_end": "2025-03-31",
                "annualized_return": 0.075,
                "benchmark_annualized_return": 0.085,
                "excess_annualized_return": -0.010,
                "sharpe": 0.64,
                "turnover_annual": 2.2,
                "avg_live_holdings": 6.3,
                "trade_days": 6,
                "top_industry_avg_share": 0.13,
                "top3_industries_avg_share": 0.27,
                "industry_constraint_violation_days": 0,
                "first_target_date": "2024-04-01",
                "first_target_symbols": "['AAA', 'BBB', 'CCC']",
            },
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 2,
                "valid_start": "2022-04-01",
                "valid_end": "2023-03-31",
                "annualized_return": 0.030,
                "benchmark_annualized_return": -0.050,
                "excess_annualized_return": 0.080,
                "sharpe": 0.36,
                "turnover_annual": 1.9,
                "avg_live_holdings": 5.8,
                "trade_days": 7,
                "top_industry_avg_share": 0.09,
                "top3_industries_avg_share": 0.18,
                "industry_constraint_violation_days": 0,
                "first_target_date": "2022-04-01",
                "first_target_symbols": "['DDD']",
            },
        ]
    ).to_csv(folds_path, index=False)
    pd.DataFrame(
        [
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 4,
                "market_context_label": "relative_lag_in_strong_benchmark_context",
                "benchmark_return_bucket": "strong_up",
                "benchmark_trend_bucket": "mostly_above_trend",
                "benchmark_vol_bucket": "mixed_vol",
                "benchmark_above_trend_share": 0.75,
                "benchmark_risk_off_share": 0.40,
                "benchmark_context_annualized_return": 0.09,
                "excess_annualized_return": -0.010,
            },
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 2,
                "market_context_label": "clean_positive_context",
                "benchmark_return_bucket": "flat_or_mild_down",
                "benchmark_trend_bucket": "mostly_below_trend",
                "benchmark_vol_bucket": "mixed_vol",
                "benchmark_above_trend_share": 0.30,
                "benchmark_risk_off_share": 0.70,
                "benchmark_context_annualized_return": -0.05,
                "excess_annualized_return": 0.080,
            },
        ]
    ).to_csv(context_path, index=False)
    pd.DataFrame(
        [
            {"symbol": "AAA", "name": "A", "industry": "Bank", "as_of_date": "2026-06-23"},
            {"symbol": "BBB", "name": "B", "industry": "Bank", "as_of_date": "2026-06-23"},
            {"symbol": "CCC", "name": "C", "industry": "Tech", "as_of_date": "2026-06-23"},
            {"symbol": "DDD", "name": "D", "industry": "Health", "as_of_date": "2026-06-23"},
        ]
    ).to_csv(universe_path, index=False)

    result = run_strategy_exposure_diagnostic(
        config={"universe": {"as_of_date": "2026-06-23"}, "walk_forward": {"price_adjustment": "qfq_asof"}},
        root=tmp_path,
        config_path=tmp_path / "config.yaml",
        candidate_folds_path=folds_path,
        market_context_path=context_path,
        universe_path=universe_path,
        output_dir=output_dir,
        command="quant.cli strategy-exposure-diagnostic ...",
    )

    assert result.rows == 2
    assert result.strong_lag_rows == 1
    out = pd.read_csv(result.csv_path)
    strong = out[out["market_context_label"] == "relative_lag_in_strong_benchmark_context"].iloc[0]
    assert strong["first_target_top_industry"] == "Bank"
    assert strong["first_target_top_industry_share"] == 2 / 3
    assert strong["first_target_metadata_scope"] == "current_snapshot_not_pit"
    assert strong["first_target_metadata_as_of"] == "2026-06-23"
    assert strong["exposure_proxy_label"] == "mild_strong_benchmark_lag_proxy"
    summary = pd.read_csv(result.summary_csv_path)
    assert "relative_lag_in_strong_benchmark_context" in set(summary["market_context_label"])
    md = result.md_path.read_text(encoding="utf-8")
    assert "research-only diagnostic" in md
    assert "does not rerun backtests" in md
    assert "current universe metadata snapshot only" in md
    run_log = result.run_log_md_path.read_text(encoding="utf-8")
    assert "iteration_id: `I9`" in run_log
    assert "promotion_boundary: `research_only" in run_log
    assert "sha256=" in run_log
    assert "artifact_key_coverage: `matched=2" in run_log


def test_strategy_exposure_diagnostic_reports_missing_required_columns(tmp_path) -> None:
    folds_path = tmp_path / "bad_folds.csv"
    context_path = tmp_path / "context.csv"
    pd.DataFrame([{"strategy_id": "x"}]).to_csv(folds_path, index=False)
    pd.DataFrame(
        [
            {
                "strategy_id": "x",
                "walk_forward_preset": "baseline",
                "fold": 1,
                "market_context_label": "mixed",
                "benchmark_return_bucket": "flat",
                "benchmark_trend_bucket": "mixed",
                "benchmark_above_trend_share": 0.5,
                "excess_annualized_return": 0.0,
            }
        ]
    ).to_csv(context_path, index=False)

    try:
        run_strategy_exposure_diagnostic(
            config={},
            root=tmp_path,
            candidate_folds_path=folds_path,
            market_context_path=context_path,
        )
    except ValueError as exc:
        assert "valid_start" in str(exc)
    else:
        raise AssertionError("expected missing column validation to fail")


def test_strategy_exposure_diagnostic_fails_on_unmatched_fold_keys(tmp_path) -> None:
    folds_path = tmp_path / "strategy_admission_candidate_folds.csv"
    context_path = tmp_path / "strategy_market_context_diagnostic.csv"
    pd.DataFrame(
        [
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline",
                "fold": 1,
                "valid_start": "2024-01-01",
                "valid_end": "2024-12-31",
                "annualized_return": 0.01,
                "benchmark_annualized_return": 0.10,
                "excess_annualized_return": -0.09,
                "avg_live_holdings": 5,
                "first_target_symbols": "['AAA']",
                "top_industry_avg_share": 0.1,
                "top3_industries_avg_share": 0.2,
            }
        ]
    ).to_csv(folds_path, index=False)
    pd.DataFrame(
        [
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline",
                "fold": 2,
                "market_context_label": "relative_lag_in_strong_benchmark_context",
                "benchmark_return_bucket": "strong_up",
                "benchmark_trend_bucket": "mostly_above_trend",
                "benchmark_above_trend_share": 0.8,
                "excess_annualized_return": -0.09,
            }
        ]
    ).to_csv(context_path, index=False)

    try:
        run_strategy_exposure_diagnostic(
            config={},
            root=tmp_path,
            candidate_folds_path=folds_path,
            market_context_path=context_path,
        )
    except ValueError as exc:
        assert "keys do not match" in str(exc)
    else:
        raise AssertionError("expected unmatched fold keys to fail")
