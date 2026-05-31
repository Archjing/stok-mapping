# Quality Growth Price V1（质量成长价格）

## 核心概念

`quality_growth_price_v1` 是当前候选里最接近“基本面 + 趋势”结合的一版。它先挑财务质量和成长性较好的公司，再要求价格趋势配合。

它不是纯价值模型，也不是纯技术模型，而是先看公司质量，再看价格时机。

## 实际做法

代码中的真实行为如下：

- 先生成 `quality_growth_score`
- 这个分数来自多个财务字段的横截面评分组合：
  - `roe`
  - `cash_flow_quality`
  - `profit_growth`
  - `revenue_growth`
  - `low_debt`
- 只有财务字段可用数量达到门槛的股票才参与
- 入选条件：
  - `quality_growth_score >= quality_threshold`
  - `close > ma(trend_window)`
  - `vol20 <= vol_threshold`
- 满足条件后，直接按 `quality_growth_score` 排名
- 组合仍然使用等权 + 波动率缩仓
- 可叠加跨市场 `risk_scale`

## 名称解释

- `Quality`：公司质量
- `Growth`：成长性
- `Price`：价格趋势确认

三者缺一不可。它不是单纯“好公司长期持有”，而是“财务质量过关的股票，在趋势也支持时才买”。

## 关键特点

- 比纯技术策略更强调公司质量
- 比纯基本面策略更强调入场时机
- 对财务数据可见性要求更高

这类策略的难点不在思路，而在时间线：财务数据必须严格遵守公告日可见性。

## 当前结果

当前还没有跑赢主候选：

- `annualized_return_mean = -0.0308`
- `sharpe_mean = -0.7194`
- `turnover_annual_mean = 24.55`

所以它现在更像一个值得保留的方向，而不是已经可以晋级的主策略。
