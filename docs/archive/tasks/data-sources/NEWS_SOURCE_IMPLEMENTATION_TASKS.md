# T1.3｜新闻源独立模块任务单

适用场景：为 `stok-mapping` 引入独立新闻源与文本事件数据层，服务盘前研判、关注个股分析工具、PEAD 研究、跨市场解释层和后续文本摘要因子。该任务不改变当前策略主线，不让新闻或 LLM 直接生成交易信号。

父级计划：[`DEVELOPMENT_PLAN.md`](../../DEVELOPMENT_PLAN.md)  
任务索引：[`docs/tasks/README.md`](../README.md)

---

## T1.3.0 目标

- [ ] 将新闻源从 Tiingo EOD 日线适配器中拆出，独立成 `news_sources` 模块
- [ ] 先验证 Alpha Vantage `NEWS_SENTIMENT` 的可用性，不直接承诺长期主源
- [ ] 记录 Benzinga Newsfeed 作为后续生产级候选
- [ ] 明确 Finnhub 仅作为单票 company news 备选，不进入首批主新闻源
- [ ] 建立统一文本事件数据层，覆盖公告、研报、新闻、政策、快讯和后续可扩展事件源
- [ ] 每条文本事件必须保留来源、发布时间、抓取时间、去重键和 as-of 可见性说明

---

## T1.3.1 Provider 分工

### T1.3.1.1 Tiingo

- [x] 保留为美股个股 / ETF / ADR 的 EOD 日线源
- [x] 不作为新闻源继续扩展
- [x] 当前 token 访问 `/tiingo/news` 返回 `403 permission_denied:news_api`

### T1.3.1.2 Alpha Vantage

- [ ] 作为第一轮低成本新闻源 probe provider
- [ ] 验证 `tickers`
- [ ] 验证 `topics`
- [ ] 验证 `time_from / time_to`
- [ ] 验证 `sort / limit`
- [ ] 验证返回字段是否可标准化为项目新闻结构

### T1.3.1.3 Benzinga

- [ ] 作为后续付费 / 生产级候选
- [ ] 评估 ticker、channel/topic、date range、实时性、成本和授权边界

### T1.3.1.4 Finnhub

- [ ] 仅作为单票 company news 备选
- [ ] 不作为第一优先级主新闻源

### T1.3.1.5 Tushare / 中文财经上游源

- [ ] 评估 Tushare 独立权限接口：`research_report`、`anns_d`、`major_news`、`npr`、`cctv_news`
- [ ] 记录 `research_report` 和 `anns_d` 为公司级文本事件优先源
- [ ] 记录 `major_news` 为结构化主新闻流候选，但需评估权限、延迟、字段完整性和可追溯性
- [ ] 记录 `npr` 为政策文本候选源，不作为短期交易信号
- [ ] 将 `rt_k / rt_min_daily` 视为盘中行情辅助，不混入新闻正文事件表
- [ ] 保留 Tushare 聚合新闻看板上游来源调查作为 provider 选择参考：[`refdocs/tushare_news_dashboard_upstream_mapping_note_2026-06-06.md`](../../../refdocs/tushare_news_dashboard_upstream_mapping_note_2026-06-06.md)

### T1.3.1.6 公开上游与替代源

- [ ] 新浪财经、财联社、华尔街见闻、中证网等只作为替代上游源候选，接入前必须评估抓取稳定性、授权边界和维护成本
- [ ] 公告优先使用 Tushare `anns_d` 或交易所 / 巨潮等官方披露源，不优先依赖财经门户转载
- [ ] 研报优先使用 Tushare `research_report` 或稳定授权源，不把网页标题抓取直接当正式研究底座

---

## T1.3.2 代码设计

### T1.3.2.1 模块边界

- [ ] 新增 `phase0/news_sources.py`
- [ ] 不把新闻 provider 塞进 `phase0/data_sources.py` 的行情日线职责
- [ ] 不接入 `phase0 run` 主链路，先保留为独立 probe / report

### T1.3.2.2 统一接口

目标接口：

```python
fetch_news(
    tickers=None,
    topics=None,
    start=None,
    end=None,
    limit=50,
    provider="alpha_vantage",
)
```

标准输出字段：

- `published_at`
- `title`
- `source`
- `url`
- `tickers`
- `topics`
- `summary`
- `provider`

### T1.3.2.3 统一文本事件模型

第一版事件表建议命名为 `market_text_events`，也可以先以 parquet / CSV 形式落到 `data/features/news/`，等数据口径稳定后再进入 SQLite。

核心字段：

- `event_id`
- `event_type`
- `provider`
- `source`
- `published_at`
- `ingested_at`
- `as_of_time`
- `title`
- `summary`
- `raw_text`
- `url`
- `symbols`
- `industries`
- `topics`
- `language`
- `dedupe_key`
- `content_hash`
- `source_confidence`

事件类型第一版：

- `announcement`
- `research_report`
- `major_news`
- `policy`
- `cctv_news`
- `market_flash`
- `derived_summary`

边界要求：

- [ ] `published_at` 表示上游发布时点，`ingested_at` 表示本系统抓取时点，二者不能混用
- [ ] `as_of_time` 必须用于后续回测或因子实验，避免文本事件未来函数
- [ ] `derived_summary` 必须保留原始事件引用，不替代原始文本事件
- [ ] 去重优先使用 `url / title / published_at / source`，并保留 `content_hash` 供后续复核

---

## T1.3.3 组合新闻过滤原则

- [ ] 不把多个 ticker 一次性传入后假设 provider 使用 OR 语义
- [ ] 组合观察池新闻应逐 ticker 请求
- [ ] 聚合层按 `url / title / published_at` 去重
- [ ] 项目内部业务标签需要映射到 provider 的固定 topic 枚举
- [ ] 主题过滤只作为筛选辅助，不替代 ticker 过滤

---

## T1.3.4 数据放置边界

- [ ] 原始响应进入 `data/raw_data/news/<provider>/`
- [ ] 清洗后的新闻事件表进入 `data/features/news/`
- [ ] 公司公告、研报、主新闻流和政策文本统一标准化为文本事件，不分散到互不兼容的目录和字段口径
- [ ] 探测报告进入 `reports/`
- [ ] 新闻摘要和盘前解释输出仍属于 `reports/` 或日报交付物

---

## T1.3.5 验收标准

- [ ] 可用独立脚本验证 Alpha Vantage 新闻权限和字段结构
- [ ] 能分别验证 ticker、topic、time window 三类过滤条件
- [ ] 能验证组合观察池逐 ticker 拉取和去重逻辑
- [ ] 生成 `reports/news_source_probe_report.md`
- [ ] 能按 `symbol / source / event_type / published_at` 查询文本事件
- [ ] 能输出文本事件覆盖率、抓取延迟、重复率和来源失败原因
- [ ] 能生成单股事件时间线，服务关注个股分析工具
- [ ] 文档明确新闻源不直接进入主 ranker，不直接生成交易信号

---

## T1.3.6 后续开发分阶段

### T1.3.6.1 P0：数据模型与 probe

- [ ] 确定 `market_text_events` 字段口径
- [ ] 对 `research_report`、`anns_d`、`major_news` 做权限和字段 probe
- [ ] 输出来源覆盖、抓取延迟、字段完整性和失败原因报告

### T1.3.6.2 P1：事件入库与查询

- [ ] 实现文本事件标准化与去重
- [ ] 支持按股票、行业、日期、来源和事件类型查询
- [ ] 为关注个股分析工具提供事件时间线输入

### T1.3.6.3 P2：解释层与研究沙盒

- [ ] 生成单股事件时间线和日报事件解释
- [ ] 为 `T2.10` PEAD / 文本因子提供覆盖率和滞后性诊断输入
- [ ] LLM 只做摘要、聚类和解释，不直接生成评分或交易动作

---

## T1.3.7 一句话提醒

> 新闻源模块的目标是服务事件解释、风险提示、关注个股分析和后续文本因子研究，不是把文本情绪提前放进交易决策主链路。
