from __future__ import annotations

import pandas as pd

from quant.research.attribution.fold import run_strategy_fold_attribution


def test_strategy_fold_attribution_pairs_folds_and_writes_outputs(tmp_path) -> None:
    quality_folds = pd.DataFrame(
        [
            {
                "strategy_id": "low_vol_low_turnover_quality_v1",
                "walk_forward_preset": "baseline",
                "fold": 1,
                "valid_start": "2024-01-01",
                "valid_end": "2024-12-31",
                "primary_fold_failure": "low_risk_adjusted_return",
                "annualized_return": 0.01,
                "excess_annualized_return": -0.02,
                "sharpe": 0.2,
                "turnover_annual": 1.0,
            }
        ]
    )
    price_folds = pd.DataFrame(
        [
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline",
                "fold": 1,
                "valid_start": "2024-01-01",
                "valid_end": "2024-12-31",
                "primary_fold_failure": "clean_positive_fold",
                "annualized_return": 0.04,
                "excess_annualized_return": 0.01,
                "sharpe": 0.6,
                "turnover_annual": 1.2,
            }
        ]
    )
    context = pd.DataFrame(
        [
            {
                "strategy_id": "any",
                "walk_forward_preset": "baseline",
                "fold": 1,
                "market_context_label": "risk_context_pressure",
                "benchmark_return_bucket": "weak_down",
            }
        ]
    )
    quality_holdings = pd.DataFrame(
        [
            {
                "strategy_id": "low_vol_low_turnover_quality_v1",
                "walk_forward_preset": "baseline",
                "fold": 1,
                "date": "2024-01-02",
                "symbol": "AAA",
                "name": "A",
                "industry": "Tech",
                "live_weight": 0.1,
                "target_weight": 0.1,
                "position_ret": 0.002,
                "quality_growth_score": 0.9,
                "score": 0.8,
            },
            {
                "strategy_id": "low_vol_low_turnover_quality_v1",
                "walk_forward_preset": "baseline",
                "fold": 1,
                "date": "2024-01-02",
                "symbol": "BBB",
                "name": "B",
                "industry": "Bank",
                "live_weight": 0.05,
                "target_weight": 0.05,
                "position_ret": -0.001,
                "quality_growth_score": 0.2,
                "score": 0.3,
            },
            {
                "strategy_id": "low_vol_low_turnover_quality_v1",
                "walk_forward_preset": "baseline",
                "fold": 1,
                "date": "2024-01-02",
                "symbol": "CCC",
                "name": "C",
                "industry": "Health",
                "live_weight": 0.02,
                "target_weight": 0.02,
                "position_ret": 0.0005,
                "quality_growth_score": 0.6,
                "score": 0.5,
            },
            {
                "strategy_id": "low_vol_low_turnover_quality_v1",
                "walk_forward_preset": "baseline",
                "fold": 1,
                "date": "2024-01-02",
                "symbol": "DDD",
                "name": "D",
                "industry": "Energy",
                "live_weight": 0.01,
                "target_weight": 0.01,
                "position_ret": 0.0001,
                "quality_growth_score": 0.4,
                "score": 0.4,
            },
        ]
    )
    price_holdings = quality_holdings.assign(
        strategy_id="price_volume_low_turnover_v1",
        quality_growth_score=pd.NA,
    )
    daily = pd.DataFrame(
        [
            {
                "strategy_id": "low_vol_low_turnover_quality_v1",
                "walk_forward_preset": "baseline",
                "fold": 1,
                "valid_start": "2024-01-01",
                "valid_end": "2024-12-31",
                "market_context_label": "risk_context_pressure",
                "date": "2024-01-02",
                "live_exposure": 0.18,
                "live_holding_count": 4,
                "live_top_industry_share": 0.10,
                "live_top3_industries_share": 0.17,
            }
        ]
    )
    paths = {}
    for name, frame in {
        "quality_folds": quality_folds,
        "price_folds": price_folds,
        "quality_context": context,
        "price_context": context,
        "quality_holdings": quality_holdings,
        "price_holdings": price_holdings,
        "quality_daily": daily,
        "price_daily": daily.assign(strategy_id="price_volume_low_turnover_v1"),
    }.items():
        path = tmp_path / f"{name}.csv"
        frame.to_csv(path, index=False)
        paths[name] = path

    result = run_strategy_fold_attribution(
        quality_fold_attribution_path=paths["quality_folds"],
        price_volume_fold_attribution_path=paths["price_folds"],
        quality_market_context_path=paths["quality_context"],
        price_volume_market_context_path=paths["price_context"],
        quality_holdings_path=paths["quality_holdings"],
        price_volume_holdings_path=paths["price_holdings"],
        quality_daily_exposure_path=paths["quality_daily"],
        price_volume_daily_exposure_path=paths["price_daily"],
        output_dir=tmp_path / "out",
    )

    paired = pd.read_csv(result.paired_fold_csv_path)
    bucket = pd.read_csv(result.quality_bucket_csv_path)

    assert result.paired_rows == 1
    assert float(paired.iloc[0]["quality_minus_price_volume_ann"]) == -0.03
    assert set(bucket["quality_bucket"]) == {"Q1_low", "Q2", "Q3", "Q4_high"}
    assert result.md_path.exists()
