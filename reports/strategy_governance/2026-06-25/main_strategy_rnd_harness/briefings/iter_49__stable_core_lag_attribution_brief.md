# Harness Iteration Brief - 2026-06-25 - I49 Stable Core Lag Attribution

> 这份简报给人读，不替代原始 CSV、日志和研究报告。它说明本轮发现了什么、证据是什么、下一步该怎么做。

## 一句话结论

`strong_market_stable_core_base_v1` 仍不能作为强沪深300环境的合格候选。它已经把换手降下来、也显著提高了沪深300核心参与度，但在强基准阶段仍然没有吃满沪深300核心权重，Top20 覆盖不足，并且行业结构偏离较大。

## 本轮做了什么

| 项目 | 内容 |
| ---- | ---- |
| 迭代编号 | `iter_49` |
| 任务性质 | research-only lag attribution |
| 研究对象 | `strong_market_stable_core_base_v1` |
| 对照对象 | `strong_market_stable_core_only_v1`、`strong_market_stable_satellite_only_v1` 仅作 attribution-only 归因变体 |
| 运行日期 | `2026-06-25` |
| 数据日期 | walk-forward 固定研究区间至 `2026-03-31` |
| 数据源 | `local_history_sqlite_as_of`，价格口径 `qfq_asof` |
| 关键边界 | 不生成买卖建议；不进入 paper review；不进入模拟账户、日报或 watchlist；不降低 admission gate |

## 关键数字

`strong_market_stable_core_base_v1` 在强沪深300跑输环境的折均值：

| 指标 | 数值 | 白话解释 |
| ---- | ---: | -------- |
| 平均实盘仓位 | `39.18%` | 比 I46 高很多，但仍不是充分参与强指数行情 |
| 平均持有沪深300权重 | `22.33%` | 没有持到足够多的基准核心权重 |
| 平均漏掉沪深300权重 | `77.67%` | 大部分基准权重仍未覆盖 |
| Top20 覆盖率 | `59.14%` | 核心权重股覆盖明显改善，但仍有约四成 Top20 权重没有被持住 |
| Top20 漏配权重 | `13.39%` | 强基准上涨时漏配的头部权重仍有影响 |
| 行业 L1 偏离 | `1.1456` | 行业结构相对沪深300偏离明显 |
| 策略年化 | `8.27%` | 自己能赚钱 |
| 沪深300年化 | `12.74%` | 但强基准阶段沪深300更强 |
| 超额总收益 | `-4.27%` | 没有实现强市场相对优势 |

## 为什么仍然跑输

| 原因 | 证据 | 解释 |
| ---- | ---- | ---- |
| 参与度仍不足 | 5 个 fold 的 CSI300 attribution `primary_driver` 均为 `low_participation` | 策略不是没仓位，而是仓位和基准核心权重都还不够 |
| 头部权重股漏配 | 强基准折里反复漏配 `贵州茅台`、`宁德时代`、`中国平安`、`五粮液`、`美的集团` 等 | 强指数行情里，漏掉高权重核心股会直接拖累相对收益 |
| 行业结构偏离 | 强基准折行业 L1 偏离约 `1.1456`；admission 仍触发行业审计问题 | 稳定底仓降低了换手，但并没有贴近沪深300行业结构 |
| 卫星增强贡献不足 | I48 长窗口显示 satellite-only 无稳定贡献 | 继续微调卫星仓不是当前最有效方向 |

## 不是候选池扩容

`strong_market_stable_core_only_v1` 和 `strong_market_stable_satellite_only_v1` 已在策略元数据中标记为 `attribution_only`。它们只用于 I48/I49 归因 evidence run，不得进入 `baseline_admission_all_v1`、paper review、模拟账户、日报或 watchlist。

`core+satellite` 也不是新策略 id，只是 I47 `strong_market_stable_core_base_v1` 在拆分实验里的对照说法。

## 研发判断

I49 把问题从“稳定底仓是否有效”推进到“稳定底仓如何更贴近强沪深300核心权重”。稳定核心底仓方向有价值，但目前只证明它能改善参与度和换手，没有证明它能在强基准环境里形成相对优势。

下一步不应继续调卫星仓参数。更合理的下一轮是：

1. 做 benchmark-aware core weight closeness 设计，明确持仓对沪深300权重、Top20 权重和行业权重的最低贴近要求。
2. 不把贴近沪深300理解为简单复制指数；要保留“核心权重可见 + alpha 排序 + 行业偏离受控”的策略边界。
3. 先预注册设计和验证指标，再写新策略，避免为了追强基准结果事后调参。

## 证据路径

- failure attribution：`reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_49__stable_core_lag_attribution/failure_attribution_short/`
- holdings exposure：`reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_49__stable_core_lag_attribution/holdings_core_base/`
- CSI300 attribution：`reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_49__stable_core_lag_attribution/csi300_core_base_all_context/`
