# Phase 0 Walk-Forward Report

Generated at: 2026-05-30T04:15:28

## Summary

| metric | value |
| --- | --- |
| status | ok |
| fold_count | 2 |
| symbol_count | 1 |
| annualized_return_mean | 0.11205707183468916 |
| sharpe_mean | 0.7833169469012886 |
| max_drawdown_mean | -0.06442244506196493 |
| win_rate_mean | 0.2581967213114754 |
| turnover_annual_mean | 4.72775798738143 |
| selected_candidate | quality_growth_price_v1 |
| candidate_comparison | legacy_momentum: score=0.3546, ann=0.3287, sharpe=0.3400, mdd=-0.2995; ma_kline_baseline_v1: score=-3.4433, ann=-0.3641, sharpe=-3.0551, mdd=-0.4123; residual_momentum_reversal_v1: score=-0.7985, ann=-0.0743, sharpe=-0.6631, mdd=-0.1965; residual_momentum_reversal_v2: score=-1.0221, ann=-0.1167, sharpe=-0.8768, mdd=-0.1740; quality_growth_price_v1: score=0.8071, ann=0.1121, sharpe=0.7833, mdd=-0.0644; multifactor_volume_price_filter_v1: score=-0.4769, ann=-0.0521, sharpe=-0.4047, mdd=-0.0921 |
| oos_fold_count | 1 |
| oos_annualized_return_mean | 0.22411414366937832 |
| oos_sharpe_mean | 1.5666338938025772 |
| oos_return_decay_ratio | 0.0 |

## Candidate Summary

| candidate | score | fold_count | annualized_return_mean | sharpe_mean | max_drawdown_mean | win_rate_mean | turnover_annual_mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| quality_growth_price_v1 | 0.8071 | 2 | 0.1121 | 0.7833 | -0.0644 | 0.2582 | 4.73 |
| legacy_momentum | 0.3546 | 228 | 0.3287 | 0.3400 | -0.2995 | 0.4621 | 52.35 |
| multifactor_volume_price_filter_v1 | -0.4769 | 2 | -0.0521 | -0.4047 | -0.0921 | 0.2273 | 26.37 |
| residual_momentum_reversal_v1 | -0.7985 | 2 | -0.0743 | -0.6631 | -0.1965 | 0.4611 | 24.00 |
| residual_momentum_reversal_v2 | -1.0221 | 2 | -0.1167 | -0.8768 | -0.1740 | 0.4126 | 67.15 |
| ma_kline_baseline_v1 | -3.4433 | 2 | -0.3641 | -3.0551 | -0.4123 | 0.3698 | 46.37 |

## Fold Details

| symbol | fold | train_start | train_end | valid_start | valid_end | annual_ret | sharpe | max_dd | win_rate | turnover_annual | trades | selected_params |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PORTFOLIO | 1 | 2021-07-30 | 2023-08-25 | 2023-08-28 | 2024-09-09 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00 | 0 | quality_growth@q1.0,ma20,vol@q0.75,target_vol=0.18,top_n=5,xmarket_overlay=True |
| PORTFOLIO | 2 | 2022-08-15 | 2024-09-09 | 2024-09-10 | 2025-09-23 | 0.2241 | 1.5666 | -0.1288 | 0.5164 | 9.46 | 245 | quality_growth@q0.7,ma60,vol@q0.6,target_vol=0.18,top_n=10,xmarket_overlay=True |
