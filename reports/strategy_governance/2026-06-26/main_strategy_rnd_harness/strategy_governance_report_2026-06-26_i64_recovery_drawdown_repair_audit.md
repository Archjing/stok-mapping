# Strategy Governance Report - I64 Recovery Drawdown Repair Audit

日期：2026-06-26

报告性质：Harness 策略研发专项审计报告。本报告只做证据审计，不新增策略、不改变 admission。

## 背景

I63 引入了 recovery quality filter，但 fold2/fold4 仍然弱于 I58。上一轮假设是：也许需要加入“回撤正在收敛”的条件，过滤弱反弹。

I64 对这个假设做离线审计。

## 审计方法

输入：

- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_63__recovery_quality/holdings_exposure/strategy_daily_exposure.csv`

新增指标：

- `drawdown_delta_20d = strong_index_drawdown - strong_index_drawdown.shift(20)`
- `drawdown_delta_20d > 0` 表示回撤相对 20 个交易日前收敛。

输出：

- `recovery_drawdown_repair_daily.csv`
- `recovery_drawdown_repair_summary.csv`
- `recovery_drawdown_repair_fold_summary.csv`
- `recovery_drawdown_repair_audit.md`

## 结果

| fold | recovery 天数 | repair 天数 | non-repair 天数 | repair 收益和 | non-repair 收益和 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2 | 56 | 43 | 13 | -0.039348 | -0.002201 |
| 3 | 22 | 16 | 6 | 0.002560 | 0.012162 |
| 4 | 49 | 26 | 23 | -0.003872 | -0.018184 |
| 5 | 46 | 46 | 0 | 0.143221 | 0.000000 |

分桶结果显示：

- fold5 的 `mild_repair` 表现很好；
- fold2 的 `mild_repair` 表现很差；
- fold4 的 repair 比 non-repair 好一些，但仍接近无效；
- fold3 的 non-repair 反而更好。

## 判断

“回撤收敛”是有信息量的，但不能单独作为交易过滤器。

它能说明 fold5 为什么有效，但不能排除 fold2 的错误 recovery。继续基于单一指数状态特征叠规则，容易变成过拟合。

## 下一步

下一轮应从“市场状态识别”转向“recovery 状态下的组合结构”：

1. 对比 fold2/fold4/fold5 recovery 日期的行业暴露；
2. 对比持仓相对沪深300的行业偏离；
3. 判断问题是市场信号误判，还是 recovery 状态下选股/行业偏离错误；
4. 如果是组合偏离错误，下一步策略应在 recovery 状态更贴近沪深300，而不是继续调 market trigger。
