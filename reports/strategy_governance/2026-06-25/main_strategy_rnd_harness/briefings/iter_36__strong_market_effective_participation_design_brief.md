# Harness Iteration Brief - 2026-06-25 - I36 强市场有效参与候选设计

## 一句话结论

下一步不该继续微调 I15/I18/I20。它们的问题已经很清楚：强市场里参与度太低、覆盖的沪深300权重太少。新的候选应该直接把“有效参与度”写成约束，而不是继续只调触发器或选股参数。

## 为什么要换方向

| 已研究候选 | 发现的问题 |
| ---------- | ---------- |
| I15 `strong_index_participation_v1` | 第 5 折强沪深300，但整折平均仓位只有 8.26%，持有沪深300权重只有 0.93% |
| I18 `strong_index_participation_dynamic_trigger_v1` | 动态触发改善了一些参与，但第 4 折仍空仓，第 5 折覆盖仍不足 |
| I20 `strong_market_liquid_breadth_participation_v1` | 宽篮子和慢换手改善有限，第 5 折平均仓位也只有 13.55% |

这说明旧方向不是“差一点参数”，而是设计目标不够直接。

## 新候选名称

```text
strong_market_effective_participation_v1
```

它仍是 research-only，不是交易策略。

## 新候选要解决什么

强沪深300状态出现时，策略必须回答三个问题：

1. 有没有足够仓位参与？
2. 有没有覆盖沪深300主要权重？
3. 有没有在成本、回撤、换手和行业审计下仍然站得住？

如果这三个问题答不上来，就不能叫强市场参与策略。

## 初版验收线

| 指标 | 初版要求 |
| ---- | -------- |
| 强市场折平均仓位 | 至少 60% |
| 强市场折持有沪深300权重 | 至少 12% |
| 沪深300前20权重股覆盖率 | 至少 25% |
| 权重可见性 | 只能用 `date - 1 day` 以前最近权重 |
| 数据口径 | PIT universe + `qfq_asof` |
| admission | 不降低门槛 |

这些阈值不是为了保证收益，而是为了防止策略再次“名义上参与强市场、实际大部分时间旁观”。

## 不允许做的事

- 不把沪深300高权重股清单写成买入建议。
- 不直接复制沪深300。
- 不用同日收盘后权重。
- 不降低 admission gate。
- 不把 `price_volume_low_turnover_v1` 简单加仓当成强市场策略。
- 不继续在 I15/I18/I20 上做小参数调优。

## 下一步

下一轮如果实现，只做最小版本：

1. 新增 `strong_market_effective_participation_v1`。
2. 写一个独立实验配置。
3. 跑 scoped admission。
4. 立刻跑 holdings exposure 和 CSI300 attribution。
5. 如果参与度或权重覆盖仍不达标，直接停止，不继续调小参数。

## 原始证据

| 类型 | 路径 |
| ---- | ---- |
| 预注册设计 | `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_36__strong_market_effective_participation_design/strong_market_effective_participation_v1_spec.md` |
| 前序归因简报 | `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/briefings/iter_35__strong_market_candidate_csi300_attribution_brief.md` |
