# Low Vol Low Turnover Quality V1（低波低换手质量）

## 核心概念

`low_vol_low_turnover_quality_v1` 是 T2.6 的首版低波、低换手、质量三因子候选。它用低波作为防御核心，用低换手控制交易噪音和成本，用质量因子避免只买到低波但基本面较弱的股票。

## 实际做法

代码中的真实行为如下：

- 生成 point-in-time 的 `quality_growth_score`
- 生成 `vol20 / vol60` 低波窗口
- 生成 `turnover_rate20` 低换手代理
- 生成 `mom20 / mom60` 中期动量轻量确认
- 综合排序分数为：

```text
score =
  0.40 * low_vol_rank
+ 0.25 * low_turnover_rank
+ 0.25 * quality_rank
+ 0.10 * medium_momentum_rank
```

- 买入前必须同时满足质量、低波和低换手阈值
- 每 `20 / 40` 个交易日才允许调仓
- 新持仓至少持有 `20` 个交易日
- 老持仓允许留在更宽的 `hold_top_n` 区间内
- 单票目标权重上限为 `10%`
- 收盘后形成目标权重，下一交易日生效，避免未来函数

## 当前定位

它目前只进入 compare，不进入盘前观察池或模拟账户。

正式晋级前仍需要完整真实数据 walk-forward、成本后 gate、overfit 诊断和 T2.8 策略准入报告。
