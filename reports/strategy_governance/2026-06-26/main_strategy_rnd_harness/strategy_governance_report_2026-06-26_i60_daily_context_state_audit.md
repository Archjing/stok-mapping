# Strategy Governance Report - I60 Daily Context State Audit

日期：2026-06-26

报告性质：Harness 策略研发专项审计报告。本报告用于解释强市场参与度不足的触发器原因，不改变 admission 结论。

## 背景

I59 证明：I58 的 live exposure 主要跟随前一交易日 target exposure，执行链路基本正常。真正的问题是 I58 在很多“强基准落后”日期没有把 target exposure 设成高仓位。

I60 继续向上追踪：为什么策略自己的日频 `strong_index_context` 没有触发。

## 工程变更

增强 `strategy-holdings-exposure` 诊断，保留并汇总策略 signal frame 里的日频状态字段：

- `strong_index_context`
- `review_day`
- `review_reason`
- `dynamic_review_trigger`
- `strong_index_ret20`
- `strong_index_ret60`
- `strong_index_close`
- `strong_index_ma120`
- `strong_index_vol20`
- `strong_index_vol_threshold`
- `strong_index_drawdown`

新增和更新的验证：

- `tests/test_strategy_holdings_exposure.py`
- `tests/test_strategy_participation_path_audit.py`

## 运行命令

```bash
./.venv/bin/python -m phase0.cli strategy-holdings-exposure \
  --config config.main_strategy_i58_strong_exposure_only_20260626.yaml \
  --candidate-folds reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/admission/strategy_admission_candidate_folds.csv \
  --market-context reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/market_context/strategy_market_context_diagnostic.csv \
  --strategy strong_benchmark_participation_boost_v1 \
  --presets baseline_2y_1y_5fold \
  --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_60__daily_context_state_audit/holdings_exposure \
  --benchmark-symbol SH.000300
```

## 关键证据

状态汇总：

| fold | 市场诊断标签 | 天数 | strong context 天数 | 高 target 天数 | 平均 target | 平均 live |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | absolute_loss_but_benchmark_weak_context | 243 | 7 | 0 | 0.211624 | 0.211007 |
| 2 | risk_context_pressure | 243 | 0 | 0 | 0.149986 | 0.149369 |
| 3 | absolute_loss_but_benchmark_weak_context | 241 | 0 | 0 | 0.150000 | 0.149378 |
| 4 | relative_lag_in_strong_benchmark_context | 241 | 0 | 0 | 0.149718 | 0.149091 |
| 5 | relative_lag_in_strong_benchmark_context | 242 | 61 | 60 | 0.387402 | 0.385749 |

触发条件拆解：

| fold | 标签 | close > MA120 | ret20 > 0 | ret60 > 0 | vol ok | drawdown ok | 平均回撤 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | relative_lag_in_strong_benchmark_context | 177 | 106 | 122 | 163 | 0 | -0.364548 |
| 5 | relative_lag_in_strong_benchmark_context | 192 | 153 | 177 | 193 | 129 | -0.147311 |

## 判断

fold4 并不是完全没有趋势修复迹象。它有 177 天处于 `close > MA120`，122 天 `ret60 > 0`，163 天波动条件通过。但 `drawdown_ok_days=0`，说明当前从历史高点计算的回撤阈值把整个 fold4 都压成非 strong。

这解释了为什么 I58 在 fold4 一直维持约 0.15 仓位。策略看到的是“从历史高点仍深度回撤”，而不是“恢复型强市场”。

## 风险边界

不能直接把 `market_context_label=relative_lag_in_strong_benchmark_context` 当交易信号。它是事后诊断标签，直接用于交易会形成未来函数。

下一步可以研究新的 as-of 触发器，但必须满足：

- 所有信号来自当日或更早的指数数据；
- 保留 `_build_shifted_index_context()` 的 T+1 口径；
- 不修改回测成本、fold 切分和 admission gate；
- 先看状态召回，再看收益，避免用收益倒推阈值。

## 下一步建议

I61 建议设计 research-only 策略：`strong_benchmark_recovery_participation_v1`。

目标不是简单放松所有风控，而是识别“熊市后修复、仍距历史高点较远、但趋势和动量已经改善”的环境。初始设计可以：

- 复用 I58 的组合构造和高仓位上限；
- 新增 `recovery_context`；
- `recovery_context` 使用 `close > MA120`、`ret60 > 0`、`ret20` 不显著为负、波动不过度失控等 as-of 条件；
- 对 `recovery_context` 给中高仓位，例如 0.65，而不是 0.15；
- 保留深度恶化退出条件，避免把下跌中继误判成恢复。

验收标准：

- fold4 的 high 或 mid-high target 天数明显增加；
- fold5 不明显恶化；
- turnover 不因状态抖动显著上升；
- 相对沪深300的 fold-level excess 有改善；
- admission 仍按 research-only 口径观察，不直接推动 paper review。
