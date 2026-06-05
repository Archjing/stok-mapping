# Database Health Report

- Status: warning
- Scope: all
- As-of date: 2026-06-05
- Generated at: 2026-06-05T09:22:19
- Findings: errors=0, warnings=10, info=0

## Summary

| Section | Check | Status | Metric | Value | Threshold |
| --- | --- | --- | --- | --- | --- |
| cn | cn.database.exists | pass | db_path | /home/zj/workspace/stok-mapping/data/manual_history/a_share_history.sqlite |  |
| cn | cn.market_daily_bars.schema | pass | missing_columns | none | none |
| cn | cn.daily.latest_date | pass | latest_date | 2026-06-04 |  |
| cn | cn.daily.latest_coverage | pass | latest_symbols/total_symbols | 5511/5761 (95.66%) | 80.00% |
| cn | cn.daily.staleness | pass | calendar_day_staleness | 1 | <= 1 |
| cn | cn.daily.ohlc | pass | recent_ohlc_violations | 0 | 0 |
| cn | cn.daily.positive_prices | pass | recent_non_positive_price_rows | 0 | 0 |
| cn | cn.daily.non_negative_liquidity | pass | recent_negative_volume_amount_rows | 0 | 0 |
| cn | cn.market_stocks.schema | pass | missing_columns | none | none |
| cn | cn.meta.active_symbols | pass | active/total | 5525/5525 |  |
| cn | cn.meta.list_date_coverage | pass | list_date_coverage | 99.98% | 95.00% |
| cn | cn.market_daily_basic.schema | pass | missing_columns | none | none |
| cn | cn.daily_basic.latest_date | pass | latest_date | 2026-06-04 |  |
| cn | cn.daily_basic.latest_rows | pass | latest_rows | 5511 |  |
| cn | cn.daily_basic.market_cap | pass | latest_non_null_coverage | 100.00% | 80.00% |
| cn | cn.daily_basic.pe_ratio | warning | latest_non_null_coverage | 71.98% | 80.00% |
| cn | cn.daily_basic.pb_ratio | pass | latest_non_null_coverage | 99.26% | 80.00% |
| cn | cn.daily_basic.turnover_rate | pass | latest_non_null_coverage | 100.00% | 80.00% |
| cn | cn.market_adj_factors.schema | pass | missing_columns | none | none |
| cn | cn.adjustment.positive_factor | pass | recent_non_positive_adj_factor_rows | 0 | 0 |
| cn | cn.trading_calendar.schema | pass | missing_columns | none | none |
| financial | financial.market_financial_factors.schema | pass | missing_columns | none | none |
| financial | financial.rows | pass | row_count | 184118 |  |
| financial | financial.latest_report | pass | latest_report_date | 2026-03-31 |  |
| financial | financial.announce_date_coverage | pass | announce_date_coverage | 100.00% | 95.00% |
| financial | financial.announce_after_report | pass | announce_before_report_rows | 0 | 0 |
| financial | financial.coverage.latest_factor | pass | eligible_symbol_coverage | 5525/5525 (100.00%) | 60.00% |
| financial | financial.coverage.roe | pass | eligible_symbol_coverage | 5480/5525 (99.19%) | 60.00% |
| financial | financial.coverage.revenue_growth | pass | eligible_symbol_coverage | 5523/5525 (99.96%) | 60.00% |
| financial | financial.coverage.profit_growth | pass | eligible_symbol_coverage | 5525/5525 (100.00%) | 60.00% |
| financial | financial.coverage.cash_flow_quality | pass | eligible_symbol_coverage | 5208/5525 (94.26%) | 60.00% |
| financial | financial.coverage.debt_to_asset | pass | eligible_symbol_coverage | 5207/5525 (94.24%) | 60.00% |
| financial | financial.backfill_tasks.empty | pass | task_count | 2100 |  |
| financial | financial.backfill_tasks.failed | warning | task_count | 1360 |  |
| financial | financial.backfill_tasks.fetched | pass | task_count | 16778 |  |
| financial | financial.backfill_tasks.pending | warning | task_count | 12397 |  |
| cross_market.us | cross_market.us.us_daily_bars.schema | pass | missing_columns | none | none |
| cross_market.us | cross_market.us.coverage | pass | fresh_configured_symbols | 6/6 (100.00%) latest=2026-06-04 | 100.00% |
| cross_market.us | cross_market.us.ohlc | warning | recent_ohlc_violations | 3 | 0 |
| cross_market.us | cross_market.us.us_data_source_runs.audit | pass | latest_fetched_at | 2026-06-05T09:17:35 | <= 5 days |
| cross_market.hk | cross_market.hk.hk_daily_bars.schema | pass | missing_columns | none | none |
| cross_market.hk | cross_market.hk.coverage | warning | fresh_configured_symbols | 28/30 (93.33%) latest=2026-06-03 | 100.00% |
| cross_market.hk | cross_market.hk.ohlc | warning | recent_ohlc_violations | 1 | 0 |
| cross_market.hk | cross_market.hk.hk_data_source_runs.audit | pass | latest_fetched_at | 2026-06-04T16:20:50 | <= 5 days |
| scheduler | scheduler.a_share_history.last_file | pass | mtime | 2026-06-04 | <= 3 days |
| scheduler | scheduler.us_market_history.last_file | pass | mtime | 2026-06-04 | <= 3 days |
| scheduler | scheduler.hk_market_history.last_file | pass | mtime | 2026-06-04 | <= 3 days |
| scheduler | scheduler.daily_brief.last_file | pass | mtime | 2026-06-05 | <= 3 days |
| scheduler | scheduler.market_data_source_runs.audit | pass | latest_fetched_at | 2026-06-04T16:30:27 | <= 3 days |

## Findings

| Severity | Check | Table | Symbol | Date | Field | Message | Sample | Expected |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| warning | cn.daily_basic.pe_ratio | market_daily_basic |  | 2026-06-04 | pe_ratio | latest daily_basic field coverage is below threshold | 71.98% | coverage >= 80% |
| warning | cross_market.hk.coverage | hk_daily_bars | HK.03690,HK.00981 |  |  | cross-market symbol freshness coverage is below threshold | 93.33% | coverage >= 100.00% |
| warning | cross_market.hk.ohlc | hk_daily_bars |  |  |  | recent_ohlc_violations found 1 violating rows | 1 | high >= low/open/close and low <= open/close |
| warning | cross_market.hk.ohlc.sample | hk_daily_bars | HK.09633 | 2025-12-17 | open,high,low,close | sample violating row | open=44.900001525878906, high=46.040000915527344, low=45.08000183105469, close=45.84000015258789, volume=5549245.0, source=yfinance | high >= low/open/close and low <= open/close |
| warning | cross_market.us.ohlc | us_daily_bars |  |  |  | recent_ohlc_violations found 3 violating rows | 3 | high >= low/open/close and low <= open/close |
| warning | cross_market.us.ohlc.sample | us_daily_bars | CNY=X | 2026-02-05 | open,high,low,close | sample violating row | open=6.941500186920166, high=6.941500186920166, low=6.941500186920166, close=6.937699794769287, volume=0.0, source=yfinance | high >= low/open/close and low <= open/close |
| warning | cross_market.us.ohlc.sample | us_daily_bars | CNY=X | 2025-11-04 | open,high,low,close | sample violating row | open=7.171800136566162, high=7.120100021362305, low=7.120100021362305, close=7.171800136566162, volume=0.0, source=yfinance | high >= low/open/close and low <= open/close |
| warning | cross_market.us.ohlc.sample | us_daily_bars | CNY=X | 2025-10-29 | open,high,low,close | sample violating row | open=7.098800182342529, high=7.098999977111816, low=7.098899841308594, close=7.098800182342529, volume=0.0, source=yfinance | high >= low/open/close and low <= open/close |
| warning | financial.backfill_tasks.failed | tushare_financial_backfill_tasks |  |  |  | Tushare financial backfill still has failed tasks | 1360 | long-running backfill task queue should eventually drain |
| warning | financial.backfill_tasks.pending | tushare_financial_backfill_tasks |  |  |  | Tushare financial backfill still has pending tasks | 12397 | long-running backfill task queue should eventually drain |
