# T1.3｜新闻源独立模块任务单

适用场景：为 `stok-mapping` 引入独立新闻源模块，服务盘前研判、跨市场解释层和后续文本摘要因子。该任务不改变当前策略主线，不让新闻或 LLM 直接生成交易信号。

父级计划：[`DEVELOPMENT_PLAN.md`](../../docs/DEVELOPMENT_PLAN.md)  
任务索引：[`tasks/README.md`](../README.md)

---

## T1.3.0 目标

- [ ] 将新闻源从 Tiingo EOD 日线适配器中拆出，独立成 `news_sources` 模块
- [ ] 先验证 Alpha Vantage `NEWS_SENTIMENT` 的可用性，不直接承诺长期主源
- [ ] 记录 Benzinga Newsfeed 作为后续生产级候选
- [ ] 明确 Finnhub 仅作为单票 company news 备选，不进入首批主新闻源

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
- [ ] 探测报告进入 `reports/`
- [ ] 新闻摘要和盘前解释输出仍属于 `reports/` 或日报交付物

---

## T1.3.5 验收标准

- [ ] 可用独立脚本验证 Alpha Vantage 新闻权限和字段结构
- [ ] 能分别验证 ticker、topic、time window 三类过滤条件
- [ ] 能验证组合观察池逐 ticker 拉取和去重逻辑
- [ ] 生成 `reports/news_source_probe_report.md`
- [ ] 文档明确新闻源不直接进入主 ranker，不直接生成交易信号

---

## T1.3.6 一句话提醒

> 新闻源模块的目标是服务盘前解释和风险提示，不是把文本情绪提前放进交易决策主链路。
