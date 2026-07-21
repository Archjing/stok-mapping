# Session Incremental Archive - 2026-06-26 05:25

范围：I69 Harness 策略研发迭代，主题为 dynamic recovery feature audit。

## 代码改动

- `phase0/strategies/strong_market_stable_core_base.py`：signal_frame 增加 mom20/mom60/amount_ratio20/vol20 诊断字段。
- `phase0/strategy_holdings_exposure.py`：holdings 导出白名单增加上述字段和 recovery breadth/tradable 字段。

## 验证

- 33 passed, 1 warning。
- 重跑 I69 holdings exposure，用于动态特征审计；大文件保留本地，不提交。

## 关键发现

- fold2 静态宽度不低，但主导行业持续性为 0，后续20日表现差。
- fold5 主导行业持续性约 0.8913，后续20日表现好。
- 正向 recovery 的成交额扩散和主线持续性明显高于负向 recovery。

## 决策

下一步如果继续实现策略，应尝试“成交额扩散 + 主线持续”的 recovery filter，而不是继续调静态宽度阈值。
