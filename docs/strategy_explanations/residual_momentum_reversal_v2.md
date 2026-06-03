# Residual Momentum Reversal V2（残差动量反转V2）

## 核心概念

`residual_momentum_reversal_v2` 是 V1 的加强过滤版。策略方向没有变，还是“强中选不那么热的强者”，但入场前加了更多量价质量检查。

## 实际做法

代码中的真实行为如下：

- 保留残差动量条件：
  - `resid_mom > residual_threshold`
- 保留短反转条件：
  - `mom(reversal_window) <= reversal_threshold`
- 保留趋势和低波动条件：
  - `close > ma(trend_window)`
  - `vol20 <= vol_threshold`
- 新增量价过滤：
  - `amount_ratio20 >= amount_ratio_min`
  - `upper_shadow_pct <= upper_shadow_max`
  - `gap_ret <= gap_ret_max`
- 排名改为：
  - `0.75 * residual rank + 0.25 * reversal rank`
- 默认不叠加跨市场 overlay

## 名称解释

这里的 `v2` 在项目里的真实含义是：比 V1 多了一层“成交质量和形态质量”的限制，不是泛指更先进的模型。

## 关键特点

- 过滤更严
- 参数更多
- 候选更少
- 交易质量要求更高

理论上它应该更稳，但现实里也更容易把可交易信号压缩得过碎。

## 当前结果

当前结果反而比 V1 更差：

- `annualized_return_mean = -0.1896`
- `sharpe_mean = -1.4056`
- `turnover_annual_mean = 59.08`

这说明“增加过滤项”本身不会自动带来更好的策略，尤其当它把交易频率和噪音一起推高时。
