# Strategy Governance Report - I59 Participation Path Audit

日期：2026-06-26

报告性质：Harness 策略研发专项审计报告。本报告为解释 I58 强市场参与度实验结果而生成，不是策略准入报告。

## 背景

I57/I58 测试了 `strong_benchmark_participation_boost_v1`。I58 关闭了上下文切换再平衡，并把 strong 状态目标仓位设为 0.85。结果显示：

- turnover 明显改善；
- fold4/fold5 绝对收益转正；
- 但相对强沪深300仍落后，admission 仍为 reject；
- fold4 平均 live exposure 约 0.149，fold5 约 0.386，没有达到直觉上预期的高仓位。

本轮 I59 的目标是把“高仓位没有出现”的原因拆开：到底是目标仓位没有设成高仓，还是目标仓位设高后执行没有跟上。

## 审计口径

输入文件：

- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/holdings_exposure/strategy_daily_exposure.csv`

输出目录：

- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_59__participation_path_audit/`

新增审计代码：

- `phase0/strategy_participation_path_audit.py`

新增测试：

- `tests/test_strategy_participation_path_audit.py`

## 关键结果

| fold | 市场诊断标签 | 天数 | 平均 target | 平均 live | 高 target 天数 | 低 live 且高 target 天数 | target 分布 | live 分布 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1 | absolute_loss_but_benchmark_weak_context | 243 | 0.211624 | 0.211007 | 0 | 0 | mixed_mid=60; risk_or_low=183 | low_live=183; low_mid_live=60 |
| 2 | risk_context_pressure | 243 | 0.149986 | 0.149369 | 0 | 0 | risk_or_low=243 | low_live=243 |
| 3 | absolute_loss_but_benchmark_weak_context | 241 | 0.150000 | 0.149378 | 0 | 0 | risk_or_low=241 | low_live=241 |
| 4 | relative_lag_in_strong_benchmark_context | 241 | 0.149718 | 0.149091 | 0 | 0 | risk_or_low=241 | low_live=241 |
| 5 | relative_lag_in_strong_benchmark_context | 242 | 0.387402 | 0.385749 | 60 | 2 | mixed_mid=62; risk_or_low=120; strong_high=60 | high_live=60; low_live=121; low_mid_live=61 |

T+1 验证：

| fold | live 对同日 target 平均误差 | live 对前一日 target 平均误差 |
| --- | ---: | ---: |
| 4 | 0.000644 | 0.000047 |
| 5 | 0.009137 | 0.000075 |

## 判断

I58 没有形成持续高仓位，不是因为持仓执行模块没跟上目标仓位。实际数据说明，live exposure 更贴近前一交易日 target exposure，这是当前 T+1 持仓生效逻辑下的合理结果。

问题在更上游：`relative_lag_in_strong_benchmark_context` 是回测后生成的市场环境诊断标签；策略真正用于调仓的是日频 `strong_index_context` 和相关上下文判断。两者不是同一个东西。fold4 虽然被诊断为“强基准环境下跑输”，但策略日频目标仓位 241 天全部处于低仓；fold5 也只有 60 天进入高仓，另外 182 天仍在中低仓。

## 对北极星目标的影响

项目目标是找到能指导实盘并形成策略选择方法论的量化策略池。I59 的价值在于明确了当前强市场候选策略的主要短板：

- 不是简单缺少沪深300核心股；
- 不是简单把仓位上限调高就能解决；
- 关键是策略的强市场识别器没有覆盖那些事后看属于强基准、但当时策略没有进入强参与状态的日期。

## 下一步建议

下一轮 I60 不应继续只改 `strong_target_exposure`。更有价值的动作是：

1. 把日频 `strong_index_context`、`mixed_context`、`risk_context` 等触发状态写入 holdings exposure 或单独状态审计表。
2. 设计一个 benchmark-aware 的强市场触发器，只使用 as-of 可见数据，不直接使用事后 `market_context_label`。
3. 用 research-only 回测验证它是否能提高 fold4/fold5 的强市场参与天数，同时控制回撤和换手。

验收标准：

- 强市场落后窗口中，高 target 天数占比明显提高；
- live exposure 仍主要贴近前一日 target，说明执行链路稳定；
- 相对沪深300的 fold-level excess 改善；
- 不引入未来函数或事后标签泄漏。
