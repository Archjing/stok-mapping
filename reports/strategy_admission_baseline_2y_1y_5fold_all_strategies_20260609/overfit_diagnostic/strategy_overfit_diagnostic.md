# 策略过拟合诊断报告

Generated at: 2026-06-09T02:47:45

- Candidates: `/home/zj/workspace/stok-mapping/reports/strategy_admission_baseline_2y_1y_5fold_all_strategies_20260609/strategy_admission_candidate_folds.csv`
- Folds: `/home/zj/workspace/stok-mapping/reports/strategy_admission_baseline_2y_1y_5fold_all_strategies_20260609/strategy_admission_candidate_folds.csv`
- Selected candidate: `quality_low_turnover_monthly_v1`

## MVP 结论

第一版只读取现有 walk-forward 产物，不重新回测，不做参数扰动。`not_available` 字段表示该维度需要后续输入产物。

## Results

| strategy_id | risk | score | action | fold_count | positive_fold_ratio | main_risk_reasons |
| --- | --- | --- | --- | --- | --- | --- |
| quality_low_turnover_monthly_v1 | high | 65 | retest | 5 | 0.4000 | positive OOS fold ratio below 50%; mean Sharpe below 0.5; mean annualized return is non-positive; selected parameters change frequently across folds |
| legacy_momentum_low_turnover_v1 | high | 65 | retest | 5 | 0.2000 | positive OOS fold ratio below 50%; mean Sharpe below 0.5; mean annualized return is non-positive; selected parameters change frequently across folds |
| low_vol_low_turnover_quality_v1 | high | 65 | retest | 5 | 0.4000 | positive OOS fold ratio below 50%; mean Sharpe below 0.5; mean annualized return is non-positive; selected parameters change frequently across folds |
| legacy_momentum | critical | 85 | reject | 5 | 0.0000 | positive OOS fold ratio below 50%; worst fold annualized return below -20%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity |
| residual_momentum_reversal_v1 | critical | 85 | reject | 5 | 0.0000 | positive OOS fold ratio below 50%; worst fold annualized return below -20%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity |
| core_selection_quality_momentum_v1 | critical | 95 | reject | 5 | 0.2000 | positive OOS fold ratio below 50%; worst fold annualized return below -20%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity; selected parameters change frequently across folds |
| ma_kline_baseline_v1 | critical | 95 | reject | 5 | 0.0000 | positive OOS fold ratio below 50%; worst fold annualized return below -20%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity; selected parameters change frequently across folds |
| multifactor_volume_price_filter_v1 | critical | 95 | reject | 5 | 0.0000 | positive OOS fold ratio below 50%; worst fold annualized return below -20%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity; selected parameters change frequently across folds |
| quality_growth_price_v1 | critical | 95 | reject | 5 | 0.2000 | positive OOS fold ratio below 50%; worst fold annualized return below -20%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity; selected parameters change frequently across folds |
| residual_momentum_reversal_v2 | critical | 95 | reject | 5 | 0.0000 | positive OOS fold ratio below 50%; worst fold annualized return below -20%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity; selected parameters change frequently across folds |
| theme_exposure_momentum_v1 | critical | 95 | reject | 5 | 0.2000 | positive OOS fold ratio below 50%; worst fold annualized return below -20%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity; selected parameters change frequently across folds |
