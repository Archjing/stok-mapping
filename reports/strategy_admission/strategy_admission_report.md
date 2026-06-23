# Strategy Admission Report

Generated at: 2026-06-23T05:23:22

## Scope

- Presets: `quality_4y_1y`
- Strategy scope source: `strategy_set`
- Strategy set: `baseline_admission_all_v1`
- Strategies: `legacy_momentum, legacy_momentum_low_turnover_v1, ma_kline_baseline_v1, residual_momentum_reversal_v1, residual_momentum_reversal_v2, quality_growth_price_v1, low_vol_low_turnover_quality_v1, quality_low_turnover_monthly_v1, multifactor_volume_price_filter_v1, core_selection_quality_momentum_v1, theme_exposure_momentum_v1, sleeve_composite_v1`
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
| core_selection_quality_momentum_v1 | reject | 0/1 | 1 | 0 | 0 | 1 | 1 | 0 | high | overfit risk is high; annual turnover exceeds threshold in one or more windows; industry concentration exceeds audit threshold in one or more windows; factor diagnostics are required but not available in one or more windows; positive fold ratio below 75% in one or more windows |
| legacy_momentum | reject | 0/1 | 1 | 0 | 0 | 1 | 0 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; industry concentration exceeds audit threshold in one or more windows; positive fold ratio below 75% in one or more windows |
| legacy_momentum_low_turnover_v1 | reject | 0/1 | 0 | 0 | 0 | 1 | 0 | 0 | medium | industry concentration exceeds audit threshold in one or more windows; positive fold ratio below 75% in one or more windows |
| low_vol_low_turnover_quality_v1 | reject | 0/1 | 0 | 0 | 0 | 1 | 0 | 0 | medium | industry concentration exceeds audit threshold in one or more windows; positive fold ratio below 75% in one or more windows |
| ma_kline_baseline_v1 | reject | 0/1 | 1 | 0 | 0 | 1 | 0 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; industry concentration exceeds audit threshold in one or more windows; positive fold ratio below 75% in one or more windows |
| multifactor_volume_price_filter_v1 | reject | 0/1 | 1 | 0 | 0 | 1 | 1 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; industry concentration exceeds audit threshold in one or more windows; factor diagnostics are required but not available in one or more windows; positive fold ratio below 75% in one or more windows |
| quality_growth_price_v1 | reject | 0/1 | 1 | 0 | 0 | 1 | 1 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; industry concentration exceeds audit threshold in one or more windows; factor diagnostics are required but not available in one or more windows; positive fold ratio below 75% in one or more windows |
| quality_low_turnover_monthly_v1 | reject | 0/1 | 0 | 0 | 0 | 1 | 0 | 0 | medium | industry concentration exceeds audit threshold in one or more windows; positive fold ratio below 75% in one or more windows |
| residual_momentum_reversal_v1 | reject | 0/1 | 1 | 0 | 0 | 1 | 0 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; industry concentration exceeds audit threshold in one or more windows; positive fold ratio below 75% in one or more windows |
| residual_momentum_reversal_v2 | reject | 0/1 | 1 | 0 | 0 | 1 | 0 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; industry concentration exceeds audit threshold in one or more windows; positive fold ratio below 75% in one or more windows |
| sleeve_composite_v1 | reject | 0/1 | 1 | 0 | 0 | 1 | 0 | 0 | critical | overfit risk is critical; annual turnover exceeds threshold in one or more windows; industry concentration exceeds audit threshold in one or more windows; positive fold ratio below 75% in one or more windows |
| theme_exposure_momentum_v1 | reject | 0/1 | 1 | 0 | 0 | 1 | 0 | 0 | high | overfit risk is high; annual turnover exceeds threshold in one or more windows; industry concentration exceeds audit threshold in one or more windows; positive fold ratio below 75% in one or more windows |

## Window Matrix

| strategy_id | preset | status | folds | window | expected | actual | warning | price_status | ann | sharpe | mdd | turnover | industry_status | top1_ind | top3_ind | account_status | acct_ann | acct_sharpe | acct_orders | pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| legacy_momentum | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | qfq_asof | -0.1861 | -1.2195 | -0.2890 | 17.20 | enabled:audited | 0.18 | 0.35 | not_enabled | n/a | n/a | n/a | False |
| legacy_momentum_low_turnover_v1 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | qfq_asof | 0.0709 | 0.4088 | -0.1492 | 2.59 | enabled:audited | 0.14 | 0.28 | not_enabled | n/a | n/a | n/a | False |
| ma_kline_baseline_v1 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | qfq_asof | -0.4461 | -3.4105 | -0.5097 | 46.01 | enabled:audited | 0.37 | 0.62 | not_enabled | n/a | n/a | n/a | False |
| residual_momentum_reversal_v1 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | qfq_asof | -0.2708 | -2.3739 | -0.3024 | 33.91 | enabled:audited | 0.25 | 0.50 | not_enabled | n/a | n/a | n/a | False |
| residual_momentum_reversal_v2 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | qfq_asof | -0.3977 | -3.2245 | -0.4369 | 78.09 | enabled:audited | 0.52 | 0.73 | not_enabled | n/a | n/a | n/a | False |
| quality_growth_price_v1 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | qfq_asof | -0.1165 | -0.9976 | -0.1824 | 24.91 | enabled:audited | 0.18 | 0.38 | not_enabled | n/a | n/a | n/a | False |
| low_vol_low_turnover_quality_v1 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | qfq_asof | 0.0794 | 0.6575 | -0.1373 | 2.49 | enabled:audited | 0.17 | 0.36 | not_enabled | n/a | n/a | n/a | False |
| quality_low_turnover_monthly_v1 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | qfq_asof | 0.0707 | 0.7038 | -0.1317 | 1.99 | enabled:audited | 0.14 | 0.29 | not_enabled | n/a | n/a | n/a | False |
| multifactor_volume_price_filter_v1 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | qfq_asof | -0.2128 | -1.6925 | -0.2584 | 55.59 | enabled:audited | 0.53 | 0.61 | not_enabled | n/a | n/a | n/a | False |
| core_selection_quality_momentum_v1 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | qfq_asof | -0.0403 | -0.3337 | -0.1399 | 9.65 | enabled:audited | 0.18 | 0.40 | not_enabled | n/a | n/a | n/a | False |
| theme_exposure_momentum_v1 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | qfq_asof | -0.0437 | -0.5313 | -0.1451 | 53.04 | enabled:audited | 0.44 | 0.61 | not_enabled | n/a | n/a | n/a | False |
| sleeve_composite_v1 | quality_4y_1y | ok | 2 | 2020-04-01~2026-03-31 | 2 | 2 |  | qfq_asof | -0.3095 | -1.8734 | -0.4019 | 30.53 | enabled:audited | 0.21 | 0.45 | not_enabled | n/a | n/a | n/a | False |

## Strategy Quality Diagnostics

| strategy_id | preset | status | pit_ann | field_cov | selected_field_cov | missing_blocked | quality_lift | cash_flow_evidence | failure_attribution |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| legacy_momentum | quality_4y_1y | not_applicable | n/a | n/a | n/a | n/a | n/a | use:cash_flow_quality | not_applicable |
| legacy_momentum_low_turnover_v1 | quality_4y_1y | not_applicable | n/a | n/a | n/a | n/a | n/a | use:cash_flow_quality | not_applicable |
| ma_kline_baseline_v1 | quality_4y_1y | not_applicable | n/a | n/a | n/a | n/a | n/a | use:cash_flow_quality | not_applicable |
| residual_momentum_reversal_v1 | quality_4y_1y | not_applicable | n/a | n/a | n/a | n/a | n/a | use:cash_flow_quality | not_applicable |
| residual_momentum_reversal_v2 | quality_4y_1y | not_applicable | n/a | n/a | n/a | n/a | n/a | use:cash_flow_quality | not_applicable |
| quality_growth_price_v1 | quality_4y_1y | not_available | n/a | n/a | n/a | n/a | n/a | use:cash_flow_quality | diagnostic_missing: financial factor diagnostics not available |
| low_vol_low_turnover_quality_v1 | quality_4y_1y | available | 1.00 | 1.00 | 1.00 | 0.00 | 0.152 | use:cash_flow_quality | passed |
| quality_low_turnover_monthly_v1 | quality_4y_1y | available | 1.00 | 1.00 | 1.00 | 0.00 | 0.175 | use:cash_flow_quality | passed |
| multifactor_volume_price_filter_v1 | quality_4y_1y | not_available | n/a | n/a | n/a | n/a | n/a | use:cash_flow_quality | diagnostic_missing: financial factor diagnostics not available |
| core_selection_quality_momentum_v1 | quality_4y_1y | not_available | n/a | n/a | n/a | n/a | n/a | use:cash_flow_quality | diagnostic_missing: financial factor diagnostics not available |
| theme_exposure_momentum_v1 | quality_4y_1y | not_applicable | n/a | n/a | n/a | n/a | n/a | use:cash_flow_quality | not_applicable |
| sleeve_composite_v1 | quality_4y_1y | available | 1.00 | 1.00 | 1.00 | 0.00 | 0.125 | use:cash_flow_quality | construction_or_regime: quality exposure did not convert to return |
