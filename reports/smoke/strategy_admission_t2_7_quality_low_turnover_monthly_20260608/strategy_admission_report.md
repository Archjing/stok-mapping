# Strategy Admission Report

Generated at: 2026-06-08T21:00:36

## Scope

- Presets: `quality_3y_1y`
- Strategies: `quality_low_turnover_monthly_v1`

## Constraint Review

| strategy_id | action | window_pass | turnover_fail | param_unstable | industry_conc | overfit | reasons |
| --- | --- | --- | --- | --- | --- | --- | --- |
| quality_low_turnover_monthly_v1 | reject | 0/1 | 0 | 1 | 0 | critical | overfit risk is critical; selected parameters change too frequently in one or more windows; positive fold ratio below 75% in one or more windows |

## Window Matrix

| strategy_id | preset | status | folds | ann | sharpe | mdd | turnover | top1_ind | top3_ind | acct_ann | acct_sharpe | acct_orders | pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quality_low_turnover_monthly_v1 | quality_3y_1y | ok | 3 | -0.0496 | -0.4112 | -0.2157 | 1.85 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |

## Strategy Quality Diagnostics

| strategy_id | preset | pit_ann | field_cov | selected_field_cov | missing_blocked | quality_lift | cash_flow_evidence | failure_attribution |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quality_low_turnover_monthly_v1 | quality_3y_1y | 0.99 | 0.99 | 1.00 | 0.01 | 0.184 | use:cash_flow_quality | construction_or_regime: quality exposure did not convert to return |
