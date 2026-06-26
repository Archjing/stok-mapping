# Harness Iteration Brief - 2026-06-26 - I55 Benchmark Core Alpha Overlay

> 本简报是本轮 Harness 策略研发记录。所有结论都是 research-only，不生成交易信号，不进入 paper review、模拟账户、日报或 watchlist。

## 一句话结论

`benchmark_core_alpha_overlay_v1` 没有通过准入，也没有证明这组 alpha overlay 有效。

它保持了沪深300核心覆盖，但收益没有明显改善。问题不在“漏配核心股”，而在“核心股内部的动量、低波、成交活跃度倾斜没有贡献足够超额收益”。

## 本轮做了什么

| 项目 | 内容 |
| ---- | ---- |
| 策略 | 新增 `benchmark_core_alpha_overlay_v1` |
| 定位 | research-only；不进入默认 12 个候选池 |
| 权重结构 | `85%` 沪深300核心权重锚 + `15%` 核心股内部 alpha overlay |
| alpha 信号 | 行业内相对 `mom60`、`mom20`、低 `vol20`、`amount_ratio20` |
| 市场状态 | 沿用 I51 的标准 context，不启用 I52 relaxed，不启用 I54 context-switch rebalance |
| 修正 | 发现并修正行业中性 rank 方向错误；权威结果使用 `rerun_after_rank_direction_fix` 目录 |

## 关键结果

| 指标 | I51 benchmark-aware core | I55 alpha overlay 修正版 | 判断 |
| ---- | ---: | ---: | ---- |
| admission action | `reject` | `reject` | 未改善 |
| 年化收益均值 | `-0.0009` | `-0.0019` | 略差 |
| Sharpe 均值 | `-0.1011` | `-0.0999` | 基本持平 |
| 正收益折比例 | `0.40` | `0.40` | 未改善 |
| 正超额折比例 | `0.60` | `0.60` | 未改善 |
| 平均超额年化 | `0.0269` | `0.0260` | 略差 |
| 年化换手均值 | `0.59` | `0.58` | 基本持平 |

## 覆盖诊断

| 指标 | I55 修正版 |
| ---- | ---: |
| 平均 live exposure | `0.2015` |
| 平均持有沪深300权重 | `0.6370` |
| 平均 Top20 覆盖率 | `0.9932` |
| 平均行业 L1 偏离 | `0.3425` |
| 强基准阶段平均超额年化 | `-0.0907` |

这说明 I55 没有破坏 I51 形成的核心覆盖能力。覆盖、Top20、行业贴近度都仍然合格；失败主要来自收益来源不足。

## 本轮判断

1. I55 的 alpha overlay 机制可以稳定运行，且不会明显破坏核心覆盖。
2. 但这组 alpha 信号没有提升正收益折比例，也没有改善正超额折比例。
3. 在强沪深300阶段，策略仍然跑输基准，说明“核心股内部简单动量/低波/成交活跃倾斜”不是当前有效突破口。
4. 不应继续围绕 `anchor_sleeve_ratio`、`overlay_sleeve_ratio`、`alpha_tilt_strength` 做网格搜索；那会变成参数挖掘。

## 下一步建议

下一轮不要继续调 I55 参数。更值得做的是：

1. 做 `I56 alpha source audit`：按持仓贡献拆解 I51/I55 在强基准阶段到底输给了哪些核心股、哪些行业、哪些风格。
2. 判断是否需要新 alpha 来源，而不是在现有动量/低波/成交活跃组合上加参数。
3. 如果要继续核心增强，应优先考虑可解释的新信息源，例如财务质量 PIT 覆盖、分析师/公告情报、指数成分权重变化、行业景气，而不是继续扩大日线价格因子自由度。

## 主要证据路径

- I55 admission 修正版：`reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/admission/`
- I55 failure attribution 修正版：`reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/failure_attribution/`
- I55 holdings exposure 修正版：`reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/holdings_exposure/`
- I55 CSI300 attribution 修正版：`reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/csi300_attribution_all/`
