# 策略过拟合诊断报告

Generated at: 2026-06-03T23:37:50

- Candidates: `/home/zj/workspace/stok-mapping/reports/phase0_walk_forward_candidates.csv`
- Folds: `/home/zj/workspace/stok-mapping/reports/phase0_walk_forward_folds.csv`
- Selected candidate: `legacy_momentum_low_turnover_v1`

## MVP 结论

第一版只读取现有 walk-forward 产物，不重新回测，不做参数扰动。`not_available` 字段表示该维度需要后续输入产物。

## Results

| strategy_id | risk | score | action | fold_count | positive_fold_ratio | main_risk_reasons |
| --- | --- | --- | --- | --- | --- | --- |
| legacy_momentum_low_turnover_v1 | low | 15 | keep | 4 | 0.7500 | mean Sharpe below 0.5 |
| legacy_momentum | critical | 85 | reject | 4 | 0.0000 | positive OOS fold ratio below 50%; worst fold annualized return below -20%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity |
| quality_growth_price_v1 | critical | 85 | reject | 4 | 0.0000 | positive OOS fold ratio below 50%; worst fold annualized return below -20%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity |
| residual_momentum_reversal_v1 | critical | 85 | reject | 4 | 0.0000 | positive OOS fold ratio below 50%; worst fold annualized return below -20%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity |
| ma_kline_baseline_v1 | critical | 95 | reject | 4 | 0.0000 | positive OOS fold ratio below 50%; worst fold annualized return below -20%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity; selected parameters change frequently across folds |
| multifactor_volume_price_filter_v1 | critical | 95 | reject | 4 | 0.0000 | positive OOS fold ratio below 50%; worst fold annualized return below -20%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity; selected parameters change frequently across folds |
| residual_momentum_reversal_v2 | critical | 95 | reject | 4 | 0.0000 | positive OOS fold ratio below 50%; worst fold annualized return below -20%; mean Sharpe below 0.5; mean annualized return is non-positive; high annual turnover increases cost sensitivity; selected parameters change frequently across folds |
