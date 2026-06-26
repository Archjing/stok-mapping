# 策略过拟合诊断报告

Generated at: 2026-06-26T03:34:58

- Candidates: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_61__recovery_participation/admission/strategy_admission_candidate_folds.csv`
- Folds: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_61__recovery_participation/admission/strategy_admission_candidate_folds.csv`
- Selected candidate: `strong_benchmark_recovery_participation_v1`

## MVP 结论

第一版只读取现有 walk-forward 产物，不重新回测，不做参数扰动。`not_available` 字段表示该维度需要后续输入产物。

## Results

| strategy_id | risk | score | action | fold_count | positive_fold_ratio | last_fold_lift_risk | last_fold_lift | main_risk_reasons |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| strong_benchmark_recovery_participation_v1 | high | 70 | retest | 5 | 0.2000 | True | 0.1116 | positive OOS fold ratio below 50%; mean Sharpe below 0.5; mean annualized return is non-positive; last fold materially lifts results |
