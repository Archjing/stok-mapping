# T1.7｜AI 语料库开发计划

承接任务：[`T1.3｜新闻源独立模块任务单`](./NEWS_SOURCE_IMPLEMENTATION_TASKS.md)
合并来源：[`自建中文文本事件 API`](./SELF_HOSTED_CHINESE_TEXT_EVENT_API_TASKS.md) / [`自建国家政策法规库 API`](./NATIONAL_POLICY_REPOSITORY_API_TASKS.md)
任务索引：[`docs/tasks/README.md`](../README.md)
计划日期：2026-07-04

当前实施状态（2026-07-04）：

- `T1.7.1-T1.7.3` 已完成第一版工程实现：`phase0/ai_corpus/` 提供 `ai_corpus_documents` schema、provider registry、gov.cn 政策库 fixture / parser、raw archive、SQLite upsert / query 和 `ai-corpus` CLI。
- `T1.7.4` 已完成主题映射 MVP：`ptype=科技` 可稳定映射为 `subchildtype=2220`。完整 `bmzcfwjg.json` / 主题树缓存仍作为 live provider 增强项。
- `CCTV` 与 `CNInfo` 目前只在 provider registry 中标记为 planned / fixture-only，不宣称生产可用，不进入策略、日报或交易信号链路。

## 1. 目标

建设一个不依赖 Tushare 权限的本地 AI 语料库 API，统一抓取、解析、归档和查询中文公开文本资料，服务研究情报、政策事件解释、公告风险提示、关注个股时间线和后续 RAG-ready 知识库。

首期不直接生成交易信号，不直接接入主 ranker。所有文档和事件必须保留原始出处、发布时间、抓取时间、as-of 可见时间、去重键、正文哈希和原始响应路径，避免未来函数、来源不可追溯和重复入库。

## 2. 合并范围

本任务把原 `T1.3A` 和 `T1.3B` 合并为统一的 `T1.7｜AI 语料库`：

| 原计划 | 合并后的职责 |
| --- | --- |
| `T1.3A｜自建中文文本事件 API` | 提供通用文本事件 schema、CCTV 新闻联播 provider、CNInfo 公告 provider、PBOC 报告和研报元数据扩展方向 |
| `T1.3B｜自建国家政策法规库 API` | 提供国家政策法规库的独立公开源调研、gov.cn 列表接口、正文 parser 和 `npr` 兼容 API |

`T1.3` 仍保留为新闻源独立模块的父任务；`T1.7` 是其中文公开文本和政策语料的具体开发任务。

## 3. 数据源边界

### 3.1 第一优先级：国家政策法规库

已独立验证的官方入口：

- 中国政府网政策文件库入口：`https://www.gov.cn/zhengce/zhengcewenjianku/`
- 实际跳转入口：`https://sousuo.www.gov.cn/zcwjk/policyDocumentLibrary?q=&t=zhengcelibrary&orpro=`
- 列表数据接口：`https://sousuo.www.gov.cn/search-gov/data`
- 国务院部门字典：`https://www.gov.cn/zhengce/bmzcfwjg.json`

`/search-gov/data` 已观察到可用字段：`title`、`url`、`pcode`、`puborg`、`childtype`、`pubtime`、`pubtimeStr`、`index`、`summary`、`id`。

已验证或从官方前端确认的查询参数：

| 参数 | 含义 | 说明 |
| --- | --- | --- |
| `q` | 关键词 | 支持标题 / 内容检索 |
| `t` | 文件库范围 | `zhengcelibrary`、`zhengcelibrary_gw`、`zhengcelibrary_bm`、`zhengcelibrary_gb` 等 |
| `p` | 页码 | 0-based |
| `n` | 每页条数 | 服务端可能有实际 cap，本地循环分页控制总量 |
| `puborg` | 国务院文件发文机关 | 如 `国务院`、`国务院办公厅` |
| `bmfl` | 国务院部门文件机构 | 如 `工业和信息化部` |
| `pcodeJiguan` | 发文字号前缀 | 如 `国发`、`国办发`、`国函` |
| `childtype` | 主题父类 ID | 例：`1088` = 科技、教育 |
| `subchildtype` | 主题子类 ID | 例：`2220` = 科技 |
| `timetype` | 时间筛选模式 | 自定义时间使用 `timezd` |
| `mintime` | 发布开始日期 | `YYYY-MM-DD` |
| `maxtime` | 发布结束日期 | `YYYY-MM-DD` |

目标参数映射：

| 本地 API 参数 | 官方接口映射 | 处理规则 |
| --- | --- | --- |
| `org=国务院` | `t=zhengcelibrary_gw` + `puborg=国务院` | 国务院 / 国务院办公厅优先走 `puborg` |
| `org=工业和信息化部` | `t=zhengcelibrary_bm` + `bmfl=工业和信息化部` | 部门文件走 `bmfl`，机构名来自 `bmzcfwjg.json` |
| `ptype=科技` | `subchildtype=2220` | 通过主题分类树缓存从名称映射 ID |
| `ptype=科技、教育` | `childtype=1088` | 父类主题映射到 `childtype` |
| `start_date` | `mintime` + `timetype=timezd` | datetime 输入裁剪为日期，同时保留审计参数 |
| `end_date` | `maxtime` + `timetype=timezd` | 同上 |
| `keyword` | `q` | 默认搜索标题、正文和摘要 |
| `limit` | `n` + 多页循环 | 单次上限由本地 API 控制 |

已验证正文页样例：

- 国务院文件页：`https://www.gov.cn/zhengce/zhengceku/202508/content_7037862.htm`
- 国务院部门文件页：`https://www.gov.cn/zhengce/zhengceku/202605/content_7068153.htm`

正文页 parser 首期抽取：

- `meta[name=firstpublishedtime]`
- 元数据表：标题、发文机关、发文字号、发布日期、主题分类、成文日期、公文种类、来源等
- `#UCAP-CONTENT` 正文 HTML

### 3.2 第二优先级：CCTV 新闻联播文字稿

首个新闻文本 MVP 仿照 `cctv_news` 调用体验，但实现不依赖 Tushare。

已确认的现代日期页格式：

```text
https://tv.cctv.com/lm/xwlb/day/YYYYMMDD.shtml
```

首期只承诺 2016-02-03 以后现代路径。历史路径差异单独立项，不纳入 MVP 验收。

抓取内容：

- 日期页中的完整节目链接和分段视频链接
- 分段页 `title`、`contentid`、`keywords`、`description`、`.video_brief`、`#content_area`
- 完整节目页 `.video_brief` 当日节目概要

### 3.3 第三优先级：公告数据库

首期 provider：

- AkShare / CNInfo 作为低成本抓取入口
- 巨潮官方字段作为长期优先方向
- Tushare `anns_d` 只作为有权限后的可替换 provider 或兼容接口参考

首批事件类型：

- `announcement`
- `abnormal_trading`
- `trading_risk_warning`
- `severe_abnormal_trading`
- `earnings_forecast`
- `major_contract`
- `shareholder_change`

验收重点：按 `announcementId` 去重；标题含 `风险提示` 时必须做语义过滤，避免混入可转债适当性、退市、摊薄等无关公告。

### 3.4 后续扩展：央行报告、研报元数据、监管规则

- PBOC 货币政策执行报告：优先抓取中国人民银行官网公开 PDF / HTML，保存原 PDF、抽取文本和报告页回链。
- 券商研报库：第一阶段只做元数据和授权摘要，不抓取或再分发付费全文。
- 监管规则和法律法规：后续扩展到全国人大法律法规库、证监会、交易所、发改委、财政部、工信部等公开站点。

## 4. 统一数据模型

建议新增 AI 语料库主表，并保留到 `market_text_events` 的事件桥接。

### 4.1 主表：`ai_corpus_documents`

| 字段 | 说明 |
| --- | --- |
| `document_id` | 本地稳定 ID，由 provider、source_id、content_hash 派生 |
| `corpus_type` | `policy`、`regulation`、`cctv_news`、`announcement`、`pboc_report`、`research_report` 等 |
| `event_type` | 事件分类，可与 `market_text_events` 对齐 |
| `provider` | `gov_cn`、`cctv`、`cninfo`、`pboc`、`broker_report` 等 |
| `source` | 原始发布方，如中国政府网、央视网、巨潮资讯、中国人民银行 |
| `source_id` | 上游内容 ID，如 gov.cn `id`、CCTV `contentid`、巨潮 `announcementId` |
| `published_at` | 上游发布时间 |
| `issued_at` | 成文日期 / 报告期 / 事件发生日期，可为空 |
| `ingested_at` | 本系统抓取时间 |
| `as_of_time` | 本系统对回测可见的最早时间 |
| `title` | 标题 |
| `summary` | 官方摘要或本地派生摘要 |
| `content_html` | 正文 HTML，若授权和用途允许保存 |
| `raw_text` | 正文纯文本或可授权保存文本 |
| `url` | 原文 URL |
| `org` | 发布机构 / 发文机关 |
| `pcode` | 发文字号 |
| `ptype` | 政策主题分类 |
| `symbols` | 关联证券代码列表，可为空 |
| `industries` | 关联行业，可为空 |
| `topics` | 主题标签 |
| `language` | 默认 `zh-CN` |
| `dedupe_key` | 去重键 |
| `content_hash` | 正文哈希 |
| `raw_path` | 原始响应本地路径 |
| `parse_status` | `ok`、`partial`、`failed`、`not_available_yet` |
| `source_confidence` | 来源可信度或解析完整度 |
| `parser_version` | parser 版本 |

### 4.2 事件桥接：`market_text_events`

不是所有语料都天然是市场事件。进入 `market_text_events` 前必须明确：

- 是否有可审计发布时间
- 是否有可审计 as-of 可见时间
- 是否能映射到证券、行业、主题或宏观事件
- 是否只是研究语料，不应进入事件时间线

## 5. API 设计

### 5.1 通用 Python API

```python
fetch_ai_corpus(
    provider: str | None = None,
    corpus_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    org: str | None = None,
    ptype: str | None = None,
    symbols: list[str] | None = None,
    topics: list[str] | None = None,
    keyword: str | None = None,
    include_content: bool = True,
    fields: list[str] | None = None,
    limit: int = 500,
) -> pandas.DataFrame
```

### 5.2 国家政策法规库兼容 API

```python
fetch_national_policy_repository(
    org: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    ptype: str | None = None,
    keyword: str | None = None,
    collection: str = "all",
    fields: list[str] | None = None,
    limit: int = 500,
    include_content: bool = True,
) -> pandas.DataFrame
```

兼容别名：

```python
npr(
    org: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    ptype: str | None = None,
    fields: str | None = None,
) -> pandas.DataFrame
```

目标输出字段：`pubtime`、`title`、`url`、`content_html`、`pcode`、`puborg`、`ptype`，并追加 `source_id`、`index_no`、`collection`、`content_hash`、`ingested_at`、`as_of_time`、`raw_path`、`parse_status` 等审计字段。

### 5.3 CCTV 专用 API

```python
fetch_cctv_news(
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    include_segments: bool = True,
    mode: str = "standard",
) -> pandas.DataFrame
```

`mode`：

- `standard`：输出统一 AI 语料库字段
- `segments`：按新闻联播分段输出，每条分段一行
- `daily_summary`：按完整节目输出，每天一行
- `tushare_compat`：输出兼容接口形态的最小字段：`date`、`title`、`content`

### 5.4 CLI 入口

首期不引入 HTTP 服务，先提供本地 CLI 和 Python API：

```bash
./runit ai-corpus fetch --provider gov-policy --org 国务院 --ptype 科技 --end-date '2025-08-26 17:00:00'
./runit ai-corpus fetch --provider cctv --start-date 20260703 --end-date 20260703
./runit ai-corpus query --corpus-type policy --keyword 人工智能 --format markdown
./runit ai-corpus export --provider cninfo --event-type abnormal_trading --start-date 20260630 --end-date 20260702
```

如果后续需要给其他本地工具调用，再用 FastAPI 暴露只读查询接口；不在 MVP 阶段增加服务化复杂度。

## 6. 模块边界

推荐新增独立 provider 层，避免扩大行情日线模块职责：

```text
phase0/ai_corpus/
  __init__.py
  schema.py
  registry.py
  storage.py
  providers/
    gov_policy.py
    cctv.py
    cninfo.py
    pboc.py
    research_report.py
```

如果首期为了降低改动面，也可以先放在 `phase0/news_sources.py`，但接口边界要按 provider 形态设计，后续能无痛迁移。

数据路径：

| 类型 | 路径 |
| --- | --- |
| 原始列表响应 | `data/raw_data/ai_corpus/<provider>/search/YYYY/MM/DD/` |
| 原始正文 HTML / PDF | `data/raw_data/ai_corpus/<provider>/content/YYYY/MM/DD/` |
| 清洗文档 | `data/features/ai_corpus/<provider>_documents_YYYYMMDD.parquet` |
| 字典缓存 | `data/reference/ai_corpus/<provider>/` |
| parser fixture | `tests/fixtures/ai_corpus/<provider>/` |

## 7. 分阶段开发任务

| 任务号 | 阶段 | 工作内容 | 预计工作量 | 验收标准 |
| --- | --- | --- | ---: | --- |
| `T1.7.1` | P0 | 定义 schema、provider registry、原始数据路径、fixtures 规则 | 0.5-1 天 | schema 字段稳定，fixture 路径和 raw_path 规则明确 |
| `T1.7.2` | P1 | 实现 gov.cn 政策库 source probe、列表 provider、分页、字段清洗 | 1 天 | 可按 `org/start_date/end_date/ptype/keyword` 返回列表字段 |
| `T1.7.3` | P2 | 实现 gov.cn 正文 parser、元数据表抽取、`content_html` 保存 | 1-2 天 | `content_html` 非空，列表字段和正文 metadata 可交叉校验 |
| `T1.7.4` | P3 | 实现政策主题 / 机构字典缓存和 `npr` 兼容别名 | 0.5-1 天 | `ptype=科技` 稳定映射到 `subchildtype=2220` |
| `T1.7.5` | P4 | 实现 CCTV provider、日期页 parser、分段正文 parser、`tushare_compat` 输出 | 1-2 天 | `20260703` fixture 可稳定解析标题、URL、content_id 和正文 |
| `T1.7.6` | P5 | 实现 CNInfo / AkShare 公告 provider 与异常波动 / 风险提示专项事件 | 1-2 天 | 能复现最近 3 天清洗口径，按公告 ID 去重 |
| `T1.7.7` | P6 | 接入本地存储、CLI 查询、导出和 `market_text_events` 桥接 | 1-2 天 | 同一日期重复运行不重复入库，可按日期 / 类型 / 关键词查询 |
| `T1.7.8` | P7 | 扩展 PBOC 报告、研报元数据和监管规则 provider | 3-5 天 | 每类 provider 至少 1 个公开样本、字段审计和授权说明 |
| `T1.7.9` | P8 | 建立 RAG-ready 索引、关注个股事件时间线和日报解释层接口 | 2-4 天 | 能为单股生成可追溯文本事件时间线 |

推荐先做 `T1.7.1` 到 `T1.7.4`。国家政策法规库已有明确官方入口和字段映射，最适合作为第一条稳定 provider 验证 schema、parser、分页、as-of 和 raw archive 规则。

## 8. 验收样例

### 8.1 国务院科技类文件

输入：

```python
npr(
    org="国务院",
    ptype="科技",
    end_date="2025-08-26 17:00:00",
    fields="pubtime,title,pcode,puborg,ptype,url,content_html",
)
```

应至少返回：

- `title`: `国务院关于深入实施“人工智能+”行动的意见`
- `pcode`: `国发〔2025〕11号`
- `puborg`: `国务院`
- `ptype`: `科技、教育\科技`
- `url`: `https://www.gov.cn/zhengce/zhengceku/202508/content_7037862.htm`
- `content_html`: 非空，来自 `#UCAP-CONTENT`

### 8.2 国务院部门文件

输入：

```python
fetch_national_policy_repository(
    org="工业和信息化部",
    keyword="人工智能",
    collection="department",
    limit=20,
)
```

应返回国务院部门文件列表，且结果中 `puborg` 包含或等于 `工业和信息化部`。

### 8.3 CCTV 新闻联播

输入：

```python
fetch_cctv_news(date="20260703", include_segments=True)
```

应返回当日完整节目或分段列表，至少包含标题、URL、`content_id`、正文或摘要、`published_at`、`ingested_at`、`as_of_time`、`dedupe_key`。

### 8.4 异常波动 / 风险提示公告

输入：

```bash
./runit ai-corpus export --provider cninfo --event-type abnormal_trading --start-date 20260630 --end-date 20260702
```

应能复现前期清洗口径：从近 3 天 A 股公告中筛选异常波动公告、交易风险提示公告，并记录 raw rows、清洗后 rows、日期范围、过滤规则和抽样审计结果。

## 9. 测试与审计要求

- Parser fixture 测试：gov.cn 列表 JSON、政策正文 HTML、CCTV 日期页、CCTV 分段页、公告列表样例。
- Schema 测试：必填字段存在，日期格式统一，`published_at`、`issued_at`、`ingested_at`、`as_of_time` 不混用。
- 去重测试：同一 URL、同一 `source_id`、同一标题发布时间、同一正文哈希不会重复入库。
- 字典测试：机构名和主题分类映射失败时必须返回可定位错误，不静默降级为全量查询。
- 集成测试：联网 probe 默认可跳过，手动运行时记录 URL、行数、字段、HTTP 状态和失败原因。
- 数据治理：每次抓取记录 provider 版本、parser 版本、抓取时间、原始路径和清洗报告。
- LLM 约束：任何 LLM 摘要都必须作为派生字段或派生文档，不能替代原始正文和原文链接。

## 10. 风险与控制

| 风险 | 影响 | 控制方式 |
| --- | --- | --- |
| gov.cn `/search-gov/data` 是前端接口，未承诺长期稳定 | 列表抓取可能失效 | provider 版本化、fixture 回归、保留 HTML 搜索页 fallback |
| 政策正文模板新旧不一 | `content_html` 或 metadata 抽取失败 | 多模板 parser，按 DOM 结构分流 |
| `pubtime` 与成文日期混淆 | 回测 as-of 污染 | `published_at/pubtime` 只表示发布时间，成文日期另存 `issued_at` |
| 主题分类使用 ID | `ptype` 名称无法直接筛选 | 缓存 `ztflTree`，支持父类和子类名称映射 |
| CCTV 页面结构变化 | Parser 失效 | fixture 回归测试、source probe 报告、provider 失败日志 |
| 当天节目未上线 | 空结果被误判为无新闻 | 早于上线时间返回 `not_available_yet` |
| 公告关键词噪声 | 风险提示结果混入无关公告 | 标题语义过滤、类型分类、抽样审计 |
| 研报版权 | 法务和再分发风险 | 先做元数据和授权摘要，不存无授权全文 |
| 抓取频率过高 | 被限流或不稳定 | 缓存、限流、增量抓取、失败退避 |
| 文本事件被误用为交易信号 | 策略风险和过拟合 | 只进入解释层和研究情报层，进入策略前必须另走 admission |

## 11. 不做清单

- 不依赖 Tushare 网站或 Tushare 高权限接口作为首期主源。
- 不在 MVP 阶段建设 HTTP 服务或多租户权限系统。
- 不抓取、保存或再分发无授权券商研报全文。
- 不把政策、公告、新闻或 LLM 摘要直接接入主 ranker。
- 不用正文发布时间替代本系统 `as_of_time`。
- 不用正则直接拼大型 HTML 正文；优先使用结构化 HTML parser。

## 12. 推荐下一步

1. 先实现 `T1.7.1`：schema、provider registry、fixture 目录和 raw archive 规则。
2. 再实现 `T1.7.2-T1.7.4`：gov.cn 政策库列表、正文 parser、字典缓存和 `npr` 兼容 API。
3. 完成 gov.cn provider 后，再接 `T1.7.5` CCTV 新闻联播 provider。
4. 第三条 provider 选择 CNInfo / AkShare 公告，以异常波动和交易风险提示公告为专项验收。
5. 最后扩展 PBOC 报告、研报元数据和 RAG-ready 索引。
