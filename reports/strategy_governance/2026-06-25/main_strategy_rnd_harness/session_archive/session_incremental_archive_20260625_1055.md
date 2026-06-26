# Session Incremental Archive - 2026-06-25 10:55 - I36 Harness

## 本轮目标

- 接续 I35 结论，决定强市场策略研发下一步。
- 不继续微调 I15/I18/I20。
- 预注册一个以“强市场有效参与度”为核心的新候选方向。

## 关键判断

I35 显示：

- I15 第 5 折平均仓位 `8.26%`，持有沪深300权重 `0.93%`，前20权重股覆盖率 `0.91%`，超额 `-13.07%`。
- I18 第 4 折空仓，第 5 折平均仓位 `27.09%`，持有沪深300权重 `3.54%`，前20覆盖率 `5.83%`，第 5 折超额 `-6.14%`。
- I20 第 5 折平均仓位 `13.55%`，持有沪深300权重 `1.68%`，前20覆盖率 `1.79%`，超额 `-10.28%`。

结论：旧方向不是“参数差一点”，而是强市场参与目标没有被直接约束。继续调触发器、`top_n` 或固定调仓周期，ROI 低。

## 新增设计

新增预注册候选：

```text
strong_market_effective_participation_v1
```

核心要求：

- 使用 T-1 可见强沪深300状态。
- 使用 PIT universe 与 `qfq_asof`。
- 使用 `cn_index_weights_asof` 的 `date - 1 day` 权重。
- 强市场折必须同时验证：
  - 平均 live exposure `>= 0.60`
  - 平均 held benchmark weight `>= 0.12`
  - 平均 top20 coverage `>= 0.25`
- 未通过 admission 前，不允许 paper review、模拟、日报或 watchlist。

## 产物

- 设计文档：`reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_36__strong_market_effective_participation_design/strong_market_effective_participation_v1_spec.md`
- 用户简报：`reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/briefings/iter_36__strong_market_effective_participation_design_brief.md`
- 策略池任务文档已更新：`docs/tasks/strategy/PHASE0_CANDIDATE_STRATEGIES.md`

## 停止条件

下一轮若实现 I36 候选，满足任一条件即停止：

1. 强市场折无法达到最低参与度或最低权重覆盖。
2. 参与度提高后收益、Sharpe 或回撤明显恶化。
3. 年化换手最大值超过 admission 上限且无法用更低频规则修复。
4. 收益主要来自单一折、单一行业或单一权重股。
5. 为了通过指标需要使用未来权重、放宽 PIT 或降低 admission gate。

## 下一步

实现 `strong_market_effective_participation_v1` 最小版本，跑 scoped admission，然后立刻跑 holdings exposure 与 CSI300 attribution。若参与度或权重覆盖不达标，不继续小参数调优。
