# T5.2 Strategy Intelligence Workflow

本文说明 `stok-mapping` 的投资策略情报采集、复核、入账和后续转化流程。它是操作说明，不替代任务定义文档 `STRATEGY_INTELLIGENCE_WORKFLOW_TASKS.md`。

## 1. 目标与边界

T5.2 属于研究情报层，目标是把论文、研究报告、公告新闻线索和策略思想整理成可追溯的候选研究输入。

完整链路是：

```text
情报来源 -> 候选 inbox -> 人工复核 -> 正式台账 -> note / translation -> 策略任务或数据任务 -> 实验报告 -> 归档复盘
```

T5.2 不做以下事情：

- 不直接生成买卖信号。
- 不绕过 PIT、as-of、成本、过拟合诊断和 `strategy-admission`。
- 不把新闻、博客、营销材料或 LLM 摘要当作策略有效性证据。
- 不自动抓取付费研报全文。
- 不把候选 CSV 自动写入正式台账。

## 2. 核心目录

| 路径 | 用途 |
| --- | --- |
| `config.yaml` | `phase0.intelligence` 配置入口，定义 ledger、inbox、report 目录和采集源 |
| `phase0/intelligence/__init__.py` | 情报采集、候选 CSV 写出、ledger / RAG manifest 校验实现 |
| `phase0/intelligence/tiingo_news_probe.py` | Tiingo News 权限与过滤条件探测实现；`scripts/tiingo_news_probe.py` 仅保留兼容旧入口 |
| `data/intelligence/inbox/` | 自动采集生成的候选情报 CSV，不能直接视为正式台账 |
| `reports/intelligence/` | 本地导入、采集和校验报告 |
| `knowledge/intelligence/strategy_intelligence_ledger.csv` | 正式情报总台账 |
| `knowledge/intelligence/rag_manifest.csv` | RAG-ready 语料清单 |
| `knowledge/intelligence/notes/` | 人工解读后的核心情报 note |
| `knowledge/intelligence/strategy_translations/` | 情报转候选策略、诊断或数据任务的草案 |
| `knowledge/intelligence/monthly/` | 月度扫描报告、索引和运行规约 |
| `knowledge/intelligence/wiki/` | 面向检索的主题精炼页、索引和 ingest log |

## 3. 采集源

主配置中的情报采集入口是 `phase0.intelligence.sources`。本地来源用于导入项目已保存的参考资料：

```yaml
phase0:
  intelligence:
    sources:
      - name: local_papers
        type: local_dir
        enabled: true
        path: refdocs/papers
```

当前主配置也启用了在线元数据源 `arxiv_quant_finance`、`openalex_quant_strategy`、`crossref_quant_strategy` 和 `rss_quantocracy`。它们只作为公开元数据和链接入口，不代表正式入账，也不抓取付费研报全文。

执行 `collect` 前必须说明本次启用源、是否会联网、扫描窗口和输出路径。一次在线采集结果不得自动写入正式 ledger。

## 4. 执行一次本地情报工作流

推荐使用带日期和任务后缀的输出路径，避免覆盖同日旧产物。

```bash
./.venv/bin/python -m phase0.cli intelligence import-local \
  --config config.yaml \
  --source-dir refdocs/papers \
  --output-csv data/intelligence/inbox/intelligence_import_local_YYYY-MM-DD_t52_run.csv \
  --output-report reports/intelligence/intelligence_import_local_report_YYYY-MM-DD_t52_run.md
```

用途：

- 扫描指定本地目录下的 Markdown、PDF、CSV、JSON。
- 生成候选情报 CSV。
- 生成本地导入报告。
- 不修改正式台账。

```bash
./.venv/bin/python -m phase0.cli intelligence collect \
  --config config.yaml \
  --output-csv data/intelligence/inbox/intelligence_collect_YYYY-MM-DD_t52_run.csv \
  --output-report reports/intelligence/intelligence_collect_report_YYYY-MM-DD_t52_run.md
```

用途：

- 按 `config.yaml` 中已启用的 sources 采集候选元数据。
- 当前主配置会同时采集已启用的本地来源和在线元数据源。
- 候选 CSV 使用 `utf-8-sig` 写出，便于 Windows Excel 直接打开。

```bash
./.venv/bin/python -m phase0.cli intelligence validate \
  --config config.yaml \
  --output-report reports/intelligence/intelligence_validate_report_YYYY-MM-DD_t52_run.md
```

用途：

- 校验正式 ledger 字段、状态、评分、数据可用性和部分本地来源路径。
- 校验 `rag_manifest.csv` 的列、语料路径、doc type、trust level、status 和 `intelligence_id` 回链。
- 不校验候选 inbox 是否应该入账。

### 4.1 生成 LLM / 人工复核建议

对候选 CSV 运行复核辅助：

```bash
./.venv/bin/python -m phase0.cli intelligence review-candidates \
  --config config.yaml \
  --candidates-csv data/intelligence/inbox/intelligence_collect_YYYY-MM-DD_t52_run.csv \
  --output-csv data/intelligence/inbox/intelligence_review_suggestions_YYYY-MM-DD_t52_run.csv \
  --output-report reports/intelligence/intelligence_review_report_YYYY-MM-DD_t52_run.md
```

用途：

- 读取候选 CSV 与本地 source 文本片段。
- 输出 `suggested_quality_score`、`suggested_novelty_score`、`suggested_actionability_score`、`suggested_data_availability`、`suggested_bias_risk`、`suggested_recommended_action`、`suggested_status`。
- 输出 `review_rationale` 和 `source_excerpt`，方便人工或 LLM 二次复核。
- 不修改正式 ledger。
- 不修改 RAG manifest。

当前实现是可复现的规则型建议，定位为 LLM-ready review package。后续接入真实 LLM provider 时，必须沿用 `suggested_*` 字段，不允许直接覆盖正式字段。

## 5. 候选 CSV 与正式台账

候选 CSV 是 inbox，不是正式台账。采集器可以自动填入：

- `intelligence_id`
- `title`
- `source_type`
- `source_path_or_url`
- `published_at`
- `collected_at`
- `topic_tags`
- `strategy_tags`
- `evidence_type`
- `recommended_action`
- `status`
- `linked_strategy_task`

以下字段默认需要人工复核或人工确认：

| 字段 | 含义 | 填写方式 |
| --- | --- | --- |
| `quality_score` | 来源质量、方法严谨度、样本外验证、公开代码或数据情况 | 1-5 分，人工判断 |
| `novelty_score` | 是否提供项目当前没有的因子、数据源、方法或风控思想 | 1-5 分，人工判断 |
| `actionability_score` | 当前数据和回测框架是否能落地验证 | 1-5 分，人工判断 |
| `data_availability` | 数据可用性 | `ready` / `partial` / `missing` / `external_required` |
| `bias_risk` | 主要偏差和风险标签 | 分号分隔，例如 `overfit;future-leakage;asof` |
| `reviewed_at` | 人工复核日期 | `YYYY-MM-DD` |

这些字段不能由采集器全自动决定，因为它们代表研究判断、数据治理判断和风险判断。

复核辅助模块会额外输出 `suggested_*` 字段。它们是建议值，不是正式台账字段。正式入账前必须由人工把建议值审阅后再写入无前缀字段。

## 6. 人工复核规则

候选情报进入正式台账前，至少检查：

1. 来源是否可复查：有原始路径、URL、发表时间或明确出处。
2. 方法是否可信：不是营销材料、新闻标题或无法验证的二手摘要。
3. 与项目是否相关：能映射到因子、数据、风控、解释层、诊断工具或反方证据。
4. 数据是否可得：明确现有数据是否足够，或需要新增数据源。
5. 是否有主要风险：未来函数、幸存者偏差、过拟合、as-of、授权、文本延迟、市场迁移、交易成本。
6. 是否值得转化：明确推荐动作是归档、稍后复核、创建策略任务，还是创建数据任务。

进入候选策略任务前必须满足：

- `quality_score >= 3`
- `actionability_score >= 3`
- `data_availability` 至少为 `ready` 或 `partial`
- `bias_risk` 非空
- 已明确转化形态，例如 `ranker`、`overlay`、`filter`、`explanation`、`baseline` 或 `data_task`

## 7. 推荐动作

建议统一使用以下 `recommended_action`：

| 值 | 含义 |
| --- | --- |
| `archive_only` | 只归档，不进入近期研究 |
| `screen_later` | 有潜在价值，但暂不投入 |
| `create_strategy_task` | 可转成候选策略、overlay、filter、baseline 或诊断任务 |
| `create_data_task` | 主要价值是补数据源、字段、覆盖率或 as-of 治理 |
| `use_for_reference` | 作为架构、方法或解释层参考 |

## 8. RAG-ready 更新规则

当前 RAG-ready foundation 只定义 Markdown / CSV 语料边界，不引入向量库、SQLite 或知识图谱。

新增或修改情报资料时按以下规则同步：

| 动作 | 必须同步 |
| --- | --- |
| 新增核心 note | `knowledge/intelligence/rag_manifest.csv`、`knowledge/intelligence/wiki/index.md` |
| 新增月度扫描报告 | `knowledge/intelligence/monthly/index.md`、`knowledge/intelligence/wiki/log.md` |
| 新增 wiki 精炼页 | `knowledge/intelligence/rag_manifest.csv`、`knowledge/intelligence/wiki/index.md` |
| 情报转候选任务 | `strategy_translations/`、相关任务文档、后续实验报告路径 |
| 源文件移动或删除 | 先修复 ledger / manifest，再运行 `intelligence validate` |

RAG 只能用于检索、摘要、反方审查和任务规划，不能直接决定交易信号、准入动作或候选组合。

## 9. 月度扫描流程

月度扫描用于近 30 天新增外部情报，不等同于自动采集器的本地目录扫描。

流程：

1. 明确扫描窗口，例如 `2026-05-11` 到 `2026-06-10`。
2. 优先查公开论文、预印本、交易所/指数公司/数据源官方材料、机构 quant research 和高质量 quant blog。
3. 每条候选必须保留来源链接、发布时间和与 `stok-mapping` 的关系。
4. 报告写入 `knowledge/intelligence/monthly/strategy_intelligence_scan_YYYY-MM[_scope].md`。
5. 候选可以先写入 `data/intelligence/inbox/`，但不得自动进入正式 ledger。
6. 高价值条目经人工复核后，再补 note、translation 或任务草案。

## 10. 验收清单

一次完整的本地情报工作流完成后，应满足：

- 候选 CSV 已生成到 `data/intelligence/inbox/`。
- 采集报告已生成到 `reports/intelligence/`。
- 如执行 LLM / 人工复核辅助，复核建议 CSV 与报告已生成，且未修改正式 ledger。
- `intelligence validate` 通过，正式 ledger 和 RAG manifest 无错误。
- 候选未被自动写入正式台账。
- 本次新增正式 note、translation 或 monthly 报告时，已同步 manifest、索引和日志。
- 任何可转策略的条目，都有评分、数据可用性、偏差风险和推荐动作。

## 11. 常见问题

### CSV 中文乱码

候选 CSV 应使用 `utf-8-sig` 写出，便于 Windows Excel 直接打开。若仍乱码，优先检查文件头是否包含 UTF-8 BOM。

### 能否在 CSV 里做下拉列表

CSV 不能保存下拉、格式和校验规则。若需要人工复核表，应额外生成 `.xlsx` 工作簿，在 Excel 中为评分、状态、数据可用性和推荐动作设置下拉列表。CSV 继续作为机器可读交换格式。

### 为什么不自动填评分

评分、数据可用性和偏差风险代表研究判断。工具可以生成建议和理由，但正式入账前必须由人工确认。

### 为什么默认关闭在线源

在线源只提供元数据入口，不代表内容已被复核。默认关闭可以避免无意联网、重复候选膨胀和把未复核外部线索误当正式情报。
