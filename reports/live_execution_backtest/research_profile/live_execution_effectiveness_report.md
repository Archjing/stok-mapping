# Phase 0 实盘仿真回测 Effectiveness Gate

Generated at: 2026-06-01T00:12:26

Pipeline: 策略研究回测

Gate source: account_daily_assets

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
| profile | research |
| slippage | 0.001 |
| commission | 0.00025 |
| stamp_duty_sell | 0.0005 |
| price_mode | close |
| lot_size | 100 |
| max_participation_rate | 0.0 |
| enable_limit_check | False |
| enable_suspension_check | False |

## Snapshot

| metric | value |
| --- | --- |
| status | ok |
| selected_candidate | legacy_momentum_low_turnover_v1_account_execution_v2 |
| selected_candidate_eligible | True |
| selected_candidate_governance_reason | eligible |
| fold_count | 4 |
| symbol_count | 1 |
| annualized_return_mean | 0.14244275537500065 |
| sharpe_mean | 1.0863172611838068 |
| max_drawdown_mean | -0.10015818976522836 |
| win_rate_mean | 0.5139442231075697 |
| turnover_annual_mean | 0.0 |
| oos_fold_count | 1 |
| oos_annualized_return_mean | 0.29524467399999965 |
| oos_sharpe_mean | 2.1390303143593665 |
| oos_return_decay_ratio | -2.226408066351407 |

## Account Simulation Stats

| metric | value |
| --- | --- |
| bill_rows | 6287 |
| daily_rows | 1008 |
| trade_status_counts | {'未成交': 4674, '全部成交': 1613} |
| min_cash_assets | 329837.07 |
| unfilled_orders_total | 4674 |
| stale_valuation_positions_total | 9 |

## Fold Details

| fold | valid_start | valid_end | annual_ret | sharpe | max_dd | win_rate | trades | final_assets | unfilled_orders |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2021-08-24 | 2022-09-06 | -0.0107 | -0.0521 | -0.1411 | 0.5179 | 613 | 989314.26 | 1762 |
| 2 | 2022-09-07 | 2023-09-19 | 0.1219 | 1.0673 | -0.0716 | 0.4980 | 370 | 1121936.17 | 932 |
| 3 | 2023-09-20 | 2024-10-11 | 0.1633 | 1.1910 | -0.1017 | 0.5060 | 391 | 1163275.93 | 915 |
| 4 | 2024-10-14 | 2025-10-24 | 0.2952 | 2.1390 | -0.0862 | 0.5339 | 239 | 1295244.67 | 1065 |
