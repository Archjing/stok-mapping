# Phase 0 Walk-Forward Report

Generated at: 2026-05-30T22:05:00

## Summary

| metric | value |
| --- | --- |
| status | ok |
| fold_count | 4 |
| symbol_count | 1 |
| annualized_return_mean | 0.0724299941587006 |
| sharpe_mean | 0.2952365417912636 |
| max_drawdown_mean | -0.18002976991347383 |
| win_rate_mean | 0.4765418326693227 |
| turnover_annual_mean | 13.475825891070368 |
| selected_candidate | legacy_momentum |
| selected_candidate_eligible | True |
| selected_candidate_governance_reason | eligible |
| candidate_comparison | legacy_momentum: score=0.2414, selection_score=0.2414, eligible=True, ann=0.0724, sharpe=0.2952, mdd=-0.1800; ma_kline_baseline_v1: score=-2.0617, selection_score=-2.0617, eligible=True, ann=-0.2410, sharpe=-1.7831, mdd=-0.3162; residual_momentum_reversal_v1: score=-0.9010, selection_score=-0.9010, eligible=True, ann=-0.0878, sharpe=-0.7766, mdd=-0.1610; residual_momentum_reversal_v2: score=-1.6348, selection_score=-1.6348, eligible=True, ann=-0.1896, sharpe=-1.4056, mdd=-0.2688; quality_growth_price_v1: score=-0.8184, selection_score=-0.8184, eligible=True, ann=-0.0308, sharpe=-0.7194, mdd=-0.1672; multifactor_volume_price_filter_v1: score=-0.6869, selection_score=-0.6869, eligible=True, ann=-0.0766, sharpe=-0.5597, mdd=-0.1778 |
| oos_fold_count | 1 |
| oos_annualized_return_mean | 0.4026510273368835 |
| oos_sharpe_mean | 2.3475923307726827 |
| oos_return_decay_ratio | -11.696376899895348 |

## Candidate Summary

| candidate | score | selection_score | eligible | governance_reason | fold_count | symbol_count | panel_scope | annualized_return_mean | sharpe_mean | max_drawdown_mean | win_rate_mean | turnover_annual_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| legacy_momentum | 0.2414 | 0.2414 | True | eligible | 4 | 1 | portfolio | 0.0724 | 0.2952 | -0.1800 | 0.4765 | 13.48 |
| multifactor_volume_price_filter_v1 | -0.6869 | -0.6869 | True | eligible | 4 | 1 | portfolio | -0.0766 | -0.5597 | -0.1778 | 0.4494 | 48.38 |
| quality_growth_price_v1 | -0.8184 | -0.8184 | True | eligible | 4 | 1 | portfolio | -0.0308 | -0.7194 | -0.1672 | 0.4609 | 24.55 |
| residual_momentum_reversal_v1 | -0.9010 | -0.9010 | True | eligible | 4 | 1 | portfolio | -0.0878 | -0.7766 | -0.1610 | 0.4586 | 30.17 |
| residual_momentum_reversal_v2 | -1.6348 | -1.6348 | True | eligible | 4 | 1 | portfolio | -0.1896 | -1.4056 | -0.2688 | 0.4059 | 59.08 |
| ma_kline_baseline_v1 | -2.0617 | -2.0617 | True | eligible | 4 | 1 | portfolio | -0.2410 | -1.7831 | -0.3162 | 0.4005 | 41.96 |

## Fold Details

| symbol | fold | train_start | train_end | valid_start | valid_end | annual_ret | sharpe | max_dd | win_rate | turnover_annual | trades | selected_params |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PORTFOLIO | 1 | 2019-07-30 | 2021-08-23 | 2021-08-24 | 2022-09-06 | -0.2117 | -1.8854 | -0.2771 | 0.4622 | 8.99 | 251 | legacy_mom5@q0.5,top_n=3,target_vol=0.18 |
| PORTFOLIO | 2 | 2020-08-12 | 2022-09-06 | 2022-09-07 | 2023-09-19 | -0.0638 | -0.3432 | -0.2011 | 0.4480 | 14.90 | 251 | legacy_mom5@q0.5,top_n=3,target_vol=0.18 |
| PORTFOLIO | 3 | 2021-08-24 | 2023-09-19 | 2023-09-20 | 2024-10-11 | 0.1626 | 1.0620 | -0.1407 | 0.4741 | 16.70 | 251 | legacy_mom5@q0.5,top_n=3,target_vol=0.18 |
| PORTFOLIO | 4 | 2022-09-07 | 2024-10-11 | 2024-10-14 | 2025-10-24 | 0.4027 | 2.3476 | -0.1012 | 0.5219 | 13.31 | 251 | legacy_mom5@q0.5,top_n=3,target_vol=0.18 |
