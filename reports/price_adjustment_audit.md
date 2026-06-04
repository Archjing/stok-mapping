# A 股历史 as-of 前复权审计报告

Generated at: 2026-06-04T01:06:07

- Database: `/home/zj/workspace/stok-mapping/data/manual_history/a_share_history.sqlite`
- Can build `qfq_asof`: `True`

## 结论

- 当前本地库具备未复权价格和复权因子，可继续实现或运行 `qfq_asof` 对照。

## Checks

| check | status | detail |
| --- | --- | --- |
| daily_table_exists | PASS | market_daily_bars |
| adj_factor_table_exists | PASS | market_adj_factors |
| dividend_table_exists | PASS | market_dividends |
| daily_table_columns | PASS | market,symbol,date,adjust_type,open,high,low,close,volume,amount,adjusted_close,change_pct,change_amount,amplitude,turnover_rate |
| daily_adjust_type_bfq | PASS | rows=10462385, symbols=5748, range=2016-05-03..2026-05-28 |
| daily_adjust_type_qfq | PASS | rows=10484516, symbols=5761, range=2016-05-03..2026-06-03 |
| has_bfq_raw | PASS | True |
| has_qfq_current | PASS | True |
| adj_factor_columns | PASS | market,symbol,date,adj_factor,source,updated_at |
| adj_factor_rows | PASS | rows=10917982, symbols=5768, range=2016-05-03..2026-05-28 |
| adj_factor_history_coverage | PASS | bfq_range=2016-05-03..2026-05-28, factor_range=2016-05-03..2026-05-28 |
| dividend_rows | WARN | 0 |
| can_build_qfq_asof | PASS | ok |
| phase0_current_adjust_type | INFO | qfq |
| phase0_backtest_price_adjustment | INFO | qfq_current |
| qfq_asof_comparison_sample | PASS | as_of=2024-05-28, symbols=12, ok=8 |
| qfq_asof_comparison_max_close_diff_ratio | INFO | 0.72133501 |
| qfq_asof_comparison_max_mom20_diff | INFO | 0.20021575 |

## qfq_current / qfq_asof 差异样例

| symbol    | status                  |   rows | max_close_diff_date   |   max_abs_close_diff |   max_abs_close_diff_ratio |   max_abs_mom20_diff |   max_abs_ma20_diff |   max_abs_vol20_diff |   max_abs_breakout20_diff |
|:----------|:------------------------|-------:|:----------------------|---------------------:|---------------------------:|---------------------:|--------------------:|---------------------:|--------------------------:|
| SZ.001298 | ok                      |    242 | 2023-10-18            |          28.9        |                 0.681333   |           0.0206778  |           22.9155   |            0.0251047 |                         0 |
| SZ.002594 | ok                      |    242 | 2023-07-31            |         183.69       |                 0.680778   |           0.00977815 |          179.135    |            0.0158088 |                         0 |
| SH.605117 | ok                      |    242 | 2023-07-04            |         107.1        |                 0.721335   |           0.200216   |           99.453    |            0.174886  |                         0 |
| SH.920478 | ok                      |    242 | 2023-11-27            |          22.23       |                 0.668094   |           0.11395    |           17.772    |            0.117199  |                         0 |
| SZ.003010 | ok                      |    242 | 2023-06-02            |          17.0341     |                 0.670063   |           0.0416938  |           15.3088   |            0.0848484 |                         0 |
| SZ.301016 | ok                      |    242 | 2023-07-13            |          18.34       |                 0.660767   |           0.113155   |           15.1955   |            0.162243  |                         0 |
| BJ.832317 | missing_comparison_data |    nan | nan                   |                      |                            |                      |                     |                      |                           |
| BJ.833874 | missing_comparison_data |    nan | nan                   |                      |                            |                      |                     |                      |                           |
| BJ.833994 | missing_comparison_data |    nan | nan                   |                      |                            |                      |                     |                      |                           |
| SH.600005 | missing_comparison_data |    nan | nan                   |                      |                            |                      |                     |                      |                           |
| SH.600010 | ok                      |    242 | 2023-05-29            |           2.179e-05  |                 1.19e-05   |           1.171e-05  |            3.26e-06 |            8.12e-06  |                         0 |
| SH.600022 | ok                      |    242 | 2023-06-02            |           0.00054086 |                 0.00037314 |           0.000368   |            4.41e-05 |            0.00182   |                         0 |
