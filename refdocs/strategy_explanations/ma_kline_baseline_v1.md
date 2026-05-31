# MA K-line Baseline V1（均线K线基线）

## 核心概念

`ma_kline_baseline_v1` 是一个低复杂度技术分析基线。它不靠财务因子，也不靠机器学习，而是用趋势、K 线形态和量能确认来挑股票。

它的作用主要是提供一个简单、透明的对照组。

## 实际做法

代码中的真实行为如下：

- 趋势条件：
  - `close > ma(trend_window)`
  - `ma(trend_window) > ma(confirm_window)`
- K 线条件：
  - `body_pct > 0`
  - `upper_shadow_pct <= upper_shadow_max`
- 量能条件：
  - `amount_ratio20 >= amount_ratio_min`
- 风险条件：
  - `vol20 <= vol_threshold`
- 满足条件后，再按
  - `0.7 * mom20 + 0.3 * breakout20`
  排名
- 组合只买前 `top_n`
- 入选后按等权加波动率缩仓持有
- 收盘后出信号，下一交易日生效

## 名称解释

这里的 `baseline` 表示它是一个低复杂度技术模板，不是主策略目标。它更适合回答“简单规则是否已经够用”。

## 关键特点

- 结构简单
- 可解释性强
- 对价格行为依赖重
- 对震荡市比较脆弱

它更像“诊断地板”，不是“最终答案”。

## 当前结果

当前结果很弱：

- `annualized_return_mean = -0.2410`
- `sharpe_mean = -1.7831`
- `max_drawdown_mean = -0.3162`

结论是：在当前股票池、成本和回测口径下，单靠这类简单均线/K线规则，撑不起主策略。
