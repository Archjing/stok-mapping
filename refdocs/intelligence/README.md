# 投资策略情报库

本目录管理与 `stok-mapping` 策略研发相关的投资策略情报，包括论文、研究报告、公告新闻线索、策略思想、反方证据和后续实验建议。

## 定位

情报库属于研究情报层，不直接生成交易信号，也不绕过回测、数据质量、PIT、过拟合诊断和账户约束。

它的职责是：

- 记录情报来源与出处。
- 评估情报质量、创新性、可落地性和偏差风险。
- 将高质量情报提炼为候选策略任务或数据建设任务。
- 维护“情报 -> 研究假设 -> 候选策略 -> 实验结果”的追溯链。

## 当前文件

| 文件 | 作用 |
| --- | --- |
| `strategy_intelligence_ledger.csv` | 情报总台账，记录状态、评分、标签、推荐动作和关联任务 |
| `templates/intelligence_note_template.md` | 单条情报解读模板 |
| `templates/strategy_translation_template.md` | 情报转候选策略任务模板 |

## 状态流转

```text
collected -> screened -> evaluated -> translated -> experiment_planned -> accepted / rejected / archived
```

## 进入候选策略的最低门槛

- `quality_score >= 3`
- `actionability_score >= 3`
- 数据路径明确，不能依赖不可验证或不可获取的数据
- 已识别主要偏差风险：未来函数、幸存者偏差、样本内过拟合、文本延迟、授权风险等

公告新闻类情报默认只进入解释层、事件时间线或研究假设，不直接进入主 ranker。
