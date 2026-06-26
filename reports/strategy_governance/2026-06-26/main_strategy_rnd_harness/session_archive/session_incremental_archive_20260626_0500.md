# Session Incremental Archive - 2026-06-26 05:00

范围：I68 Harness 策略研发迭代，主题为 negative recovery classifier audit。

## 关键发现

- fold2 是主要假 recovery：未来20日为负的 recovery 日期 49 天，I67 保留 26 天；未来20日为正的 recovery 日期 7 天，I67 只保留 2 天。
- fold4 是部分成功案例：I67 大幅减少 recovery 参与，策略年化改善。
- fold5 是真 recovery：I67 保留大多数 recovery 日期，策略表现不被破坏。

## 决策

不要继续微调当前静态宽度阈值。下一轮应研究宽度变化、行业领导持续性和成交额扩散持续性。

## 产物

- `negative_recovery_fold_summary.csv`
- `negative_recovery_outcome_summary.csv`
- `negative_recovery_leadership_summary.csv`
- `negative_recovery_classifier_audit.md`
- `strategy_governance_report_2026-06-26_i68_negative_recovery_classifier_audit.md`
