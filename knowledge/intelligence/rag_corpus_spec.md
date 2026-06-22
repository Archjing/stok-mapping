# Strategy Intelligence RAG Corpus Spec

## 目标

本文件定义 `knowledge/intelligence/` 进入后续 RAG 的最小语料规范。目标是让论文、月度扫描、情报解读、策略转化任务和 wiki 精炼页可以被稳定检索，并保留“来源 -> 解读 -> 任务 -> 实验结果”的追溯关系。

本规范不引入向量库、SQLite 或知识图谱；当前只定义 Markdown / CSV 语料边界和字段约定。

## 语料层级

| 层级 | 路径 | RAG 用途 |
| --- | --- | --- |
| Source | `refdocs/papers/**/markdown/*.md` | 原始论文和资料正文，作为事实来源 |
| Ledger | `knowledge/intelligence/strategy_intelligence_ledger.csv` | 情报 ID、来源、状态、评分和推荐动作 |
| Note | `knowledge/intelligence/notes/*.md` | 人工解读、风险、数据需求和项目映射 |
| Translation | `knowledge/intelligence/strategy_translations/*.md` | 情报转候选策略、诊断或数据任务的草案 |
| Monthly | `knowledge/intelligence/monthly/*.md` | 周期性扫描、候选线索和复核状态 |
| Wiki | `knowledge/intelligence/wiki/*.md` | 面向检索的主题精炼页和 ingest log |

## 文档元数据要求

每篇 Note 必须包含：

- `Intelligence ID`
- `Source Type`
- `Source Path or URL`
- `Published At`
- `Collected At`
- `Market Scope`
- `Topic Tags`
- `Strategy Tags`
- `Status`
- `Next Action`

每篇 Translation 必须包含：

- 来源情报 ID
- Linked Note
- 策略假设
- 所需数据
- as-of 约束
- 验证设计
- 准入结论

每篇 Monthly Scan 必须包含：

- 扫描窗口
- 输入范围
- 候选情报清单
- 是否进入正式台账
- 人工复核状态
- 下一步动作

## Chunking 建议

- Source 论文：按一级/二级标题切分，单 chunk 保留标题、页码和 source path。
- Note：按 `Abstract`、`核心观点`、`对 stok-mapping 的启发`、`风险与反证` 切分。
- Translation：按 `策略假设`、`所需数据`、`验证设计`、`准入结论` 切分。
- Monthly：按候选情报条目切分。
- Wiki：按主题 hub 切分。

## Trust Level

| Trust Level | 含义 | 可用于 |
| --- | --- | --- |
| `source` | 原始论文 / 官方资料 / 可复查链接 | 事实核验、引用回查 |
| `curated` | 人工解读 note、wiki 精炼页 | RAG 检索和任务规划 |
| `candidate` | 月扫候选、inbox CSV | 待复核线索 |
| `derived` | 策略转化任务草案 | 实验设计，不作为有效性证据 |
| `runtime_report` | CLI 校验报告和实验报告 | 验收记录 |

## 检索标签

最小标签集合：

- 市场：`a_share`, `global`, `hk`, `us`
- 主题：`factor-selection`, `portfolio-construction`, `text-event`, `machine-learning`, `risk-control`
- 风险：`future-leakage`, `survivorship`, `overfit`, `data-license`, `asof`
- 项目任务：`T1.3`, `T2.5`, `T2.6`, `T2.7`, `T2.8`, `T2.10`, `T5.2`

## 使用边界

- RAG 只能辅助摘要、检索、反方审查和任务规划。
- RAG 不能直接决定交易信号、准入 action 或 selected candidate。
- 任何策略假设进入回测前，必须经过数据可见性、PIT、成本、过拟合诊断和 `strategy-admission`。
- 候选情报 inbox 不能直接当作正式台账；必须人工评分、补充偏差风险并通过门禁。

## 更新规则

- 新增 note 后，同步更新 `rag_manifest.csv`。
- 新增月扫报告后，同步更新 `monthly/index.md` 和 `wiki/log.md`。
- 情报进入策略任务后，必须在 Translation、任务文档和后续实验报告之间建立双向路径。
- 若源文件移动或删除，先修复 manifest 和 ledger，再运行 `phase0.cli intelligence validate`。
