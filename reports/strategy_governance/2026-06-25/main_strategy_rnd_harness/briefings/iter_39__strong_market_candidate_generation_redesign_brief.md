# Harness Iteration Brief - 2026-06-25 - I39 强市场候选生成层重设计

## 一句话结论

下一轮不要直接写新交易策略。先做一个“沪深300核心权重可达性”只读诊断，确认本地 PIT 数据和基础可交易过滤能不能覆盖足够多的沪深300核心权重。

## 为什么要这样改

I38 已经说明：当前强市场策略失败，不只是组合权重器问题。第 5 折强市场日虽然有候选，但这些候选平均只覆盖沪深300约 `9.05%` 权重，当前 panel 可见权重前20只覆盖约 `3.93%`。

这意味着如果继续在这个候选池上调权重、调 top_n、调 multiplier，很可能只是把低权重尾部股票配得更重，仍然跟不上沪深300主升段。

## 新设计边界

| 层 | 要解决的问题 | 禁止事项 |
| -- | ------------ | -------- |
| 指数参与层 | 先保证 CSI300 核心权重可达 | 不先用过窄 alpha 过滤砍掉核心权重股 |
| 风险过滤层 | 排除不可交易、数据缺失和流动性异常 | 不把普通弱势直接视为不可买 |
| alpha 排序层 | 在可达核心成分内轻量排序 | 不改变核心权重覆盖目标 |
| 组合约束层 | 控制单股、行业、换手和成本 | 不为填满仓位突破单股上限 |

## I40 前置验收

| 验收项 | 最低要求 |
| ------ | -------: |
| 强市场日可达沪深300权重 | >= 50% |
| 强市场日完整基准 Top20 可达权重 | >= 35% |
| 权重 as-of 覆盖率 | 100% |
| 缺失原因 | 每日可解释 |
| 未来函数风险 | 只使用 T-1 或更早可见权重 |

如果达不到这些要求，就不要进入策略实现。

## 下一步动作

新增或扩展一个只读诊断命令，暂名：

```text
strategy-core-reachability-diagnostic
```

它从 T-1 CSI300 核心权重出发，逐层解释：

```text
CSI300 core weights
-> PIT price availability
-> tradability / liquidity
-> industry availability
-> risk filter
-> reachable core weight
```

这一步的目标不是赚钱，而是判断“强市场指数参与型策略是否具备数据和候选池基础”。

## 原始设计

| 类型 | 路径 |
| ---- | ---- |
| I39 spec | `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_39__strong_market_candidate_generation_redesign/strong_market_candidate_generation_redesign_spec.md` |
