# 策略过拟合诊断报告

Generated at: 2026-06-08T20:34:55

- Candidates: `/home/zj/workspace/stok-mapping/reports/smoke/strategy_admission_industry_enforce_20260608/admission/strategy_admission_candidate_folds.csv`
- Folds: `/home/zj/workspace/stok-mapping/reports/smoke/strategy_admission_industry_enforce_20260608/admission/strategy_admission_candidate_folds.csv`
- Selected candidate: `low_vol_low_turnover_quality_v1`

## MVP 结论

第一版只读取现有 walk-forward 产物，不重新回测，不做参数扰动。`not_available` 字段表示该维度需要后续输入产物。

## Results

| strategy_id | risk | score | action | fold_count | positive_fold_ratio | main_risk_reasons |
| --- | --- | --- | --- | --- | --- | --- |
| low_vol_low_turnover_quality_v1 | critical | 75 | reject | 3 | 0.3333 | OOS fold count below governance floor; positive OOS fold ratio below 50%; mean Sharpe below 0.5; mean annualized return is non-positive |
