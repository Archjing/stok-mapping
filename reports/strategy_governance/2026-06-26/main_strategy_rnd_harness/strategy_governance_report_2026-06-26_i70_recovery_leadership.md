# Strategy Governance Report - I70 Recovery Leadership

日期：2026-06-26

报告性质：Harness 策略研发专项报告。本报告记录 I70 research-only 候选策略，不代表准入、模拟盘或实盘建议。

## 背景

I68/I69 指出：I67 的静态宽度过滤会在 fold2 误判假 recovery。I69 进一步发现，事后看正向 recovery 往往有更强的成交额扩散和主线持续性。但事后20日主线持续性不能直接用作交易信号。

I70 的目标是构造一个只使用 T-1 可见历史的代理版本：用近期主导行业稳定度和全市场成交额扩散，过滤 recovery 高仓位。

## 本轮代码变化

- 新增 research-only 策略：`strong_benchmark_recovery_leadership_v1`。
- 新增可见历史代理特征：`recovery_leadership_stability_ratio`、`recovery_leadership_top_industry`。
- 修复 `strategy-holdings-exposure`：让 scoped research 策略和 admission 一样可以被强制启用。
- 增强 holdings exposure 的 recovery/leadership 诊断字段输出。

## 验证命令

```bash
./.venv/bin/python -m pytest tests/test_strategy_holdings_exposure.py tests/test_strong_market_stable_core_base_strategy.py tests/test_strategy_admission_config.py::test_force_strategy_set_enabled_supports_strong_benchmark_recovery_leadership_strategy -q -s

./.venv/bin/python -m phase0.cli strategy-admission --config config.main_strategy_i67_recovery_tradable_20260626.yaml --presets baseline_2y_1y_5fold --strategies strong_benchmark_recovery_leadership_v1 --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_70__recovery_leadership/admission
```

测试结果：36 passed, 1 warning。

## Admission 结果

I70 admission action: reject。

主要原因：年化收益均值仍为负，Sharpe 仍为负，正收益折比例仍低于 0.75，overfit 风险仍为 high，且策略声明不支持 paper trade。

## I67 vs I70 总览

| metric                        |   I67 tradable |   I70 leadership |     delta |
|:------------------------------|---------------:|-----------------:|----------:|
| annualized_return_mean        |      -0.006663 |        -0.004363 |  0.0023   |
| sharpe_mean                   |      -0.31679  |        -0.270549 |  0.046241 |
| positive_fold_ratio           |       0.4      |         0.4      |  0        |
| positive_excess_fold_ratio    |       0.4      |         0.6      |  0.2      |
| excess_annualized_return_mean |       0.02115  |         0.023451 |  0.0023   |
| excess_annualized_return_min  |      -0.072235 |        -0.093077 | -0.020842 |
| max_drawdown_worst            |      -0.077962 |        -0.070386 |  0.007576 |
| turnover_annual_mean          |       1.41635  |         1.16622  | -0.250134 |

## 分折变化

|   fold |   annualized_return_i67 |   annualized_return_i70 |   annualized_return_delta |   excess_annualized_return_i67 |   excess_annualized_return_i70 |   excess_annualized_return_delta |   max_drawdown_i67 |   max_drawdown_i70 |   turnover_annual_i67 |   turnover_annual_i70 |
|-------:|------------------------:|------------------------:|--------------------------:|-------------------------------:|-------------------------------:|---------------------------------:|-------------------:|-------------------:|----------------------:|----------------------:|
|      1 |               -0.046541 |               -0.046541 |                  0        |                       0.133066 |                       0.133066 |                         0        |          -0.070386 |          -0.070386 |              0.706422 |              0.706422 |
|      2 |               -0.062257 |               -0.029392 |                  0.032865 |                      -0.007689 |                       0.025176 |                         0.032865 |          -0.077962 |          -0.05455  |              2.44414  |              1.1997   |
|      3 |               -0.016602 |               -0.016602 |                  0        |                       0.124324 |                       0.124324 |                         0        |          -0.036015 |          -0.036015 |              0.575104 |              0.575104 |
|      4 |                0.012735 |                0.012735 |                  0        |                      -0.072235 |                      -0.072235 |                         0        |          -0.030491 |          -0.030491 |              1.01076  |              1.01076  |
|      5 |                0.079348 |                0.057985 |                 -0.021363 |                      -0.071715 |                      -0.093077 |                        -0.021363 |          -0.049024 |          -0.049024 |              2.34533  |              2.3391   |

## 判断

I70 对 fold2 有明显帮助。它把假 recovery 的伤害降下来，这是本轮最有价值的证据。

但 I70 也削弱了 fold5。说明“一刀切领导稳定阈值”太粗，会把部分真 recovery 的上行收益砍掉。

因此，I70 不应进入默认候选池，也不应进入 paper review。它应该作为 I71 的依据：从硬过滤改成连续评分或分档仓位。

## 下一步建议

1. I71 做 recovery score，而不是单一阈值：成交额扩散、近期主线稳定、宽度、指数趋势各自给分。
2. 仓位分三档：弱 recovery、可交易 recovery、高质量 recovery，不要只做通过/不通过。
3. 重点验收 fold2 不再亏相对基准，同时 fold5 不明显丢失收益。
