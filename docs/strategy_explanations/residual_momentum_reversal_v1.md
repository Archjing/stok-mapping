# Residual Momentum Reversal V1（残差动量反转V1）

## 核心概念

`residual_momentum_reversal_v1` 不是直接追涨，而是想找“相对市场更强，但短期没有热过头”的股票。

它把残差动量和短期反转放在一起，本质是在强势股里再做一次质量筛选。

## 实际做法

代码中的真实行为如下：

- 先生成本地残差特征 `resid_mom`
- 只有 `resid_mom > residual_threshold` 的股票才有资格入选
- 同时要求短反转窗口动量 `mom3` 不高于 `reversal_threshold`
- 还要求：
  - `close > ma(trend_window)`
  - `vol20 <= vol_threshold`
- 排名时不是只看残差动量，而是：
  - `residual rank + 0.5 * reversal rank`
- 组合选前 `top_n`
- 按等权和波动率控制仓位
- 可选择叠加跨市场 `risk_scale`

## 名称解释

- `Residual` 指相对市场平均后的剩余强度，不是原始涨幅
- `Reversal` 在这里不是做反转交易，而是防止买进短期过热的强势股

## 关键特点

- 比纯动量更强调“别追得太急”
- 试图降低动量策略在 A 股震荡环境下的失真
- 方向是合理的，但交易频率仍然不低

## 当前结果

当前结果没有跑出来：

- `annualized_return_mean = -0.0878`
- `sharpe_mean = -0.7766`
- `turnover_annual_mean = 30.17`

更准确地说，它现在的问题不是完全没有逻辑，而是当前持仓节奏和成本水平下，优势没能留下来。
