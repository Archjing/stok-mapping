# Phase 0 Walk-Forward Report

Generated at: 2026-06-03T17:41:07

## Summary

| metric | value |
| --- | --- |
| status | ok |
| fold_count | 4 |
| symbol_count | 1 |
| annualized_return_mean | 0.11212763383832514 |
| sharpe_mean | 0.82036890964417 |
| max_drawdown_mean | -0.11099878689840137 |
| win_rate_mean | 0.5 |
| turnover_annual_mean | 1.4864332695558795 |
| positive_fold_count | 3 |
| negative_fold_count | 1 |
| positive_fold_ratio | 0.75 |
| min_fold_annualized_return | -0.11172374473701674 |
| min_fold_sharpe | -0.9761356411380427 |
| selected_candidate | legacy_momentum_low_turnover_v1 |
| selected_candidate_eligible | True |
| selected_candidate_governance_reason | eligible |
| candidate_comparison | legacy_momentum: score=-0.6982, selection_score=-0.6982, eligible=True, ann=-0.0536, sharpe=-0.5634, mdd=-0.2160; legacy_momentum_low_turnover_v1: score=0.8209, selection_score=0.8209, eligible=True, ann=0.1121, sharpe=0.8204, mdd=-0.1110; ma_kline_baseline_v1: score=-3.9748, selection_score=-3.9748, eligible=True, ann=-0.4203, sharpe=-3.5391, mdd=-0.4512; residual_momentum_reversal_v1: score=-2.7499, selection_score=-2.7499, eligible=True, ann=-0.2593, sharpe=-2.4780, mdd=-0.2845; residual_momentum_reversal_v2: score=-3.5346, selection_score=-3.5346, eligible=True, ann=-0.3676, sharpe=-3.1566, mdd=-0.3884; quality_growth_price_v1: score=-1.6060, selection_score=-1.6060, eligible=True, ann=-0.1173, sharpe=-1.4395, mdd=-0.2158; multifactor_volume_price_filter_v1: score=-2.3810, selection_score=-2.3810, eligible=True, ann=-0.2528, sharpe=-2.1113, mdd=-0.2866 |
| oos_fold_count | 1 |
| oos_annualized_return_mean | 0.2921301628510151 |
| oos_sharpe_mean | 2.103897672084983 |
| oos_positive_fold_count | 1 |
| oos_positive_fold_ratio | 1.0 |
| oos_min_fold_annualized_return | 0.2921301628510151 |
| oos_return_decay_ratio | -4.60422305260999 |

## Candidate Summary

| candidate | score | selection_score | eligible | governance_reason | fold_count | symbol_count | panel_scope | annualized_return_mean | sharpe_mean | max_drawdown_mean | win_rate_mean | turnover_annual_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| legacy_momentum_low_turnover_v1 | 0.8209 | 0.8209 | True | eligible | 4 | 1 | portfolio | 0.1121 | 0.8204 | -0.1110 | 0.5000 | 1.49 |
| legacy_momentum | -0.6982 | -0.6982 | True | eligible | 4 | 1 | portfolio | -0.0536 | -0.5634 | -0.2160 | 0.4456 | 13.33 |
| quality_growth_price_v1 | -1.6060 | -1.6060 | True | eligible | 4 | 1 | portfolio | -0.1173 | -1.4395 | -0.2158 | 0.4368 | 24.89 |
| multifactor_volume_price_filter_v1 | -2.3810 | -2.3810 | True | eligible | 4 | 1 | portfolio | -0.2528 | -2.1113 | -0.2866 | 0.3661 | 49.40 |
| residual_momentum_reversal_v1 | -2.7499 | -2.7499 | True | eligible | 4 | 1 | portfolio | -0.2593 | -2.4780 | -0.2845 | 0.4039 | 29.22 |
| residual_momentum_reversal_v2 | -3.5346 | -3.5346 | True | eligible | 4 | 1 | portfolio | -0.3676 | -3.1566 | -0.3884 | 0.3672 | 65.22 |
| ma_kline_baseline_v1 | -3.9748 | -3.9748 | True | eligible | 4 | 1 | portfolio | -0.4203 | -3.5391 | -0.4512 | 0.3484 | 40.44 |

## Fold Details

| symbol | fold | train_start | train_end | valid_start | valid_end | annual_ret | sharpe | max_dd | win_rate | turnover_annual | trades | selected_params |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PORTFOLIO | 1 | 2019-07-30 | 2021-08-23 | 2021-08-24 | 2022-09-06 | -0.1117 | -0.9761 | -0.1960 | 0.4741 | 1.25 | 13 | mom5@q0.6,hold_q=0.4,buy_top=5,hold_top=10,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 2 | 2020-08-12 | 2022-09-06 | 2022-09-07 | 2023-09-19 | 0.1667 | 1.3865 | -0.0708 | 0.5020 | 1.17 | 13 | mom20@q0.6,hold_q=0.4,buy_top=5,hold_top=10,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 3 | 2021-08-24 | 2023-09-19 | 2023-09-20 | 2024-10-11 | 0.1014 | 0.7672 | -0.1059 | 0.4980 | 2.14 | 13 | mom20@q0.6,hold_q=0.4,buy_top=5,hold_top=10,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 4 | 2022-09-07 | 2024-10-11 | 2024-10-14 | 2025-10-24 | 0.2921 | 2.1039 | -0.0713 | 0.5259 | 1.39 | 16 | mom20@q0.6,hold_q=0.4,buy_top=5,hold_top=10,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
