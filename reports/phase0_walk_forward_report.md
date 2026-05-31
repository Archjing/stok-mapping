# Phase 0 Walk-Forward Report

Generated at: 2026-05-31T18:59:23

## Summary

| metric | value |
| --- | --- |
| status | ok |
| fold_count | 4 |
| symbol_count | 1 |
| annualized_return_mean | 0.13312709618858617 |
| sharpe_mean | 1.008292015623601 |
| max_drawdown_mean | -0.10417008645710835 |
| win_rate_mean | 0.5109561752988048 |
| turnover_annual_mean | 1.5023090842074356 |
| selected_candidate | legacy_momentum_low_turnover_v1 |
| selected_candidate_eligible | True |
| selected_candidate_governance_reason | eligible |
| candidate_comparison | legacy_momentum: score=-0.6398, selection_score=-0.6398, eligible=True, ann=-0.0439, sharpe=-0.5082, mdd=-0.2193; legacy_momentum_low_turnover_v1: score=1.0228, selection_score=1.0228, eligible=True, ann=0.1331, sharpe=1.0083, mdd=-0.1042; ma_kline_baseline_v1: score=-4.0468, selection_score=-4.0468, eligible=True, ann=-0.4253, sharpe=-3.6044, mdd=-0.4596; residual_momentum_reversal_v1: score=-2.7442, selection_score=-2.7442, eligible=True, ann=-0.2525, sharpe=-2.4770, mdd=-0.2818; residual_momentum_reversal_v2: score=-3.2179, selection_score=-3.2179, eligible=True, ann=-0.3433, sharpe=-2.8521, mdd=-0.3883; quality_growth_price_v1: score=-1.5837, selection_score=-1.5837, eligible=True, ann=-0.1095, sharpe=-1.4224, mdd=-0.2130; multifactor_volume_price_filter_v1: score=-1.9371, selection_score=-1.9371, eligible=True, ann=-0.2059, sharpe=-1.7095, mdd=-0.2493 |
| oos_fold_count | 1 |
| oos_annualized_return_mean | 0.28334493863104626 |
| oos_sharpe_mean | 2.0430343095309547 |
| oos_return_decay_ratio | -2.411555062023421 |

## Candidate Summary

| candidate | score | selection_score | eligible | governance_reason | fold_count | symbol_count | panel_scope | annualized_return_mean | sharpe_mean | max_drawdown_mean | win_rate_mean | turnover_annual_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| legacy_momentum_low_turnover_v1 | 1.0228 | 1.0228 | True | eligible | 4 | 1 | portfolio | 0.1331 | 1.0083 | -0.1042 | 0.5110 | 1.50 |
| legacy_momentum | -0.6398 | -0.6398 | True | eligible | 4 | 1 | portfolio | -0.0439 | -0.5082 | -0.2193 | 0.4486 | 13.48 |
| quality_growth_price_v1 | -1.5837 | -1.5837 | True | eligible | 4 | 1 | portfolio | -0.1095 | -1.4224 | -0.2130 | 0.4381 | 24.79 |
| multifactor_volume_price_filter_v1 | -1.9371 | -1.9371 | True | eligible | 4 | 1 | portfolio | -0.2059 | -1.7095 | -0.2493 | 0.3799 | 44.58 |
| residual_momentum_reversal_v1 | -2.7442 | -2.7442 | True | eligible | 4 | 1 | portfolio | -0.2525 | -2.4770 | -0.2818 | 0.4057 | 30.00 |
| residual_momentum_reversal_v2 | -3.2179 | -3.2179 | True | eligible | 4 | 1 | portfolio | -0.3433 | -2.8521 | -0.3883 | 0.3634 | 63.41 |
| ma_kline_baseline_v1 | -4.0468 | -4.0468 | True | eligible | 4 | 1 | portfolio | -0.4253 | -3.6044 | -0.4596 | 0.3513 | 40.34 |

## Fold Details

| symbol | fold | train_start | train_end | valid_start | valid_end | annual_ret | sharpe | max_dd | win_rate | turnover_annual | trades | selected_params |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PORTFOLIO | 1 | 2019-07-30 | 2021-08-23 | 2021-08-24 | 2022-09-06 | -0.0326 | -0.2618 | -0.1624 | 0.5139 | 1.15 | 13 | mom20@q0.6,hold_q=0.4,buy_top=10,hold_top=20,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 2 | 2020-08-12 | 2022-09-06 | 2022-09-07 | 2023-09-19 | 0.1667 | 1.3865 | -0.0708 | 0.5020 | 1.17 | 13 | mom20@q0.6,hold_q=0.4,buy_top=5,hold_top=10,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 3 | 2021-08-24 | 2023-09-19 | 2023-09-20 | 2024-10-11 | 0.1150 | 0.8654 | -0.1059 | 0.5020 | 2.28 | 13 | mom20@q0.6,hold_q=0.4,buy_top=5,hold_top=10,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 4 | 2022-09-07 | 2024-10-11 | 2024-10-14 | 2025-10-24 | 0.2833 | 2.0430 | -0.0776 | 0.5259 | 1.40 | 16 | mom20@q0.6,hold_q=0.4,buy_top=5,hold_top=10,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
