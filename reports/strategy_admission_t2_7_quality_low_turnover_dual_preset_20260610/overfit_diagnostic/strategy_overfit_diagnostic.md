# 策略过拟合诊断报告

Generated at: 2026-06-10T01:35:37

- Candidates: `/home/zj/workspace/stok-mapping/reports/strategy_admission_t2_7_quality_low_turnover_dual_preset_20260610/strategy_admission_candidate_folds.csv`
- Folds: `/home/zj/workspace/stok-mapping/reports/strategy_admission_t2_7_quality_low_turnover_dual_preset_20260610/strategy_admission_candidate_folds.csv`
- Selected candidate: `quality_low_turnover_monthly_v1`

## MVP 结论

第一版只读取现有 walk-forward 产物，不重新回测，不做参数扰动。`not_available` 字段表示该维度需要后续输入产物。

## Results

| strategy_id | risk | score | action | fold_count | positive_fold_ratio | last_fold_lift_risk | last_fold_lift | main_risk_reasons |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quality_low_turnover_monthly_v1 | critical | 80 | reject | 9 | 0.3333 | True | 0.2316 | positive OOS fold ratio below 50%; mean Sharpe below 0.5; mean annualized return is non-positive; selected parameters change frequently across folds; last fold materially lifts results |
