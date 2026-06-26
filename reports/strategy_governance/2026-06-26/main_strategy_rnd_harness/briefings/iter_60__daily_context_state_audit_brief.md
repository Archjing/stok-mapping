# I60 Daily Context State Audit Brief

日期：2026-06-26

本轮目标：把策略真实日频状态写入 holdings exposure 诊断，解释 I58 为什么在“强基准落后”窗口里没有持续高仓位。

## 结论

I60 进一步确认：问题不是执行层，而是强市场触发器太保守。

fold4 是最典型的例子。这个窗口事后被诊断为 `relative_lag_in_strong_benchmark_context`，但策略日频 `strong_index_context` 一天都没有触发：

| fold | 标签 | 天数 | strong context 天数 | 高目标仓天数 | 平均 target | 平均 live |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 4 | relative_lag_in_strong_benchmark_context | 241 | 0 | 0 | 0.149718 | 0.149091 |
| 5 | relative_lag_in_strong_benchmark_context | 242 | 61 | 60 | 0.387402 | 0.385749 |

fold4 不是完全没有趋势修复信号：

| fold | close > MA120 天数 | ret20 > 0 天数 | ret60 > 0 天数 | vol ok 天数 | drawdown ok 天数 | 平均回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 177 | 106 | 122 | 163 | 0 | -0.364548 |
| 5 | 192 | 153 | 177 | 193 | 129 | -0.147311 |

关键卡点是 `drawdown_ok_days=0`。当前触发器要求从历史高点回撤不深于约 -12%，fold4 虽然进入趋势修复，但距离历史高点仍太远，于是长期被判成风险压力。

## 对下一轮策略构造的含义

下一轮不应继续只调高 `strong_target_exposure`。更值得做的是一个 research-only “恢复型强市场触发器”：

- 仍只使用 as-of 可见的指数价格特征；
- 保留 T+1 shift；
- 不使用事后 `market_context_label`；
- 把“从历史高点回撤很深但趋势正在修复”的阶段单独识别出来；
- 对这类阶段给中高仓位，而不是长期压在 0.15。

## 本轮产物

- 代码增强：`phase0/strategy_holdings_exposure.py`
- 测试增强：`tests/test_strategy_holdings_exposure.py`
- 小型状态汇总：`reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_60__daily_context_state_audit/daily_context_state_summary.csv`
- 触发器失效摘要：`reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_60__daily_context_state_audit/daily_context_trigger_failure_summary.csv`
- daily exposure：`reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_60__daily_context_state_audit/holdings_exposure/strategy_daily_exposure.csv`

大文件说明：`strategy_daily_holdings.csv` 和 `strategy_daily_industry_exposure.csv` 仅作为本地过程产物，不建议提交。
