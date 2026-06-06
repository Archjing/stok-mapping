# Maintenance Status Report

Generated at: 2026-06-07T04:53:38
State DB: /home/zj/workspace/stok-mapping/data/maintenance/maintenance.sqlite

## Summary

| metric | value |
| --- | --- |
| tasks | 5 |
| decisions | {"skipped": 5} |
| latest_run_statuses | {"never": 5} |
| shard_statuses | {"pending": 3} |

## Scheduled Tasks

| task | enabled | schedule | last_decision | reason | last_run | last_error | retry_count | log |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| a_share_history | yes | time:16:30 | skipped | not_trading_day(cn_trading_calendar(is_open=0)) | never |  | 0 | logs/manual_history_update.log |
| daily_brief | yes | time:07:20 | skipped | not_trading_day(cn_trading_calendar(is_open=0)) | never |  | 0 | logs/daily_brief_pipeline.log |
| financial_factors | yes | time:03:30 | skipped | not_trading_day(cn_trading_calendar(is_open=0)) | never |  | 0 | logs/financial_factors_update.log |
| hk_market_history | yes | time:16:20 | skipped | not_trading_day(market_calendar_weekday_fallback(scope=hk, weekday=7)) | never |  | 0 | logs/hk_market_history_update.log |
| us_market_history | yes | time:17:10 | skipped | not_trading_day(market_calendar_weekday_fallback(scope=us, weekday=7)) | never |  | 0 | logs/us_market_history_update.log |

## Long Backfill Shards

| run_id | task | shard | status | pid | started_at | finished_at | log | report | error | conclusion |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | tushare_financial_backfill | 0/3 | pending |  | 2026-06-07T04:26:57 |  | logs/maintenance/tushare_financial_backfill_run_1_shard_0.log |  |  |  |
| 1 | tushare_financial_backfill | 1/3 | pending |  | 2026-06-07T04:26:57 |  | logs/maintenance/tushare_financial_backfill_run_1_shard_1.log |  |  |  |
| 1 | tushare_financial_backfill | 2/3 | pending |  | 2026-06-07T04:26:57 |  | logs/maintenance/tushare_financial_backfill_run_1_shard_2.log |  |  |  |

## Open Risks

- None
