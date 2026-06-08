# Strategy Admission Report

Generated at: 2026-06-09T03:24:33

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
| core_selection_quality_momentum_v1 | reject | 0/1 | 1 | 1 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; selected parameters change too frequently in one or more windows; positive fold ratio below 75% in one or more windows |
| legacy_momentum | reject | 0/1 | 1 | 0 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; positive fold ratio below 75% in one or more windows |
| legacy_momentum_low_turnover_v1 | reject | 0/1 | 0 | 0 | 0 | medium | positive fold ratio below 75% in one or more windows |
| low_vol_low_turnover_quality_v1 | reject | 0/1 | 0 | 1 | 0 | medium | selected parameters change too frequently in one or more windows; positive fold ratio below 75% in one or more windows |
| ma_kline_baseline_v1 | reject | 0/1 | 1 | 1 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; selected parameters change too frequently in one or more windows; positive fold ratio below 75% in one or more windows |
| multifactor_volume_price_filter_v1 | reject | 0/1 | 1 | 1 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; selected parameters change too frequently in one or more windows; positive fold ratio below 75% in one or more windows |
| quality_growth_price_v1 | reject | 0/1 | 1 | 0 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; positive fold ratio below 75% in one or more windows |
| quality_low_turnover_monthly_v1 | reject | 0/1 | 0 | 1 | 0 | medium | selected parameters change too frequently in one or more windows; positive fold ratio below 75% in one or more windows |
| residual_momentum_reversal_v1 | reject | 0/1 | 1 | 1 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; selected parameters change too frequently in one or more windows; positive fold ratio below 75% in one or more windows |
| residual_momentum_reversal_v2 | reject | 0/1 | 1 | 1 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; selected parameters change too frequently in one or more windows; positive fold ratio below 75% in one or more windows |
| theme_exposure_momentum_v1 | reject | 0/1 | 1 | 1 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; selected parameters change too frequently in one or more windows; positive fold ratio below 75% in one or more windows |

## Window Matrix

| strategy_id | preset | status | folds | window | expected | actual | warning | ann | sharpe | mdd | turnover | top1_ind | top3_ind | acct_ann | acct_sharpe | acct_orders | pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| legacy_momentum | quality_4y_1y | ok | 3 | ~ |  | 3 |  | -0.1295 | -0.9713 | -0.2630 | 16.46 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| legacy_momentum_low_turnover_v1 | quality_4y_1y | ok | 3 | ~ |  | 3 |  | 0.1147 | 0.5808 | -0.1729 | 2.55 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| ma_kline_baseline_v1 | quality_4y_1y | ok | 3 | ~ |  | 3 |  | -0.4930 | -4.4614 | -0.5587 | 43.36 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| residual_momentum_reversal_v1 | quality_4y_1y | ok | 3 | ~ |  | 3 |  | -0.3293 | -3.1514 | -0.4164 | 33.22 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| residual_momentum_reversal_v2 | quality_4y_1y | ok | 3 | ~ |  | 3 |  | -0.4558 | -4.1086 | -0.5029 | 62.37 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| quality_growth_price_v1 | quality_4y_1y | ok | 3 | ~ |  | 3 |  | -0.0319 | -0.4412 | -0.1946 | 27.70 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| low_vol_low_turnover_quality_v1 | quality_4y_1y | ok | 3 | ~ |  | 3 |  | 0.1203 | 1.0513 | -0.1752 | 1.88 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| quality_low_turnover_monthly_v1 | quality_4y_1y | ok | 3 | ~ |  | 3 |  | 0.1211 | 1.0290 | -0.2115 | 1.84 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| multifactor_volume_price_filter_v1 | quality_4y_1y | ok | 3 | ~ |  | 3 |  | -0.1728 | -1.4584 | -0.2232 | 49.00 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| core_selection_quality_momentum_v1 | quality_4y_1y | ok | 3 | ~ |  | 3 |  | -0.0015 | -0.2337 | -0.1745 | 9.27 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| theme_exposure_momentum_v1 | quality_4y_1y | ok | 3 | ~ |  | 3 |  | -0.0407 | -0.4893 | -0.1020 | 52.30 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |

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
| quality_low_turnover_monthly_v1 | quality_4y_1y | 1.00 | 1.00 | 1.00 | 0.00 | 0.181 | use:cash_flow_quality | passed |
| multifactor_volume_price_filter_v1 | quality_4y_1y | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
| core_selection_quality_momentum_v1 | quality_4y_1y | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
| theme_exposure_momentum_v1 | quality_4y_1y | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
