# 情报转候选策略任务：factor_effectiveness_redundancy_diagnostic_v1

## 来源情报

- Intelligence ID: `INT-CN-007`
- Source: `refdocs/papers/cn/markdown/cn07_lasso_pricing_factors_china.md`
- Linked Note: `knowledge/intelligence/notes/INT-CN-007_lasso_pricing_factors_china.md`

## 策略假设

高维候选因子或策略信号中存在大量冗余和无效信息。若在候选策略进入 admission 之前增加“边际有效性 / 冗余控制”诊断，可以减少因子动物园式堆叠，降低样本内拟合和与既有 baseline 重复暴露的风险。

该任务不是直接生成买卖信号，而是把 `INT-CN-007` 转化为策略治理工具：对候选策略的核心信号、现有低换手质量 baseline、收益序列和行业/风格暴露做冗余复核。

## 所需数据

- 已有字段：walk-forward folds、candidate returns、baseline returns、overfit diagnostic、行业暴露、换手、成本后收益。
- 需新增字段：候选策略信号与主要 baseline 的相关性、分折冗余诊断、最近折贡献占比、候选因子或信号分组后的边际解释度。
- as-of 约束：所有信号、财务字段、股票池和收益窗口必须沿用 `qfq_asof` 与 PIT universe。
- 数据质量门禁：`db-health` 通过；candidate CSV 覆盖所有当前候选；admission 输出包含 fold-level 结果。

## 信号定义

- 因子 / 特征：不新增交易信号；读取候选策略已有 score、rank 或组合收益。
- 方向：诊断方向为“冗余越高、边际贡献越低，准入风险越高”。
- 标准化 / 去极值 / 中性化：沿用候选策略已有 score 口径；诊断层只做横截面相关、折内收益相关和 baseline 增量比较。
- 调仓频率：与被诊断策略一致。

## 组合与风控

- 选股方式：不直接选股。
- 权重方式：不直接分配权重。
- 流动性约束：读取 admission / universe 审计产物，不重复实现。
- 行业 / 单票限制：读取现有 constraint review，不改变策略约束。
- 交易成本假设：沿用 admission preset 成本口径。

## 验证设计

- 回测入口：`phase0.cli strategy-admission` 后置诊断或 `phase0.cli` 新增只读诊断入口。
- baseline：`legacy_momentum_low_turnover_v1`、`low_vol_low_turnover_quality_v1`、当前所有 admitted/rejected 候选的 fold returns。
- walk-forward 设置：先复用 `baseline_2y_1y_5fold`。
- effectiveness gate：不替代 gate；作为 admission 报告的附加风险解释。
- overfit diagnostic：重点标记“只靠最后一折拉高”“与 baseline 高相关但无成本后增量”“收益集中于单行业/单窗口”。

## 准入结论

- 进入实验：`yes`
- 原因：该任务是只读治理工具，直接服务当前策略池完善和 admission 解释，不会绕过交易信号门禁。
- 下一步：在 T2.5 中补一版只读诊断表，先对当前 12 个候选策略运行一次 qfq_asof 全量 admission 后再接入。
