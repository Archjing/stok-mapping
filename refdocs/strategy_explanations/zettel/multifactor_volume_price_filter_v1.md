# multifactor_volume_price_filter_v1｜多因子量价过滤器

## 核心命题

`multifactor_volume_price_filter_v1` 是多层资格过滤加综合排序的组合模型，试图同时兼顾公司质量、残差动量、低波动和量价形态。

## 策略机制

- 基础特征：`quality_growth_score` 和 `resid_mom`。
- 入选要求质量、残差动量、趋势、低波、量能、上影线等多项条件。
- 排名权重：质量成长 0.45、残差动量 0.35、低波动 0.20。
- 取前 `top_n`，再用等权和波动率控制仓位。

## 风险与结论

它代表常见的“把合理优点叠加”路径，但过滤条件越多不代表结果越好。当前成本后换手过高，收益覆盖不了摩擦。

## Source

- `docs/strategy_explanations/multifactor_volume_price_filter_v1.md`
