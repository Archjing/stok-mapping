# Quality Low Turnover Monthly V1（质量低换手月频）

## 核心概念

`quality_low_turnover_monthly_v1` 是 `quality_growth_price_v1` 的低频改造版。它不再用短线趋势过滤做入场确认，而是把公司质量作为核心排序信号，再用低波和低换手约束降低噪音与交易成本。

它要回答的问题是：如果财务质量是慢变量，能不能用更低频、更宽容的持仓机制，把质量因子从日频交易噪音中分离出来。

## 实际做法

代码中的真实行为如下：

- 先生成 point-in-time 的 `quality_growth_score`
- `quality_growth_score` 来自五类质量子因子：
  - `ROE`
  - 现金流质量
  - 利润增长
  - 营收增长
  - 低负债
- 同时保留质量子因子贡献字段，便于后续报告解释候选为什么入选
- 只把满足以下条件的股票放入候选池：
  - `quality_growth_score >= quality_threshold`
  - `vol20 / vol60 <= vol_threshold`
  - `turnover_rate20 <= turnover_threshold`
- 候选池内只按 `quality_growth_score` 排序
- 每 `20 / 40` 个交易日才允许调仓
- 新持仓至少持有 `20` 个交易日
- 老持仓允许留在更宽的 `hold_top_n` 区间内，避免轻微掉队就卖出
- 单票目标权重上限为 `10%`
- 收盘后形成目标权重，下一交易日才生效，避免未来函数

## 与 `quality_growth_price_v1` 的区别

`quality_growth_price_v1` 是“质量 + 价格趋势”的日频候选：它要求 `close > ma(trend_window)`，并且每天重新排序选股。

`quality_low_turnover_monthly_v1` 则刻意去掉短线趋势过滤：

- 排序核心只看质量
- 低波和低换手是约束，不是主 ranker
- 调仓频率降到月频或更低
- 更重视换手、持有期和解释性

## 当前定位

它目前只是策略重建阶段的候选，不进入盘前观察池或模拟账户。

进入下一阶段前，必须经过：

- qfq_asof walk-forward
- 成本后 gate
- 因子有效性诊断
- 过拟合诊断
- T2.8 策略准入报告
- 窗口稳健性矩阵
