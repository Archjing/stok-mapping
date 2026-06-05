# Phase 0 Walk-Forward Report

Generated at: 2026-06-05T09:22:33

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
| annualized_return_mean | -0.025532506411103884 |
| sharpe_mean | -0.2432513671297904 |
| max_drawdown_mean | -0.14465572657744502 |
| win_rate_mean | 0.4820717131474104 |
| turnover_annual_mean | 2.1039271245251743 |
| positive_fold_count | 2 |
| negative_fold_count | 2 |
| positive_fold_ratio | 0.5 |
| min_fold_annualized_return | -0.10573668205755271 |
| min_fold_sharpe | -0.9920788327043395 |
| selected_candidate | legacy_momentum_low_turnover_v1 |
| selected_candidate_eligible | True |
| selected_candidate_governance_reason | eligible |
| candidate_comparison | legacy_momentum: score=-2.5362, selection_score=-2.5362, eligible=True, ann=-0.2664, sharpe=-2.2413, mdd=-0.3233; legacy_momentum_low_turnover_v1: score=-0.3283, selection_score=-0.3283, eligible=True, ann=-0.0255, sharpe=-0.2433, mdd=-0.1447; ma_kline_baseline_v1: score=-4.7518, selection_score=-4.7518, eligible=True, ann=-0.4824, sharpe=-4.2597, mdd=-0.5018; residual_momentum_reversal_v1: score=-3.3162, selection_score=-3.3162, eligible=True, ann=-0.3004, sharpe=-3.0075, mdd=-0.3170; residual_momentum_reversal_v2: score=-5.5284, selection_score=-5.5284, eligible=True, ann=-0.4960, sharpe=-5.0267, mdd=-0.5074; quality_growth_price_v1: score=-2.2383, selection_score=-2.2383, eligible=True, ann=-0.1675, sharpe=-2.0362, mdd=-0.2366; multifactor_volume_price_filter_v1: score=-1.8829, selection_score=-1.8829, eligible=True, ann=-0.1736, sharpe=-1.6975, mdd=-0.1972 |
| universe_fold_count | 4 |
| universe_symbol_count_mean | 120.0 |
| universe_symbol_count_min | 120 |
| universe_source | local_history_sqlite_as_of |
| oos_fold_count | 1 |
| oos_annualized_return_mean | 0.04085704284890257 |
| oos_sharpe_mean | 0.36759750664643603 |
| oos_positive_fold_count | 1 |
| oos_positive_fold_ratio | 1.0 |
| oos_min_fold_annualized_return | 0.04085704284890257 |
| oos_return_decay_ratio | -1.857218277416713 |

## Candidate Summary

| candidate | score | selection_score | eligible | governance_reason | fold_count | symbol_count | panel_scope | annualized_return_mean | sharpe_mean | max_drawdown_mean | win_rate_mean | turnover_annual_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| legacy_momentum_low_turnover_v1 | -0.3283 | -0.3283 | True | eligible | 4 | 1 | portfolio | -0.0255 | -0.2433 | -0.1447 | 0.4821 | 2.10 |
| multifactor_volume_price_filter_v1 | -1.8829 | -1.8829 | True | eligible | 4 | 1 | portfolio | -0.1736 | -1.6975 | -0.1972 | 0.3507 | 38.74 |
| quality_growth_price_v1 | -2.2383 | -2.2383 | True | eligible | 4 | 1 | portfolio | -0.1675 | -2.0362 | -0.2366 | 0.4133 | 23.57 |
| legacy_momentum | -2.5362 | -2.5362 | True | eligible | 4 | 1 | portfolio | -0.2664 | -2.2413 | -0.3233 | 0.4124 | 15.11 |
| residual_momentum_reversal_v1 | -3.3162 | -3.3162 | True | eligible | 4 | 1 | portfolio | -0.3004 | -3.0075 | -0.3170 | 0.3849 | 28.66 |
| ma_kline_baseline_v1 | -4.7518 | -4.7518 | True | eligible | 4 | 1 | portfolio | -0.4824 | -4.2597 | -0.5018 | 0.3451 | 42.09 |
| residual_momentum_reversal_v2 | -5.5284 | -5.5284 | True | eligible | 4 | 1 | portfolio | -0.4960 | -5.0267 | -0.5074 | 0.3290 | 64.05 |

## Fold Details

| symbol | fold | train_start | train_end | valid_start | valid_end | annual_ret | sharpe | max_dd | win_rate | turnover_annual | trades | selected_params |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PORTFOLIO | 1 | 2019-08-01 | 2021-06-01 | 2021-06-02 | 2022-06-16 | -0.1057 | -0.9240 | -0.2322 | 0.4741 | 2.17 | 56 | mom20@q0.6,hold_q=0.4,buy_top=10,hold_top=20,rebalance=5d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 2 | 2020-05-20 | 2022-06-16 | 2022-06-17 | 2023-06-29 | -0.0906 | -0.9921 | -0.1299 | 0.4861 | 1.07 | 13 | mom20@q0.6,hold_q=0.4,buy_top=10,hold_top=20,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 3 | 2021-06-02 | 2023-06-29 | 2023-06-30 | 2024-07-12 | 0.0533 | 0.5755 | -0.0739 | 0.4821 | 1.74 | 13 | mom20@q0.6,hold_q=0.4,buy_top=5,hold_top=10,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 4 | 2022-06-17 | 2024-07-12 | 2024-07-15 | 2025-07-28 | 0.0409 | 0.3676 | -0.1427 | 0.4861 | 3.42 | 26 | mom5@q0.6,hold_q=0.4,buy_top=10,hold_top=20,rebalance=10d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
