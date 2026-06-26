# Strategy Governance Report - I61 Recovery Participation

日期：2026-06-26

报告性质：Harness 策略研发专项报告。本报告记录 `strong_benchmark_recovery_participation_v1` 的 research-only 实验结果，不代表准入或交易建议。

## 背景

I60 发现，I58 在 fold4 的强基准落后窗口里没有进入 strong 状态，关键原因是 `strong_index_drawdown` 长期低于 -12% 门槛。换句话说，指数虽然出现趋势修复，但从历史高点看仍是深回撤，所以策略一直按风险压力处理。

I61 的问题是：能否用一个只依赖 as-of 指数数据的 recovery context，识别“深回撤后的趋势修复”，把仓位从 0.15 提高到中高仓，从而改善强基准环境下的参与不足。

## 实现边界

新增策略：

- `strong_benchmark_recovery_participation_v1`

保持不变：

- T+1 shift 逻辑；
- 沪深300核心权重构造；
- 成本、滑点、佣金、印花税；
- fold 切分；
- admission gate；
- 默认 12 个候选策略池。

新增 research-only 参数：

| 参数 | 值 | 含义 |
| --- | ---: | --- |
| recovery_target_exposure | 0.65 | recovery 状态目标仓位 |
| recovery_ret20_min | -0.02 | 20日收益不能明显转弱 |
| recovery_ret60_min | 0.03 | 60日收益需为正并有一定修复 |
| recovery_drawdown_min | -0.50 | 排除过深破位 |
| recovery_drawdown_max | -0.12 | 仍处深回撤区间，不等同 strong |
| recovery_max_vol_multiplier | 1.25 | 波动可略高于原阈值，但不能失控 |

## 运行命令

```bash
./.venv/bin/python -m phase0.cli strategy-admission \
  --config config.main_strategy_i61_recovery_participation_20260626.yaml \
  --presets baseline_2y_1y_5fold \
  --strategy-set i61_strong_benchmark_recovery_participation_v1 \
  --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_61__recovery_participation/admission
```

```bash
./.venv/bin/python -m phase0.cli strategy-holdings-exposure \
  --config config.main_strategy_i61_recovery_participation_20260626.yaml \
  --candidate-folds reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_61__recovery_participation/admission/strategy_admission_candidate_folds.csv \
  --market-context reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/market_context/strategy_market_context_diagnostic.csv \
  --strategy strong_benchmark_recovery_participation_v1 \
  --presets baseline_2y_1y_5fold \
  --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_61__recovery_participation/holdings_exposure \
  --benchmark-symbol SH.000300
```

## Admission 结果

结论：`reject`

| 指标 | 结果 |
| --- | ---: |
| annualized_return_mean | -0.009913 |
| sharpe_mean | -0.380056 |
| max_drawdown_worst | -0.077962 |
| positive_fold_ratio | 0.20 |
| positive_excess_fold_ratio | 0.40 |
| turnover_annual_mean | 1.855004 |
| turnover_annual_max | 2.755256 |
| admission action | reject |

主要失败原因：

- overfit risk is high；
- industry concentration exceeds audit threshold；
- positive fold ratio below 75%；
- research-only 策略不支持 paper review。

## 对比 I58

| fold | I58 年化 | I61 年化 | 年化变化 | I58 超额 | I61 超额 | 超额变化 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | -0.046541 | -0.046541 | 0.000000 | 0.133066 | 0.133066 | 0.000000 |
| 2 | -0.008920 | -0.059767 | -0.050848 | 0.045648 | -0.005200 | -0.050848 |
| 3 | -0.012735 | -0.022512 | -0.009778 | 0.128191 | 0.118414 | -0.009778 |
| 4 | 0.021060 | -0.000094 | -0.021154 | -0.063910 | -0.085064 | -0.021154 |
| 5 | 0.036200 | 0.079348 | 0.043148 | -0.114863 | -0.071715 | 0.043148 |

I61 改善了 fold5，但牺牲了 fold2、fold3、fold4。整体不是稳定改进。

## 状态覆盖对比

| fold | 标签 | I58 strong 天数 | I58 高仓天数 | I61 recovery 天数 | I61 中高仓天数 | I58 平均 target | I61 平均 target |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | relative_lag_in_strong_benchmark_context | 0 | 0 | 49 | 60 | 0.149718 | 0.274200 |
| 5 | relative_lag_in_strong_benchmark_context | 61 | 60 | 46 | 100 | 0.387402 | 0.469680 |

I61 的 recovery trigger 确实提升了参与度。但参与度提升没有自动转化为稳定收益。

## 判断

I61 证明了一个方向：当前策略可以通过 as-of recovery context 提高深回撤修复阶段的仓位覆盖。

但 I61 也证明当前版本过粗：

- 它把部分弱反弹也当成可参与阶段；
- 中高仓位 0.65 对 recovery 状态可能偏激进；
- fold2、fold3、fold4 的收益恶化说明恢复触发器需要更强的质量过滤。

因此 I61 不能进入 paper review，也不应加入默认候选池。

## 下一步

I62 建议做“恢复触发器分层”：

1. recovery 仓位先降到 0.40 或 0.50，作为 mixed 与 strong 中间档。
2. 加入修复质量条件，例如连续站上 MA、ret20/ret60 改善斜率、回撤收敛。
3. 将 recovery 触发器的目标从“提高年化”改为“在 fold4/fold5 改善参与度但不伤害 fold2/fold3”。
4. 继续保持 research-only，不进入默认 admission all 策略池。
