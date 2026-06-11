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
| `wiki/` | 已归档情报的 wiki-ingest 风格精炼页、索引和 ingest log |
| `anki/` | 从已归档情报生成的 Anki 记忆卡片 Markdown 与 `.apkg` 包 |

## 自动采集器

自动采集器通过 `phase0.cli intelligence` 提供三个命令：

```bash
./.venv/bin/python -m phase0.cli intelligence import-local --config config.yaml --source-dir refdocs/papers
./.venv/bin/python -m phase0.cli intelligence collect --config config.yaml
./.venv/bin/python -m phase0.cli intelligence validate --config config.yaml
```

输出位置：

| 产物 | 默认路径 |
| --- | --- |
| 候选情报 CSV | `data/intelligence/inbox/intelligence_candidates_YYYY-MM-DD.csv` |
| 采集报告 | `reports/intelligence/intelligence_collect_report_YYYY-MM-DD.md` |
| 本地导入报告 | `reports/intelligence/intelligence_import_local_report_YYYY-MM-DD.md` |
| 台账校验报告 | `reports/intelligence/intelligence_validate_report_YYYY-MM-DD.md` |

候选情报 CSV 是 inbox，不是正式台账。正式写入 `strategy_intelligence_ledger.csv` 前必须人工筛选、评分、补充偏差风险和推荐动作。

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

## 采集边界

- 默认只扫描本地 `refdocs/papers/`。
- `arxiv`、`openalex`、`crossref`、`rss` 仅作为元数据和链接来源，默认关闭。
- 不抓取付费研报全文。
- 不替代新闻/文本事件数据层。
- 不自动把候选情报转为交易信号。
