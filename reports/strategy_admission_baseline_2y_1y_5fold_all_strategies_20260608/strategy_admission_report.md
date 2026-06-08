# Strategy Admission Report

Generated at: 2026-06-08T22:58:50

## Scope

- Presets: `baseline_2y_1y_5fold`
- Strategies: `core_selection_quality_momentum_v1, legacy_momentum, legacy_momentum_low_turnover_v1, low_vol_low_turnover_quality_v1, ma_kline_baseline_v1, multifactor_volume_price_filter_v1, quality_growth_price_v1, quality_low_turnover_monthly_v1, residual_momentum_reversal_v1, residual_momentum_reversal_v2, theme_exposure_momentum_v1`

## Constraint Review

| strategy_id | action | window_pass | turnover_fail | param_unstable | industry_conc | overfit | reasons |
| --- | --- | --- | --- | --- | --- | --- | --- |
| core_selection_quality_momentum_v1 | reject | 0/1 | 0 | 0 | 0 | unknown | one or more presets produced no valid folds; positive fold ratio below 75% in one or more windows |
| legacy_momentum | reject | 0/1 | 1 | 0 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; positive fold ratio below 75% in one or more windows |
| legacy_momentum_low_turnover_v1 | reject | 0/1 | 0 | 1 | 0 | high | overfit risk is high; selected parameters change too frequently in one or more windows; positive fold ratio below 75% in one or more windows |
| low_vol_low_turnover_quality_v1 | reject | 0/1 | 0 | 1 | 0 | high | overfit risk is high; selected parameters change too frequently in one or more windows; positive fold ratio below 75% in one or more windows |
| ma_kline_baseline_v1 | reject | 0/1 | 1 | 1 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; selected parameters change too frequently in one or more windows; positive fold ratio below 75% in one or more windows |
| multifactor_volume_price_filter_v1 | reject | 0/1 | 1 | 1 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; selected parameters change too frequently in one or more windows; positive fold ratio below 75% in one or more windows |
| quality_growth_price_v1 | reject | 0/1 | 1 | 1 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; selected parameters change too frequently in one or more windows; positive fold ratio below 75% in one or more windows |
| quality_low_turnover_monthly_v1 | reject | 0/1 | 0 | 1 | 0 | high | overfit risk is high; selected parameters change too frequently in one or more windows; positive fold ratio below 75% in one or more windows |
| residual_momentum_reversal_v1 | reject | 0/1 | 1 | 0 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; positive fold ratio below 75% in one or more windows |
| residual_momentum_reversal_v2 | reject | 0/1 | 1 | 1 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; selected parameters change too frequently in one or more windows; positive fold ratio below 75% in one or more windows |
| theme_exposure_momentum_v1 | reject | 0/1 | 0 | 0 | 0 | unknown | one or more presets produced no valid folds; positive fold ratio below 75% in one or more windows |

## Window Matrix

| strategy_id | preset | status | folds | window | expected | actual | warning | ann | sharpe | mdd | turnover | top1_ind | top3_ind | acct_ann | acct_sharpe | acct_orders | pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| legacy_momentum | baseline_2y_1y_5fold | ok | 5 | 2019-04-01~2026-03-31 | 5.0 | 5 | nan | -0.2308 | -1.8963 | -0.3263 | 13.88 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| legacy_momentum_low_turnover_v1 | baseline_2y_1y_5fold | ok | 5 | 2019-04-01~2026-03-31 | 5.0 | 5 | nan | -0.0536 | -0.4498 | -0.1911 | 1.96 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| ma_kline_baseline_v1 | baseline_2y_1y_5fold | ok | 5 | 2019-04-01~2026-03-31 | 5.0 | 5 | nan | -0.4350 | -3.6009 | -0.4646 | 43.86 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| residual_momentum_reversal_v1 | baseline_2y_1y_5fold | ok | 5 | 2019-04-01~2026-03-31 | 5.0 | 5 | nan | -0.2716 | -2.5253 | -0.3763 | 28.21 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| residual_momentum_reversal_v2 | baseline_2y_1y_5fold | ok | 5 | 2019-04-01~2026-03-31 | 5.0 | 5 | nan | -0.4176 | -3.7023 | -0.4589 | 66.75 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| quality_growth_price_v1 | baseline_2y_1y_5fold | ok | 5 | 2019-04-01~2026-03-31 | 5.0 | 5 | nan | -0.0944 | -1.2620 | -0.2636 | 22.74 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| low_vol_low_turnover_quality_v1 | baseline_2y_1y_5fold | ok | 5 | 2019-04-01~2026-03-31 | 5.0 | 5 | nan | -0.0466 | -0.4086 | -0.1660 | 2.05 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| quality_low_turnover_monthly_v1 | baseline_2y_1y_5fold | ok | 5 | 2019-04-01~2026-03-31 | 5.0 | 5 | nan | -0.0318 | -0.2709 | -0.1621 | 1.78 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| multifactor_volume_price_filter_v1 | baseline_2y_1y_5fold | ok | 5 | 2019-04-01~2026-03-31 | 5.0 | 5 | nan | -0.1918 | -1.8723 | -0.2737 | 44.31 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| core_selection_quality_momentum_v1 | baseline_2y_1y_5fold | failed | 0 | nan~nan | nan | 0 | no valid folds | 0.0000 | 0.0000 | 0.0000 | 0.00 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |
| theme_exposure_momentum_v1 | baseline_2y_1y_5fold | failed | 0 | nan~nan | nan | 0 | no valid folds | 0.0000 | 0.0000 | 0.0000 | 0.00 | 0.00 | 0.00 | 0.0000 | 0.0000 | 0 | False |

## Strategy Quality Diagnostics

| strategy_id | preset | pit_ann | field_cov | selected_field_cov | missing_blocked | quality_lift | cash_flow_evidence | failure_attribution |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| legacy_momentum | baseline_2y_1y_5fold | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
| legacy_momentum_low_turnover_v1 | baseline_2y_1y_5fold | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
| ma_kline_baseline_v1 | baseline_2y_1y_5fold | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
| residual_momentum_reversal_v1 | baseline_2y_1y_5fold | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
| residual_momentum_reversal_v2 | baseline_2y_1y_5fold | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
| quality_growth_price_v1 | baseline_2y_1y_5fold | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
| low_vol_low_turnover_quality_v1 | baseline_2y_1y_5fold | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
| quality_low_turnover_monthly_v1 | baseline_2y_1y_5fold | 1.00 | 1.00 | 1.00 | 0.00 | 0.178 | use:cash_flow_quality | construction_or_regime: quality exposure did not convert to return |
| multifactor_volume_price_filter_v1 | baseline_2y_1y_5fold | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
| core_selection_quality_momentum_v1 | baseline_2y_1y_5fold | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
| theme_exposure_momentum_v1 | baseline_2y_1y_5fold | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | use:cash_flow_quality | not_applicable |
