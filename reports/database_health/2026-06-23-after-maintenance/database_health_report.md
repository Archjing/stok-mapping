# Database Health Report

- Status: pass
- Scope: cn
- As-of date: 2026-06-23
- Generated at: 2026-06-23T00:23:14
- Findings: errors=0, warnings=0, info=0

## Summary

| Section | Check | Status | Metric | Value | Threshold |
| --- | --- | --- | --- | --- | --- |
| cn | cn.database.exists | pass | db_path | /home/zj/workspace/stok-mapping/data/manual_history/a_share_history.sqlite |  |
| cn | cn.market_daily_bars.schema | pass | missing_columns | none | none |
| cn | cn.daily.latest_date | pass | latest_date | 2026-06-22 |  |
| cn | cn.daily.latest_coverage | pass | latest_symbols/total_symbols | 5510/5530 (99.64%) | 80.00% |
| cn | cn.daily.staleness | pass | trade_day_staleness | 1 | <= 1; expected_trade_date=2026-06-23 |
| cn | cn.daily.ohlc | pass | recent_ohlc_violations | 0 | 0 |
| cn | cn.daily.positive_prices | pass | recent_non_positive_price_rows | 0 | 0 |
| cn | cn.daily.non_negative_liquidity | pass | recent_negative_volume_amount_rows | 0 | 0 |
| cn | cn.market_stocks.schema | pass | missing_columns | none | none |
| cn | cn.meta.active_symbols | pass | active/total | 5530/5530 |  |
| cn | cn.meta.list_date_coverage | pass | list_date_coverage | 99.89% | 95.00% |
| cn | cn.market_daily_basic.schema | pass | missing_columns | none | none |
| cn | cn.daily_basic.latest_date | pass | latest_date | 2026-06-22 |  |
| cn | cn.daily_basic.latest_rows | pass | latest_rows | 5510 |  |
| cn | cn.daily_basic.market_cap | pass | latest_non_null_coverage | 100.00% | 80.00% |
| cn | cn.daily_basic.pe_ratio | pass | latest_non_null_coverage | 72.03% | diagnostic only |
| cn | cn.daily_basic.pb_ratio | pass | latest_non_null_coverage | 99.22% | 80.00% |
| cn | cn.daily_basic.turnover_rate | pass | latest_non_null_coverage | 100.00% | 80.00% |
| cn | cn.daily_basic.pe_ratio_missing | info | missing/rows | 1541/5510 (27.97%) | diagnostic only |
| cn | cn.daily_basic.pe_ratio_missing_pb_present | info | pb_present_among_pe_missing | 1499/1541 (97.27%) | diagnostic only |
| cn | cn.daily_basic.pe_ratio_missing_st | info | st_or_star_st_among_pe_missing | 195/1541 (12.65%) | diagnostic only |
| cn | cn.market_adj_factors.schema | pass | missing_columns | none | none |
| cn | cn.adjustment.positive_factor | pass | recent_non_positive_adj_factor_rows | 0 | 0 |
| cn | cn.trading_calendar.schema | pass | missing_columns | none | none |

## Findings

| Severity | Check | Table | Symbol | Date | Field | Message | Sample | Expected |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| info | database_health.clean |  |  |  |  | no findings |  |  |
