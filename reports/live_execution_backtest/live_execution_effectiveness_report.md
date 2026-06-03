# Phase 0 实盘仿真回测 Effectiveness Gate

Generated at: 2026-06-03T17:35:47

Pipeline: 实盘仿真回测

Gate source: account_daily_assets

Overall verdict: FAIL

## Base Gate

| gate | status |
| --- | --- |
| selected_candidate_eligible == True | PASS |
| annualized_return_mean > 0.00 | PASS |
| sharpe_mean > 0.50 | PASS |
| max_drawdown_mean > -0.25 | PASS |
| win_rate_mean > 0.45 | PASS |
| oos_return_decay_ratio < 0.30 | PASS |

## Robustness Gate

| gate | status |
| --- | --- |
| oos_fold_count >= 2 | FAIL |
| oos_annualized_return_mean > 0.00 | PASS |
| oos_sharpe_mean > 0.50 | PASS |
| positive_fold_ratio >= 0.75 | PASS |
| negative_fold_count <= 1 | PASS |
| min_fold_annualized_return > -0.10 | FAIL |
| oos_positive_fold_ratio >= 1.00 | PASS |

## Execution Quality Gate

| gate | status |
| --- | --- |
| unfilled_or_partial_order_ratio <= 0.60 | FAIL |
| partial_fill_order_ratio <= 0.05 | PASS |
| stale_valuation_positions_total <= 0 | FAIL |

## Execution Config

| key | value |
| --- | --- |
| profile | live |
| slippage | 0.00246 |
| commission | 0.00025 |
| stamp_duty_sell | 0.0005 |
| price_mode | next_open |
| lot_size | 100 |
| max_participation_rate | 0.05 |
| enable_limit_check | True |
| enable_suspension_check | True |

## Snapshot

| metric | value |
| --- | --- |
| status | ok |
| selected_candidate | legacy_momentum_low_turnover_v1_account_execution_v2 |
| selected_candidate_eligible | True |
| selected_candidate_governance_reason | eligible |
| fold_count | 4 |
| symbol_count | 1 |
| annualized_return_mean | 0.06896090268749938 |
| sharpe_mean | 0.5085722597633263 |
| max_drawdown_mean | -0.12296583058771926 |
| win_rate_mean | 0.4900398406374502 |
| turnover_annual_mean | 0.0 |
| positive_fold_count | 3 |
| negative_fold_count | 1 |
| positive_fold_ratio | 0.75 |
| min_fold_annualized_return | -0.15389061644000024 |
| min_fold_sharpe | -1.423028967090842 |
| oos_fold_count | 1 |
| oos_annualized_return_mean | 0.22866954156999686 |
| oos_sharpe_mean | 1.756317690198075 |
| oos_positive_fold_count | 1 |
| oos_positive_fold_ratio | 1.0 |
| oos_min_fold_annualized_return | 0.22866954156999686 |
| oos_return_decay_ratio | -13.542070180386776 |
| executable_order_count | 5242 |
| unfilled_or_partial_order_count | 3733 |
| unfilled_or_partial_order_ratio | 0.7121327737504769 |
| partial_fill_order_count | 33 |
| partial_fill_order_ratio | 0.00629530713468142 |
| stale_valuation_positions_total | 9 |

## Account Simulation Stats

| metric | value |
| --- | --- |
| bill_rows | 5242 |
| daily_rows | 1008 |
| trade_status_counts | {'未成交': 3700, '全部成交': 1509, '部分成交': 33} |
| min_cash_assets | 293445.81 |
| unfilled_orders_total | 3733 |
| stale_valuation_positions_total | 9 |

## Fold Details

| fold | valid_start | valid_end | annual_ret | sharpe | max_dd | win_rate | trades | final_assets | unfilled_orders |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2021-08-24 | 2022-09-06 | -0.1539 | -1.4230 | -0.2215 | 0.4542 | 514 | 846109.38 | 790 |
| 2 | 2022-09-07 | 2023-09-19 | 0.1178 | 1.0403 | -0.0759 | 0.4900 | 375 | 1117779.71 | 947 |
| 3 | 2023-09-20 | 2024-10-11 | 0.0833 | 0.6607 | -0.1065 | 0.4980 | 414 | 1083284.98 | 920 |
| 4 | 2024-10-14 | 2025-10-24 | 0.2287 | 1.7563 | -0.0880 | 0.5179 | 239 | 1228669.54 | 1076 |
