# Harness Iteration Brief - 2026-06-25 - I37 强市场有效参与候选验证

## 一句话结论

`strong_market_effective_participation_v1` 没有通过。修正单股权重上限后，它仍然是 `reject`，而且第 5 折在强沪深300相关窗口里平均实盘暴露只有 `10.29%`，持有沪深300权重只有 `2.13%`，前20权重股覆盖只有 `2.79%`。

## 本轮做了什么

| 项目 | 内容 |
| ---- | ---- |
| 新策略 | `strong_market_effective_participation_v1` |
| 任务性质 | research-only 最小实现 |
| 配置 | `config.main_strategy_i37_strong_market_effective_participation_20260625.yaml` |
| 验证链 | scoped admission -> failure attribution -> market context -> holdings exposure -> CSI300 attribution |
| 修正口径 | `_scale_to_budget` 不再为了填满预算而突破 `max_symbol_weight` |
| admission | `reject` |
| 是否允许进入 paper review / 模拟 / 日报 / watchlist | 否 |

## Admission 结果

| 指标 | 结果 | 是否通过 |
| ---- | ---: | -------- |
| 年化收益均值 | -3.47% | 否 |
| Sharpe 均值 | -0.46 | 否 |
| 最差最大回撤 | -17.11% | 是 |
| 正收益折比例 | 20% | 否 |
| 年化换手均值 | 3.58 | 否 |
| 年化换手最大值 | 14.01 | 否 |
| 行业审计 | 45 个违规日 | 否 |
| overfit risk | high | 否 |

这不是一个接近进入 paper review 的策略。它的准入失败不是单一指标问题，而是收益、正收益折比例、换手、行业审计和 research-only 边界同时不满足。

## 有效参与验收

I36 预设的最低线：

| 验收项 | 目标 |
| ------ | ---: |
| 强市场折平均仓位 | >= 60% |
| 持有沪深300权重 | >= 12% |
| 沪深300前20权重股覆盖率 | >= 25% |

I37 修正后实际结果：

| 折 | 市场状态 | 平均实盘暴露 | 持有沪深300权重 | 前20权重股覆盖率 | 策略总收益 | 沪深300总收益 | 超额 |
| -: | -------- | -----------: | --------------: | ----------------: | ---------: | ------------: | ---: |
| 4 | mixed / unresolved | 0.00% | 0.00% | 0.00% | 0.00% | 9.89% | -9.89% |
| 5 | mixed / unresolved | 10.29% | 2.13% | 2.79% | -8.96% | 14.48% | -23.43% |

结论：策略名义上想参与强市场，但真实持仓没有吃到沪深300主升段。

## 怎么理解

这次修正很重要：旧口径会把未用完预算补给最高权重股票，可能突破单股上限，使仓位看起来更高。修正后，候选股票如果没有足够权重容量，就允许实际仓位低于目标仓位。

这更符合真实约束，也让结论更清楚：I37 首版的问题不是“参数再调一点就好”，而是强市场状态下可买到的核心沪深300权重太少，组合自然无法形成有效指数参与。

## 下一步

1. 停止 `strong_market_effective_participation_v1` 首版。
2. 不继续调 `benchmark_weight_multiplier`、`top_n` 或单股权重参数。
3. 下一步转入 I38：做强市场候选池可达性诊断，回答“强市场当天到底有多少沪深300成分股满足 PIT、流动性、趋势、行业和权重可见性约束”。
4. 如果可达性不足，强市场策略池角色要改方向：先放宽或重构候选生成，而不是继续改组合权重器。

## 原始证据

| 类型 | 路径 |
| ---- | ---- |
| admission | `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/admission/` |
| failure attribution | `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/failure_attribution/` |
| market context | `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/market_context/` |
| holdings exposure | `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/holdings_exposure/` |
| CSI300 attribution | `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/csi300_attribution_mixed_context/` |
