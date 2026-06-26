# Strategy Governance Report - I68 Negative Recovery Classifier Audit

日期：2026-06-26

报告性质：Harness 策略研发专项审计报告。本报告只做事后归因，不新增策略，不改变 admission。报告中 forward 5/20 日收益只作为标签使用，不能作为交易输入。

## 背景

I67 增加了 recovery breadth 过滤，但策略仍未通过 admission。虽然 fold4 有改善，但 fold2 基本没有改善。I68 的目标是解释：当前过滤为什么没有识别出 fold2 的假 recovery。

## 输入

- I67 daily exposure：`reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_67__recovery_tradable/holdings_exposure/strategy_daily_exposure.csv`
- I66 active industry daily summary：`reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_66__recovery_active_industry_audit/recovery_active_industry_daily_summary.csv`

## 方法

1. 取 `recovery_index_context=True` 的日期；
2. 标记其中 I67 认为 `recovery_quality_index_context=True` 的日期，即 tradable recovery；
3. 计算未来 5/20 日沪深300收益作为事后标签；
4. 比较 fold2、fold4、fold5 的 false recovery 和 true recovery。

## 核心结果

|   fold |   recovery_days |   tradable_days |   tradable_ratio_of_recovery |   avg_forward_20d_return |   positive_forward_20d_ratio |   avg_drawdown |   avg_vol_ratio |
|-------:|----------------:|----------------:|-----------------------------:|-------------------------:|-----------------------------:|---------------:|----------------:|
|      2 |              56 |              28 |                       0.5    |                  -0.0266 |                       0.125  |        -0.2795 |          0.7093 |
|      4 |              49 |               8 |                       0.1633 |                  -0.0127 |                       0.3265 |        -0.3635 |          0.9194 |
|      5 |              46 |              36 |                       0.7826 |                   0.0499 |                       0.9783 |        -0.1773 |          0.593  |

## fold2 细看

| recovery_outcome_20d   |   days |   tradable_days |   tradable_ratio |   avg_forward_20d_return |   avg_ret20 |   avg_ret60 |   avg_drawdown |   avg_vol_ratio |
|:-----------------------|-------:|----------------:|-----------------:|-------------------------:|------------:|------------:|---------------:|----------------:|
| negative_forward_20d   |     49 |              26 |           0.5306 |                  -0.0346 |      0.0387 |      0.0808 |        -0.2759 |          0.7191 |
| positive_forward_20d   |      7 |               2 |           0.2857 |                   0.0214 |      0.0235 |      0.0691 |        -0.3046 |          0.641  |

## 行业领导模式

|   fold | top_overweight_industry   |   days |   tradable_days |   avg_forward_20d_return |   avg_benchmark_return_sum |
|-------:|:--------------------------|-------:|----------------:|-------------------------:|---------------------------:|
|      2 | 白酒                        |     56 |              28 |              -0.0265661  |                -0.0415494  |
|      3 | 白酒                        |     21 |               6 |              -0.024943   |                 0.00493684 |
|      4 | 白酒                        |     35 |               6 |              -0.00553111 |                -0.0119082  |
|      4 | 银行                        |     13 |               2 |              -0.0343308  |                -0.0265923  |
|      5 | 银行                        |     46 |              36 |               0.0499201  |                 0.143221   |

## 判断

I68 的关键结论是：当前 I67 宽度过滤在 fold2 上没有识别出假 recovery，甚至更偏向保留未来20日为负的 recovery 日期。

- fold2：未来20日为负的 recovery 日期 49 天，I67 保留 26 天；未来20日为正的 recovery 日期 7 天，I67 只保留 2 天。
- fold4：I67 大幅过滤 recovery 日期，策略年化改善，这说明过滤方向不是完全无效。
- fold5：I67 保留大多数 recovery 日期，说明它没有破坏真正有效的恢复窗口。

因此，当前结论不是“宽度过滤错了”，而是“静态宽度水平不够”。下一步要看宽度变化、行业领导持续性和成交额持续扩散。

## 下一步

I69 建议做 negative recovery feature audit，至少计算：

- recovery 日前 5/10/20 日的市场宽度变化；
- 主导超配行业是否持续，还是频繁切换；
- 银行/白酒/科技等主线在 recovery 期间的相对收益是否连续；
- 成交额扩散是否连续，而不是单日达到阈值；
- deep drawdown 后第一次修复和二次修复是否表现不同。

只有找到能区分 fold2 与 fold5 的事前可见特征，才值得把 I67 变成下一版策略。
