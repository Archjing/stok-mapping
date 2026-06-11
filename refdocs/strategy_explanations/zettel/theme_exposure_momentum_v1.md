# theme_exposure_momentum_v1｜主题暴露动量

## 核心命题

`theme_exposure_momentum_v1` 允许收益来自强势主题、强势行业和跨市场风险偏好的同向共振，不刻意回避集中暴露。

## 策略机制

- 主要信号来自价格趋势和中短期动量。
- 同时要求低波、量能，部分配置下要求突破。
- 开启跨市场 overlay 时要求 `mapped_xmarket_score` 达标。
- 排名权重：动量 0.75、跨市场映射 0.25。
- 组合仍用等权 + 波动率缩仓。

## 风险与结论

它不能和核心选股策略用同一把尺子解释。若明显跑赢，收益可能来自主题暴露；若核心选股更稳，则主线更适合约束行业集中。

## Source

- `docs/strategy_explanations/theme_exposure_momentum_v1.md`
