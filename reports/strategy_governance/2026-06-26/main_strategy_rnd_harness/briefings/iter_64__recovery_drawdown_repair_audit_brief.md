# I64 Recovery Drawdown Repair Audit Brief

日期：2026-06-26

本轮目标：审计“回撤正在收敛”能否区分 I63 中有效 recovery 和错误 recovery。

## 审计口径

使用 I63 的 `strategy_daily_exposure.csv`，计算：

- `drawdown_delta_20d = strong_index_drawdown - strong_index_drawdown.shift(20)`
- 大于 0 表示相对 20 个交易日前回撤收敛；
- 分桶为 `strong_repair`、`mild_repair`、`flat_or_unknown`、`worsening`。

## 结果

| fold | recovery 天数 | repair 天数 | repair 期间沪深300收益 | non-repair 期间沪深300收益 |
| --- | ---: | ---: | ---: | ---: |
| 2 | 56 | 43 | -0.039348 | -0.002201 |
| 3 | 22 | 16 | 0.002560 | 0.012162 |
| 4 | 49 | 26 | -0.003872 | -0.018184 |
| 5 | 46 | 46 | 0.143221 | 0.000000 |

## 结论

单独使用“20日回撤收敛”不能直接作为 I64 新策略过滤器。

它能解释 fold5：fold5 的 recovery 全部处于 repair 状态，且收益好。

但它不能过滤 fold2：fold2 也有大量 repair 日，而且这些 repair 日整体收益为负。

## 下一步建议

不要马上把 `drawdown_delta_20d > 0` 加进策略。

下一步更合理的是检查 recovery 期间的持仓结构：

- 是否在 fold2/fold4 押中了错误行业；
- 是否行业/风格暴露导致 recovery 信号正确但组合选股错误；
- 是否需要在 recovery 状态下更贴近沪深300权重，而不是继续 alpha tilt。
