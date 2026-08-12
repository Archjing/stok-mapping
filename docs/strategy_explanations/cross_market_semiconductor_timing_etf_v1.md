# cross_market_semiconductor_timing_etf_v1

## 定位

这是一个“已完成的美股市场信号 → 下一个 A 股交易日单只半导体 ETF”的映射策略，不是股票池选股策略。默认模拟账户使用 `SH.512480`，但账户可在受控 ETF 白名单内配置其他目标；每个目标都需要独立的数据和准入验证。

## 当前规则

- 信号输入：`^SOX` 与 `^VIX` 的已完成美股交易日数据。
- 当前阈值：SOX 单日上涨超过 0.5%、VIX 小于 19；SOX 上涨超过 1% 为强信号。
- 强信号：目标 A 股交易日按开盘价入场。
- 弱信号：提交当日限价单；若当天未触及，撤单且不追价买入。
- 退出：下一 A 股交易日根据已完成的 5 分钟 bar 追踪止损；未触发则按配置的 14:55 bar 收盘价退出，不留隔夜。

策略参数、限价折扣、仓位和标的均以 `config.yaml` 为准；本文不固化回测业绩，避免历史样本或参数改变后造成误读。

## 数据与执行边界

- 日信号读自 `data/us_market_history.sqlite` 的 `core_signal`；新闻、半导体广度、利率和中国科技情绪当前只做解释层。
- ETF 日线、复权、5 分钟线和开盘快照读自 `data/etf_history.sqlite`。
- 订单、成交、资产和状态写入模拟账户 SQLite；空仓时账户应显示全额现金、证券市值 0、仓位 0%。
- `intraday-account --recover-missing` 是盘后核验和恢复，不是实时自动交易服务。

完整架构和验证门槛见 [架构说明](../PROJECT_ARCHITECTURE_OVERVIEW.md) 与 [策略研发规范](../STRATEGY_DEVELOPMENT_GUIDELINES.md)。
