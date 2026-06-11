# Strategy Admission Report

Generated at: 2026-06-10T01:35:37

## Scope

- Presets: `baseline_2y_1y_5fold, quality_3y_1y_4fold`
- Strategy scope source: `cli_strategies`
- Strategy set: ``
- Strategies: `quality_low_turnover_monthly_v1`
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

| strategy_id | action | window_pass | turnover_fail | param_unstable | industry_missing | industry_conc | factor_missing | price_fail | overfit | reasons |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quality_low_turnover_monthly_v1 | reject | 0/2 | 0 | 1 | 0 | 2 | 0 | 0 | critical | overfit risk is critical; selected parameters change too frequently in one or more windows; industry concentration exceeds audit threshold in one or more windows; positive fold ratio below 75% in one or more windows |

## Window Matrix

| strategy_id | preset | status | folds | window | expected | actual | warning | price_status | ann | sharpe | mdd | turnover | industry_status | top1_ind | top3_ind | account_status | acct_ann | acct_sharpe | acct_orders | pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quality_low_turnover_monthly_v1 | baseline_2y_1y_5fold | ok | 5 | 2019-04-01~2026-03-31 | 5 | 5 |  | qfq_asof | -0.0471 | -0.4244 | -0.1701 | 2.03 | enabled:audited | 0.14 | 0.29 | not_enabled | n/a | n/a | n/a | False |
| quality_low_turnover_monthly_v1 | quality_3y_1y_4fold | ok | 4 | 2019-04-01~2026-03-31 | 4 | 4 |  | qfq_asof | -0.0123 | -0.1685 | -0.1531 | 1.59 | enabled:audited | 0.13 | 0.30 | not_enabled | n/a | n/a | n/a | False |

## Strategy Quality Diagnostics

| strategy_id | preset | status | pit_ann | field_cov | selected_field_cov | missing_blocked | quality_lift | cash_flow_evidence | failure_attribution |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quality_low_turnover_monthly_v1 | baseline_2y_1y_5fold | available | 1.00 | 1.00 | 1.00 | 0.00 | 0.184 | use:cash_flow_quality | construction_or_regime: quality exposure did not convert to return |
| quality_low_turnover_monthly_v1 | quality_3y_1y_4fold | available | 1.00 | 1.00 | 1.00 | 0.00 | 0.161 | use:cash_flow_quality | construction_or_regime: quality exposure did not convert to return |
