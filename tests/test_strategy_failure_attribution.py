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
    assert "只读取已有 admission / overfit CSV" in result.md_path.read_text(encoding="utf-8")


def test_failure_attribution_reports_missing_required_csv(tmp_path) -> None:
    admission_dir = tmp_path / "missing"
    admission_dir.mkdir()

    try:
        run_strategy_failure_attribution(config=_config(), root=tmp_path, admission_dir=admission_dir)
    except FileNotFoundError as exc:
        assert "strategy_admission_candidate_folds.csv" in str(exc)
    else:
        raise AssertionError("expected missing CSV to fail before producing attribution")
