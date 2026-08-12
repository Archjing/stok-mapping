from __future__ import annotations

import pandas as pd

from quant.research.attribution.alpha_source import run_strategy_alpha_source_audit


def test_strategy_alpha_source_audit_compares_folds_and_contributors(tmp_path) -> None:
    context = "relative_lag_in_strong_benchmark_context"
    baseline_fold = pd.DataFrame(
        [
            {
                "strategy_id": "baseline_core",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 4,
                "valid_start": "2024-01-01",
                "valid_end": "2024-12-31",
                "market_context_label": context,
                "avg_live_exposure": 0.25,
                "avg_benchmark_weight_held": 0.64,
                "avg_top_n_coverage_ratio": 0.98,
                "avg_industry_l1_gap_normalized": 0.34,
                "excess_total_return": -0.08,
                "primary_driver": "low_participation",
            }
        ]
    )
    treatment_fold = baseline_fold.assign(
        strategy_id="alpha_overlay",
        avg_live_exposure=0.25,
        avg_benchmark_weight_held=0.64,
        avg_top_n_coverage_ratio=0.99,
        avg_industry_l1_gap_normalized=0.31,
        excess_total_return=-0.10,
    )
    baseline_holdings = pd.DataFrame(
        [
            {
                "strategy_id": "baseline_core",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 4,
                "valid_start": "2024-01-01",
                "valid_end": "2024-12-31",
                "market_context_label": context,
                "date": "2024-03-01",
                "symbol": "AAA",
                "name": "A",
                "industry": "通信设备",
                "live_weight": 0.05,
                "position_ret": 0.010,
            },
            {
                "strategy_id": "baseline_core",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 4,
                "valid_start": "2024-01-01",
                "valid_end": "2024-12-31",
                "market_context_label": context,
                "date": "2024-03-01",
                "symbol": "BBB",
                "name": "B",
                "industry": "白酒",
                "live_weight": 0.04,
                "position_ret": -0.004,
            },
        ]
    )
    treatment_holdings = baseline_holdings.assign(strategy_id="alpha_overlay").copy()
    treatment_holdings.loc[treatment_holdings["symbol"] == "AAA", "position_ret"] = 0.006
    treatment_holdings.loc[treatment_holdings["symbol"] == "BBB", "position_ret"] = -0.008
    treatment_holdings.loc[treatment_holdings["symbol"] == "BBB", "live_weight"] = 0.05
    baseline_missed = pd.DataFrame(
        [
            {
                "strategy_id": "baseline_core",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 4,
                "valid_start": "2024-01-01",
                "valid_end": "2024-12-31",
                "market_context_label": context,
                "benchmark_symbol": "SH.000300",
                "symbol": "SH.600519",
                "name": "贵州茅台",
                "industry": "白酒",
                "missed_days": 12,
                "avg_benchmark_weight": 0.05,
                "max_benchmark_weight": 0.06,
                "avg_benchmark_rank": 1.0,
            }
        ]
    )
    treatment_missed = baseline_missed.assign(strategy_id="alpha_overlay", missed_days=15)

    paths = {}
    for name, frame in {
        "baseline_fold": baseline_fold,
        "treatment_fold": treatment_fold,
        "baseline_holdings": baseline_holdings,
        "treatment_holdings": treatment_holdings,
        "baseline_missed": baseline_missed,
        "treatment_missed": treatment_missed,
    }.items():
        path = tmp_path / f"{name}.csv"
        frame.to_csv(path, index=False)
        paths[name] = path

    result = run_strategy_alpha_source_audit(
        baseline_label="I51",
        treatment_label="I55",
        baseline_csi300_fold_path=paths["baseline_fold"],
        treatment_csi300_fold_path=paths["treatment_fold"],
        baseline_holdings_path=paths["baseline_holdings"],
        treatment_holdings_path=paths["treatment_holdings"],
        baseline_missed_top_path=paths["baseline_missed"],
        treatment_missed_top_path=paths["treatment_missed"],
        output_dir=tmp_path / "out",
        context_label=context,
    )

    fold = pd.read_csv(result.fold_comparison_csv_path)
    symbols = pd.read_csv(result.symbol_contribution_csv_path)
    industries = pd.read_csv(result.industry_contribution_csv_path)
    missed = pd.read_csv(result.missed_top_csv_path)

    assert result.fold_rows == 1
    assert float(fold.iloc[0]["excess_total_return_delta"]) == -0.02
    assert fold.iloc[0]["dominant_gap"] == "low_participation"
    assert symbols.iloc[0]["symbol"] == "BBB"
    assert float(symbols.iloc[0]["position_ret_delta"]) == -0.004
    assert industries.iloc[0]["industry"] == "白酒"
    assert float(industries.iloc[0]["position_ret_delta"]) == -0.004
    assert int(missed.iloc[0]["treatment_missed_days"]) == 15
    assert result.report_md_path.exists()


def test_strategy_alpha_source_audit_filters_context_and_handles_missing_missed_top(tmp_path) -> None:
    target_context = "relative_lag_in_strong_benchmark_context"
    other_context = "risk_context_pressure"
    folds = pd.DataFrame(
        [
            {
                "strategy_id": "strategy_a",
                "walk_forward_preset": "baseline",
                "fold": 1,
                "valid_start": "2024-01-01",
                "valid_end": "2024-12-31",
                "market_context_label": target_context,
                "excess_total_return": -0.1,
                "primary_driver": "low_participation",
            },
            {
                "strategy_id": "strategy_a",
                "walk_forward_preset": "baseline",
                "fold": 2,
                "valid_start": "2025-01-01",
                "valid_end": "2025-12-31",
                "market_context_label": other_context,
                "excess_total_return": 0.1,
                "primary_driver": "clean_fold",
            },
        ]
    )
    holdings = pd.DataFrame(
        [
            {
                "strategy_id": "strategy_a",
                "walk_forward_preset": "baseline",
                "fold": 1,
                "valid_start": "2024-01-01",
                "valid_end": "2024-12-31",
                "market_context_label": target_context,
                "date": "2024-02-01",
                "symbol": "AAA",
                "name": "A",
                "industry": "银行",
                "live_weight": 0.1,
                "position_ret": -0.002,
            },
            {
                "strategy_id": "strategy_a",
                "walk_forward_preset": "baseline",
                "fold": 2,
                "valid_start": "2025-01-01",
                "valid_end": "2025-12-31",
                "market_context_label": other_context,
                "date": "2025-02-01",
                "symbol": "BBB",
                "name": "B",
                "industry": "保险",
                "live_weight": 0.2,
                "position_ret": 0.003,
            },
        ]
    )
    baseline_fold = tmp_path / "baseline_fold.csv"
    treatment_fold = tmp_path / "treatment_fold.csv"
    baseline_holdings = tmp_path / "baseline_holdings.csv"
    treatment_holdings = tmp_path / "treatment_holdings.csv"
    folds.to_csv(baseline_fold, index=False)
    folds.assign(strategy_id="strategy_b", excess_total_return=[-0.12, 0.12]).to_csv(treatment_fold, index=False)
    holdings.to_csv(baseline_holdings, index=False)
    holdings.assign(strategy_id="strategy_b", position_ret=[-0.003, 0.004]).to_csv(treatment_holdings, index=False)

    result = run_strategy_alpha_source_audit(
        baseline_label="baseline",
        treatment_label="treatment",
        baseline_csi300_fold_path=baseline_fold,
        treatment_csi300_fold_path=treatment_fold,
        baseline_holdings_path=baseline_holdings,
        treatment_holdings_path=treatment_holdings,
        output_dir=tmp_path / "out",
        context_label=target_context,
    )

    fold = pd.read_csv(result.fold_comparison_csv_path)
    symbols = pd.read_csv(result.symbol_contribution_csv_path)
    missed = pd.read_csv(result.missed_top_csv_path)

    assert list(fold["fold"]) == [1]
    assert set(symbols["symbol"]) == {"AAA"}
    assert missed.empty


def test_strategy_alpha_source_audit_keeps_asymmetric_symbols(tmp_path) -> None:
    context = "relative_lag_in_strong_benchmark_context"
    fold = pd.DataFrame(
        [
            {
                "strategy_id": "strategy_a",
                "walk_forward_preset": "baseline",
                "fold": 1,
                "valid_start": "2024-01-01",
                "valid_end": "2024-12-31",
                "market_context_label": context,
                "excess_total_return": -0.02,
            }
        ]
    )
    baseline_holdings = pd.DataFrame(
        [
            {
                "strategy_id": "strategy_a",
                "walk_forward_preset": "baseline",
                "fold": 1,
                "valid_start": "2024-01-01",
                "valid_end": "2024-12-31",
                "market_context_label": context,
                "date": "2024-03-01",
                "symbol": "BASE",
                "name": "Baseline Only",
                "industry": "通信设备",
                "live_weight": 0.1,
                "position_ret": 0.006,
            }
        ]
    )
    treatment_holdings = pd.DataFrame(
        [
            {
                "strategy_id": "strategy_b",
                "walk_forward_preset": "baseline",
                "fold": 1,
                "valid_start": "2024-01-01",
                "valid_end": "2024-12-31",
                "market_context_label": context,
                "date": "2024-03-01",
                "symbol": "TREAT",
                "name": "Treatment Only",
                "industry": "白酒",
                "live_weight": 0.2,
                "position_ret": -0.004,
            }
        ]
    )
    paths = {}
    for name, frame in {
        "baseline_fold": fold,
        "treatment_fold": fold.assign(strategy_id="strategy_b", excess_total_return=-0.03),
        "baseline_holdings": baseline_holdings,
        "treatment_holdings": treatment_holdings,
    }.items():
        path = tmp_path / f"{name}.csv"
        frame.to_csv(path, index=False)
        paths[name] = path

    result = run_strategy_alpha_source_audit(
        baseline_label="baseline",
        treatment_label="treatment",
        baseline_csi300_fold_path=paths["baseline_fold"],
        treatment_csi300_fold_path=paths["treatment_fold"],
        baseline_holdings_path=paths["baseline_holdings"],
        treatment_holdings_path=paths["treatment_holdings"],
        output_dir=tmp_path / "out",
        context_label=context,
    )

    symbols = pd.read_csv(result.symbol_contribution_csv_path)
    by_symbol = symbols.set_index("symbol")

    assert set(symbols["symbol"]) == {"BASE", "TREAT"}
    assert float(by_symbol.loc["BASE", "position_ret_delta"]) == -0.006
    assert float(by_symbol.loc["TREAT", "position_ret_delta"]) == -0.004
