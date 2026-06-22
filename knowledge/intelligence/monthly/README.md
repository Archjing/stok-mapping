# Strategy Intelligence Monthly Scan

本目录保存 T5.2 月度策略情报扫描报告。月扫的目标不是收集更多链接，而是把近 30 天的高价值策略线索转化为可复核的研究假设、数据建设任务或反方证据。

## 固定口径

- 扫描窗口：默认近 30 天，报告中必须写明起止日期。
- 输入范围：论文、预印本、券商金工、指数公司、交易所/数据源说明和高质量 quant research。
- 输出报告：`strategy_intelligence_scan_YYYY-MM[_scope].md`
- 候选 CSV：优先写入 `data/intelligence/inbox/`，人工复核后才允许进入正式台账。
- 索引文件：每次新增报告后同步更新 `index.md`。

## 复核流程

```text
monthly scan -> inbox candidate -> manual review -> ledger update -> note / translation -> experiment or archive
```

## 入账门禁

- 来源、发布时间和链接可复查。
- 已记录核心观点、可验证假设、所需数据和主要风险。
- 已完成质量、创新性、可落地性评分。
- 已识别未来函数、幸存者偏差、过拟合、授权和市场迁移风险。
- 不把营销材料、新闻标题或未验证观点直接作为策略有效性证据。

## RAG 规则

- 月扫报告属于 `candidate` 或 `curated` 语料，默认不能作为策略有效性证据。
- 被人工复核并写入 `strategy_intelligence_ledger.csv` 后，才能进入正式情报检索主链路。
- 高价值条目若转化为策略任务，必须新增 `knowledge/intelligence/strategy_translations/` 草案并链接回源报告。
