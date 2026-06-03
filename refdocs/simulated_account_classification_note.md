# 多模拟账户分类原则原文备忘

不建议默认“每个策略预设一个账户”。更合理的分类是：

**1. 按资金规模分类**
这是最有用的，因为成交可行性、参与率、滑点都和资金规模直接相关。

例如：

```yaml
small_cash_100k     # 10 万
personal_500k       # 50 万
large_2m            # 200 万
```

同一个 watchlist，在 10 万账户里可能好执行，在 200 万账户里可能流动性压力明显变大。

**2. 按执行约束分类**
用于比较不同交易假设。

例如：

```yaml
conservative_next_open
aggressive_next_open
close_price_research
```

区别可以是：

```text
成交价口径
最大成交参与率
滑点
佣金
是否允许追涨停/跌停
```

**3. 按风险偏好分类**
比如同一个策略，但目标仓位、最大暴露、单票上限不同。

例如：

```yaml
low_risk
balanced
high_risk
```

这更接近真实用户账户设置。

**4. 按策略分类**
这个可以有，但我建议作为“策略实验账户”，不要作为默认主结构。

例如：

```yaml
legacy_momentum_low_turnover_default
quality_growth_default
multi_strategy_blend_default
```

适合做策略对照实验，但对最终产品用户来说，“账户”首先代表资金和执行约束，不是策略本身。

我的建议是当前先保留一个默认账户：

```yaml
default:
  name: 默认模拟账户
  initial_cash: 1000000
  strategy_scope: current_selected
```

后续扩展时优先加：

```yaml
personal_500k:
  name: 个人账户 50 万
  initial_cash: 500000
  max_participation_rate: 0.03
  risk_profile: balanced
```

策略维度用另一个字段表达，而不是让账户完全等同于策略：

```yaml
strategy_scope: current_selected
# 或
strategy_scope: legacy_momentum_low_turnover_v1
# 或未来
strategy_scope: multi_strategy_blend_v1
```

这样结构更稳：账户管理资金和约束，策略管理信号来源。
