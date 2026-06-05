# Database Health Report

- Status: pass
- Scope: scheduler
- As-of date: 2026-06-05
- Generated at: 2026-06-05T17:10:03
- Findings: errors=0, warnings=0, info=0

## Summary

| Section | Check | Status | Metric | Value | Threshold |
| --- | --- | --- | --- | --- | --- |
| scheduler | scheduler.a_share_history.last_file | pass | mtime | 2026-06-05 | <= 3 days |
| scheduler | scheduler.us_market_history.last_file | pass | mtime | 2026-06-04 | <= 3 days |
| scheduler | scheduler.hk_market_history.last_file | pass | mtime | 2026-06-04 | <= 3 days |
| scheduler | scheduler.daily_brief.last_file | pass | mtime | 2026-06-05 | <= 3 days |
| scheduler | scheduler.market_data_source_runs.audit | pass | latest_fetched_at | 2026-06-05T16:30:35 | <= 3 days |

## Findings

| Severity | Check | Table | Symbol | Date | Field | Message | Sample | Expected |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| info | database_health.clean |  |  |  |  | no findings |  |  |
