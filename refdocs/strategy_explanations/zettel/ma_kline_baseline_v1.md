# ma_kline_baseline_v1｜均线 K 线技术 baseline

## 核心命题

`ma_kline_baseline_v1` 是低复杂度技术分析基线，用趋势、K 线形态和量能确认挑股票，主要用于提供透明对照组。

## 策略机制

- 趋势条件：`close > ma(trend_window)` 且 `ma(trend_window) > ma(confirm_window)`。
- K 线条件：阳线实体为正，上影线不超过阈值。
- 量能条件：`amount_ratio20 >= amount_ratio_min`。
- 风险条件：`vol20 <= vol_threshold`。
- 排名：`0.7 * mom20 + 0.3 * breakout20`。

## 风险与结论

当前结果较弱，说明单靠简单均线/K线规则在当前股票池、成本和回测口径下不足以支撑主策略。它更像诊断地板。

## Source

- `docs/strategy_explanations/ma_kline_baseline_v1.md`
