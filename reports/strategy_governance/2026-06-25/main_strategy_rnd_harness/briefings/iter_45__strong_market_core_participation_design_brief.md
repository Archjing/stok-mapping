# Harness Iteration Brief - 2026-06-25 - I45 强市场核心参与候选设计

## 一句话结论

I45 完成了新候选的预注册设计，但没有写策略代码。

下一候选暂定为：

```text
strong_market_core_participation_v1
```

它的目标不是固定买沪深300前20只，而是在强沪深300市场里，先保证策略能看见核心股票，再用趋势、流动性、风险和行业约束决定是否持有。

## 为什么要做

I44 已证明：如果显式保留 as-of 可见的沪深300核心成分，候选池可达性可以通过。

现在还缺下一步验证：

> 能看见核心股，是否真的能转化成有效持仓和成本后收益？

这就是 I45/I46 要解决的问题。

## 设计边界

做：

- 使用 I44 的 core seed panel 思路。
- 使用 T-1 可见 CSI300 成分和权重。
- 强市场才建仓。
- 核心股票先进入候选池，再轻量排序。
- admission 后必须跑持仓暴露和 CSI300 归因。

不做：

- 不复制沪深300。
- 不固定买前20只。
- 不使用未来权重。
- 不降低 admission gate。
- 不绕过 PIT、`qfq_asof`、成本和行业审计。

## 初版构造

组合分两层：

| 层 | 作用 | 预算 |
| --- | --- | ---: |
| `benchmark_core_sleeve` | 参与沪深300核心成分 | 70%-85% |
| `alpha_satellite_sleeve` | 保留少量主动选择空间 | 15%-30% |

核心层不是无脑买入，而是按以下维度轻量排序：

- CSI300 权重
- 60 日趋势
- 20 日趋势
- 流动性
- 异常波动 / 回撤
- 行业内不过弱

## 验收标准

如果下一轮实现 I46，至少要验证：

| 项目 | 目标 |
| --- | ---: |
| 强市场平均仓位 | >= 60% |
| 持有沪深300权重 | >= 12%，优先争取 >= 20% |
| Top20 持仓覆盖 | >= 25% |
| 年化换手均值 | <= 3.0 |
| 年化换手最大值 | <= 5.0 |
| admission | 不降低门槛 |

## 停止条件

如果提高参与度后收益、Sharpe、回撤或换手明显恶化，就停止，不继续小参数调优。

如果收益只来自单一折、单一行业或单一权重股，也停止。

## 产物

- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_45__strong_market_core_participation_design/strong_market_core_participation_v1_spec.md`

## 下一步

I46 可以做最小实现：

- 新增 `strong_market_core_participation_v1`
- scoped admission
- holdings exposure
- CSI300 attribution
- failure attribution

通过这些验证后，才能判断它是否真的补上强市场参与型策略角色。
