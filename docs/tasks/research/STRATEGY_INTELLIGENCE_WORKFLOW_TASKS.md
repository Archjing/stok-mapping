# T5.2｜投资策略情报搜集、评估、维护、提炼与解读模块

## T5.2.1 背景

项目启动阶段的候选策略设计来自 `refdocs/papers/` 中的论文搜集和解读。后续实践证明，外部论文、研究报告、公告新闻和策略线索会持续影响项目的因子方向、数据建设顺序、候选策略优先级和风险判断。

因此需要把情报工作流从“零散资料归档”升级为可维护的研究情报层，形成可追溯链路：

```text
情报来源 -> 筛选评估 -> 解读提炼 -> 策略假设 -> 候选任务 -> 实验结果 -> 归档复盘
```

## T5.2.2 模块定位

本模块属于研究情报层，不属于交易信号层。

它负责：

- 管理论文、研究报告、公告新闻等外部情报。
- 评估情报质量、创新性、可落地性、数据要求和偏差风险。
- 把高质量情报转化为候选策略任务、数据建设任务或研究假设。
- 维护情报与候选策略之间的追溯关系。

它不负责：

- 直接生成买卖信号。
- 绕过 `db-health`、PIT、回测、过拟合诊断或策略准入门禁。
- 把新闻公告或 LLM 摘要直接作为主 ranker。
- 自动爬取全网内容。

## T5.2.3 V1 产物

当前 V1 采用 Markdown + CSV，不引入数据库。

| 产物 | 路径 | 状态 |
| --- | --- | --- |
| 情报库说明 | `refdocs/intelligence/README.md` | 已创建 |
| 情报总台账 | `refdocs/intelligence/strategy_intelligence_ledger.csv` | 已创建 |
| 情报解读模板 | `refdocs/intelligence/templates/intelligence_note_template.md` | 已创建 |
| 情报转策略模板 | `refdocs/intelligence/templates/strategy_translation_template.md` | 已创建 |
| 自动采集器 V1 | `phase0.cli intelligence` / `phase0/intelligence.py` | 已创建 |

## T5.2.4 情报来源范围

V1 覆盖：

- 论文：`refdocs/papers/` 中的中英文量化投资论文。
- 研究报告：券商策略、量化报告、宏观策略、行业研究。
- 公告新闻：只作为事件线索、解释材料或研究假设，不直接生成交易信号。

V1 自动采集器覆盖：

- 本地论文/研报目录扫描：`local_dir`
- 论文/研报索引元数据接口预留：`arxiv`、`openalex`、`crossref`
- 手工配置 RSS 元数据入口：`rss`

V1 暂不做：

- 全网自动搜索。
- 自动抓取付费研报。
- 大规模新闻爬虫。
- 情报知识图谱或 SQLite 化。
- 自动把候选情报写入正式台账。

## T5.2.5 情报台账字段

`strategy_intelligence_ledger.csv` 使用以下字段：

```text
intelligence_id
title
source_type
source_path_or_url
published_at
collected_at
market_scope
topic_tags
strategy_tags
evidence_type
quality_score
novelty_score
actionability_score
data_availability
bias_risk
recommended_action
status
linked_strategy_task
reviewed_at
```

## T5.2.6 状态流转

```text
collected
screened
evaluated
translated
experiment_planned
accepted
rejected
archived
```

状态含义：

- `collected`：已收集，未筛选。
- `screened`：已初筛，有研究价值但未形成完整策略判断。
- `evaluated`：已完成质量、落地性和风险评估。
- `translated`：已转化为候选策略或数据建设任务。
- `experiment_planned`：已进入实验排期。
- `accepted`：实验后确认可保留。
- `rejected`：实验后确认不保留。
- `archived`：仅保留背景资料，不进入近期研究。

## T5.2.7 评分口径

评分范围：`1-5`。

| 维度 | 含义 |
| --- | --- |
| `quality_score` | 来源质量、方法严谨度、样本外验证、是否有公开代码/数据 |
| `novelty_score` | 是否提供当前项目没有的因子、数据源、建模方法或风控思想 |
| `actionability_score` | 是否能用当前数据和回测框架落地 |

数据可用性：

```text
ready
partial
missing
external_required
```

偏差风险必须记录：

- 未来函数
- 幸存者偏差
- 样本内过拟合
- 文本延迟
- 数据授权风险
- 市场迁移风险
- 流动性与交易成本风险

## T5.2.8 策略转化门禁

情报进入候选策略任务前必须满足：

- [ ] `quality_score >= 3`
- [ ] `actionability_score >= 3`
- [ ] 数据路径明确，至少为 `ready` 或 `partial`
- [ ] 已记录主要偏差风险
- [ ] 已明确转化形态：`主 ranker / overlay / filter / explanation / baseline / data task`
- [ ] 若涉及文本、公告或新闻，必须先满足文本事件数据层的 as-of、去重、覆盖率和授权治理要求

## T5.2.9 首批补录范围

已从现有资料补录首批 20 条情报：

- 中文 A 股论文 10 条：`INT-CN-001` 到 `INT-CN-010`
- 英文量化论文 10 条：`INT-EN-001` 到 `INT-EN-010`

重点追溯关系：

| 情报 | 对项目的作用 |
| --- | --- |
| `INT-CN-007` LASSO 因子边际有效性 | 支撑 `T2.5` 因子有效性诊断和因子冗余控制 |
| `INT-CN-005` 资产特征组合选择 | 支撑 `T2.6 / T2.7` 质量低换手方向 |
| `INT-CN-008` 分析师文本量化 | 支撑 `T1.3 / T2.10` 文本事件层和 PEAD 研究 |
| `INT-EN-003` StockMixer | 支撑后续 KISS 风格 ML baseline，而不是优先复杂 Transformer |
| `INT-EN-006` AI portfolio review | 支撑系统架构中 AI 作为研究辅助和解释层的定位 |

## T5.2.10 后续任务

- [x] 创建 `refdocs/intelligence/` 情报库目录
- [x] 创建情报总台账 CSV
- [x] 创建情报解读模板
- [x] 创建情报转候选策略模板
- [x] 补录首批 20 条既有论文情报
- [x] 新增自动采集器 V1：搜索/抓取元数据/导入候选情报
- [x] 新增情报台账校验命令
- [x] 默认只启用本地论文目录扫描，在线源以配置方式预留但关闭
- [ ] 为 `INT-CN-007` 生成完整情报解读 note
- [ ] 为 `INT-CN-005` 生成完整情报解读 note
- [ ] 为 `INT-CN-008` 生成完整情报解读 note
- [ ] 建立 `Strategy Intelligence Monthly Scan`：每月搜集近 30 天发表/发布的量化策略情报，并输出月度扫描报告
- [ ] 建立情报台账的定期维护流程：新增、复评、归档、淘汰
- [ ] 将通过门禁的情报转入 `docs/STRATEGY_DEV_CHECKLIST.md` 风格的候选策略任务单
- [ ] 后续评估是否需要 SQLite / 知识图谱 / 双链同步

## T5.2.11 验收标准

- [x] 情报模块有独立任务文档
- [x] 情报库有 README、台账和模板
- [x] 首批台账不少于 10 条，当前已 20 条
- [x] 每条情报包含来源、标签、评分、状态、推荐动作和关联任务
- [x] 项目计划、周任务清单和架构文档有入口
- [x] `phase0.cli intelligence import-local` 可把本地资料导入候选 CSV
- [x] `phase0.cli intelligence collect` 可按配置采集候选 CSV
- [x] `phase0.cli intelligence validate` 可校验正式台账
- [ ] 至少 3 条核心情报完成完整 Markdown 解读 note
- [ ] 至少 1 条情报完成“转候选策略任务”模板填充
- [x] 至少 1 次近 30 天月度策略情报扫描完成归档，并对高价值情报给出策略假设、数据需求和风险判断

## T5.2.12 自动采集器 V1

### T5.2.12.1 命令

```bash
./.venv/bin/python -m phase0.cli intelligence import-local --config config.yaml --source-dir refdocs/papers
./.venv/bin/python -m phase0.cli intelligence collect --config config.yaml
./.venv/bin/python -m phase0.cli intelligence validate --config config.yaml
```

### T5.2.12.2 输出

- 候选情报 CSV：`data/intelligence/inbox/intelligence_candidates_YYYY-MM-DD.csv`
- 采集报告：`reports/intelligence/intelligence_collect_report_YYYY-MM-DD.md`
- 本地导入报告：`reports/intelligence/intelligence_import_local_report_YYYY-MM-DD.md`
- 台账校验报告：`reports/intelligence/intelligence_validate_report_YYYY-MM-DD.md`

候选 CSV 不是正式台账。人工筛选、评分、补充偏差风险后，才可并入 `refdocs/intelligence/strategy_intelligence_ledger.csv`。

### T5.2.12.3 边界

- 默认只扫描 `refdocs/papers/`。
- `arxiv`、`openalex`、`crossref`、`rss` 仅采集元数据和链接，默认关闭。
- 不抓取付费研报全文。
- 不替代 T1.3 文本/新闻数据层。
- 不直接把情报转为交易信号。

## T5.2.13 Strategy Intelligence Monthly Scan

### T5.2.13.1 目标

每月执行一次近 30 天量化策略情报扫描，把最新论文、机构研究、指数公司资料、交易所/数据源官方说明和高质量 quant blog 中的策略线索转入项目情报工作流。

该任务的核心价值不是“多收集链接”，而是持续发现可验证的策略假设、数据建设需求和反方证据，服务 `T2.5-T2.10` 有效策略重建。

### T5.2.13.2 输入范围

- 近 30 天发表或发布的论文、预印本和正式期刊文章。
- 近 30 天发布的券商金工、指数公司、交易所、数据源和机构 quant research。
- 与 A 股本土因子、PEAD、文本事件、跨市场增强、组合构建、成本后验证、过拟合诊断有关的资料。
- 可提供明确来源、发布时间和可复查链接的公开资料。

### T5.2.13.3 输出

- 月度扫描报告：`refdocs/intelligence/monthly/strategy_intelligence_scan_YYYY-MM.md`
- 候选情报清单：可先进入 `data/intelligence/inbox/`，人工筛选后再写入正式台账。
- 对每条高价值情报至少记录：
  - 发布时间
  - 来源链接
  - 核心观点
  - 可验证策略假设
  - 所需数据
  - 实现成本
  - 过拟合 / 数据偏差 / 授权风险
  - 推荐动作：`archive_only` / `screen_later` / `create_strategy_task` / `create_data_task`

### T5.2.13.4 验收标准

- [x] 报告明确扫描窗口，例如 `2026-05-09` 到 `2026-06-09`。
- [x] 每条入选情报都有来源链接、发布时间和项目内用途判断。
- [x] 至少筛出 3 条可转化为策略假设或数据建设任务的高价值情报。
- [x] 不把新闻、博客或营销材料直接当作策略有效性证据。
- [x] 不绕过 T5.2 情报门禁，所有正式入账仍需人工评分和偏差风险复核。
