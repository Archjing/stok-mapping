# Session Incremental Archive - 2026-06-26 05:50

范围：I70 Harness 策略研发迭代。

## 新增标准

- recovery 主线持续性不能使用未来窗口标签；必须用 T-1 可见历史代理特征。
- scoped research 策略在 holdings exposure 诊断中应与 admission 一样支持强制启用，否则诊断路径会误报策略未启用。

## 代码变更

- `phase0/strategies/strong_market_stable_core_base.py`：新增 `strong_benchmark_recovery_leadership_v1`，新增 recovery leadership 历史代理特征。
- `phase0/strategy_admission.py`：新增 I70 策略 force-enable 映射。
- `phase0/strategy_holdings_exposure.py`：scoped 策略强制启用；增加 leadership 诊断列。
- `phase0/strategies/__init__.py`、相关测试同步更新。

## 验证结果

- targeted pytest：36 passed, 1 warning。
- I70 scoped admission 完成，结果 reject。

## 策略结论

I70 能改善 fold2 假 recovery，但削弱 fold5 真 recovery。方向有价值，但硬阈值过滤太粗。下一轮应做连续 recovery score / 分档仓位。
