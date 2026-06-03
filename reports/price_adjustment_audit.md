# A 股历史 as-of 前复权审计报告

Generated at: 2026-06-03T23:37:57

- Database: `/home/zj/workspace/stok-mapping/data/manual_history/a_share_history.sqlite`
- Can build `qfq_asof`: `False`

## 结论

- 当前本地库尚不能构造严格 `qfq_asof`。在审计通过前，`qfq_current` 结果不能解释为严格 point-in-time 价格结果。

## Warnings

- cannot_build_qfq_asof: bfq raw bars or market_adj_factors are missing
- current backtest price adjustment is not strict point-in-time until qfq_asof audit passes

## Checks

| check | status | detail |
| --- | --- | --- |
| daily_table_exists | PASS | market_daily_bars |
| adj_factor_table_exists | FAIL | market_adj_factors |
| daily_table_columns | PASS | market,symbol,date,adjust_type,open,high,low,close,volume,amount,adjusted_close,change_pct,change_amount,amplitude,turnover_rate |
| daily_adjust_type_bfq | PASS | rows=10462385, symbols=5748, range=2016-05-03..2026-05-28 |
| daily_adjust_type_qfq | PASS | rows=10484516, symbols=5761, range=2016-05-03..2026-06-03 |
| has_bfq_raw | PASS | True |
| has_qfq_current | PASS | True |
| can_build_qfq_asof | FAIL | cannot_build_qfq_asof |
| phase0_current_adjust_type | INFO | qfq |
| phase0_backtest_price_adjustment | INFO | qfq_current |
