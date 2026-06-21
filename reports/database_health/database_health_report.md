# Database Health Report

- Status: warning
- Scope: scheduler
- As-of date: 2026-06-22
- Generated at: 2026-06-22T03:47:04
- Findings: errors=0, warnings=5, info=0

## Summary

| Section | Check | Status | Metric | Value | Threshold |
| --- | --- | --- | --- | --- | --- |
| scheduler | scheduler.a_share_history.last_file | warning | mtime | 2026-06-05 | <= 3 days |
| scheduler | scheduler.us_market_history.last_file | warning | mtime | 2026-06-05 | <= 3 days |
| scheduler | scheduler.hk_market_history.last_file | warning | mtime | 2026-06-04 | <= 3 days |
| scheduler | scheduler.daily_brief.last_file | warning | mtime | 2026-06-12 | <= 3 days |
| scheduler | scheduler.market_data_source_runs.audit | warning | latest_fetched_at | 2026-06-12T03:40:35 | <= 3 days |

## Findings

| Severity | Check | Table | Symbol | Date | Field | Message | Sample | Expected |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| warning | scheduler.a_share_history.last_file |  |  |  |  | scheduler last-run marker is stale | 2026-06-05 | mtime within 3 days |
| warning | scheduler.daily_brief.last_file |  |  |  |  | scheduler last-run marker is stale | 2026-06-12 | mtime within 3 days |
| warning | scheduler.hk_market_history.last_file |  |  |  |  | scheduler last-run marker is stale | 2026-06-04 | mtime within 3 days |
| warning | scheduler.market_data_source_runs.audit | market_data_source_runs |  |  |  | source audit table has no recent run record | 2026-06-12T03:40:35 | latest fetched_at within 3 days |
| warning | scheduler.us_market_history.last_file |  |  |  |  | scheduler last-run marker is stale | 2026-06-05 | mtime within 3 days |
