# 策略过拟合诊断报告

Generated at: 2026-06-08T21:00:36

- Candidates: `/home/zj/workspace/stok-mapping/reports/smoke/strategy_admission_t2_7_quality_low_turnover_monthly_20260608/strategy_admission_candidate_folds.csv`
- Folds: `/home/zj/workspace/stok-mapping/reports/smoke/strategy_admission_t2_7_quality_low_turnover_monthly_20260608/strategy_admission_candidate_folds.csv`
- Selected candidate: `quality_low_turnover_monthly_v1`

## MVP 结论

第一版只读取现有 walk-forward 产物，不重新回测，不做参数扰动。`not_available` 字段表示该维度需要后续输入产物。

## Results

| strategy_id | risk | score | action | fold_count | positive_fold_ratio | main_risk_reasons |
| --- | --- | --- | --- | --- | --- | --- |
| quality_low_turnover_monthly_v1 | critical | 85 | reject | 3 | 0.3333 | OOS fold count below governance floor; positive OOS fold ratio below 50%; mean Sharpe below 0.5; mean annualized return is non-positive; selected parameters change frequently across folds |
