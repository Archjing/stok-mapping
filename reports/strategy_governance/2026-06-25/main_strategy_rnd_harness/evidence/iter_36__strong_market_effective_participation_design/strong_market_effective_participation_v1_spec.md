# I36 Strong Market Effective Participation V1 - 预注册设计

## 背景

I15、I18、I20 都试图解决“强沪深300行情下要有参与型策略”的角色缺口，但 I35 的真实持仓级 CSI300 权重归因显示：

| 候选 | 关键折 | 平均仓位 | 持有沪深300权重 | 前20权重股覆盖率 | 超额 |
| ---- | ----: | -------: | --------------: | ----------------: | ---: |
| `strong_index_participation_v1` | 5 | 8.26% | 0.93% | 0.91% | -13.07% |
| `strong_index_participation_dynamic_trigger_v1` | 4 | 0.00% | 0.00% | 0.00% | -9.89% |
| `strong_index_participation_dynamic_trigger_v1` | 5 | 27.09% | 3.54% | 5.83% | -6.14% |
| `strong_market_liquid_breadth_participation_v1` | 5 | 13.55% | 1.68% | 1.79% | -10.28% |

这说明失败主因不是“是否识别强指数状态”这么简单，而是识别后仍没有形成足够的有效参与度。

## 新假设

新增 research-only 候选：

```text
strong_market_effective_participation_v1
```

核心假设：

> 在 T-1 可见的强沪深300环境下，如果候选组合不能同时满足最低实际仓位和最低沪深300权重覆盖，就不能称为强市场参与策略。新候选应把“有效参与度”作为一等约束，而不是只靠触发器、top_n 或调仓频率间接改善。

## 做什么

1. 继续使用 `strong_index_participation` 的 T-1 可见强指数状态定义：
   - `SH.000300` 高于 `ma120`
   - `ret20 > 0`
   - `ret60 > 0`
   - `vol20 <= rolling vol quantile`
   - drawdown 不低于阈值
2. 继续使用 point-in-time universe 和 `qfq_asof`。
3. 使用本地 `cn_index_weights_asof` 的 `date - 1 day` 可见权重。
4. 在强指数状态下构建权重感知候选：
   - 优先考虑有沪深300权重记录的股票。
   - 对沪深300内股票，组合权重上限可以参考其指数权重，但不做成分复制。
   - 对非沪深300股票，只允许作为补充 alpha sleeve，不能主导强市场参与仓位。
5. 设置最低有效参与验收：
   - 强市场折平均 live exposure 目标下限建议先设 `>= 0.60`。
   - 强市场折平均 held benchmark weight 目标下限建议先设 `>= 0.12`。
   - 强市场折前20权重股覆盖率目标下限建议先设 `>= 0.25`。
   - 若低于这些阈值，即使 admission 指标偶然变好，也不能解释为强市场参与角色成立。

## 不做什么

- 不直接复制沪深300，不把本策略做成指数基金。
- 不使用同日收盘后才确认的指数权重。
- 不降低 admission gate。
- 不把贵州茅台、宁德时代等权重股遗漏清单写成买入建议。
- 不把最低仓位覆盖层直接套到 `price_volume_low_turnover_v1`。
- 不继续对 I15/I18/I20 做小参数微调。

## 初版构造建议

### 信号

强指数状态为 true 时才允许建仓；状态为 false 时逐步降仓或清仓。首版不引入盘中信号。

### 股票池

候选池分两层：

| 层 | 作用 | 约束 |
| ---- | ---- | ---- |
| `benchmark_participation_core` | 覆盖沪深300主要权重和流动性 | 必须来自 T-1 可见 `cn_index_weights_asof`；按指数权重、流动性和趋势排序 |
| `alpha_satellite` | 保留少量趋势/流动性 alpha 空间 | 来自 PIT universe；总权重不超过组合目标仓位的一小部分 |

### 权重

首版可以采用规则权重，不做优化器：

1. 组合目标仓位：强指数状态下 `0.60` 到 `0.80`。
2. benchmark core 至少占组合目标仓位的 `70%`。
3. 单票权重上限：`min(0.08, max(0.02, benchmark_weight * multiplier))`。
4. 行业仍走策略层 audit，不在首版强行放宽行业审计。
5. 权重全部使用 T-1 可见数据。

## 验收标准

先做 research-only scoped admission，再做持仓级归因。

| 验收项 | 通过条件 |
| ------ | -------- |
| admission | 仍按 `baseline_2y_1y_5fold` gate，不降低门槛 |
| PIT | 使用 point-in-time universe |
| 价格 | 使用 `qfq_asof` |
| 权重可见性 | `strategy-csi300-attribution` run log 必须显示 `weight_date_lag_days=1` |
| 强市场参与度 | 强市场折平均 live exposure `>= 0.60` |
| 沪深300权重覆盖 | 强市场折平均 held benchmark weight `>= 0.12` |
| 前20权重股覆盖 | 强市场折平均 top20 coverage `>= 0.25` |
| 风险 | 回撤、换手、行业审计必须纳入 admission |
| 输出边界 | 未通过 admission 前，不能进入 paper review、模拟、日报或 watchlist |

## 停止条件

满足任一条件即停止本候选，不继续小参数调优：

1. 强市场折仍无法达到最低参与度或最低权重覆盖。
2. 参与度提高后收益、Sharpe 或回撤明显恶化，类似 I11 的最低仓位反事实。
3. 年化换手最大值超过 admission 上限且无法用更低频规则修复。
4. 策略收益主要来自单一折、单一行业或单一权重股。
5. 为了通过指标需要使用同日未来权重、放宽 PIT 或降低 admission gate。

## 本轮结论

I36 暂不编码新策略。先把新假设、边界、验收项和停止条件落盘。下一轮若继续实现，应只做最小版本，并且必须在 admission 后立即跑 holdings exposure 和 CSI300 attribution，否则不能解释为强市场参与候选。
