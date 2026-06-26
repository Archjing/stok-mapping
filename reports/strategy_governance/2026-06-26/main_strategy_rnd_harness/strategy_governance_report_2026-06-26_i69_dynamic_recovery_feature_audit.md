# Strategy Governance Report - I69 Dynamic Recovery Feature Audit

日期：2026-06-26

报告性质：Harness 策略研发专项审计报告。本报告不新增策略，不改变 admission。forward 20 日收益只作为事后标签，用来发现可能的事前特征。

## 背景

I68 证明 I67 的静态宽度过滤在 fold2 上选反。I69 继续检查：是否存在更有用的动态特征，可以把 fold2 假 recovery 与 fold5 真 recovery 分开。

## 工程补充

为了完成本轮审计，补充了 holdings exposure 的诊断字段透传：`mom20`、`mom60`、`amount_ratio20`、`vol20`、`recovery_tradable_index_context` 和 recovery breadth 字段。该改动只增强审计可观测性，不改变策略收益计算。

验证命令：

```bash
./.venv/bin/python -m pytest tests/test_strategy_holdings_exposure.py tests/test_strong_market_stable_core_base_strategy.py tests/test_strategy_admission_config.py::test_force_strategy_set_enabled_supports_strong_benchmark_recovery_tradable_strategy -q -s
```

结果：33 passed, 1 warning。

## 方法

1. 用 I67 holdings exposure 重建日级宽度与行业领导特征；
2. 对 recovery 日期计算 5/10/20 日变化；
3. 用未来20日沪深300收益标记事后好/坏 recovery；
4. 对比 fold2、fold4、fold5。

## 重点结果

|   fold |   recovery_days |   positive_forward_20d_ratio |   avg_forward_20d_return |   tradable_days |   avg_breadth20 |   avg_industry_breadth |   avg_amount_ratio |   avg_amount_delta_20d |   avg_leader_persistence_20d |
|-------:|----------------:|-----------------------------:|-------------------------:|----------------:|----------------:|-----------------------:|-------------------:|-----------------------:|-----------------------------:|
|      2 |              56 |                       0.125  |                  -0.0266 |              28 |          0.6369 |                 0.6402 |             1.059  |                 0.0383 |                       0      |
|      4 |              49 |                       0.3265 |                  -0.0127 |               8 |          0.5157 |                 0.5574 |             0.9897 |                 0.0376 |                       0.0204 |
|      5 |              46 |                       0.9783 |                   0.0499 |              36 |          0.7592 |                 0.7598 |             1.1758 |                 0.0334 |                       0.8913 |

## 好/坏 recovery 标签对比

| positive_forward_20d   |   days |   avg_forward_20d_return |   tradable_ratio |   avg_breadth20 |   avg_breadth60 |   avg_industry_breadth |   avg_amount_ratio |   avg_breadth20_delta_20d |   avg_industry_breadth_delta_20d |   avg_amount_delta_20d |   avg_leader_persistence_20d |
|:-----------------------|-------:|-------------------------:|-----------------:|----------------:|----------------:|-----------------------:|-------------------:|--------------------------:|---------------------------------:|-----------------------:|-----------------------------:|
| False                  |    105 |                  -0.0327 |           0.3714 |          0.6296 |          0.6934 |                 0.6421 |             1.0045 |                    0.0886 |                           0.0646 |                -0.0369 |                       0.0476 |
| True                   |     68 |                   0.0428 |           0.5735 |          0.6508 |          0.7464 |                 0.6652 |             1.1492 |                    0.066  |                           0.0665 |                 0.0811 |                       0.6029 |

## 判断

I69 的关键结论：静态宽度水平不是主要分界。fold2 的 `avg_breadth20` 约 0.6369，不算低，但后续20日表现差；fold5 的 `avg_breadth20` 更高，但真正明显的差异是主线持续性和成交额扩散。

具体看：

- fold2：`avg_leader_persistence_20d = 0.0000`，说明主导行业不稳定；
- fold5：`avg_leader_persistence_20d = 0.8913`，说明主导行业高度持续；
- 正向 recovery 的 `avg_amount_ratio` 约 1.1492，负向 recovery 约 1.0045；
- 正向 recovery 的 `avg_leader_persistence_20d` 约 0.6029，负向 recovery 约 0.0476。

这支持下一步策略构造方向：如果继续做 recovery 策略，过滤条件应从“静态宽度达标”转为“宽度不差 + 成交额扩散 + 可见历史下的近期主线稳定性代理特征”。本轮 `avg_leader_persistence_20d` 是事后解释指标，不能直接进入交易信号。

## 下一步

I70 可以先做一个很小的 research-only 设计验证：在 I67 基础上加入仅使用 T-1 可见历史的代理特征，例如：

- 最近若干交易日主导行业稳定性；
- `amount_ratio20_min` 或历史窗口内成交额扩散改善；
- 保持 fold2 不参与、fold5 保留的目标。

但在实现前需要注意：主导行业持续性必须用可见历史计算，不能用未来20日标签。
