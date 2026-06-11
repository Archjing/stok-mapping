---
name: tushare-backfill
description: Use for Stok Mapping Tushare history or financial backfill commands, sharding, retrying failed/pending tasks, rate-limit planning, and audit report review.
---

# Tushare Backfill

Use this skill when the task concerns Tushare daily/history/financial backfill, sharding, retries, rate limits, audit outputs, or failed/pending/empty task cleanup.

## Scope

- Respect Tushare frequency and point limits.
- Prefer small targeted retries over broad backfill when cleaning tail states.
- Preserve report traceability: dated per-run reports plus summary audit rows.
- Do not commit generated audit reports unless the user explicitly wants runtime artifacts tracked.

## Primary Commands

```bash
./.venv/bin/python -m phase0.cli backfill-tushare-financials --config config.yaml --start-period YYYY-MM-DD --end-period YYYY-MM-DD --max-requests-per-minute 67
./.venv/bin/python -m phase0.cli backfill-tushare-financials --config config.yaml --start-period YYYY-MM-DD --end-period YYYY-MM-DD --max-requests-per-minute 67 --shard-index 0 --shard-count 3 --retry-failed
./.venv/bin/python -m phase0.cli backfill-tushare-history --config config.yaml --start-date YYYY-MM-DD --end-date YYYY-MM-DD
```

## Key Files

- `phase0/tushare_financial_backfill.py`
- `phase0/tushare_source.py`
- `phase0/cli.py`
- `data/manual_history/a_share_history.sqlite`
- `reports/tushare_financial_backfill_audit/`
- `reports/tushare_history_backfill_audit/`

## Review Rules

- `--shard-index` is zero-based; `--shard-count` is total shard count.
- Empty usually means the interface returned no usable rows for that stock-period-interface tuple.
- Failed usually means API, rate limit, permission, schema, network, or write failure.
- For 200 calls/minute limits, three shards at 67/minute each are close to the aggregate cap; leave operational margin if other jobs also call Tushare.

