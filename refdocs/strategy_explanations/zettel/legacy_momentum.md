# legacy_momentum｜经典短动量 baseline

## 核心命题

`legacy_momentum` 是最基础的横截面动量策略：每天在同一股票池里比较最近 5 日动量，从强者中继续挑强者。

## 策略机制

- 核心信号：`mom5`。
- 用训练期分位数得到 `mom_threshold`。
- 只买 `mom5 > mom_threshold` 且排名靠前的股票。
- 等权后按 `vol20` 缩仓。
- 收盘生成信号，下一交易日生效。
- 每次调仓扣滑点、佣金和印花税。

## 风险与结论

该策略逻辑直观，但没有持有缓冲、最小持有期或低换手约束，因此容易被交易成本侵蚀。当前定位是旧 baseline，不再是主候选。

## Source

- `docs/strategy_explanations/legacy_momentum.md`
