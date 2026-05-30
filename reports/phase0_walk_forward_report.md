# Phase 0 Walk-Forward Report

Generated at: 2026-05-31T04:11:56

## Summary

| metric | value |
| --- | --- |
| status | ok |
| fold_count | 4 |
| symbol_count | 1 |
| annualized_return_mean | 0.14398098861238032 |
| sharpe_mean | 1.0886200539613382 |
| max_drawdown_mean | -0.10117349863293343 |
| win_rate_mean | 0.5129482071713147 |
| turnover_annual_mean | 1.5023090842074356 |
| selected_candidate | legacy_momentum_low_turnover_v1 |
| selected_candidate_eligible | True |
| selected_candidate_governance_reason | eligible |
| candidate_comparison | legacy_momentum: score=0.2414, selection_score=0.2414, eligible=True, ann=0.0724, sharpe=0.2952, mdd=-0.1800; legacy_momentum_low_turnover_v1: score=1.1100, selection_score=1.1100, eligible=True, ann=0.1440, sharpe=1.0886, mdd=-0.1012; ma_kline_baseline_v1: score=-2.0617, selection_score=-2.0617, eligible=True, ann=-0.2410, sharpe=-1.7831, mdd=-0.3162; residual_momentum_reversal_v1: score=-0.9010, selection_score=-0.9010, eligible=True, ann=-0.0878, sharpe=-0.7766, mdd=-0.1610; residual_momentum_reversal_v2: score=-1.6348, selection_score=-1.6348, eligible=True, ann=-0.1896, sharpe=-1.4056, mdd=-0.2688; quality_growth_price_v1: score=-0.8184, selection_score=-0.8184, eligible=True, ann=-0.0308, sharpe=-0.7194, mdd=-0.1672; multifactor_volume_price_filter_v1: score=-0.6869, selection_score=-0.6869, eligible=True, ann=-0.0766, sharpe=-0.5597, mdd=-0.1778 |
| oos_fold_count | 1 |
| oos_annualized_return_mean | 0.2936368726433385 |
| oos_sharpe_mean | 2.111799534830921 |
| oos_return_decay_ratio | -2.1206196624146103 |

## Candidate Summary

| candidate | score | selection_score | eligible | governance_reason | fold_count | symbol_count | panel_scope | annualized_return_mean | sharpe_mean | max_drawdown_mean | win_rate_mean | turnover_annual_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| legacy_momentum_low_turnover_v1 | 1.1100 | 1.1100 | True | eligible | 4 | 1 | portfolio | 0.1440 | 1.0886 | -0.1012 | 0.5129 | 1.50 |
| legacy_momentum | 0.2414 | 0.2414 | True | eligible | 4 | 1 | portfolio | 0.0724 | 0.2952 | -0.1800 | 0.4765 | 13.48 |
| multifactor_volume_price_filter_v1 | -0.6869 | -0.6869 | True | eligible | 4 | 1 | portfolio | -0.0766 | -0.5597 | -0.1778 | 0.4494 | 48.38 |
| quality_growth_price_v1 | -0.8184 | -0.8184 | True | eligible | 4 | 1 | portfolio | -0.0308 | -0.7194 | -0.1672 | 0.4609 | 24.55 |
| residual_momentum_reversal_v1 | -0.9010 | -0.9010 | True | eligible | 4 | 1 | portfolio | -0.0878 | -0.7766 | -0.1610 | 0.4586 | 30.17 |
| residual_momentum_reversal_v2 | -1.6348 | -1.6348 | True | eligible | 4 | 1 | portfolio | -0.1896 | -1.4056 | -0.2688 | 0.4059 | 59.08 |
| ma_kline_baseline_v1 | -2.0617 | -2.0617 | True | eligible | 4 | 1 | portfolio | -0.2410 | -1.7831 | -0.3162 | 0.4005 | 41.96 |

## Fold Details

| symbol | fold | train_start | train_end | valid_start | valid_end | annual_ret | sharpe | max_dd | win_rate | turnover_annual | trades | selected_params |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PORTFOLIO | 1 | 2019-07-30 | 2021-08-23 | 2021-08-24 | 2022-09-06 | -0.0232 | -0.1703 | -0.1569 | 0.5219 | 1.15 | 13 | mom20@q0.6,hold_q=0.4,buy_top=10,hold_top=20,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 2 | 2020-08-12 | 2022-09-06 | 2022-09-07 | 2023-09-19 | 0.1770 | 1.4581 | -0.0687 | 0.5020 | 1.17 | 13 | mom20@q0.6,hold_q=0.4,buy_top=5,hold_top=10,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 3 | 2021-08-24 | 2023-09-19 | 2023-09-20 | 2024-10-11 | 0.1285 | 0.9549 | -0.1042 | 0.5020 | 2.28 | 13 | mom20@q0.6,hold_q=0.4,buy_top=5,hold_top=10,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 4 | 2022-09-07 | 2024-10-11 | 2024-10-14 | 2025-10-24 | 0.2936 | 2.1118 | -0.0749 | 0.5259 | 1.40 | 16 | mom20@q0.6,hold_q=0.4,buy_top=5,hold_top=10,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
