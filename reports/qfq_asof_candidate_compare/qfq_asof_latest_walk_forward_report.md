# Phase 0 Walk-Forward Report

Generated at: 2026-06-04T01:51:49

## Universe Guard

Historical walk-forward uses a fold-local point-in-time universe when `universe_mode=point_in_time`; live watchlist and simulated account reports keep using the current daily universe.

## Summary

| metric | value |
| --- | --- |
| status | ok |
| universe_mode | point_in_time |
| universe_lookahead_guard | True |
| fold_count | 4 |
| symbol_count | 1 |
| annualized_return_mean | -0.07512389588338875 |
| sharpe_mean | -0.7304120080968161 |
| max_drawdown_mean | -0.167112184137096 |
| win_rate_mean | 0.44920318725099606 |
| turnover_annual_mean | 2.205557552836356 |
| positive_fold_count | 0 |
| negative_fold_count | 4 |
| positive_fold_ratio | 0.0 |
| min_fold_annualized_return | -0.18087116380721457 |
| min_fold_sharpe | -1.8877032767212565 |
| selected_candidate | legacy_momentum_low_turnover_v1 |
| selected_candidate_eligible | True |
| selected_candidate_governance_reason | eligible |
| candidate_comparison | legacy_momentum: score=-2.8335, selection_score=-2.8335, eligible=True, ann=-0.2913, sharpe=-2.5194, mdd=-0.3367; legacy_momentum_low_turnover_v1: score=-0.8515, selection_score=-0.8515, eligible=True, ann=-0.0751, sharpe=-0.7304, mdd=-0.1671; ma_kline_baseline_v1: score=-4.9341, selection_score=-4.9341, eligible=True, ann=-0.4979, sharpe=-4.4299, mdd=-0.5106; residual_momentum_reversal_v2: score=-4.6987, selection_score=-4.6987, eligible=True, ann=-0.4487, sharpe=-4.2381, mdd=-0.4725; quality_growth_price_v1: score=-2.4859, selection_score=-2.4859, eligible=True, ann=-0.1995, sharpe=-2.2612, mdd=-0.2499; multifactor_volume_price_filter_v1: score=-2.0736, selection_score=-2.0736, eligible=True, ann=-0.1853, sharpe=-1.8785, mdd=-0.2050 |
| universe_fold_count | 4 |
| universe_symbol_count_mean | 120.0 |
| universe_symbol_count_min | 120 |
| universe_source | local_history_sqlite_as_of |
| oos_fold_count | 1 |
| oos_annualized_return_mean | -0.0073414571857095545 |
| oos_sharpe_mean | 0.012938288989621937 |
| oos_positive_fold_count | 0 |
| oos_positive_fold_ratio | 0.0 |
| oos_min_fold_annualized_return | -0.0073414571857095545 |
| oos_return_decay_ratio | -0.9248710163779329 |

## Candidate Summary

| candidate | score | selection_score | eligible | governance_reason | fold_count | symbol_count | panel_scope | annualized_return_mean | sharpe_mean | max_drawdown_mean | win_rate_mean | turnover_annual_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| legacy_momentum_low_turnover_v1 | -0.8515 | -0.8515 | True | eligible | 4 | 1 | portfolio | -0.0751 | -0.7304 | -0.1671 | 0.4492 | 2.21 |
| multifactor_volume_price_filter_v1 | -2.0736 | -2.0736 | True | eligible | 4 | 1 | portfolio | -0.1853 | -1.8785 | -0.2050 | 0.3775 | 41.33 |
| quality_growth_price_v1 | -2.4859 | -2.4859 | True | eligible | 4 | 1 | portfolio | -0.1995 | -2.2612 | -0.2499 | 0.4063 | 25.85 |
| legacy_momentum | -2.8335 | -2.8335 | True | eligible | 4 | 1 | portfolio | -0.2913 | -2.5194 | -0.3367 | 0.4014 | 15.64 |
| residual_momentum_reversal_v2 | -4.6987 | -4.6987 | True | eligible | 4 | 1 | portfolio | -0.4487 | -4.2381 | -0.4725 | 0.3406 | 72.18 |
| ma_kline_baseline_v1 | -4.9341 | -4.9341 | True | eligible | 4 | 1 | portfolio | -0.4979 | -4.4299 | -0.5106 | 0.3312 | 46.04 |

## Fold Details

| symbol | fold | train_start | train_end | valid_start | valid_end | annual_ret | sharpe | max_dd | win_rate | turnover_annual | trades | selected_params |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PORTFOLIO | 1 | 2019-07-31 | 2021-05-31 | 2021-06-01 | 2022-06-15 | -0.0719 | -0.6960 | -0.1589 | 0.4940 | 1.07 | 15 | mom5@q0.6,hold_q=0.4,buy_top=10,hold_top=20,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 2 | 2020-05-19 | 2022-06-15 | 2022-06-16 | 2023-06-28 | -0.1809 | -1.8877 | -0.2192 | 0.4223 | 2.20 | 51 | mom5@q0.6,hold_q=0.4,buy_top=10,hold_top=20,rebalance=5d,min_hold=10d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 3 | 2021-06-01 | 2023-06-28 | 2023-06-29 | 2024-07-11 | -0.0404 | -0.3509 | -0.1324 | 0.4183 | 3.76 | 51 | mom5@q0.6,hold_q=0.4,buy_top=10,hold_top=20,rebalance=5d,min_hold=10d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 4 | 2022-06-16 | 2024-07-11 | 2024-07-12 | 2025-07-25 | -0.0073 | 0.0129 | -0.1580 | 0.4622 | 1.80 | 13 | mom5@q0.6,hold_q=0.4,buy_top=10,hold_top=20,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
