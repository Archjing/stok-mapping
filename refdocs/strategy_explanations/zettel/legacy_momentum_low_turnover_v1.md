# legacy_momentum_low_turnover_v1｜低换手经典动量

## 核心命题

`legacy_momentum_low_turnover_v1` 的核心不是替换动量信号，而是把高频追涨改造成更克制、更接近真实执行的低换手版本。

## 策略机制

- 动量窗口在 `mom5` 和 `mom20` 中选择。
- 买入阈值 `buy_threshold` 高于持有阈值 `hold_threshold`。
- 新买只看 `buy_top_n`，已持有股票可留在更宽的 `hold_top_n`。
- 按 `rebalance_days` 周期调仓，并要求 `min_hold_days`。
- 训练阶段惩罚高换手 `turnover_penalty`。
- 等权后叠加 `vol20` 缩仓。

## 风险与结论

它胜出的主要原因是保留动量收益同时减少换手，降低交易摩擦。它说明执行约束本身可以显著改变策略结果。

## Source

- `docs/strategy_explanations/legacy_momentum_low_turnover_v1.md`
