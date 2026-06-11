# core_selection_quality_momentum_v1｜核心选股质量动量

## 核心命题

`core_selection_quality_momentum_v1` 面向核心选股策略，不追求行业押注，而是在控制风格噪音后寻找质量较好、相对强势、波动不过高的股票。

## 策略机制

- 核心特征：`quality_growth_score` 和 `resid_mom`。
- 候选需满足质量、残差动量、趋势和低波条件。
- 排名权重：质量成长 0.55、残差动量 0.25、低波动 0.20。
- 取前 `top_n`，等权基础上叠加 `vol20` 缩仓。
- 默认不依赖跨市场 overlay。

## 风险与结论

它的价值在于作为核心选股型对照实验，帮助判断主策略是否只是靠行业轮动赚钱。当前是方法论候选，未进入正式 compare 主线。

## Source

- `docs/strategy_explanations/core_selection_quality_momentum_v1.md`
