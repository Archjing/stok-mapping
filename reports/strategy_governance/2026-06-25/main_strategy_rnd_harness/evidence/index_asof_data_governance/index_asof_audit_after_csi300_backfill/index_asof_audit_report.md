# Index As-Of Data Audit

This is a research-only data capability audit. It does not change strategies, admission, paper-review status, daily brief, watchlist, or trading signals.

## Metadata

- generated_at: `2026-06-25T09:19:23`
- benchmark_symbol: `SH.000300`
- sqlite_db: `/home/zj/workspace/stok-mapping/data/manual_history/a_share_history.sqlite`
- candidate_folds: ``

## Plain Conclusion

CSI300 成分和权重 as-of 审计表已具备最小 schema，可进入覆盖率细查。

## Capability Summary

| artifact | status | table | rows | benchmark_rows | min_trade_date | max_trade_date | coverage_ratio | missing_open_days | latest_lag_days | close_non_null_ratio | volume_non_null_ratio | amount_non_null_ratio | asof_status | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| benchmark_index_metadata | available | market_indices | 997 | 1 | 2005-04-08 | 2005-04-08 |  |  |  |  |  |  | not_applicable | index metadata identifies the benchmark but does not provide constituents |
| benchmark_index_price | available | market_index_bars | 1876918 | 2445 | 2016-05-03 | 2026-05-28 |  |  | 28 | 1.000000 | 1.000000 | 1.000000 | not_applicable | index prices support benchmark return context, not constituent/weight attribution |
| benchmark_open_day_coverage | available | trading_calendar | 13162 | 2445 | 2016-05-03 | 2026-05-28 | 1.000000 | 0 |  |  |  |  | not_applicable | open trading day coverage for benchmark price rows; this is not constituent coverage |
| benchmark_constituents | available | cn_index_constituents_asof | 60900 | 60900 | 2016-01-29 | 2026-05-06 |  |  |  |  |  |  | available | available for audit |
| benchmark_weights | available | cn_index_weights_asof | 60900 | 60900 | 2016-01-29 | 2026-05-06 |  |  |  |  |  |  | available | available for audit |

## Fold Coverage

| walk_forward_preset | fold | valid_start | valid_end | universe_as_of_date | coverage_status | note |
| --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  | not_checked | candidate folds path not provided |

## Decision Boundary

- `benchmark_index_price` can support CSI300 return and trend context only.
- `benchmark_constituents` and `benchmark_weights` must be available before claiming CSI300 constituent exposure, active weight, or missed top-weight names.
- Any future ingestion must carry an auditable as-of field such as `asof_time` or `effective_date`.
- Current result does not authorize a new strong-market strategy or any promotion of existing candidates.
