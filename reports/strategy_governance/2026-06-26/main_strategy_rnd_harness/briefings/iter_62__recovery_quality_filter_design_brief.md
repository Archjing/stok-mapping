# I62 Recovery Quality Filter Design Brief

日期：2026-06-26

本轮先做低成本设计评估，不直接新增策略。

## 从 I61 学到什么

I61 的 recovery trigger 能提高仓位，但它没有稳定带来收益。

按 recovery 日期上的沪深300日收益看：

| fold | recovery 天数 | recovery 期间沪深300累计日收益 | recovery 日均收益 |
| --- | ---: | ---: | ---: |
| 2 | 56 | -0.041549 | -0.000742 |
| 3 | 22 | 0.014722 | 0.000669 |
| 4 | 49 | -0.022057 | -0.000450 |
| 5 | 46 | 0.143221 | 0.003113 |

fold5 的 recovery 信号很有用；fold2 和 fold4 的 recovery 信号反而容易误伤。说明当前触发器能找到“修复形态”，但不能区分“有效修复”和“弱反弹”。

## I62 推荐方向

不要继续简单调 `recovery_target_exposure`。

更值得验证的是 recovery quality filter：

- 保留 recovery 的基本定义；
- 新增“修复质量”条件；
- 只在修复质量较高时给 0.65；
- 修复质量不足时只给 0.40，或者维持 mixed。

可选质量条件：

1. `ret20 > 0`，去掉 I61 中允许 `ret20 >= -0.02` 的宽松口径。
2. `ret60 >= 0.05`，提高中期修复门槛。
3. `drawdown` 比 20 日前改善，即回撤正在收敛。
4. 连续 N 天在 MA120 上方，避免刚突破后又跌回。
5. recovery 日的波动不能超过阈值，避免高波动反抽。

## 最小实现建议

I62 可以做一个 research-only 变体，而不是改 I61：

- `strong_benchmark_recovery_quality_v1`
- 复用 I61 组合构造；
- 新增参数：
  - `recovery_quality_ret20_min: 0.0`
  - `recovery_quality_ret60_min: 0.05`
  - `recovery_quality_target_exposure: 0.65`
  - `recovery_weak_target_exposure: 0.40`

验收标准：

- fold5 保留大部分改善；
- fold2/fold4 的恶化减少；
- positive_excess_fold_ratio 至少不低于 I61；
- turnover 不高于 I61；
- 仍保持 research-only。
