# Harness Iteration Brief - 2026-06-25 - I40 CSI300 核心权重可达性诊断

## 一句话结论

本地 PIT 数据不是主要障碍。沪深300核心权重在基础数据层大体可达；真正把强市场参与策略打残的是 I37 那类过窄的 alpha / hard filters。

## 本轮做了什么

新增只读命令：

```text
strategy-core-reachability-diagnostic
```

它从完整沪深300 T-1 权重表出发，而不是从某个策略的候选池出发，逐日检查：

```text
T-1 CSI300 weights
-> core constituents
-> PIT panel availability
-> price / amount / amount_ratio20 / industry basic filters
-> reachable core weight
```

这一步不生成策略、不生成买卖信号、不改变 admission。

## 关键数字

| 折 | as-of 覆盖 | 平均可达核心权重 | 最低可达核心权重 | 平均可达完整 Top20 权重 | 最低可达完整 Top20 权重 | 状态 |
| -: | --------: | ---------------: | ---------------: | ----------------------: | ----------------------: | ---- |
| 1 | 100.00% | 57.74% | 55.65% | 34.28% | 31.95% | 未过 Top20 门槛 |
| 2 | 100.00% | 55.82% | 54.55% | 32.70% | 30.76% | 未过 Top20 门槛 |
| 3 | 100.00% | 53.39% | 52.01% | 31.00% | 29.89% | 未过 Top20 门槛 |
| 4 | 100.00% | 54.96% | 54.26% | 32.47% | 31.67% | 未过 Top20 门槛 |
| 5 | 100.00% | 54.98% | 52.40% | 33.01% | 31.41% | 未过 Top20 门槛 |

I39 预设门槛是：

| 验收项 | 门槛 | I40 结果 |
| ------ | ---: | -------- |
| 强市场日可达沪深300核心权重 | >= 50% | 五折都达到 |
| 强市场日完整基准 Top20 可达权重 | >= 35% | 五折都略低 |
| 权重 as-of 覆盖率 | 100% | 达到 |

## 和 I38 的关系

I38 看到的是：在 I37 的策略过滤后，第 5 折强市场日可买候选只覆盖沪深300约 `9.05%` 权重，panel 可见 Top20 只覆盖 `3.93%`。

I40 看到的是：如果不先套 I37 的过窄过滤，只做基础 PIT / 价格 / 成交 / 行业可达性，第 5 折平均可达核心权重约 `54.98%`，完整 Top20 可达约 `33.01%`。

这说明：

1. 本地数据和 PIT 股票池足以覆盖大部分沪深300核心权重。
2. I37 的过滤层把可达权重从约 `55%` 砍到约 `9%`。
3. 下一步应该改过滤层结构，而不是继续调组合权重器。

## 失败原因

当前只读诊断里，核心成分不可达原因全部是：

```text
missing_from_pit_panel
```

没有出现价格无效、成交额不足、amount_ratio20 不足或行业缺失造成的大面积阻断。也就是说，基础可交易过滤不是主瓶颈。

## 下一步

可以进入 I41 设计，但仍不应该直接做强策略。

I41 应设计一个新的强市场候选生成器：

1. 先保留 CSI300 核心权重池。
2. 只用基础风险过滤排除明显不可交易标的。
3. alpha 过滤改为轻量排序，不再作为硬门槛先砍核心权重。
4. 若完整 Top20 可达权重仍低于 35%，组合构造要明确降级，而不是用尾部股票补仓。

## 原始证据

| 类型 | 路径 |
| ---- | ---- |
| I40 core reachability | `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_40__csi300_core_reachability_diagnostic/core_reachability/` |
| fold summary | `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_40__csi300_core_reachability_diagnostic/core_reachability/strategy_core_reachability_fold_summary.csv` |
| daily diagnostic | `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_40__csi300_core_reachability_diagnostic/core_reachability/strategy_core_reachability_daily.csv` |
| failure reasons | `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_40__csi300_core_reachability_diagnostic/core_reachability/strategy_core_reachability_failure_reasons.csv` |
