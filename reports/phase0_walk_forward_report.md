# Phase 0 Walk-Forward Report

Generated at: 2026-06-03T21:51:08

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
| annualized_return_mean | 0.01720626072664841 |
| sharpe_mean | 0.010184350245621643 |
| max_drawdown_mean | -0.10893979140221807 |
| win_rate_mean | 0.4621513944223108 |
| turnover_annual_mean | 1.8732107860640914 |
| positive_fold_count | 3 |
| negative_fold_count | 1 |
| positive_fold_ratio | 0.75 |
| min_fold_annualized_return | -0.14670077704842488 |
| min_fold_sharpe | -1.533148050529403 |
| selected_candidate | legacy_momentum_low_turnover_v1 |
| selected_candidate_eligible | True |
| selected_candidate_governance_reason | eligible |
| candidate_comparison | legacy_momentum: score=-2.4680, selection_score=-2.4680, eligible=True, ann=-0.2571, sharpe=-2.1792, mdd=-0.3204; legacy_momentum_low_turnover_v1: score=-0.0357, selection_score=-0.0357, eligible=True, ann=0.0172, sharpe=0.0102, mdd=-0.1089; ma_kline_baseline_v1: score=-4.6233, selection_score=-4.6233, eligible=True, ann=-0.4733, sharpe=-4.1393, mdd=-0.4947; residual_momentum_reversal_v1: score=-3.4191, selection_score=-3.4191, eligible=True, ann=-0.3181, sharpe=-3.0893, mdd=-0.3415; residual_momentum_reversal_v2: score=-4.3548, selection_score=-4.3548, eligible=True, ann=-0.4300, sharpe=-3.9108, mdd=-0.4580; quality_growth_price_v1: score=-2.8104, selection_score=-2.8104, eligible=True, ann=-0.2226, sharpe=-2.5648, mdd=-0.2686; multifactor_volume_price_filter_v1: score=-2.4613, selection_score=-2.4613, eligible=True, ann=-0.1687, sharpe=-2.2864, mdd=-0.1813 |
| universe_fold_count | 4 |
| universe_symbol_count_mean | 120.0 |
| universe_symbol_count_min | 120 |
| universe_source | local_history_sqlite_as_of |
| oos_fold_count | 1 |
| oos_annualized_return_mean | 0.17335412856165466 |
| oos_sharpe_mean | 1.0658456032586796 |
| oos_positive_fold_count | 1 |
| oos_positive_fold_ratio | 1.0 |
| oos_min_fold_annualized_return | 0.17335412856165466 |
| oos_return_decay_ratio | -5.975288767005338 |

## Candidate Summary

| candidate | score | selection_score | eligible | governance_reason | fold_count | symbol_count | panel_scope | annualized_return_mean | sharpe_mean | max_drawdown_mean | win_rate_mean | turnover_annual_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| legacy_momentum_low_turnover_v1 | -0.0357 | -0.0357 | True | eligible | 4 | 1 | portfolio | 0.0172 | 0.0102 | -0.1089 | 0.4622 | 1.87 |
| multifactor_volume_price_filter_v1 | -2.4613 | -2.4613 | True | eligible | 4 | 1 | portfolio | -0.1687 | -2.2864 | -0.1813 | 0.3579 | 38.86 |
| legacy_momentum | -2.4680 | -2.4680 | True | eligible | 4 | 1 | portfolio | -0.2571 | -2.1792 | -0.3204 | 0.4074 | 15.10 |
| quality_growth_price_v1 | -2.8104 | -2.8104 | True | eligible | 4 | 1 | portfolio | -0.2226 | -2.5648 | -0.2686 | 0.4085 | 23.17 |
| residual_momentum_reversal_v1 | -3.4191 | -3.4191 | True | eligible | 4 | 1 | portfolio | -0.3181 | -3.0893 | -0.3415 | 0.3869 | 29.82 |
| residual_momentum_reversal_v2 | -4.3548 | -4.3548 | True | eligible | 4 | 1 | portfolio | -0.4300 | -3.9108 | -0.4580 | 0.3631 | 62.34 |
| ma_kline_baseline_v1 | -4.6233 | -4.6233 | True | eligible | 4 | 1 | portfolio | -0.4733 | -4.1393 | -0.4947 | 0.3392 | 43.75 |

## Fold Details

| symbol | fold | train_start | train_end | valid_start | valid_end | annual_ret | sharpe | max_dd | win_rate | turnover_annual | trades | selected_params |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PORTFOLIO | 1 | 2019-07-30 | 2021-05-28 | 2021-05-31 | 2022-06-14 | 0.0060 | 0.1092 | -0.1057 | 0.4940 | 1.76 | 27 | mom5@q0.6,hold_q=0.4,buy_top=10,hold_top=20,rebalance=10d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 2 | 2020-05-18 | 2022-06-14 | 2022-06-15 | 2023-06-27 | -0.1467 | -1.5331 | -0.1580 | 0.4183 | 2.13 | 51 | mom5@q0.6,hold_q=0.4,buy_top=10,hold_top=20,rebalance=5d,min_hold=10d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 3 | 2021-05-31 | 2023-06-27 | 2023-06-28 | 2024-07-10 | 0.0362 | 0.3988 | -0.0814 | 0.4781 | 1.51 | 13 | mom20@q0.6,hold_q=0.4,buy_top=5,hold_top=10,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 4 | 2022-06-15 | 2024-07-10 | 2024-07-11 | 2025-07-24 | 0.1734 | 1.0658 | -0.0907 | 0.4582 | 2.09 | 13 | mom20@q0.6,hold_q=0.4,buy_top=5,hold_top=10,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
