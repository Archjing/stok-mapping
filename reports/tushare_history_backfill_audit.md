# Tushare 历史数据补全验收报告

## 覆盖率汇总

| table | field | start_date | end_date | rows | non_null_ratio |
| --- | --- | --- | --- | --- | --- |
| market_daily_bars | bfq.ohlcv | 2016-05-03 | 2026-05-28 | 10462385 | 1.0000 |
| market_daily_bars | qfq.ohlcv | 2016-05-03 | 2026-06-03 | 10484516 | 1.0000 |
| market_daily_basic | pe_ratio | 2016-01-04 | 2026-06-03 | 10672387 | 0.8147 |
| market_daily_basic | pb_ratio | 2016-01-04 | 2026-06-03 | 10672387 | 0.9937 |
| market_daily_basic | turnover_rate | 2016-01-04 | 2026-06-03 | 10672387 | 1.0000 |
| market_adj_factors | adj_factor | 2016-01-04 | 2026-06-04 | 11175324 | 1.0000 |
| market_financial_factors | roe | 2018-06-30 | 2026-03-31 | 167340 | 0.9739 |
| market_financial_factors | revenue_growth | 2018-06-30 | 2026-03-31 | 167340 | 0.9612 |
| market_financial_factors | profit_growth | 2018-06-30 | 2026-03-31 | 167340 | 0.9619 |
| market_financial_factors | operating_cash_flow_to_net_profit | 2018-06-30 | 2026-03-31 | 167340 | 0.9338 |
| market_financial_factors | debt_to_asset | 2018-06-30 | 2026-03-31 | 167340 | 0.9115 |
| market_dividends | dividend_events | 2016-04-16 | 2016-04-16 | 1 | 1.0000 |

## Warnings

- 2026-06-04: daily_basic returned empty
