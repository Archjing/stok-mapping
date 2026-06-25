# I45 Strong Market Core Participation V1 - 预注册设计

生成时间：2026-06-25 13:15 CST

## 背景

I15、I18、I20 和 I37 都没有解决“强势沪深300行情下有效参与”的问题。

已确认的证据：

- I35 显示三条早期强市场候选在强指数阶段仓位低、持有沪深300权重低。
- I37 `strong_market_effective_participation_v1` admission 为 `reject`，第 5 折强相关窗口平均实盘暴露只有 `10.29%`，持有沪深300权重只有 `2.13%`，Top20 覆盖只有 `2.79%`。
- I40/I42/I43 说明，问题不是本地 CSI300 权重表不可用，而是常规 PIT panel 和过窄过滤容易把核心成分挡在策略可选范围外。
- I44 证明，只读地显式保留 as-of 可见的沪深300核心成分后，五折可达性通过：平均核心可达权重 `59.45%`，平均核心覆盖率 `99.28%`，平均 Top20 覆盖率 `99.95%`。

I45 的任务不是立即编码新策略，而是冻结下一候选的设计边界，避免把 I44 误解成“固定买沪深300前20只”。

## 新候选

候选名：

```text
strong_market_core_participation_v1
```

候选角色：

```text
strong_market_participation / research-only
```

核心假设：

> 在 T-1 可见的强沪深300环境下，先确保沪深300核心成分进入候选池，再用轻量趋势、流动性、风险和行业约束决定实际持仓，可能比继续在常规 120 只 panel 内做主动选股更能改善强市场参与度。

## 做什么

1. 使用 I44 的 core seed panel 思路。
   - 从 T-1 或更早可见的 `cn_index_weights_asof` 读取沪深300成分和权重。
   - 每个交易日把 Top20、Top60 或累计权重前 60% 的核心成分纳入候选生成面板。
   - 仍保留常规 PIT universe 中的少量 alpha satellite 候选。

2. 使用强市场状态作为建仓前提。
   - 沿用当前 `strong_index_context` 的 T-1 可见定义。
   - 不引入盘中信号。
   - 非强市场状态下逐步降仓或空仓。

3. 把过滤从“硬砍核心股”改成“基础可交易过滤 + 排序”。
   - 必须有 `qfq_asof` 价格和可用收益。
   - 必须有行业字段。
   - 必须有基本成交额 / 流动性。
   - 不用普通短期动量、行业相对强弱或残差动量先把核心股排除在候选池外。

4. 组合构造分两层。

| 层 | 作用 | 预算建议 |
| --- | --- | ---: |
| `benchmark_core_sleeve` | 参与沪深300核心成分 | 组合目标仓位的 `70%` 到 `85%` |
| `alpha_satellite_sleeve` | 保留少量主动选择空间 | 组合目标仓位的 `15%` 到 `30%` |

5. 首版用规则权重，不上优化器。
   - 强市场目标仓位：`0.60` 到 `0.80`。
   - 单票上限：建议 `0.06` 到 `0.08`。
   - 核心股权重参考指数权重，但不复制指数。
   - 行业约束继续纳入策略层审计，不因 I44 放宽。

## 不做什么

- 不固定买沪深300前20只。
- 不复制沪深300。
- 不把 I44 缺失清单解释为买入建议。
- 不使用同日收盘后才知道的指数权重。
- 不绕过 PIT、`qfq_asof`、交易成本、行业审计或 admission gate。
- 不把 `price_volume_low_turnover_v1` 简单加仓改造成强市场策略。
- 不继续在 I15/I18/I20/I37 上做小参数调优。

## 初版候选生成流程

```text
T-1 CSI300 as-of weights
-> seed core candidates
-> merge regular PIT universe candidates
-> basic tradability and data checks
-> strong_index_context gate
-> core sleeve light ranking
-> alpha satellite ranking
-> portfolio constraints
-> next-day executable weights
```

### Core sleeve 排序建议

排序只用于轻微区分核心股，不用于把核心股大面积砍掉。

建议权重：

| 因子 | 作用 | 建议权重 |
| --- | --- | ---: |
| CSI300 权重 rank | 保持核心参与 | `40%` |
| 60 日趋势 | 避开明显弱势核心股 | `20%` |
| 20 日趋势 | 轻量动量确认 | `10%` |
| 流动性 / 成交额 | 执行友好 | `15%` |
| 低异常波动 / 回撤 | 风险过滤 | `10%` |
| 行业内不过弱 | 避免行业内明显掉队 | `5%` |

### Alpha satellite 排序建议

只在目标核心仓位已满足时启用。

可复用现有价量线和强市场线的轻量排序字段，但总预算不能超过目标仓位的 `30%`。

## 验收标准

I45 之后若进入实现，必须按以下顺序验证：

| 阶段 | 验收项 | 通过条件 |
| --- | --- | --- |
| 可达性 | core seed panel | 沿用 I44，五折可达性不退化 |
| admission | scoped admission | `baseline_2y_1y_5fold`，不降低 gate |
| 强市场参与度 | live exposure | 强市场折平均 `>= 0.60` |
| 指数权重覆盖 | held benchmark weight | 强市场折平均 `>= 0.12`，优先争取 `>= 0.20` |
| Top20 覆盖 | held top20 coverage | 强市场折平均 `>= 0.25` |
| 成本 | turnover | 年化换手均值 `<= 3.0`，最大 `<= 5.0` |
| 风险 | drawdown | 不得通过显著放大回撤换取参与度 |
| 归因 | CSI300 attribution | admission 后必须跑持仓级归因 |
| 输出边界 | 正式用途 | admission pass 前不得进入 paper review、模拟、日报或 watchlist |

## 停止条件

满足任一条件即停止，不继续小参数调优：

1. 强市场折仍不能达到最低仓位或最低沪深300权重覆盖。
2. 持仓权重改善了，但收益、Sharpe 或回撤明显恶化，类似 I11 简单加仓反事实。
3. 年化换手最大值超过 admission 上限。
4. 收益主要来自单一折、单一行业或单一权重股。
5. 为了通过指标需要使用未来权重、放宽 PIT 或降低 admission gate。
6. 行业集中审计显示组合实质上变成少数行业押注。

## 和 I37 的差异

| 维度 | I37 `strong_market_effective_participation_v1` | I45 `strong_market_core_participation_v1` |
| --- | --- | --- |
| 核心问题 | 已经知道参与度不足 | 先保证核心成分可见 |
| 候选池 | 常规 PIT panel 内排序 | I44 core seed panel + PIT universe |
| 过滤方式 | hard filters 仍会砍掉核心股 | 基础过滤后轻量排序 |
| Top20 口径 | 看真实持仓覆盖，首版很低 | 先保证候选池覆盖，再验证真实持仓 |
| 下一步 | 已 reject，停止小调参 | 可进入最小实现 |

## 实现建议

若下一轮编码，建议最小改动：

1. 新增 `phase0/strategies/strong_market_core_participation.py`。
2. 复用 `strong_market_effective_participation.py` 中：
   - `strong_index_context`
   - T-1 CSI300 权重读取
   - 持仓输出字段
3. 不直接复用其过窄 hard filter 作为核心股入池条件。
4. 新增实验配置：
   - `config.main_strategy_i46_strong_market_core_participation_20260625.yaml`
5. scoped admission 后立即运行：
   - `strategy-holdings-exposure`
   - `strategy-csi300-attribution`
   - `strategy-failure-attribution`

## 本轮结论

I45 只完成预注册设计，不编码策略。

下一轮可以进入 I46 最小实现，但实现后必须用 admission 和持仓级 CSI300 归因证明：候选池能看见核心股，并不等于策略真实持仓已经有效参与强市场。
