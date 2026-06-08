# Strategy Admission Report

Generated at: 2026-06-09T03:54:35

## Scope

- Presets: `quality_4y_1y`
- Strategy scope source: `strategy_set`
- Strategy set: `baseline_admission_all_v1`
- Strategies: `legacy_momentum, legacy_momentum_low_turnover_v1, ma_kline_baseline_v1, residual_momentum_reversal_v1, residual_momentum_reversal_v2, quality_growth_price_v1, low_vol_low_turnover_quality_v1, quality_low_turnover_monthly_v1, multifactor_volume_price_filter_v1, core_selection_quality_momentum_v1, theme_exposure_momentum_v1`
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

## Constraint Review

| strategy_id | action | window_pass | turnover_fail | param_unstable | industry_conc | overfit | reasons |
| --- | --- | --- | --- | --- | --- | --- | --- |
| core_selection_quality_momentum_v1 | reject | 0/1 | 1 | 0 | 0 | high | overfit risk is high; annual turnover exceeds threshold in one or more windows; positive fold ratio below 75% in one or more windows |
| legacy_momentum | reject | 0/1 | 1 | 0 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; positive fold ratio below 75% in one or more windows |
| legacy_momentum_low_turnover_v1 | reject | 0/1 | 0 | 0 | 0 | medium | positive fold ratio below 75% in one or more windows |
| low_vol_low_turnover_quality_v1 | reject | 0/1 | 0 | 0 | 0 | medium | positive fold ratio below 75% in one or more windows |
| ma_kline_baseline_v1 | reject | 0/1 | 1 | 0 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; positive fold ratio below 75% in one or more windows |
| multifactor_volume_price_filter_v1 | reject | 0/1 | 1 | 0 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; positive fold ratio below 75% in one or more windows |
| quality_growth_price_v1 | reject | 0/1 | 1 | 0 | 0 | high | overfit risk is high; annual turnover exceeds threshold in one or more windows; positive fold ratio below 75% in one or more windows |
| quality_low_turnover_monthly_v1 | reject | 0/1 | 0 | 0 | 0 | medium | positive fold ratio below 75% in one or more windows |
| residual_momentum_reversal_v1 | reject | 0/1 | 1 | 0 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; positive fold ratio below 75% in one or more windows |
| residual_momentum_reversal_v2 | reject | 0/1 | 1 | 0 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; positive fold ratio below 75% in one or more windows |
| theme_exposure_momentum_v1 | reject | 0/1 | 1 | 0 | 0 | high | overfit risk is high; annual turnover exceeds threshold in one or more windows; positive fold ratio below 75% in one or more windows |

## Window Matrix

| strategy_id | preset | status | folds | window | expected | actual | warning | ann | sharpe | mdd | turnover | top1_ind | top3_ind | acct_ann | acct_sharpe | acct_orders | pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| legacy_momentum | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | -0.1639 | -1.0445 | -0.2497 | 16.39 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| legacy_momentum_low_turnover_v1 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | 0.0859 | 0.5142 | -0.1701 | 2.81 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| ma_kline_baseline_v1 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | -0.4523 | -3.5553 | -0.5060 | 46.11 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| residual_momentum_reversal_v1 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | -0.2898 | -2.6653 | -0.3658 | 31.39 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| residual_momentum_reversal_v2 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | -0.4470 | -3.6332 | -0.4457 | 80.30 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| quality_growth_price_v1 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | -0.0293 | -0.3358 | -0.1728 | 24.04 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| low_vol_low_turnover_quality_v1 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | 0.0992 | 0.8121 | -0.1237 | 2.23 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| quality_low_turnover_monthly_v1 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | 0.0803 | 0.7673 | -0.1330 | 2.04 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| multifactor_volume_price_filter_v1 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | -0.1872 | -1.5426 | -0.2420 | 49.85 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| core_selection_quality_momentum_v1 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | -0.0247 | -0.2001 | -0.1300 | 9.25 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| theme_exposure_momentum_v1 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | -0.0162 | -0.3315 | -0.1554 | 51.73 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |

## Strategy Quality Diagnostics

| strategy_id | preset | pit_ann | field_cov | selected_field_cov | missing_blocked | quality_lift | cash_flow_evidence | failure_attribution |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| legacy_momentum | quality_4y_1y | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
| legacy_momentum_low_turnover_v1 | quality_4y_1y | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
| ma_kline_baseline_v1 | quality_4y_1y | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
| residual_momentum_reversal_v1 | quality_4y_1y | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
| residual_momentum_reversal_v2 | quality_4y_1y | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
| quality_growth_price_v1 | quality_4y_1y | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
| low_vol_low_turnover_quality_v1 | quality_4y_1y | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
| quality_low_turnover_monthly_v1 | quality_4y_1y | 1.00 | 1.00 | 1.00 | 0.00 | 0.175 | use:cash_flow_quality | passed |
| multifactor_volume_price_filter_v1 | quality_4y_1y | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
| core_selection_quality_momentum_v1 | quality_4y_1y | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
| theme_exposure_momentum_v1 | quality_4y_1y | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
