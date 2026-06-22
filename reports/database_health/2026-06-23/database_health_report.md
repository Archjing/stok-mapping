# Database Health Report

- Status: fail
- Scope: all
- As-of date: 2026-06-23
- Generated at: 2026-06-23T00:16:53
- Findings: errors=1, warnings=17, info=0

## Summary

| Section | Check | Status | Metric | Value | Threshold |
| --- | --- | --- | --- | --- | --- |
| cn | cn.database.exists | pass | db_path | /home/zj/workspace/stok-mapping/data/manual_history/a_share_history.sqlite |  |
| cn | cn.market_daily_bars.schema | pass | missing_columns | none | none |
| cn | cn.daily.latest_date | pass | latest_date | 2026-06-11 |  |
| cn | cn.daily.latest_coverage | pass | latest_symbols/total_symbols | 5511/5529 (99.67%) | 80.00% |
| cn | cn.daily.staleness | fail | trade_day_staleness | 7 | <= 1; expected_trade_date=2026-06-23 |
| cn | cn.daily.ohlc | pass | recent_ohlc_violations | 0 | 0 |
| cn | cn.daily.positive_prices | pass | recent_non_positive_price_rows | 0 | 0 |
| cn | cn.daily.non_negative_liquidity | pass | recent_negative_volume_amount_rows | 0 | 0 |
| cn | cn.market_stocks.schema | pass | missing_columns | none | none |
| cn | cn.meta.active_symbols | pass | active/total | 5529/5529 |  |
| cn | cn.meta.list_date_coverage | pass | list_date_coverage | 99.91% | 95.00% |
| cn | cn.market_daily_basic.schema | pass | missing_columns | none | none |
| cn | cn.daily_basic.latest_date | pass | latest_date | 2026-06-11 |  |
| cn | cn.daily_basic.latest_rows | pass | latest_rows | 5511 |  |
| cn | cn.daily_basic.market_cap | pass | latest_non_null_coverage | 100.00% | 80.00% |
| cn | cn.daily_basic.pe_ratio | pass | latest_non_null_coverage | 72.00% | diagnostic only |
| cn | cn.daily_basic.pb_ratio | pass | latest_non_null_coverage | 99.26% | 80.00% |
| cn | cn.daily_basic.turnover_rate | pass | latest_non_null_coverage | 100.00% | 80.00% |
| cn | cn.daily_basic.pe_ratio_missing | info | missing/rows | 1543/5511 (28.00%) | diagnostic only |
| cn | cn.daily_basic.pe_ratio_missing_pb_present | info | pb_present_among_pe_missing | 1503/1543 (97.41%) | diagnostic only |
| cn | cn.daily_basic.pe_ratio_missing_st | info | st_or_star_st_among_pe_missing | 193/1543 (12.51%) | diagnostic only |
| cn | cn.market_adj_factors.schema | pass | missing_columns | none | none |
| cn | cn.adjustment.positive_factor | pass | recent_non_positive_adj_factor_rows | 0 | 0 |
| cn | cn.trading_calendar.schema | pass | missing_columns | none | none |
| financial | financial.market_financial_factors.schema | pass | missing_columns | none | none |
| financial | financial.rows | pass | row_count | 193817 |  |
| financial | financial.latest_report | pass | latest_report_date | 2026-03-31 |  |
| financial | financial.announce_date_coverage | pass | announce_date_coverage | 100.00% | 95.00% |
| financial | financial.announce_after_report | pass | announce_before_report_rows | 0 | 0 |
| financial | financial.coverage.latest_factor | pass | eligible_symbol_coverage | 5529/5529 (100.00%) | 60.00% |
| financial | financial.coverage.roe | pass | eligible_symbol_coverage | 5484/5529 (99.19%) | 60.00% |
| financial | financial.coverage.revenue_growth | pass | eligible_symbol_coverage | 5527/5529 (99.96%) | 60.00% |
| financial | financial.coverage.profit_growth | pass | eligible_symbol_coverage | 5529/5529 (100.00%) | 60.00% |
| financial | financial.coverage.cash_flow_quality | pass | eligible_symbol_coverage | 5209/5529 (94.21%) | 60.00% |
| financial | financial.coverage.debt_to_asset | pass | eligible_symbol_coverage | 5208/5529 (94.19%) | 60.00% |
| financial | financial.backfill_tasks.empty | pass | task_count | 8803 |  |
| financial | financial.backfill_tasks.failed | warning | task_count | 3850 |  |
| financial | financial.backfill_tasks.fetched | pass | task_count | 26477 |  |
| financial | financial.backfill_tasks.pending | warning | task_count | 3036 |  |
| cross_market.us | cross_market.us.us_daily_bars.schema | pass | missing_columns | none | none |
| cross_market.us | cross_market.us.coverage | warning | fresh_configured_symbols | 0/6 (0.00%) latest=2026-06-04 | 100.00% |
| cross_market.us | cross_market.us.ohlc | warning | recent_ohlc_violations | 3 | 0 |
| cross_market.us | cross_market.us.us_data_source_runs.audit | warning | latest_fetched_at | 2026-06-05T17:10:14 | <= 5 days |
| cross_market.hk | cross_market.hk.hk_daily_bars.schema | pass | missing_columns | none | none |
| cross_market.hk | cross_market.hk.coverage | warning | fresh_configured_symbols | 0/30 (0.00%) latest=2026-06-04 | 100.00% |
| cross_market.hk | cross_market.hk.ohlc | warning | recent_ohlc_violations | 1 | 0 |
| cross_market.hk | cross_market.hk.hk_data_source_runs.audit | warning | latest_fetched_at | 2026-06-05T16:20:51 | <= 5 days |
| scheduler | scheduler.a_share_history.last_file | warning | mtime | 2026-06-05 | <= 3 days |
| scheduler | scheduler.us_market_history.last_file | warning | mtime | 2026-06-05 | <= 3 days |
| scheduler | scheduler.hk_market_history.last_file | warning | mtime | 2026-06-04 | <= 3 days |
| scheduler | scheduler.daily_brief.last_file | warning | mtime | 2026-06-12 | <= 3 days |
| scheduler | scheduler.market_data_source_runs.audit | warning | latest_fetched_at | 2026-06-12T03:40:35 | <= 3 days |

## Findings

| Severity | Check | Table | Symbol | Date | Field | Message | Sample | Expected |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| error | cn.daily.staleness | market_daily_bars |  | 2026-06-11 |  | latest A-share daily bar date is stale relative to expected trade date | 7 | staleness <= 1 trading days (trading_calendar) |
| warning | cross_market.hk.coverage | hk_daily_bars | HK.00700,HK.09988,HK.03690,HK.01810,HK.00981,HK.01211,HK.09618,HK.09888,HK.01024,HK.09999 |  |  | cross-market symbol freshness coverage is below threshold | 0.00% | coverage >= 100.00% |
| warning | cross_market.hk.hk_data_source_runs.audit | hk_data_source_runs |  |  |  | source audit table has no recent run record | 2026-06-05T16:20:51 | latest fetched_at within 5 days |
| warning | cross_market.hk.ohlc | hk_daily_bars |  |  |  | recent_ohlc_violations found 1 violating rows | 1 | high >= low/open/close and low <= open/close |
| warning | cross_market.hk.ohlc.sample | hk_daily_bars | HK.09633 | 2025-12-17 | open,high,low,close | sample violating row | open=44.900001525878906, high=46.040000915527344, low=45.08000183105469, close=45.84000015258789, volume=5549245.0, source=yfinance | high >= low/open/close and low <= open/close |
| warning | cross_market.us.coverage | us_daily_bars | ^NDX,^SOX,NVDA,KWEB,^VIX,CNY=X |  |  | cross-market symbol freshness coverage is below threshold | 0.00% | coverage >= 100.00% |
| warning | cross_market.us.ohlc | us_daily_bars |  |  |  | recent_ohlc_violations found 3 violating rows | 3 | high >= low/open/close and low <= open/close |
| warning | cross_market.us.ohlc.sample | us_daily_bars | CNY=X | 2026-02-05 | open,high,low,close | sample violating row | open=6.941500186920166, high=6.941500186920166, low=6.941500186920166, close=6.937699794769287, volume=0.0, source=yfinance | high >= low/open/close and low <= open/close |
| warning | cross_market.us.ohlc.sample | us_daily_bars | CNY=X | 2025-11-04 | open,high,low,close | sample violating row | open=7.171800136566162, high=7.120100021362305, low=7.120100021362305, close=7.171800136566162, volume=0.0, source=yfinance | high >= low/open/close and low <= open/close |
| warning | cross_market.us.ohlc.sample | us_daily_bars | CNY=X | 2025-10-29 | open,high,low,close | sample violating row | open=7.098800182342529, high=7.098999977111816, low=7.098899841308594, close=7.098800182342529, volume=0.0, source=yfinance | high >= low/open/close and low <= open/close |
| warning | cross_market.us.us_data_source_runs.audit | us_data_source_runs |  |  |  | source audit table has no recent run record | 2026-06-05T17:10:14 | latest fetched_at within 5 days |
| warning | financial.backfill_tasks.failed | tushare_financial_backfill_tasks |  |  |  | Tushare financial backfill still has failed tasks | 3850 | long-running backfill task queue should eventually drain |
| warning | financial.backfill_tasks.pending | tushare_financial_backfill_tasks |  |  |  | Tushare financial backfill still has pending tasks | 3036 | long-running backfill task queue should eventually drain |
| warning | scheduler.a_share_history.last_file |  |  |  |  | scheduler last-run marker is stale | 2026-06-05 | mtime within 3 days |
| warning | scheduler.daily_brief.last_file |  |  |  |  | scheduler last-run marker is stale | 2026-06-12 | mtime within 3 days |
| warning | scheduler.hk_market_history.last_file |  |  |  |  | scheduler last-run marker is stale | 2026-06-04 | mtime within 3 days |
| warning | scheduler.market_data_source_runs.audit | market_data_source_runs |  |  |  | source audit table has no recent run record | 2026-06-12T03:40:35 | latest fetched_at within 3 days |
| warning | scheduler.us_market_history.last_file |  |  |  |  | scheduler last-run marker is stale | 2026-06-05 | mtime within 3 days |
