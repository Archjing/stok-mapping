# I46 Strong Market Core Participation 简报

生成日期：2026-06-25

## 一句话结论

`strong_market_core_participation_v1` 本轮不通过 admission，不能进入 paper review、模拟或实盘观察。它解决了一部分“沪深300核心股看不见”的工程问题，但还没有解决“强行情里持续、足量参与”的策略问题。

## 本轮做了什么

- 新增 `strong_market_core_participation_v1` research-only 策略。
- 在 walk-forward 和 holdings exposure 中传入 fold 上下文，避免补核心股时混用训练期和验证期可见信息。
- 用 T-1 可见的沪深300权重补入核心成分，不固定买前20，不复制沪深300。
- 响应本轮复核意见：趋势、流动性、风险、行业约束不再作为沪深300核心股的硬筛选器；这些信息改为排序、降权、审计和归因依据。
- 修复 `strategy-csi300-attribution` 报告标题固定写 `I34` 的问题，改成通用标题，避免后续回查误读。

## 关键结果

| 指标 | 结果 | 解读 |
| --- | ---: | --- |
| admission action | `reject` | 不准入 |
| 年化收益均值 | `-3.30%` | 扣成本后没有赚钱能力 |
| Sharpe 均值 | `-0.43` | 单位风险收益不合格 |
| 最差回撤 | `-15.30%` | 回撤没爆，但收益太弱 |
| 正收益折比例 | `0%` | 5 折没有一折绝对收益为正 |
| 正超额折比例 | `60%` | 弱市中相对沪深300有保护，但强市不行 |
| 平均年化换手 | `4.08` | 超过 admission 均值门槛 `3.0` |
| 最大年化换手 | `16.04` | 第 5 折换手过高 |
| overfit risk | `high` | 不适合继续小参数硬调 |

## 分折表现

| 折 | 验证期 | 策略年化 | 沪深300年化 | 超额 | 解释 |
| ---: | --- | ---: | ---: | ---: | --- |
| 1 | 2021-04-01..2022-03-31 | `-0.65%` | `-17.96%` | `+17.31%` | 弱市抗跌，不代表强市有效 |
| 2 | 2022-04-01..2023-03-31 | `0.00%` | `-5.46%` | `+5.46%` | 基本空仓，靠没参与下跌取得相对优势 |
| 3 | 2023-04-03..2024-03-29 | `0.00%` | `-14.09%` | `+14.09%` | 基本空仓，仍是弱市保护 |
| 4 | 2024-04-01..2025-03-31 | `0.00%` | `+8.50%` | `-8.50%` | 强市没有参与 |
| 5 | 2025-04-01..2026-03-31 | `-15.83%` | `+15.11%` | `-30.94%` | 强市参与不足且交易效果差 |

## 持仓和沪深300覆盖

| 折 | 全折平均实盘仓位 | 全折平均持有沪深300权重 | Top20 覆盖率 | 主因 |
| ---: | ---: | ---: | ---: | --- |
| 1 | `2.02%` | `0.93%` | `1.89%` | 参与太少 |
| 2 | `0.00%` | `0.00%` | `0.00%` | 空仓 |
| 3 | `0.00%` | `0.00%` | `0.00%` | 空仓 |
| 4 | `0.00%` | `0.00%` | `0.00%` | 空仓 |
| 5 | `17.64%` | `7.83%` | `16.39%` | 参与太少 |

注意：持仓诊断显示活跃交易日平均仓位能到约 `49%` 到 `59%`，但触发日太少，所以摊到完整验证折后，整体参与仍很低。I46 的失败不是“完全买不到核心股”，而是“没有在强行情中持续参与”。

## 本轮判断

这轮把问题推进了一步：I44 证明候选池可以看见核心股，I46 证明仅把核心股放进候选池还不够。当前强市场候选最大问题仍是触发和组合参与机制太窄，不能稳定吃到沪深300上涨。

不建议继续调小参数来凑指标。下一轮应做 I47：把强市场参与策略拆成两层，一层是更稳定的低频核心参与底仓，另一层才是主动 alpha 卫星仓；先验证“强市时是否能稳定保持最低有效仓位”，再谈选股增强。

## 产物路径

- admission: `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/admission/`
- failure attribution: `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/failure_attribution/`
- market context: `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/market_context/`
- holdings exposure: `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/holdings_exposure/`
- CSI300 attribution: `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/csi300_attribution_all_context/`
