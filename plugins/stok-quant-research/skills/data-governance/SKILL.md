---
name: data-governance
description: Use for Stok Mapping database health checks, scheduler gates, data coverage audits, trading-calendar staleness checks, and maintenance status reviews.
---

# Data Governance

Use this skill when the task concerns local database health, data quality gates, scheduler readiness, stale data, coverage audits, or maintenance state in the Stok Mapping project.

## Scope

- Prefer the project CLI over ad hoc SQL when a command exists.
- Treat health checks as gates for research and operations.
- Preserve auditability: report database path, scope, status, findings, and report path.
- Narrow a gate to true dependencies when a shared scope blocks unrelated work.

## Primary Commands

```bash
./.venv/bin/python -m phase0.cli db-health --config config.yaml --scope cn
./.venv/bin/python -m phase0.cli db-health --config config.yaml --scope cn --fail-on error
./.venv/bin/python -m phase0.cli db-health --config config.yaml --scope scheduler --fail-on warning
./.venv/bin/python -m phase0.cli maintain status --config config.yaml
./.venv/bin/python -m phase0.cli maintain tick --config config.yaml --dry-run
```

## Key Files

- `phase0/db_health.py`
- `phase0/maintenance_orchestrator.py`
- `scripts/run_project_scheduler.sh`
- `docs/PROJECT_ARCHITECTURE_OVERVIEW.md`
- `docs/DEVELOPMENT_PLAN.md`
- `data/README.md`
- `reports/database_health/database_health_report.md`
- `data/maintenance/maintenance.sqlite`

Historical scheduler task breakdowns live under `docs/archive/tasks/`; they do not define current operations.

## Review Rules

- Check whether a warning is actually relevant to the blocked task before changing gates.
- For A-share research, prefer `cn` scope unless the task truly depends on HK/US data.
- Trading-day staleness should use the maintained `trading_calendar`, not calendar-day arithmetic.
- Runtime artifacts such as `maintenance.sqlite`, logs, and generated reports normally should not be committed.
