# residual_momentum_reversal_v2｜残差动量反转 V2

## 核心命题

`residual_momentum_reversal_v2` 是 V1 的加强过滤版，仍然寻找“强中不太热”的股票，但额外加入成交质量和形态质量检查。

## 策略机制

- 保留残差动量、短反转、趋势和低波条件。
- 新增 `amount_ratio20`、`upper_shadow_pct`、`gap_ret` 等量价过滤。
- 排名改为 0.75 倍残差排名加 0.25 倍反转排名。
- 默认不叠加跨市场 overlay。

## 风险与结论

过滤更严、参数更多、候选更少，理论上更稳，但现实中可能把信号压得过碎。当前结果比 V1 更差，说明增加过滤项不会自动改善策略。

## Source

- `docs/strategy_explanations/residual_momentum_reversal_v2.md`
