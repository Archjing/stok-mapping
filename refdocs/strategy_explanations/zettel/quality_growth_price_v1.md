# quality_growth_price_v1｜质量成长价格

## 核心命题

`quality_growth_price_v1` 先挑财务质量和成长性较好的公司，再要求价格趋势配合，是“基本面 + 趋势”的候选。

## 策略机制

- `quality_growth_score` 来自 ROE、现金流质量、利润增长、营收增长、低负债。
- 只有财务字段可用数量达标的股票才参与。
- 入选条件：质量分达标、`close > ma(trend_window)`、`vol20 <= vol_threshold`。
- 满足条件后按质量分排名。
- 等权 + 波动率缩仓，可叠加跨市场 `risk_scale`。

## 风险与结论

难点在财务数据时间线。所有财务字段必须遵守公告日可见性，否则会产生未来函数。当前更像保留方向，不是主策略。

## Source

- `docs/strategy_explanations/quality_growth_price_v1.md`
