# Strategy Admission Report

Generated at: 2026-06-26T01:09:47

## Scope

- Presets: `baseline_2y_1y_5fold`
- Strategy scope source: `strategy_set`
- Strategy set: `i51_strong_market_benchmark_aware_core_v1`
- Strategies: `strong_market_benchmark_aware_core_v1`
- Diagnostics suites: `data_quality_v1, execution_feasibility_v1, factor_explainability_v1, overfit_v1`

## Global Admission Gate

| gate | value |
| --- | --- |
| annualized_return_min | 0.0 |
| sharpe_min | 0.5 |
| max_drawdown_min | -0.25 |
| positive_fold_ratio_min | 0.75 |
| turnover_annual_mean_max | 3.0 |
| turnover_annual_max_max | 5.0 |
| overfit_risk_max | medium |
| require_parameter_stability | True |
| require_industry_concentration_check | True |
| require_factor_diagnostics | True |
| require_qfq_asof | True |

## Constraint Review

| strategy_id | action | window_pass | turnover_fail | param_unstable | industry_missing | industry_conc | factor_missing | price_fail | paper_trade | overfit | reasons |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| strong_market_benchmark_aware_core_v1 | reject | 0/1 | 0 | 0 | 0 | 1 | 0 | 0 | False | high | overfit risk is high; industry concentration exceeds audit threshold in one or more windows; strategy does not support paper trade review; positive fold ratio below 75% in one or more windows |

## Window Matrix

| strategy_id | preset | status | folds | window | expected | actual | warning | price_status | ann | sharpe | mdd | turnover | industry_status | top1_ind | top3_ind | account_status | acct_ann | acct_sharpe | acct_orders | pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| strong_market_benchmark_aware_core_v1 | baseline_2y_1y_5fold | ok | 5 | 2019-04-01~2026-03-31 | 5 | 5 |  | qfq_asof | -0.0009 | -0.1011 | -0.0705 | 0.59 | enabled:audited | 0.03 | 0.08 | not_enabled | n/a | n/a | n/a | False |

## Benchmark / Excess Diagnostics

Supplemental only: these relative benchmark fields explain regime-adjusted behavior and do not change `is_window_pass` or `admission_action` in this run.

| strategy_id | preset | benchmark_status | bench_folds | bench_ann | excess_ann | excess_min | pos_abs | pos_excess | neg_abs | neg_pos_excess | neg_neg_excess | neg_bench_na |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| strong_market_benchmark_aware_core_v1 | baseline_2y_1y_5fold | available | 5 | -0.0278 | 0.0269 | -0.1084 | 0.40 | 0.60 | 3 | 3 | 0 | 0 |

## Strategy Quality Diagnostics

| strategy_id | preset | status | pit_ann | field_cov | selected_field_cov | missing_blocked | quality_lift | cash_flow_evidence | failure_attribution |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| strong_market_benchmark_aware_core_v1 | baseline_2y_1y_5fold | not_applicable | n/a | n/a | n/a | n/a | n/a | use:cash_flow_quality | not_applicable |
