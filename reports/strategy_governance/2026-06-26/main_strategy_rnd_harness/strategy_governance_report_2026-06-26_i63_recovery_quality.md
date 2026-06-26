# Strategy Governance Report - I63 Recovery Quality

日期：2026-06-26

报告性质：Harness 策略研发专项报告。本报告记录 `strong_benchmark_recovery_quality_v1` 的 research-only 实验结果，不代表准入或交易建议。

## 背景

I61 证明 recovery trigger 能提高强基准窗口参与度，但也造成 fold2、fold3、fold4 的错误参与。I62 的设计结论是：需要把 recovery 拆成“高质量修复”和“弱修复”，而不是所有 recovery 都给 0.65 仓位。

I63 将这个设计实现为 `strong_benchmark_recovery_quality_v1`。

## 实现边界

保持不变：

- 默认 12 个候选策略池；
- T+1 持仓生效；
- 回测成本；
- walk-forward fold 切分；
- admission gate；
- 沪深300核心组合构造。

新增：

- `recovery_quality_index_context`
- weak recovery 目标仓位 0.40；
- quality recovery 目标仓位 0.65。

## 运行结果

Admission action：`reject`

| 指标 | 结果 |
| --- | ---: |
| annualized_return_mean | -0.009519 |
| sharpe_mean | -0.388704 |
| max_drawdown_worst | -0.077962 |
| positive_fold_ratio | 0.20 |
| positive_excess_fold_ratio | 0.40 |
| turnover_annual_mean | 1.594024 |
| turnover_annual_max | 2.495997 |

失败原因：

- overfit risk is high；
- industry concentration exceeds audit threshold；
- positive fold ratio below 75%；
- research-only 策略不支持 paper review。

## 和 I58/I61 比

| fold | I58 年化 | I61 年化 | I63 年化 | I63 相对 I58 | I63 相对 I61 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | -0.046541 | -0.046541 | -0.046541 | 0.000000 | 0.000000 |
| 2 | -0.008920 | -0.059767 | -0.061842 | -0.052922 | -0.002075 |
| 3 | -0.012735 | -0.022512 | -0.017582 | -0.004847 | 0.004930 |
| 4 | 0.021060 | -0.000094 | -0.000980 | -0.022040 | -0.000886 |
| 5 | 0.036200 | 0.079348 | 0.079348 | 0.043148 | 0.000000 |

I63 保留了 fold5 的收益改善，也降低了 I61 的换手；但 fold2/fold4 仍然明显弱于 I58。

## 状态覆盖

| fold | 标签 | recovery 天数 | quality recovery 天数 | weak recovery 天数 | I63 平均 target |
| --- | --- | ---: | ---: | ---: | ---: |
| 2 | risk_context_pressure | 56 | 34 | 22 | 0.235377 |
| 3 | absolute_loss_but_benchmark_weak_context | 22 | 11 | 11 | 0.172822 |
| 4 | relative_lag_in_strong_benchmark_context | 49 | 17 | 32 | 0.232706 |
| 5 | relative_lag_in_strong_benchmark_context | 46 | 41 | 5 | 0.469680 |

quality filter 起到了分层作用：fold4 的平均 target 从 I61 的 0.274200 降到 0.232706。但这还不足以修复 fold4 的超额表现。

## 判断

I63 的方向比 I61 更稳，但当前仍不能作为候选策略推进。

主要问题不是“是否需要 recovery”，而是“如何过滤错误 recovery”。现在的质量条件只看 ret20、ret60、vol，缺少对回撤修复路径的判断。因此它仍会在部分弱反弹阶段加仓。

## 下一步建议

下一步 I64 应先做审计，不直接再加策略：

1. 计算 `drawdown_delta_20d` 或类似“回撤是否收敛”的日频特征。
2. 对 I61/I63 的 recovery 日期做分组，比较 `drawdown_delta_20d` 与后续 benchmark return。
3. 如果证据支持，再实现 `recovery_drawdown_repair` 过滤器。

继续保持 research-only，不进入默认候选策略池。
