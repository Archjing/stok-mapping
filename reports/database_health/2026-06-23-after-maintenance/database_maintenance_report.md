# Historical Database Maintenance Report

- Date: 2026-06-23
- Scope: A-share main database (`cn`)
- Database: `data/manual_history/a_share_history.sqlite`
- Background: Pre-maintenance `db-health --scope all` failed because A-share daily bars were stale. The latest `market_daily_bars` date was `2026-06-11`, while the expected trade date was `2026-06-23`; `cn.daily.staleness` was `7`, above the `<= 1` threshold.

## Maintenance Action

Ran:

```bash
./.venv/bin/python -m phase0.cli update-history --config config.yaml
```

Result:

- Status: `updated`
- Calendar latest trade date: `2026-06-23`
- Target trade date: `2026-06-22`
- Before latest date: `2026-06-11`
- After latest date: `2026-06-22`
- Fetched rows: `5510`
- Inserted rows: `5510`
- Metadata updated rows: `5510`
- Primary source: `tushare.daily+daily_basic+adj_factor`
- Universe rebuild: `500/500` selected from `local_history_sqlite`

Note: AkShare all-A snapshot failed through the proxy during universe rebuild, so the process used the configured local history fallback.

## Verification

Ran:

```bash
./.venv/bin/python -m phase0.cli db-health --config config.yaml --scope cn --output-dir reports/database_health/2026-06-23-after-maintenance --fail-on never
```

Result:

- Status: `pass`
- Findings: `errors=0`, `warnings=0`, `info=0`
- `cn.daily.latest_date`: `2026-06-22`
- `cn.daily.latest_coverage`: `5510/5530 (99.64%)`
- `cn.daily.staleness`: `1`, threshold `<= 1`
- `cn.daily_basic.latest_date`: `2026-06-22`
- `cn.daily_basic.latest_rows`: `5510`

Final main-database admission:

```bash
./.venv/bin/python -m phase0.cli db-health --config config.yaml --scope cn --fail-on error
```

Expected result: pass with exit code `0`.

## Residual Items

An additional all-scope check was run for visibility:

```bash
./.venv/bin/python -m phase0.cli db-health --config config.yaml --scope all --output-dir reports/database_health/2026-06-23-after-maintenance-all --fail-on never
```

Result:

- Status: `warning`
- Findings: `errors=0`, `warnings=16`, `info=0`

The remaining warnings are outside this A-share main database maintenance gate:

- Tushare financial backfill task queue still has failed and pending tasks.
- US and HK cross-market daily bars are stale and have existing OHLC warnings.
- Scheduler last-run marker files are stale, although `market_data_source_runs.audit` is fresh after this maintenance.

These items should be handled as separate maintenance tasks rather than blocking the main A-share database health gate.
