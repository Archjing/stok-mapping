# AI 语料库事件研究回测引擎 实施计划

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 在现有 AI 语料库（`quant/ai_corpus/`，7 个 provider、246 行文档）之上，建成一个**事件研究（event study）回测引擎**：政策 + 公告 → 板块级 + 个股级累计超额收益（CAR），量化"这条政策/公告对股价/板块冲击多大"。

**Architecture:** 纯函数事件研究核心（市场模型 → AR/CAR → 显著性检验），配一个本地 embedding 关联层把政策文本映射到行业/主题指数，再用两个新 provider（PBOC、研报元数据）扩语料。输出 Markdown 报告，仪表盘留作后续增量。

**Tech Stack:** Python（项目已有 numpy/pandas/sqlite3）、本地 `sentence-transformers`（新增）、`market_daily_bars`/`market_index_bars`/`trading_calendar`（现有 SQLite）、`quant/ai_corpus/`（现有 provider 框架）。

---

## 1. 背景与现状（审计结论）

上一轮审计 `AI_CORPUS_IMPLEMENTATION_TASKS.md`（T1.7）结果：

| 任务 | 状态 |
| --- | --- |
| T1.7.1–T1.7.6（schema/registry/gov.cn/CCTV/CNInfo） | ✅ 已完成，代码在 `quant/ai_corpus/`（3386 行） |
| T1.7.7（存储/CLI/导出/`market_text_events` 桥接） | ⚠️ 存储/CLI 已完成，**桥接未做**（`symbols` 过滤留 `NotImplementedError` 占位） |
| T1.7.8（PBOC/研报/监管 provider） | ❌ 未做 |
| T1.7.9（RAG 索引/个股时间线） | ❌ 未做 |

关键底座事实（已实测）：

- **行情**：`data/a_share_history.sqlite` 的 `market_daily_bars`（2734 万行，2011-01-04 至 2026-08-12，含 `adjusted_close`）、`market_stocks`（110 个 `industry`）、`market_index_bars`（105 个一级行业指数 + 504 个主题指数，沪深300 `SH.000300` 基准 2015-2026 共 2818 根）、`trading_calendar`。
- **语料**：`data/ai_corpus/ai_corpus.sqlite` 的 `ai_corpus_documents`（246 行）。cninfo provider **已抽取个股代码**到 `symbols` 字段（8/100 条带代码，如 `601096`、`688025`）；gov_policy 的 `symbols` 全空（需 embedding 关联）。
- **无事件研究残留代码**（从零建，干净）。
- **`sentence_transformers` 未安装**（需新增依赖）。
- provider 开发规范见 `anthropic-skills:ai-corpus-provider-development`（注意：skill 内路径写 `phase0/ai_corpus/`，代码已迁移到 `quant/ai_corpus/`，以 `quant/` 为准）。

## 2. 用户已确认的四个方向决策

1. **主攻**：事件研究回测（不是 RAG 检索、不是情感信号）。
2. **LLM 接入**：本地 embedding 优先（`sentence-transformers`，无外部 API）。
3. **provider 补齐**：PBOC 报告 + 券商研报元数据，两个都补。
4. **落地形态**：先引擎 + Markdown 报告，仪表盘作为后续增量。

## 3. 技术设计决策（ADRs）

### 3.1 市场模型：单因子（沪深300）

```
R_it = α_i + β_i · R_mt + ε_it
```

- 估计窗口：事件日前 **[-120, -21]** 交易日（标准 100 天净窗口）。
- 基准 `R_mt` 用 `SH.000300` 的 `market_index_bars`（`adjusted_close` 的 pct_change）。
- 个股收益用 `market_daily_bars` 的 `adjusted_close` pct_change（不复权除权数据污染）。
- **不做多因子**（Fama-French 三因子在 A 股需要额外数据，YAGNI；单因子是事件研究法标准起点，先跑通）。

### 3.2 事件日对齐（防未来函数，最关键）

事件 `published_at`（政策发布/公告披露时间）到交易日的映射规则：

1. `published_at` 取日期 D。
2. 用 `trading_calendar` 找 **D 之后第一个交易日**，记为事件交易日 `T`（若 D 本身是交易日且事件在收盘后发布，实际冲击从下一交易日起；保守起见统一取 `> D` 的第一个交易日）。
3. 事件窗口相对 `T` 展开：`[-1, +1]`、`[-5, +10]`、`[-5, +20]` 三档默认。

这是与项目现有"严格交易日历映射"主线（`quant/data_governance/market_calendar.py`）一致的做法——**复用该模块**，不要自然日 +1。

### 3.3 事件→标的映射（两级）

- **个股级**：cninfo 公告的 `symbols` 字段直接映射（`601096` → `SH.601096`）。研报元数据的 `symbols` 同理。
- **板块级**：gov_policy 政策文本 embedding → 行业/主题指数名称 embedding 的余弦相似度，取 top-k（k=3）行业指数。用**本地多语言模型** `paraphrase-multilingual-MiniLM-L12-v2`（约 120MB，中文政策文本 + 中文指数名都覆盖）。
- **embedding 是关联层，不是信号**：只用于"政策 → 板块"的静态映射，不进入任何策略 ranker。符合项目"LLM 派生字段不替代原始正文"的治理铁律。

### 3.4 显著性检验

- 截面 t 检验（事件研究法 J1 检验）：CAR 均值 / (CAR 标准差 / √N)。
- 报告 CAR 均值、t 值、p 值、正负占比。不拟合参数、不挑窗口（窗口是固定先验）。

### 3.5 边界

- **不做**：把事件研究结果直接接入主 ranker、把 CAR 当交易信号、embedding 关联的行业映射落库进策略层。
- 事件研究定位：**研究情报 + 解释层**，为后续"政策/公告冲击因子"进入 admission 提供假设依据。

---

## 4. 分阶段任务（tracer-bullet 顺序，每段独立可验收）

> 依赖图：Task 1（核心引擎，无依赖）→ Task 2（映射层，依赖 1）→ Task 5（报告，依赖 1+2）→ Task 6（端到端）；Task 3、4（provider）与 1/2 并行。

### Task 1：事件研究核心引擎（市场模型 + AR/CAR + 显著性）

**Objective:** 纯函数事件研究核心，输入事件日 + 标的代码，输出 CAR + 检验统计量。

**Files:**
- Create: `quant/research/event_study/__init__.py`
- Create: `quant/research/event_study/market_model.py`
- Create: `quant/research/event_study/abnormal_returns.py`
- Create: `quant/research/event_study/aggregation.py`
- Test: `tests/test_event_study.py`

**实现要点：**

`market_model.py`：
- `load_returns(conn, symbol, start, end) -> pd.Series`：从 `market_daily_bars`（个股）或 `market_index_bars`（指数）读 `adjusted_close` 收益，按 `date` 升序。
- `estimate_beta(asset_ret, market_ret, event_idx, est_start=-120, est_end=-21) -> (alpha, beta)`：估计窗口 OLS。
- `expected_returns(asset_ret, market_ret, beta, alpha) -> pd.Series`。

`abnormal_returns.py`：
- `map_event_to_trading_day(calendar_df, published_date) -> str`：复用 `quant/data_governance/market_calendar.py`，取 `> D` 第一个交易日。
- `compute_ar_car(asset_ret, market_ret, event_date, windows) -> pd.DataFrame`：每个窗口 `[-n, +m]` 输出 AR 序列和 CAR。

`aggregation.py`：
- `cross_sectional_test(car_series) -> dict`：均值、std、t 值、p 值、N、正占比。
- `aggregate_events(car_frame, group_col) -> pd.DataFrame`：板块级/个股级聚合。

**验收：**
```
/tmp/venv-stok/bin/python -m pytest tests/test_event_study.py -q
```
- 用合成数据测：已知 β=1.5 的序列，事件日收益率 +5% 冲击，CAR 应显著为正；β 估计窗口长度不足时返回 NaN 而非崩溃；事件日落在非交易日时正确映射到下一交易日。

### Task 2：事件→标的映射层（个股直连 + 政策 embedding 关联）

**Objective:** 把 `ai_corpus_documents` 行映射为事件研究的输入（事件日 + 标的 + 窗口）。

**Files:**
- Create: `quant/ai_corpus/linking.py`
- Create: `quant/ai_corpus/linking_embed.py`（embedding 关联，独立以便不装模型时降级）
- Test: `tests/test_event_linking.py`

**实现要点：**
- `link_stock_events(docs) -> pd.DataFrame`：cninfo/研报行，`symbols` 非空 → `SH.XXXXXX`/`SZ.XXXXXX` 格式归一（6 位代码 → 前缀映射：6/9 开头 SH，0/3 开头 SZ，8 开头看 board；用 `market_stocks` 表反查最稳）。
- `link_policy_events(docs, industry_indices, model) -> pd.DataFrame`：政策文本 embedding 与行业指数名 embedding 余弦 top-k=3。
- `EmbeddingLinker` 类：懒加载 `paraphrase-multilingual-MiniLM-L12-v2`，缓存 embedding 到 `data/ai_corpus/embeddings/`（json/parquet），无网络时读缓存；**无模型时显式报错并给降级路径**（关键词 fallback）。
- 依赖注入：`pyproject.toml` 加 `sentence-transformers`（可选依赖组 `event-study`，不强制所有环境安装）。

**验收：**
```
/tmp/venv-stok/bin/python -m pytest tests/test_event_linking.py -q
```
- 代码归一化正确（`601096`→`SH.601096`，`000062`→`SZ.000062`）；`symbols` 空的政策行能产出行业指数 top-k；不装 embedding 模型时降级路径可用。

### Task 3：PBOC 货币政策报告 provider

**Objective:** 新增 `pboc` provider，抓取中国人民银行官网货币政策执行报告（公开 PDF/HTML），抽文本入库。

**Files:**
- Create: `quant/ai_corpus/providers/pboc.py`
- Modify: `quant/ai_corpus/registry.py`（加 spec + aliases + parser version）
- Modify: `quant/ai_corpus/api.py`（加分发分支）
- Modify: `quant/cli_commands/ai_corpus.py`（若需要 CLI 参数）
- Test: `tests/test_ai_corpus_pboc.py`
- Fixture: `tests/fixtures/ai_corpus/pboc/`

**实现要点（遵循 provider 开发 skill）：**
- corpus_type=`pboc_report`；`pcode`=报告期（如 `2026Q1`），`ptype`=quarter。
- 抓官方列表页 → 定位当期报告 PDF/HTML 链接 → 下载 → 抽文本（pymupdf 或 `pdftotext`，注意 skill 里 PDF 用 pymupdf 而非 pypdf）→ `raw_text` 入库。
- fixture 用真实抓取页面，测试解析逻辑而非 mock 网络。

**验收：**
```
/tmp/venv-stok/bin/python -m pytest tests/test_ai_corpus_pboc.py -q
```
- fixture 可解析出报告期、标题、正文文本；`upsert` 幂等（行数稳定，非 `==0`）。

### Task 4：券商研报元数据 provider

**Objective:** 新增 `research_report` provider，只存研报元数据 + 授权摘要，不存无授权全文。

**Files:**
- Create: `quant/ai_corpus/providers/research_report.py`
- Modify: `quant/ai_corpus/registry.py`
- Modify: `quant/ai_corpus/api.py`
- Test: `tests/test_ai_corpus_research_report.py`
- Fixture: `tests/fixtures/ai_corpus/research_report/`

**实现要点（遵循 provider 开发 skill + 计划 §11 不做清单）：**
- corpus_type=`research_report`；`parse_status` 用 `metadata_only`。
- 字段：`title`、`org`（券商）、`published_at`、`summary`（授权摘要）、`symbols`（关联个股）、`topics`（`stat:` 标签如评级/目标价）。
- **不抓取、不保存无授权全文**；只存元数据和授权摘要，`content_html`/`raw_text` 留空。
- 数据源：巨潮研报入口（公开元数据）或 AkShare 研报接口，fixture 回归。

**验收：**
```
/tmp/venv-stok/bin/python -m pytest tests/test_ai_corpus_research_report.py -q
```
- fixture 解析出券商、标题、评级、目标价、关联个股；`content_html` 为空（符合不做清单）。

### Task 5：CLI + Markdown 报告

**Objective:** 端到端命令：`ai-corpus event-study` 跑事件研究，输出 Markdown 报告 + CAR 明细 CSV。

**Files:**
- Create: `quant/research/event_study/report.py`
- Modify: `quant/cli_commands/ai_corpus.py`（加 `event-study` 子命令）
- Test: `tests/test_event_study_report.py`

**实现要点：**
- `run_event_study(*, corpus_db, market_db, provider, event_type, start, end, benchmark) -> (summary, detail, report_path)`。
- 报告内容：事件样本数、板块级 CAR 汇总表（含 t 值/p 值）、个股级 CAR 汇总表、top/bottom 冲击事件、显著性结论。
- 输出路径：`reports/runs/YYYY-MM-DD/event_study_<provider>_<event_type>.md` + `.csv`。

**验收：**
```
/tmp/venv-stok/bin/python -m pytest tests/test_event_study_report.py -q
```
- 合成事件跑通，报告文件生成且包含 CAR 汇总表、t 值、p 值。

### Task 6：端到端集成 + 真实数据验证

**Objective:** 用真实语料（246 行）+ 真实行情（2734 万行）跑通，产出一份真实事件研究报告。

**Files:**
- 无新文件；跑通 Task 1-5 的组合。
- 输出：`reports/runs/2026-08-13/event_study_gov_policy_policy.md`、`event_study_cninfo_abnormal_trading.md`

**验收：**
- gov_policy 政策（40 行）→ 板块级 CAR（用 top-3 行业指数）。
- cninfo 公告（100 行，含 8 条带代码）→ 个股级 CAR。
- 报告含样本量、CAR 均值、t 值、p 值，并注明**样本量小的统计局限**（真实数据 40-100 个事件，显著性结论要保守）。

---

## 5. Files likely to change（汇总）

新增：
- `quant/research/event_study/{__init__,market_model,abnormal_returns,aggregation,report}.py`
- `quant/ai_corpus/linking.py`、`quant/ai_corpus/linking_embed.py`
- `quant/ai_corpus/providers/pboc.py`、`quant/ai_corpus/providers/research_report.py`
- `tests/test_event_study.py`、`tests/test_event_linking.py`、`tests/test_ai_corpus_pboc.py`、`tests/test_ai_corpus_research_report.py`、`tests/test_event_study_report.py`
- `tests/fixtures/ai_corpus/{pboc,research_report}/`

修改：
- `quant/ai_corpus/registry.py`（2 个 provider spec + aliases）
- `quant/ai_corpus/api.py`（2 个分发分支 + `event-study` 入口）
- `quant/cli_commands/ai_corpus.py`（`event-study` 子命令）
- `pyproject.toml`（`sentence-transformers` 可选依赖组）

## 6. Tests / validation（全局）

```
/tmp/venv-stok/bin/python -m pytest tests/test_event_study.py tests/test_event_linking.py tests/test_ai_corpus_pboc.py tests/test_ai_corpus_research_report.py tests/test_event_study_report.py -q
```
预期：全部通过。完整套件 `pytest -q` 无新增失败。

## 7. Risks, tradeoffs, open questions

| 风险 | 影响 | 控制 |
| --- | --- | --- |
| 事件样本量小（政策 40、公告 100） | 显著性检验效力不足 | 报告明确标注样本量局限；CAR 结论保守措辞 |
| `published_at` 精度不足（无具体时分） | 事件日对齐偏一天 | 统一取 `> D` 首交易日（保守），文档记录假设 |
| 本地 embedding 模型首次下载（120MB） | 离线环境失败 | 缓存 + 无模型降级（关键词 fallback） |
| 行业指数名与政策文本语义 gap | top-k 映射不准 | top-k=3 + 人工抽查报告里附映射明细 |
| PBOC PDF 解析质量 | 正文抽取失败 | fixture 回归 + `parse_status=partial` 兜底 |
| 研报版权 | 法务风险 | 只存元数据 + 授权摘要，不存全文（硬约束） |

**开放问题（执行时定）：**
1. embedding 模型最终选型：`paraphrase-multilingual-MiniLM-L12-v2`（通用）vs `bge-small-zh-v1.5`（中文更准但更大）。默认前者，中文效果不足再换。
2. 事件窗口默认值是否要按事件类型区分（政策长期 `[-5,+20]`、公告短期 `[-1,+5]`）？默认不区分，跑出结果后再调。
3. 仪表盘（后续增量）的具体形态——等引擎报告跑通后另立计划。

## 8. 落地顺序建议

按 tracer-bullet：**Task 1 → Task 2 → Task 5 → Task 6**（核心价值链，先跑通出报告）；**Task 3、4** 并行补语料，不阻塞主线。
