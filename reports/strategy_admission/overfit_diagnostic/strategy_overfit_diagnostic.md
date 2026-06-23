# 策略过拟合诊断报告

Generated at: 2026-06-23T05:23:22

- Candidates: `/home/zj/workspace/stok-mapping/reports/strategy_admission/strategy_admission_candidate_folds.csv`
- Folds: `/home/zj/workspace/stok-mapping/reports/strategy_admission/strategy_admission_candidate_folds.csv`
- Selected candidate: `quality_low_turnover_monthly_v1`

## MVP 结论

第一版只读取现有 walk-forward 产物，不重新回测，不做参数扰动。`not_available` 字段表示该维度需要后续输入产物。

## Results

| strategy_id | risk | score | action | fold_count | positive_fold_ratio | last_fold_lift_risk | last_fold_lift | main_risk_reasons |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quality_low_turnover_monthly_v1 | medium | 32 | observe | 2 | 0.5000 | False | 0.0000 | OOS fold count below governance floor; positive OOS fold ratio below 75% |
| low_vol_low_turnover_quality_v1 | medium | 32 | observe | 2 | 0.5000 | False | 0.0000 | OOS fold count below governance floor; positive OOS fold ratio below 75% |
| legacy_momentum_low_turnover_v1 | medium | 47 | observe | 2 | 0.5000 | False | 0.0000 | OOS fold count below governance floor; positive OOS fold ratio below 75%; mean Sharpe below 0.5 |
| core_selection_quality_momentum_v1 | high | 72 | retest | 2 | 0.5000 | False | 0.0000 | OOS fold count below governance floor; positive OOS fold ratio below 75%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity |
| theme_exposure_momentum_v1 | high | 72 | retest | 2 | 0.5000 | False | 0.0000 | OOS fold count below governance floor; positive OOS fold ratio below 75%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity |
| quality_growth_price_v1 | critical | 85 | reject | 2 | 0.0000 | False | 0.0000 | OOS fold count below governance floor; positive OOS fold ratio below 50%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity |
| legacy_momentum | critical | 100 | reject | 2 | 0.0000 | False | 0.0000 | OOS fold count below governance floor; positive OOS fold ratio below 50%; worst fold annualized return below -20%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity |
| ma_kline_baseline_v1 | critical | 100 | reject | 2 | 0.0000 | False | 0.0000 | OOS fold count below governance floor; positive OOS fold ratio below 50%; worst fold annualized return below -20%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity |
| multifactor_volume_price_filter_v1 | critical | 100 | reject | 2 | 0.0000 | False | 0.0000 | OOS fold count below governance floor; positive OOS fold ratio below 50%; worst fold annualized return below -20%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity |
| residual_momentum_reversal_v1 | critical | 100 | reject | 2 | 0.0000 | False | 0.0000 | OOS fold count below governance floor; positive OOS fold ratio below 50%; worst fold annualized return below -20%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity |
| residual_momentum_reversal_v2 | critical | 100 | reject | 2 | 0.0000 | False | 0.0000 | OOS fold count below governance floor; positive OOS fold ratio below 50%; worst fold annualized return below -20%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity |
| sleeve_composite_v1 | critical | 100 | reject | 2 | 0.0000 | False | 0.0000 | OOS fold count below governance floor; positive OOS fold ratio below 50%; worst fold annualized return below -20%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity |
