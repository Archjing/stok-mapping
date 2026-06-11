---
name: daily-brief-ops
description: Use for Stok Mapping daily brief, watchlist generation, scheduler health gates, watchlist_today publishing, ECS rsync target checks, and premarket report troubleshooting.
---

# Daily Brief Ops

Use this skill when the task concerns `daily_brief`, `brief watchlist`, premarket watchlist generation, scheduler gates, `watchlist_today/index.html`, or ECS publishing.

## Scope

- Treat daily brief as an operational A-share workflow unless the command explicitly depends on HK/US data.
- Use local history and explicit price-adjustment mode for watchlist generation.
- Debug the gate first, then panel/cache generation, then report copying/publishing.

## Primary Commands

```bash
./.venv/bin/python -m phase0.cli daily-brief --config config.yaml --watchlist --skip-update
./.venv/bin/python -m phase0.cli brief watchlist --config config.yaml
./.venv/bin/python -m phase0.cli maintain status --config config.yaml
./.venv/bin/python -m phase0.cli db-health --config config.yaml --scope cn
```

## Key Files

- `phase0/cli.py`
- `phase0/maintenance_orchestrator.py`
- `scripts/export_premarket_watchlist.py`
- `scripts/export_strategy_bill.py`
- `scripts/run_project_scheduler.sh`
- `reports/watchlist_today/index.html`
- `logs/daily_brief_pipeline.log`
- `logs/scheduler/daily_brief.state`

## Review Rules

- If `watchlist_today/index.html` is stale, check whether `daily_brief` was blocked before checking copy logic.
- The ECS sync target currently comes from code/config inspection as `root@39.105.102.5:/brief/`; port mapping is not defined in this repo.
- Runtime outputs under `reports/`, `logs/`, and `data/maintenance/` are usually not source changes.

