# Harness Iteration Brief - 2026-06-26 - I51-I54 Benchmark-Aware Core

> 本简报是本轮 Harness 策略研发记录。所有结论都是 research-only，不生成交易信号，不进入 paper review、模拟账户、日报或 watchlist。

## 一句话结论

`strong_market_benchmark_aware_core_v1` 把“沪深300核心股覆盖”做上去了，但没有把收益做出来。
强行增加强市场参与度后，收益反而更差、换手明显升高。因此这一轮不应该继续微调“更贴近沪深300核心”的参数，而应该转向寻找真正能贡献超额收益的 alpha 来源。

## 本轮做了什么

| 迭代 | 动作 | 结果 |
| ---- | ---- | ---- |
| I51 | 新增 `strong_market_benchmark_aware_core_v1`，以 T-1 沪深300权重为核心锚，默认使用标准市场状态识别，保留轻微 alpha tilt | `reject`；但相对沪深300正超额折比例达到 `0.60` |
| I52 | 显式放宽 benchmark-aware 强市场状态识别 | `reject`；年化和 Sharpe 比 I51 更差 |
| I53 | 增加“状态切换触发调仓”的实验配置 | 发现配置未真正传入策略参数，保留为可追溯证据 |
| I54 | 修复 `rebalance_on_context_change` 参数通路后复跑 | `reject`；强行切换调仓导致换手过高、收益恶化 |

## 复核修正说明

Reviewer 复核发现：早版实现里 `context_mode` 默认就是 relaxed，会让 I51 和 I52 的实验边界不清。已修正为：

- I51 默认 `context_mode=standard`。
- I52/I54 才显式使用 `context_mode=benchmark_aware_relaxed`。
- 移除了未使用的 `relaxed_allow_high_vol` 假开关。
- 重跑 I51/I52/I54 admission 后，核心数值与本简报表格一致。以下 admission 路径以 `rerun_after_context_default_fix` 目录为准；I51 的 holdings exposure 和 CSI300 attribution 因 candidate folds 哈希一致，沿用原诊断目录。

## 关键数字

| 指标 | I51 benchmark-aware core | I52 relaxed context | I54 context-switch rebalance |
| ---- | ---: | ---: | ---: |
| admission action | `reject` | `reject` | `reject` |
| 年化收益均值 | `-0.0009` | `-0.0070` | `-0.0264` |
| Sharpe 均值 | `-0.1011` | `-0.1902` | `-0.4963` |
| 正收益折比例 | `0.40` | `0.40` | `0.20` |
| 正超额折比例 | `0.60` | `0.60` | `0.60` |
| 平均超额年化 | `0.0269` | `0.0208` | `0.0014` |
| 年化换手均值 | `0.59` | `0.59` | `3.67` |
| admission 主要阻塞 | 正收益折不足、overfit 高、行业集中、paper review 不支持 | 同 I51 | 同 I51，且换手超标 |

## 参与度诊断

I51 的沪深300权重归因显示：

- 平均持有沪深300权重约 `0.62` - `0.66`。
- Top20 覆盖率约 `0.98` - `0.996`。
- 行业 L1 偏离约 `0.34` - `0.38`。

这说明核心权重股覆盖已经明显改善。
但强基准阶段平均 live exposure 仍只有约 `0.249`，I52 也只提高到约 `0.274`。
I54 强制状态切换后，换手从 `0.59` 上升到 `3.67`，收益从接近持平恶化到 `-2.64%` 年化。

## 本轮判断

1. I51 证明“benchmark-aware core”可以解决 I49 看到的核心股漏配和行业偏离问题。
2. 但 I51 没有证明它能成为赚钱策略。绝对收益、Sharpe、正收益折比例都不达标。
3. I52/I54 说明，单纯扩大强市场参与或更频繁切换仓位，不是好方向。
4. 当前策略池缺口仍然是：强沪深300行情下能产生正超额的 alpha 机制，而不是单纯贴近沪深300。

## 下一步建议

下一轮不要继续调 `core_top_n`、`seed_core_top_n`、`rebalance_days` 这类参数。更有价值的方向是：

1. 保留 benchmark-aware core 作为诊断基线，不进入默认候选池。
2. 新设计一个 `benchmark_core_alpha_overlay_v1`：
   - 底仓仍用沪深300核心权重；
   - alpha 只在核心股内部做相对强弱、盈利质量、资金流或波动结构倾斜；
   - 目标不是提高覆盖，而是提高持有核心股时的超额收益。
3. 将 admission 的相对基准指标继续作为解释字段，但不降低现有准入门槛。

## 主要证据路径

- I51 admission: `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core_rerun_after_context_default_fix/admission/`
- I51 holdings exposure: `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/holdings_exposure/`
- I51 CSI300 attribution: `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/csi300_attribution_all/`
- I52 admission: `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context_rerun_after_context_default_fix/admission/`
- I54 admission: `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_54__context_switch_rebalance_param_fix_rerun_after_context_default_fix/admission/`
