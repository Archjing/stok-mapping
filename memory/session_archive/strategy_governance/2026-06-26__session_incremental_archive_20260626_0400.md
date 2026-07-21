# Session Incremental Archive - 2026-06-26 04:00

范围：I62 初步设计评估。

## 关键发现

I61 recovery trigger 对不同 fold 的效果差异很大：

- fold5 recovery 期间沪深300累计日收益为 0.143221，信号有效。
- fold2 recovery 期间沪深300累计日收益为 -0.041549，信号误伤。
- fold4 recovery 期间沪深300累计日收益为 -0.022057，信号误伤。

## 决策

下一步不应继续简单调高或调低 recovery 仓位。应引入 recovery quality filter，把“有效修复”和“弱反弹”区分开。

## 建议候选

- `strong_benchmark_recovery_quality_v1`

## 验收目标

- 保留 fold5 改善；
- 减少 fold2/fold4 恶化；
- turnover 不高于 I61；
- research-only，不进入默认候选池。
