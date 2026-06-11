# low_vol_low_turnover_quality_v1｜低波低换手质量

## 核心命题

`low_vol_low_turnover_quality_v1` 用低波做防御核心、低换手控制交易噪音、质量因子避免买到基本面弱的低波股票。

## 策略机制

- 使用 point-in-time 的 `quality_growth_score`。
- 生成 `vol20 / vol60`、`turnover_rate20`、`mom20 / mom60`。
- 排名权重：低波 0.40、低换手 0.25、质量 0.25、中期动量 0.10。
- 买入前必须同时满足质量、低波和低换手阈值。
- 每 20/40 个交易日调仓，新持仓至少持有 20 个交易日。
- 单票目标权重上限 10%。

## 风险与结论

该策略仍处于候选阶段，必须经过真实数据 walk-forward、成本后 gate、overfit 诊断和准入报告。

## Source

- `docs/strategy_explanations/low_vol_low_turnover_quality_v1.md`
