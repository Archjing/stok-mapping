# Multifactor Volume Price Filter V1（多因子量价过滤）

## 核心概念

`multifactor_volume_price_filter_v1` 是当前结构最完整的多因子候选。它想同时兼顾公司质量、价格相对强度、低波动和量价形态过滤。

它不是单一因子策略，而是一套“先多层过滤，再综合排序”的组合模型。

## 实际做法

代码中的真实行为如下：

- 先生成两类基础特征：
  - `quality_growth_score`
  - `resid_mom`
- 入选条件同时要求：
  - `quality_growth_score >= quality_threshold`
  - `resid_mom > residual_threshold`
  - `close > ma(trend_window)`
  - `ma(trend_window) > ma(confirm_window)`
  - `vol20 <= vol_threshold`
  - `amount_ratio20 >= amount_ratio_min`
  - `upper_shadow_pct <= upper_shadow_max`
  - 某些参数下还要求 `breakout20`
- 排名分数由三部分组成：
  - `quality_growth_weight = 0.45`
  - `residual_momentum_weight = 0.35`
  - `low_volatility_weight = 0.20`
- 再取前 `top_n`
- 组合权重仍然是等权基础上叠加波动率控制

## 名称解释

这里的 `filter` 很关键。它不只是“多因子加权打分”，而是先做多层资格过滤，再在过滤后的股票里排序。

换句话说，它既是 ranker，也是多层门槛筛选器。

## 关键特点

- 因子结构完整
- 过滤条件丰富
- 参数维度较高
- 对交易成本和噪音很敏感

它代表的是一种很常见的策略开发路径：把多个看起来合理的优点叠加在一起。但叠加越多，不代表结果越好。

## 当前结果

当前结果并不支持它进入主线：

- `annualized_return_mean = -0.0766`
- `sharpe_mean = -0.5597`
- `turnover_annual_mean = 48.38`

问题不在于结构不完整，而在于当前这套组合在真实成本下太贵，收益没能覆盖摩擦。
