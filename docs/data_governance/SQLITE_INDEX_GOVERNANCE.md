# SQLite Index and Optimizer Governance

**Status:** Storage P0.3 baseline completed on 2026-08-14. This document is an audit and proposal, not authorization to mutate a production database.

## Scope and safety boundary

- Production source inspected: `/Users/aj/workspace/stok-mapping/data/a_share_history.sqlite`.
- The source was opened with SQLite URI `mode=ro` and `PRAGMA query_only=ON` before SQLite's backup API created a temporary working copy.
- `DROP INDEX`, `ANALYZE`, and `PRAGMA optimize` ran only on that temporary copy.
- The source candidate index was queried again after the experiment and remained present. No production database was vacuumed, reformatted, or modified.
- The local JSON receipt is intentionally not committed: `reports/database_health/sqlite_index_governance/a_share_history_idx_market_adj_factors_symbol_date.json`.

## Inventory findings

The read-only capacity baseline found 16 primary SQLite databases and five named backups. Primary files totalled 11,106,168,832 bytes; named backups totalled 15,035,850,752 bytes. For `a_share_history.sqlite` (9,908,109,312 bytes), the exact-key duplicate analysis found:

| Table | Candidate index | Covering index | Ordered key columns | Candidate bytes | Assessment |
| --- | --- | --- | --- | ---: | --- |
| `market_adj_factors` | `idx_market_adj_factors_symbol_date` | `sqlite_autoindex_market_adj_factors_1` | `(market, symbol, date)` | 514,293,760 | Exact duplicate of the primary-key index |
| `market_financial_factors` | `idx_market_financial_factors_symbol_report` | `sqlite_autoindex_market_financial_factors_1` | `(market, symbol, report_date)` | 6,946,816 | Exact duplicate of the primary-key index |

The current code search found no tracked schema initializer that recreates either legacy candidate index. A separately approved production change must nevertheless re-run that search immediately before execution, because local migration scripts or operational tooling may exist outside the tracked source tree.

## Reproducible copy-only benchmark

The reusable helper is `quant.data_governance.sqlite_index_governance.run_index_removal_benchmark`. It rejects a copy path equal to the source path, creates a backup from a read-only source connection, captures `EXPLAIN QUERY PLAN`, drops the candidate only in the copy, runs `ANALYZE` and `PRAGMA optimize` only in the copy, and captures the same queries again.

The representative run used the largest candidate, `idx_market_adj_factors_symbol_date`, with:

1. a 2024-01-01 through 2025-12-31 qfq symbol history for `SH.600004`;
2. the 2026-08-14 qfq market cross section;
3. a point-in-time adjustment-factor history for `SH.600004` through 2026-08-14; and
4. the 2026-08-14 qfq daily-bar/daily-basic join.

| Query | Rows | Before (ms) | After drop (ms) | After `ANALYZE` + optimize (ms) | Result equality |
| --- | ---: | ---: | ---: | ---: | --- |
| Symbol range | 485 | 1.686 | 0.926 | 0.660 | SHA-256 identical across all stages |
| Date cross section | 5,540 | 4,127.557 | 1,508.603 | 16.085 | SHA-256 identical across all stages |
| PIT adjustment | 3,531 | 392.090 | 311.755 | 435.437 | SHA-256 identical across all stages |
| Daily-basic join | 5,540 | 1,315.173 | 1,271.298 | 13.690 | SHA-256 identical across all stages |

The PIT query's planner changed from the explicit candidate index to `sqlite_autoindex_market_adj_factors_1` immediately after the drop, with unchanged rows and result hash. This directly demonstrates that the primary-key index covers this access path.

These are single-run, warm-cache-sensitive observations, not throughput claims. In particular, the large cross-section and join timing changes after `ANALYZE` reflect a changed planner choice and must not be attributed solely to dropping the candidate index. A production change requires a repeated, controlled benchmark and a restore drill under the backup policy in P0.5.

## Decision and production proposal

1. **No production mutation in Storage P0.3.** The candidate indexes remain present in the local production database.
2. **Eligible for a separately approved change:** remove `idx_market_adj_factors_symbol_date` only after taking a verified backup, preserving the rollback asset, repeating the bounded query and strategy checks, and executing a restore drill.
3. **Not yet approved:** `idx_market_financial_factors_symbol_report` is recorded as an exact duplicate but has not received its own copy-only representative-query benchmark. It must not be removed based solely on its size signature.
4. **Optimizer policy:** do not run `ANALYZE` or `PRAGMA optimize` against the production history database until P0.5 defines transaction ownership, backup/restore, and scheduler-reader contention controls. The P0.3 result shows that optimizer statistics can materially change planner selection.
5. **Regression guard:** any future migration or maintenance task that creates an index on a table with a composite primary key must compare ordered key signatures against existing primary-key and unique indexes before adding it.
