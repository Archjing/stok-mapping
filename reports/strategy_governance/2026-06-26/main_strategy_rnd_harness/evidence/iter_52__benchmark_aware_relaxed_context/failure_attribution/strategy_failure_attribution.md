# 策略失败归因诊断报告

Generated at: 2026-06-26T00:43:41

## 输入

- 本报告只读取已有 admission / overfit CSV，不重新回测，不修改 admission 产物。
- folds: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/admission/strategy_admission_candidate_folds.csv`
- window_matrix: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/admission/strategy_admission_window_matrix.csv`
- constraint_review: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/admission/strategy_admission_constraint_review.csv`
- overfit: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/admission/overfit_diagnostic/strategy_overfit_diagnostic.csv`

## 汇总

| strategy_id | preset | action | severity | primary_failure | return | execution | construction | factor | parameter | regime | data |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| strong_market_benchmark_aware_core_v1 | baseline_2y_1y_5fold | reject | 高 | 收益失败 | high | none | high | none | none | high | none |

## 策略级建议

### strong_market_benchmark_aware_core_v1

- Admission action: `reject`
- 主要失败原因：收益失败（severity=high）
- 证据：收益失败：年化收益均值 -0.0070 未通过 gate 0.0000；Sharpe 均值 -0.1902 未通过 gate 0.5000；正收益折比例 40.00% 未通过 gate 75.00% | 组合构造失败：行业集中度触发 admission 审计阈值：top1_mean=3.30%, top3_mean=8.03%, violation_days=1205 | 市场阶段失败：策略级 overfit_risk_level=high
- 下一步建议：当前 spec 维持 reject；优先重审 alpha 假设和收益来源，不要先做参数微调。
