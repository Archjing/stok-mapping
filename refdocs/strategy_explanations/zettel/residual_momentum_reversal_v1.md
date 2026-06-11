# residual_momentum_reversal_v1｜残差动量反转 V1

## 核心命题

`residual_momentum_reversal_v1` 不是直接追涨，而是在相对市场更强的股票中避开短期过热标的。

## 策略机制

- 先生成本地残差特征 `resid_mom`。
- 只允许 `resid_mom > residual_threshold` 的股票入选。
- 同时要求 `mom3 <= reversal_threshold`，避免短期过热。
- 还要求趋势和低波条件。
- 排名为残差排名加 0.5 倍反转排名。

## 风险与结论

方向上试图降低 A 股震荡环境中纯动量失真，但当前持仓节奏和成本水平下优势没能保留下来。

## Source

- `docs/strategy_explanations/residual_momentum_reversal_v1.md`
