# 中文 A 股量化策略情报精炼页

## Summary

本页基于当前已归档的中文策略情报 `INT-CN-001` 到 `INT-CN-010`、`docs/tasks/research/STRATEGY_SUMMARY.md` 和 `refdocs/papers/cn/cn_INDEX.md` 精炼而成。核心结论是：中文 A 股策略资料主要集中在多因子、机器学习、资产特征组合、量价增强、文本情绪、网络因子和技术规则 baseline。对 `stok-mapping` 当前阶段最有价值的不是直接照搬论文收益，而是抽取可验证假设、数据字段、偏差风险和回测治理要求。

## Key takeaways

- [[资产特征组合]] 是当前最值得转化的方向之一，因为它直接连接“特征 -> 权重 -> 组合构建”。
- [[LASSO 因子筛选]] 更适合作为因子库治理工具，而不是单独策略。
- [[SVM 多因子选股]] 是可复现的机器学习 baseline，但需要严格控制参数漂移和样本外过拟合。
- [[量价增强]] 可以作为传统多因子的二次筛选层，但必须加入换手、流动性和交易成本复核。
- [[分析师文本因子]] 更适合进入文本事件层和 PEAD 研究，不能在缺少时间戳和授权审计时直接进入主 ranker。
- [[网络因子]] 有结构信息价值，但当前数据路径不足，宜保留为 research-only。
- [[均线 K 线规则]] 更适合作为 baseline 和反事实比较，不应因单年超额收益直接升级为主策略。

## Entities and concepts

- [[A 股多因子选股]]
- [[资产特征组合]]
- [[LASSO 因子筛选]]
- [[SVM 多因子选股]]
- [[量价增强]]
- [[分析师文本因子]]
- [[网络因子]]
- [[技术规则 baseline]]
- [[PEAD]]
- [[过拟合诊断]]
- [[Point-in-time 数据]]

## Claims

- `INT-CN-005` 的资产特征组合资料对 `T2.6 / T2.7` 质量低换手方向最有直接映射价值。
- `INT-CN-007` 的双重选择 LASSO 更适合支撑 `T2.5` 因子有效性诊断和因子冗余控制。
- `INT-CN-008` 的分析师文本研究需要先完成文本事件层、时间戳和覆盖率审计，才能考虑进入策略实验。
- 当前中文资料中的高收益结论大多来自论文回测，不能替代本项目的 `qfq_asof`、PIT 股票池、交易成本、整手约束和 walk-forward 准入。

## Strategy translation notes

| 情报 | 项目内最佳用途 | 主要风险 |
| --- | --- | --- |
| `INT-CN-005` 资产特征组合 | 质量 / 低换手 / 组合构建复核 | 特征泄漏、换手、权重过拟合 |
| `INT-CN-007` LASSO 因子边际有效性 | 因子筛选、冗余控制、T2.5 诊断 | 因子动物园、选择偏差 |
| `INT-CN-003` SVM 多因子沪深300 | ML baseline、因子分类模型模板 | 参数不稳定、样本外衰减 |
| `INT-CN-009` SVM + 量价中证1000 | 量价增强二次筛选 | 小盘流动性、换手和成本 |
| `INT-CN-008` 分析师文本 | 文本事件层、PEAD、解释层 | 文本延迟、覆盖率、授权风险 |
| `INT-CN-004` 网络因子 | 结构因子 research-only | 关系定义、未来信息污染 |
| `INT-CN-010` 均线 K 线 | baseline / 反事实比较 | 数据窥探、经济解释弱 |

## Tensions and contradictions

- 多篇论文给出较高样本外收益，但项目当前严格 `qfq_asof` 与成本后准入口径显示旧候选策略不再合格。
- 最合理解释是：论文结论可作为策略假设来源，但不能作为项目有效性证据。
- 当前应优先把中文情报转化为可复现实验，而不是直接采纳论文参数或收益结论。
- Confidence: medium

## Open questions

- 哪些中文论文的原始数据口径能够被项目本地库完整复现？
- `INT-CN-005` 的资产特征组合是否能在本项目 2016Q2-2026Q1 财务数据覆盖下稳定通过 walk-forward？
- 分析师文本数据的可得性、授权边界和时间戳质量是否足以支撑 PEAD 实验？

## Related wiki pages

- [[A 股多因子选股]]
- [[策略情报工作流]]
- [[因子有效性诊断]]
- [[策略准入]]
- [[文本事件层]]

## Provenance

- Date: 2026-06-09
- Sources:
  - `knowledge/intelligence/strategy_intelligence_ledger.csv`
  - `docs/tasks/research/STRATEGY_SUMMARY.md`
  - `refdocs/papers/cn/cn_INDEX.md`
  - `refdocs/papers/cn/markdown/*.md`
