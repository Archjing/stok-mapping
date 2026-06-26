from __future__ import annotations

import pandas as pd

from phase0.research.summaries.role_card import run_strategy_role_card


def test_strategy_role_card_generates_research_only_rules(tmp_path) -> None:
    strategy_id = "price_volume_low_turnover_v1"
    matrix = pd.DataFrame(
        [
            {
                "strategy_id": strategy_id,
                "walk_forward_preset": "baseline",
                "annualized_return_mean": 0.025,
                "sharpe_mean": 0.16,
                "max_drawdown_worst": -0.095,
                "turnover_annual_mean": 1.87,
                "positive_fold_ratio": 0.80,
                "positive_excess_fold_ratio": 0.60,
                "is_window_pass": False,
            },
            {
                "strategy_id": strategy_id,
                "walk_forward_preset": "quality",
                "annualized_return_mean": 0.051,
                "sharpe_mean": 0.52,
                "max_drawdown_worst": -0.091,
                "turnover_annual_mean": 2.27,
                "positive_fold_ratio": 1.00,
                "positive_excess_fold_ratio": 0.00,
                "is_window_pass": True,
            },
        ]
    )
    constraints = pd.DataFrame(
        [
            {
                "strategy_id": strategy_id,
                "admission_action": "research_only",
                "window_pass_count": 1,
                "window_count": 2,
                "overfit_risk_level": "low",
                "supports_paper_trade": False,
                "main_reasons": "only one preset passed; classify as research-only",
            }
        ]
    )
    folds = pd.DataFrame(
        [
            {
                "strategy_id": strategy_id,
                "primary_fold_failure": "clean_positive_fold",
            },
            {
                "strategy_id": strategy_id,
                "primary_fold_failure": "relative_failure_benchmark_strong",
            },
        ]
    )
    market = pd.DataFrame(
        [
            {
                "strategy_id": strategy_id,
                "market_context_label": "risk_context_pressure",
                "strategy_annualized_return": 0.03,
                "benchmark_annualized_return": -0.05,
                "excess_annualized_return": 0.08,
            },
            {
                "strategy_id": strategy_id,
                "market_context_label": "relative_lag_in_strong_benchmark_context",
                "strategy_annualized_return": 0.06,
                "benchmark_annualized_return": 0.12,
                "excess_annualized_return": -0.06,
            },
        ]
    )
    holdings = pd.DataFrame(
        [
            {
                "market_context_label": "relative_lag_in_strong_benchmark_context",
                "avg_live_exposure": 0.44,
                "avg_live_holding_count": 6.4,
                "avg_live_top_industry_share": 0.15,
            }
        ]
    )
    overlay = pd.DataFrame(
        [
            {
                "walk_forward_preset": "ALL",
                "scope": "all",
                "market_context_label": "ALL",
                "base_annualized_return": 0.063,
                "overlay_annualized_return": 0.038,
                "base_sharpe": 0.60,
                "overlay_sharpe": 0.34,
                "base_max_drawdown": -0.095,
                "overlay_max_drawdown": -0.149,
            }
        ]
    )
    paths = {}
    for name, frame in {
        "matrix": matrix,
        "constraints": constraints,
        "folds": folds,
        "market": market,
        "holdings": holdings,
        "overlay": overlay,
    }.items():
        path = tmp_path / f"{name}.csv"
        frame.to_csv(path, index=False)
        paths[name] = path

    result = run_strategy_role_card(
        strategy_id=strategy_id,
        matrix_path=paths["matrix"],
        constraints_path=paths["constraints"],
        fold_attribution_path=paths["folds"],
        market_context_path=paths["market"],
        holdings_summary_path=paths["holdings"],
        overlay_summary_path=paths["overlay"],
        output_dir=tmp_path / "out",
    )

    rules = pd.read_csv(result.rule_csv_path)
    assert result.admission_action == "research_only"
    assert result.rows >= 5
    assert "strong_benchmark_lag" in set(rules["rule_id"])
    assert "exposure_overlay_counterevidence" in set(rules["rule_id"])
    assert "no_eligible_strategy" in set(rules["research_state"])
    report = result.report_md_path.read_text(encoding="utf-8")
    assert "research-only governance report" in report
    assert "not trading enablement rules" in report


def test_strategy_role_card_requires_strategy_rows(tmp_path) -> None:
    matrix = tmp_path / "matrix.csv"
    constraints = tmp_path / "constraints.csv"
    pd.DataFrame([{"strategy_id": "other", "walk_forward_preset": "baseline"}]).to_csv(matrix, index=False)
    pd.DataFrame([{"strategy_id": "other", "admission_action": "reject"}]).to_csv(constraints, index=False)

    try:
        run_strategy_role_card(
            strategy_id="missing",
            matrix_path=matrix,
            constraints_path=constraints,
            output_dir=tmp_path / "out",
        )
    except ValueError as exc:
        assert "strategy_id='missing'" in str(exc)
    else:
        raise AssertionError("expected missing strategy rows to fail")


def test_strategy_role_card_does_not_label_reject_as_defensive_sample(tmp_path) -> None:
    strategy_id = "sleeve_composite_low_churn_v1"
    matrix = tmp_path / "matrix.csv"
    constraints = tmp_path / "constraints.csv"
    market = tmp_path / "market.csv"
    pd.DataFrame(
        [
            {
                "strategy_id": strategy_id,
                "walk_forward_preset": "baseline",
                "annualized_return_mean": 0.04,
                "sharpe_mean": 0.19,
                "max_drawdown_worst": -0.26,
                "turnover_annual_mean": 3.06,
                "positive_fold_ratio": 0.60,
                "is_window_pass": False,
            }
        ]
    ).to_csv(matrix, index=False)
    pd.DataFrame(
        [
            {
                "strategy_id": strategy_id,
                "admission_action": "reject",
                "window_pass_count": 0,
                "window_count": 1,
                "overfit_risk_level": "high",
                "supports_paper_trade": False,
                "main_reasons": "overfit risk is high",
            }
        ]
    ).to_csv(constraints, index=False)
    pd.DataFrame(
        [
            {
                "strategy_id": strategy_id,
                "market_context_label": "risk_context_pressure",
                "strategy_annualized_return": 0.10,
                "benchmark_annualized_return": -0.05,
                "excess_annualized_return": 0.15,
            }
        ]
    ).to_csv(market, index=False)

    result = run_strategy_role_card(
        strategy_id=strategy_id,
        matrix_path=matrix,
        constraints_path=constraints,
        market_context_path=market,
        output_dir=tmp_path / "out",
    )

    rules = pd.read_csv(result.rule_csv_path)
    weak_rule = rules[rules["rule_id"] == "weak_or_risk_pressure"].iloc[0]
    assert weak_rule["research_state"] == "weak_context_diagnostic_only"
    assert "Do not claim defensive fit" in weak_rule["next_step"]
