# Phase 0 Account Execution Effectiveness Gate

Generated at: 2026-06-01T00:04:59

Overall verdict: PASS

## Gate

| gate | status |
| --- | --- |
| selected_candidate_eligible == True | PASS |
| annualized_return_mean > 0 | PASS |
| sharpe_mean > 0.5 | PASS |
| max_drawdown_mean > -0.25 | PASS |
| win_rate_mean > 0.45 | PASS |
| oos_return_decay_ratio < 0.30 | PASS |

## Execution Config

| key | value |
| --- | --- |
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
| annualized_return_mean | 0.09179996960749917 |
| sharpe_mean | 0.7157427262141763 |
| max_drawdown_mean | -0.11522274522994766 |
| win_rate_mean | 0.5059760956175299 |
| turnover_annual_mean | 0.0 |
| oos_fold_count | 1 |
| oos_annualized_return_mean | 0.2254698867399989 |
| oos_sharpe_mean | 1.731762672536552 |
| oos_return_decay_ratio | -3.7725231064677502 |

## Account Simulation Stats

| metric | value |
| --- | --- |
| bill_rows | 6369 |
| daily_rows | 1008 |
| trade_status_counts | {'未成交': 4739, '全部成交': 1605, '部分成交': 25} |
| min_cash_assets | 309034.53 |
| unfilled_orders_total | 4764 |
| stale_valuation_positions_total | 9 |

## Fold Details

| fold | valid_start | valid_end | annual_ret | sharpe | max_dd | win_rate | trades | final_assets | unfilled_orders |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2021-08-24 | 2022-09-06 | -0.0707 | -0.6552 | -0.1865 | 0.5139 | 615 | 929280.71 | 1803 |
| 2 | 2022-09-07 | 2023-09-19 | 0.1178 | 1.0403 | -0.0759 | 0.4900 | 375 | 1117779.71 | 947 |
| 3 | 2023-09-20 | 2024-10-11 | 0.0947 | 0.7461 | -0.1069 | 0.4980 | 399 | 1094669.57 | 938 |
| 4 | 2024-10-14 | 2025-10-24 | 0.2255 | 1.7318 | -0.0917 | 0.5219 | 241 | 1225469.89 | 1076 |
