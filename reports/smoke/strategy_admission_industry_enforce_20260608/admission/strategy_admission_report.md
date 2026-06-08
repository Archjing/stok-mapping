# Strategy Admission Report

Generated at: 2026-06-08T20:34:55

## Scope

- Presets: `quality_3y_1y`
- Strategies: `low_vol_low_turnover_quality_v1`

## Constraint Review

| strategy_id | action | window_pass | turnover_fail | param_unstable | industry_conc | overfit | reasons |
| --- | --- | --- | --- | --- | --- | --- | --- |
| low_vol_low_turnover_quality_v1 | reject | 0/1 | 0 | 0 | 0 | critical | overfit risk is critical; positive fold ratio below 75% in one or more windows |

## Window Matrix

| strategy_id | preset | status | folds | ann | sharpe | mdd | turnover | top1_ind | top3_ind | acct_ann | acct_sharpe | acct_orders | pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| low_vol_low_turnover_quality_v1 | quality_3y_1y | ok | 3 | -0.0165 | -0.2510 | -0.1644 | 2.16 | 0.11 | 0.27 | -0.0234 | -0.3861 | 1152 | False |
