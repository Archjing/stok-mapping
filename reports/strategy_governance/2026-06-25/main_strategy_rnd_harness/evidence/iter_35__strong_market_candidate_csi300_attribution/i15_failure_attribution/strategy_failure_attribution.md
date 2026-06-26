# 策略失败归因诊断报告

Generated at: 2026-06-25T10:24:04

## 输入

- 本报告只读取已有 admission / overfit CSV，不重新回测，不修改 admission 产物。
- folds: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-24/main_strategy_admission_breakthrough/evidence/iter_15__strong_index_participation_minimal/admission/strategy_admission_candidate_folds.csv`
- window_matrix: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-24/main_strategy_admission_breakthrough/evidence/iter_15__strong_index_participation_minimal/admission/strategy_admission_window_matrix.csv`
- constraint_review: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-24/main_strategy_admission_breakthrough/evidence/iter_15__strong_index_participation_minimal/admission/strategy_admission_constraint_review.csv`
- overfit: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-24/main_strategy_admission_breakthrough/evidence/iter_15__strong_index_participation_minimal/admission/overfit_diagnostic/strategy_overfit_diagnostic.csv`

## 汇总

| strategy_id | preset | action | severity | primary_failure | return | execution | construction | factor | parameter | regime | data |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| strong_index_participation_v1 | baseline_2y_1y_5fold | reject | 高 | 收益失败 | high | none | high | none | none | none | none |

## 策略级建议

### strong_index_participation_v1

- Admission action: `reject`
- 主要失败原因：收益失败（severity=high）
- 证据：收益失败：Sharpe 均值 0.0361 未通过 gate 0.5000；正收益折比例 20.00% 未通过 gate 75.00% | 组合构造失败：行业集中度触发 admission 审计阈值：top1_mean=1.75%, top3_mean=3.50%, violation_days=20；归因层观察到平均实盘持仓数偏低：1.00
- 下一步建议：当前 spec 维持 reject；优先重审 alpha 假设和收益来源，不要先做参数微调。
