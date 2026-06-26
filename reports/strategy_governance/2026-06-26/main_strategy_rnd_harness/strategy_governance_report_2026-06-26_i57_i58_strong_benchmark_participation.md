# Strategy Governance Report - I57/I58 Strong Benchmark Participation

生成日期：2026-06-26

## 报告背景

I56 alpha source audit 显示，I51/I55 在强沪深300阶段跑输的主因仍是 `low_participation`。本轮 I57/I58 围绕同一假设推进：

> 如果沪深300处于强趋势，策略应该提高核心参与仓位，而不是只做到“名义覆盖头部成分”。

本轮新增 research-only 策略 `strong_benchmark_participation_boost_v1`，并做了两个 scoped admission 实验。

## 代码与配置变更

| 文件 | 说明 |
| --- | --- |
| `phase0/strategies/strong_market_stable_core_base.py` | 新增 `StrongBenchmarkParticipationBoostStrategy`，继承 benchmark-aware core 逻辑 |
| `phase0/strategies/__init__.py` | 导出新策略 |
| `phase0/strategy_admission.py` | admission scoped strategy set 可强制启用新策略 |
| `tests/test_strong_market_stable_core_base_strategy.py` | 覆盖新策略注册、research-only 边界、强市场目标仓位行为 |
| `tests/test_strategy_admission_config.py` | 覆盖 admission 强制启用映射 |
| `config.main_strategy_i57_strong_benchmark_participation_boost_20260626.yaml` | I57a：强市场加仓 + 状态切换再平衡 |
| `config.main_strategy_i58_strong_exposure_only_20260626.yaml` | I58：关闭状态切换再平衡，只验证强市场加仓 |

新策略保持 `supports_brief=False`、`supports_paper_trade=False`，未加入 `baseline_admission_all_v1`。

## 实验变量

| 实验 | strong_target_exposure | rebalance_on_context_change | core_budget_ratio | satellite_budget_ratio | 目的 |
| --- | ---: | --- | ---: | ---: | --- |
| I57a | 0.85 | true | 1.0 | 0.0 | 验证强市场加仓，并在状态切换时及时加仓 |
| I58 | 0.85 | false | 1.0 | 0.0 | 排除状态切换导致的换手污染，只验证强市场目标仓位 |

其它口径保持不变：PIT universe、`qfq_asof`、沪深300 as-of 权重、交易成本、`baseline_2y_1y_5fold` admission gate 均不变。

## I57a 结果

| 指标 | I57a |
| --- | ---: |
| admission action | reject |
| 年化收益均值 | -2.86% |
| Sharpe 均值 | -0.56 |
| 正收益折比例 | 20% |
| 正超额折比例 | 60% |
| 年化换手均值 | 4.30 |
| 最差最大回撤 | -9.40% |

I57a 的关键问题是换手失控：

- fold 1 年化换手 8.68；
- fold 5 年化换手 12.32；
- fold 5 年化收益 -5.59%，相对沪深300年化超额 -20.70%。

结论：`rebalance_on_context_change=true` 不能直接进入下一步策略，它把实验从“提高强市场参与”污染成“频繁切换交易”。

## I58 结果

| 指标 | I58 |
| --- | ---: |
| admission action | reject |
| 年化收益均值 | -0.22% |
| Sharpe 均值 | -0.12 |
| 正收益折比例 | 40% |
| 正超额折比例 | 60% |
| 年化换手均值 | 0.70 |
| 最差最大回撤 | -7.04% |

I58 修复了 I57a 的换手问题，但仍未准入。分折结果如下：

| Fold | 策略年化 | 沪深300年化 | 超额年化 | 换手 | 归因 |
| --- | ---: | ---: | ---: | ---: | --- |
| 1 | -4.65% | -17.96% | +13.31% | 0.71 | 弱基准环境下绝对亏损但有正超额 |
| 2 | -0.89% | -5.46% | +4.56% | 0.16 | 弱基准环境下绝对亏损但有正超额 |
| 3 | -1.27% | -14.09% | +12.82% | 0.16 | 弱基准环境下绝对亏损但有正超额 |
| 4 | +2.11% | +8.50% | -6.39% | 0.17 | 强基准阶段跑输 |
| 5 | +3.62% | +15.11% | -11.49% | 2.32 | 强基准阶段跑输 |

## 与 I51/I55 的强基准对比

| Fold | 版本 | 实际仓位 | 持有基准权重 | 前20覆盖率 | 超额总收益 | 主因 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 4 | I51 | 14.91% | 63.06% | 99.59% | -7.78% | low_participation |
| 4 | I55 | 14.90% | 63.06% | 99.59% | -7.79% | low_participation |
| 4 | I58 | 14.91% | 63.06% | 99.59% | -7.78% | low_participation |
| 5 | I51 | 34.84% | 63.86% | 99.59% | -9.75% | low_participation |
| 5 | I55 | 34.86% | 63.85% | 99.59% | -10.64% | low_participation |
| 5 | I58 | 38.57% | 63.85% | 99.59% | -10.24% | low_participation |

I58 的 `strong_target_exposure=0.85` 没有充分转化成强基准窗口的实际仓位。fold 4 几乎没有变化，fold 5 只从约 34.8% 提升到 38.6%。因此，本轮不能简单归结为“把目标仓位调高就行”。

## 行业与个股观察

I58 相比 I51 仍削弱了若干强市场正贡献来源：

| 来源 | I51 贡献 | I58 贡献 | 变化 |
| --- | ---: | ---: | ---: |
| 元器件 | +1.30% | +0.16% | -1.15pct |
| 通信设备 | +2.27% | +1.56% | -0.71pct |
| 染料涂料 | +0.46% | 0.00% | -0.46pct |
| 银行 | +0.73% | +0.52% | -0.20pct |

代表个股：

| 个股 | 行业 | I51 贡献 | I58 贡献 | 变化 |
| --- | --- | ---: | ---: | ---: |
| 信维通信 | 元器件 | +1.15% | 0.00% | -1.15pct |
| 海格通信 | 通信设备 | +0.74% | 0.00% | -0.74pct |
| 浙江龙盛 | 染料涂料 | +0.46% | 0.00% | -0.46pct |
| 恒瑞医药 | 化学制药 | -0.11% | -0.20% | -0.09pct |

这说明 I58 虽然提高了配置意图，但并没有解决“强势行业/个股贡献来源被削弱”的问题。

## 阶段判断

I58 不是可准入策略，但它保留了一个研发线索：

- 强市场加仓方向比 I55 alpha overlay 更符合问题根因；
- 但当前实现没有把目标仓位有效转化为实际强基准参与；
- `rebalance_on_context_change=true` 会造成换手失控，短期不应使用；
- 后续必须先做“强市场参与链路审计”，再继续设计策略。

## 下一步建议

I59 建议做 `strong_participation_path_audit`，目标不是新策略，而是解释为什么 `strong_target_exposure=0.85` 没有变成强基准窗口的高实际仓位。

最小审计口径：

1. 按日期输出 `strong_index_context`、`market_context_label`、`review_day`、`target_exposure`、`live_exposure`。
2. 分 fold 统计：强基准窗口内，多少天目标仓位高于 80%，多少天实际仓位低于 50%。
3. 把 T+1 权重延迟、再平衡日、状态标签错位拆开看。
4. 再决定是否需要更早触发器、渐进加仓，或不同的强市场状态定义。

## 验证记录

已执行：

```bash
./.venv/bin/python -m pytest tests/test_strong_market_stable_core_base_strategy.py tests/test_strategy_admission_config.py -q -s
./.venv/bin/python -m phase0.cli strategy-admission --config config.main_strategy_i57_strong_benchmark_participation_boost_20260626.yaml --presets baseline_2y_1y_5fold --strategy-set i57_strong_benchmark_participation_boost_v1 --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_57__strong_benchmark_participation_boost/admission --trace-run
./.venv/bin/python -m phase0.cli strategy-admission --config config.main_strategy_i58_strong_exposure_only_20260626.yaml --presets baseline_2y_1y_5fold --strategy-set i58_strong_exposure_only_v1 --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/admission --trace-run
```

结果：

- 定向测试：`55 passed, 1 warning`
- I57a admission：`reject`
- I58 admission：`reject`
- I58 CSI300 attribution：`status=ok`
- I58 alpha source audit vs I51：已生成

## 产物说明

大体量原始明细仅作为本地分析依据，不建议提交：

- `iter_58__strong_exposure_only/holdings_exposure/strategy_daily_holdings.csv`，约 32M。
- `iter_58__strong_exposure_only/csi300_attribution_all/strategy_csi300_industry_active_weights.csv`，约 20M。
- `iter_58__strong_exposure_only/holdings_exposure/strategy_daily_industry_exposure.csv`，约 7.2M。

建议提交代码、配置、报告、小型 CSV 汇总和 alpha audit 小产物。
