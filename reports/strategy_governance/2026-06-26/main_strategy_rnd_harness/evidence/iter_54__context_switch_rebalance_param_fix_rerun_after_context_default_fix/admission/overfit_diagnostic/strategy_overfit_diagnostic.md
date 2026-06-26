# 策略过拟合诊断报告

Generated at: 2026-06-26T01:17:50

- Candidates: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_54__context_switch_rebalance_param_fix_rerun_after_context_default_fix/admission/strategy_admission_candidate_folds.csv`
- Folds: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_54__context_switch_rebalance_param_fix_rerun_after_context_default_fix/admission/strategy_admission_candidate_folds.csv`
- Selected candidate: `strong_market_benchmark_aware_core_v1`

## MVP 结论

第一版只读取现有 walk-forward 产物，不重新回测，不做参数扰动。`not_available` 字段表示该维度需要后续输入产物。

## Results

| strategy_id | risk | score | action | fold_count | positive_fold_ratio | last_fold_lift_risk | last_fold_lift | main_risk_reasons |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| strong_market_benchmark_aware_core_v1 | high | 55 | retest | 5 | 0.2000 | False | 0.0000 | positive OOS fold ratio below 50%; mean Sharpe below 0.5; mean annualized return is non-positive |
