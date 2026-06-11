# quality_low_turnover_monthly_v1｜质量低换手月频

## 核心命题

`quality_low_turnover_monthly_v1` 把财务质量视为慢变量，去掉短线趋势过滤，用低频调仓和持仓宽容机制降低噪音与交易成本。

## 策略机制

- 使用 point-in-time 的 `quality_growth_score`。
- 质量子因子包括 ROE、现金流质量、利润增长、营收增长和低负债。
- 候选需满足质量、低波和低换手阈值。
- 候选池内只按质量分排序。
- 每 20/40 个交易日调仓，新持仓至少持有 20 个交易日。
- 老持仓可留在更宽的 `hold_top_n`，单票目标权重上限 10%。

## 风险与结论

它是质量策略低频化的重要候选。晋级前必须通过 `qfq_asof` walk-forward、成本后 gate、因子有效性、过拟合诊断和窗口稳健性矩阵。

## Source

- `docs/strategy_explanations/quality_low_turnover_monthly_v1.md`
