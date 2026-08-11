---
name: factor-diagnostics
description: Use for Stok Mapping factor effectiveness diagnostics, PIT financial factor coverage, missing-field patch analysis, factor explainability, and factor data audits.
---

# Factor Diagnostics

Use this skill when the task concerns factor validity, factor coverage, PIT financial factors, missing fields, factor explainability, or factor diagnostic reports.

## Scope

- Confirm field coverage before discussing factor effectiveness.
- Separate `fetched`, `empty`, `failed`, `pending`, and missing-field states.
- Prefer quarter-by-quarter financial factor coverage for long backfills.
- Treat low coverage as a data quality issue, not a strategy result.

## Primary Commands

```bash
./.venv/bin/python -m phase0.cli factor-effectiveness --config config.yaml
./.venv/bin/python -m phase0.cli db-health --config config.yaml --scope cn --fail-on error
./.venv/bin/python -m phase0.cli backfill-tushare-financials --config config.yaml --start-period YYYY-MM-DD --end-period YYYY-MM-DD --max-requests-per-minute 67
```

Use shard and retry options only when the task explicitly requires backfill execution.

## Key Files

- `phase0/factor_effectiveness.py`
- `phase0/tushare_financial_backfill.py`
- `phase0/db_health.py`
- `data/a_share_history.sqlite`
- `reports/tushare_financial_backfill_audit/`
- `reports/factor_effectiveness/`

## Review Rules

- Explain coverage as percentages in user-facing Markdown when reviewing reports.
- For financial PIT inputs, verify report periods and as-of visibility before strategy interpretation.
- For missing-field patch work, call only the interfaces needed by missing fields when code supports that path.
