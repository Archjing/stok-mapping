from __future__ import annotations

import pandas as pd

from phase0.strategy_failure_attribution import run_strategy_failure_attribution


def _config() -> dict:
    return {
        "walk_forward": {
            "gate": {"annualized_return_min": 0.0, "sharpe_min": 0.5, "min_positive_fold_ratio": 0.75},
            "admission": {
                "gate": {
                    "turnover_annual_mean_max": 3.0,
                    "turnover_annual_max_max": 5.0,
                    "require_parameter_stability": True,
                    "require_industry_concentration_check": True,
                    "require_factor_diagnostics": True,
                    "require_qfq_asof": True,
                }
            },
        }
    }


def test_failure_attribution_reads_existing_csvs_and_explains_main_failures(tmp_path) -> None:
    admission_dir = tmp_path / "admission"
    overfit_dir = admission_dir / "overfit_diagnostic"
    output_dir = tmp_path / "out"
    overfit_dir.mkdir(parents=True)

    pd.DataFrame(
        [
            {
                "strategy_id": "quality_low_turnover_monthly_v1",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "status": "ok",
                "failure_reason": "",
                "fold_count": 5,
                "positive_fold_ratio": 0.4,
                "annualized_return_mean": -0.047,
                "sharpe_mean": -0.42,
                "max_drawdown_worst": -0.17,
                "turnover_annual_mean": 2.0,
                "turnover_annual_max": 3.3,
                "parameter_unique_count": 5,
                "industry_diagnostic_status": "enabled:audited",
                "financial_diagnostic_status": "available",
                "top_industry_avg_share_mean": 0.14,
                "top3_industries_avg_share_mean": 0.29,
                "industry_violation_days_total": 482,
                "selected_quality_score_lift_mean": 0.18,
                "financial_missing_blocked_ratio_mean": 0.0,
                "is_return_pass": False,
                "is_sharpe_pass": False,
                "is_drawdown_pass": True,
                "is_positive_fold_pass": False,
                "is_turnover_pass": True,
                "price_adjustment_status": "qfq_asof",
            },
            {
                "strategy_id": "bad_data_strategy",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "status": "ok",
                "failure_reason": "",
                "fold_count": 3,
                "positive_fold_ratio": 1.0,
                "annualized_return_mean": 0.08,
                "sharpe_mean": 0.9,
                "max_drawdown_worst": -0.08,
                "turnover_annual_mean": 1.0,
                "turnover_annual_max": 1.5,
                "parameter_unique_count": 1,
                "industry_diagnostic_status": "not_available",
                "financial_diagnostic_status": "not_available",
                "top_industry_avg_share_mean": 0.0,
                "top3_industries_avg_share_mean": 0.0,
                "industry_violation_days_total": 0,
                "selected_quality_score_lift_mean": 0.0,
                "financial_missing_blocked_ratio_mean": 0.0,
                "is_return_pass": True,
                "is_sharpe_pass": True,
                "is_drawdown_pass": True,
                "is_positive_fold_pass": True,
                "is_turnover_pass": True,
                "price_adjustment_status": "not_qfq_asof",
            },
        ]
    ).to_csv(admission_dir / "strategy_admission_window_matrix.csv", index=False)
    pd.DataFrame(
        [
            {
                "strategy_id": "quality_low_turnover_monthly_v1",
                "admission_action": "reject",
                "window_pass_count": 0,
                "window_count": 1,
                "missing_window_count": 0,
                "parameter_unstable_window_count": 1,
                "industry_concentration_window_count": 1,
                "industry_diagnostic_missing_window_count": 0,
                "factor_diagnostic_missing_window_count": 0,
                "price_adjustment_fail_window_count": 0,
                "main_reasons": "overfit risk is critical; selected parameters change too frequently",
            },
            {
                "strategy_id": "bad_data_strategy",
                "admission_action": "retest",
                "window_pass_count": 1,
                "window_count": 1,
                "missing_window_count": 0,
                "parameter_unstable_window_count": 0,
                "industry_concentration_window_count": 0,
                "industry_diagnostic_missing_window_count": 1,
                "factor_diagnostic_missing_window_count": 1,
                "price_adjustment_fail_window_count": 1,
                "main_reasons": "qfq_asof price adjustment is required",
            },
        ]
    ).to_csv(admission_dir / "strategy_admission_constraint_review.csv", index=False)
    pd.DataFrame(
        [
            {
                "strategy_id": "quality_low_turnover_monthly_v1",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 1,
                "trades": 10,
                "avg_live_holdings": 12,
                "universe_symbol_count": 120,
            },
            {
                "strategy_id": "bad_data_strategy",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 1,
                "trades": 5,
                "avg_live_holdings": 10,
                "universe_symbol_count": 100,
            },
        ]
    ).to_csv(admission_dir / "strategy_admission_candidate_folds.csv", index=False)
    pd.DataFrame(
        [
            {
                "strategy_id": "quality_low_turnover_monthly_v1",
                "overfit_risk_level": "critical",
                "overfit_score": 80,
                "last_fold_lift_risk": True,
                "last_fold_lift_preset": "baseline_2y_1y_5fold",
                "last_fold_annualized_return": 0.16,
                "prior_fold_annualized_return_mean": -0.07,
                "last_fold_lift": 0.23,
            },
            {
                "strategy_id": "bad_data_strategy",
                "overfit_risk_level": "low",
                "overfit_score": 5,
                "last_fold_lift_risk": False,
            },
        ]
    ).to_csv(overfit_dir / "strategy_overfit_diagnostic.csv", index=False)

    result = run_strategy_failure_attribution(
        config=_config(),
        root=tmp_path,
        admission_dir=admission_dir,
        output_dir=output_dir,
    )

    assert result.rows == 2
    out = pd.read_csv(result.csv_path)
    quality = out[out["strategy_id"] == "quality_low_turnover_monthly_v1"].iloc[0]
    bad_data = out[out["strategy_id"] == "bad_data_strategy"].iloc[0]
    assert quality["primary_failure_dimension"] == "return_failure"
    assert quality["return_failure"] == "high"
    assert quality["parameter_failure"] == "high"
    assert quality["construction_failure"] == "high"
    assert quality["regime_failure"] == "high"
    assert "最后一折" in quality["evidence"]
    assert bad_data["primary_failure_dimension"] == "data_failure"
    assert bad_data["data_failure"] == "critical"
    assert "qfq_asof" in bad_data["evidence"]
    assert result.md_path.exists()
    assert result.fold_csv_path is not None
    assert result.fold_md_path is not None
    assert result.fold_csv_path.exists()
    assert result.fold_md_path.exists()
    assert "只读取已有 admission / overfit CSV" in result.md_path.read_text(encoding="utf-8")


def test_failure_attribution_writes_fold_level_benchmark_context(tmp_path) -> None:
    admission_dir = tmp_path / "admission"
    overfit_dir = admission_dir / "overfit_diagnostic"
    output_dir = tmp_path / "out"
    overfit_dir.mkdir(parents=True)

    pd.DataFrame(
        [
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "status": "ok",
                "fold_count": 3,
                "positive_fold_ratio": 2 / 3,
                "annualized_return_mean": 0.01,
                "sharpe_mean": 0.2,
                "max_drawdown_worst": -0.09,
                "turnover_annual_mean": 2.0,
                "turnover_annual_max": 2.4,
                "parameter_unique_count": 1,
                "industry_diagnostic_status": "enabled:audited",
                "financial_diagnostic_status": "not_applicable",
                "is_return_pass": True,
                "is_sharpe_pass": False,
                "is_drawdown_pass": True,
                "is_positive_fold_pass": False,
                "is_turnover_pass": True,
                "price_adjustment_status": "qfq_asof",
            }
        ]
    ).to_csv(admission_dir / "strategy_admission_window_matrix.csv", index=False)
    pd.DataFrame(
        [
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "admission_action": "research_only",
                "window_pass_count": 0,
                "window_count": 1,
                "missing_window_count": 0,
                "main_reasons": "only one preset passed; classify as research-only",
            }
        ]
    ).to_csv(admission_dir / "strategy_admission_constraint_review.csv", index=False)
    pd.DataFrame(
        [
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 1,
                "valid_start": "2021-04-01",
                "valid_end": "2022-03-31",
                "status": "ok",
                "annualized_return": -0.05,
                "benchmark_status": "available",
                "benchmark_annualized_return": -0.18,
                "excess_annualized_return": 0.13,
                "sharpe": -1.2,
                "max_drawdown": -0.07,
                "turnover_annual": 1.1,
                "negative_fold_attribution": "negative_absolute_but_positive_excess: market_down_or_benchmark_weaker",
                "selected_params": "p1",
            },
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 2,
                "valid_start": "2022-04-01",
                "valid_end": "2023-03-31",
                "status": "ok",
                "annualized_return": 0.04,
                "benchmark_status": "available",
                "benchmark_annualized_return": -0.05,
                "excess_annualized_return": 0.09,
                "sharpe": 0.55,
                "max_drawdown": -0.06,
                "turnover_annual": 1.8,
                "negative_fold_attribution": "positive_fold",
                "selected_params": "p1",
            },
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 3,
                "valid_start": "2024-04-01",
                "valid_end": "2025-03-31",
                "status": "ok",
                "annualized_return": 0.06,
                "benchmark_status": "available",
                "benchmark_annualized_return": 0.12,
                "excess_annualized_return": -0.06,
                "sharpe": 0.52,
                "max_drawdown": -0.08,
                "turnover_annual": 2.2,
                "negative_fold_attribution": "positive_fold",
                "selected_params": "p1",
            },
        ]
    ).to_csv(admission_dir / "strategy_admission_candidate_folds.csv", index=False)
    pd.DataFrame(
        [
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "overfit_risk_level": "low",
                "overfit_score": 10,
                "last_fold_lift_risk": False,
            }
        ]
    ).to_csv(overfit_dir / "strategy_overfit_diagnostic.csv", index=False)

    result = run_strategy_failure_attribution(
        config=_config(),
        root=tmp_path,
        admission_dir=admission_dir,
        output_dir=output_dir,
    )

    assert result.fold_csv_path is not None
    out = pd.read_csv(result.fold_csv_path)
    labels = out.set_index("fold")["primary_fold_failure"].to_dict()
    assert labels[1] == "absolute_failure_market_weak_but_outperform"
    assert labels[2] == "clean_positive_fold"
    assert labels[3] == "relative_failure_benchmark_strong"
    md = result.fold_md_path.read_text(encoding="utf-8") if result.fold_md_path else ""
    assert "not admission gates and not trading rules" in md
    assert "Do not infer a regime filter from this report alone" in md


def test_failure_attribution_all_pass_window_keeps_none_primary_failure(tmp_path) -> None:
    admission_dir = tmp_path / "admission"
    overfit_dir = admission_dir / "overfit_diagnostic"
    output_dir = tmp_path / "out"
    overfit_dir.mkdir(parents=True)

    pd.DataFrame(
        [
            {
                "strategy_id": "clean_strategy",
                "walk_forward_preset": "quality_4y_1y",
                "status": "ok",
                "fold_count": 1,
                "positive_fold_ratio": 1.0,
                "annualized_return_mean": 0.05,
                "sharpe_mean": 0.7,
                "max_drawdown_worst": -0.08,
                "turnover_annual_mean": 1.5,
                "turnover_annual_max": 1.8,
                "parameter_unique_count": 1,
                "industry_diagnostic_status": "enabled:audited",
                "financial_diagnostic_status": "not_applicable",
                "is_return_pass": True,
                "is_sharpe_pass": True,
                "is_drawdown_pass": True,
                "is_positive_fold_pass": True,
                "is_turnover_pass": True,
                "price_adjustment_status": "qfq_asof",
            }
        ]
    ).to_csv(admission_dir / "strategy_admission_window_matrix.csv", index=False)
    pd.DataFrame(
        [
            {
                "strategy_id": "clean_strategy",
                "admission_action": "research_only",
                "window_pass_count": 1,
                "window_count": 1,
                "missing_window_count": 0,
                "main_reasons": "strategy does not support paper trade review",
            }
        ]
    ).to_csv(admission_dir / "strategy_admission_constraint_review.csv", index=False)
    pd.DataFrame(
        [
            {
                "strategy_id": "clean_strategy",
                "walk_forward_preset": "quality_4y_1y",
                "fold": 1,
                "valid_start": "2025-04-01",
                "valid_end": "2026-03-31",
                "status": "ok",
                "annualized_return": 0.05,
                "benchmark_status": "available",
                "benchmark_annualized_return": 0.03,
                "excess_annualized_return": 0.02,
                "sharpe": 0.7,
                "max_drawdown": -0.08,
                "turnover_annual": 1.5,
                "negative_fold_attribution": "positive_fold",
                "selected_params": "stable",
            }
        ]
    ).to_csv(admission_dir / "strategy_admission_candidate_folds.csv", index=False)
    pd.DataFrame(
        [
            {
                "strategy_id": "clean_strategy",
                "overfit_risk_level": "low",
                "overfit_score": 0,
                "last_fold_lift_risk": False,
            }
        ]
    ).to_csv(overfit_dir / "strategy_overfit_diagnostic.csv", index=False)

    result = run_strategy_failure_attribution(
        config=_config(),
        root=tmp_path,
        admission_dir=admission_dir,
        output_dir=output_dir,
    )

    out = pd.read_csv(result.csv_path)
    assert out.loc[0, "primary_failure_dimension"] == "none"
    assert out.loc[0, "severity"] == "none"
    assert "未归因" in result.md_path.read_text(encoding="utf-8")


def test_failure_attribution_reports_missing_required_csv(tmp_path) -> None:
    admission_dir = tmp_path / "missing"
    admission_dir.mkdir()

    try:
        run_strategy_failure_attribution(config=_config(), root=tmp_path, admission_dir=admission_dir)
    except FileNotFoundError as exc:
        assert "strategy_admission_candidate_folds.csv" in str(exc)
    else:
        raise AssertionError("expected missing CSV to fail before producing attribution")
