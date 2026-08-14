# Hybrid Data Storage Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve stok-mapping from SQLite-only persistence to a locally operated hybrid architecture where SQLite remains the transactional and governance store while Parquet plus DuckDB becomes the analytical store for large historical fact tables.

**Architecture:** Preserve current data semantics and CLI behavior behind an explicit history-store boundary. Start with read-only SQLite governance and capacity evidence, then benchmark a bounded Parquet/DuckDB pilot, introduce dual-backend shadow reads, and migrate one fact table at a time only after point-in-time, strategy-output, performance, backup, and rollback gates pass.

**Tech Stack:** Python, SQLite, pytest, existing `quant.data_governance` and `quant.data_access` modules; DuckDB and Parquet are optional P1 dependencies and must not become runtime requirements before the P1 admission gate passes.

---

## 1. Decision and Boundaries

The approved target is:

```text
Raw archives -> cleaning/PIT gates -> Parquet analytical facts -> DuckDB queries
                                      SQLite transactional/governance state
                                                     -> quant research and reports
```

Keep in SQLite:

- scheduler, job, run, source-audit, and data-quality state;
- simulated accounts, orders, fills, positions, and ledgers;
- small dimensions, calendars, catalogs, and configuration snapshots;
- AI corpus and other stores whose dominant access remains transactional or indexed document lookup, unless a separate benchmark proves otherwise.

Candidate analytical migration tables, in order:

1. `market_daily_bars`
2. `market_daily_basic`
3. `market_adj_factors`
4. `market_index_bars`
5. `market_financial_factors`
6. ETF intraday bars

Non-goals:

- no big-bang replacement of SQLite;
- no production database mutation during P0 inventory work;
- no deletion of QFQ rows until `qfq_asof` and strategy equivalence are independently proven;
- no PostgreSQL migration unless multi-user or multi-writer requirements become real;
- no new strategy factors or changed trading semantics as part of storage migration.

## 2. Phase Gates

| Phase | Purpose | Entry gate | Exit gate |
| --- | --- | --- | --- |
| Storage P0 | Govern current SQLite estate | Current production files remain untouched | Reproducible inventory, index findings, retention/backup policy, connection policy |
| Storage P1 | Benchmark Parquet/DuckDB pilot | P0 evidence reviewed | Measured storage, latency, memory, PIT correctness, and incremental-write results |
| Storage P2 | Add storage abstraction and shadow reads | P1 admission thresholds pass | SQLite and DuckDB backends return equivalent governed results |
| Storage P3 | Migrate fact tables incrementally | P2 shadow comparisons pass | Per-table cutover, rollback, and operational runbook verified |

---

## 3. Storage P0 — SQLite Governance Baseline

### Task P0.1: Archive the decision and publish the roadmap

**Files:**
- Create: `docs/data_governance/logs/2026-08-14-sqlite-storage-architecture-assessment.md`
- Create: `docs/archive/superpowers/plans/2026-08-14-hybrid-data-storage-migration.md`
- Modify: `docs/DEVELOPMENT_PLAN.md`

- [x] Preserve the architecture assessment as a dated project log.
- [x] Declare the hybrid target and non-goals.
- [x] Add Storage P0-P3 phases, gates, validation, and rollback requirements to the project development plan.

### Task P0.2: Build a read-only SQLite capacity audit

**Files:**
- Create: `quant/data_governance/sqlite_capacity.py`
- Create: `tests/test_sqlite_capacity.py`
- Modify: `quant/cli_commands/data_governance.py`
- Modify: `quant/cli.py`
- Modify: `tests/test_cli_data_governance_commands.py`

- [x] **Step 1: Write failing discovery and inventory tests**

Create temporary SQLite databases and backups. Assert that the audit discovers primary `*.sqlite` files separately from `.sqlite.bak*`, reports file/page/freelist/journal metadata, and never opens a database for writing.

- [x] **Step 2: Run the focused tests and verify RED**

Run:

```bash
PYTHONPATH="$PWD" /Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q tests/test_sqlite_capacity.py
```

Expected: failure because `quant.data_governance.sqlite_capacity` does not exist.

- [x] **Step 3: Implement minimal read-only inventory**

Implement URI `mode=ro` connections with `PRAGMA query_only=ON`, filesystem discovery under `data/`, page metadata, object sizes through `dbstat`, optional row counts, optional `quick_check`, and structured warnings without modifying the inspected database.

- [x] **Step 4: Add exact redundant-index detection**

Compare ordered key columns from `PRAGMA index_xinfo`. Report a non-unique index as covered when a unique or primary-key autoindex has the same ordered key and neither index is partial. Do not issue `DROP INDEX`.

- [x] **Step 5: Write Markdown and JSON artifacts**

Default output:

```text
reports/database_health/sqlite_capacity/
  sqlite_capacity_report.md
  sqlite_capacity_report.json
```

Include primary database total bytes, backup total bytes, table/index bytes, row counts when requested, integrity status, duplicate-index findings, and per-database errors.

- [x] **Step 6: Add `db-capacity` CLI**

Required contract:

```bash
./runit db-capacity --config config.yaml
./runit db-capacity --config config.yaml --quick-check --row-counts
./runit db-capacity --config config.yaml --output-dir /tmp/sqlite-capacity
```

The command is read-only and exits non-zero only for inspection errors or failed integrity checks, not merely because a database is large.

- [x] **Step 7: Verify GREEN**

Run focused module and CLI tests, then existing data-governance CLI regression tests.

Execution evidence (2026-08-14):

- focused capacity/CLI/governance/maintenance tests: `35 passed`;
- complete repository suite: `837 passed, 2 failed`; both failures are pre-existing and outside the changed files (`data_update` mock signature and historical report-path policy);
- real read-only deep audit: 14 databases, 5 named backups, 0 inspection/integrity errors;
- `a_share_history.sqlite`: `quick_check=ok`, 27,371,467 daily-bar rows, 2011-01-04 through 2026-08-14;
- static 400 MiB maintenance database copy retained identical size and mtime before/after deep audit;
- Ruff was unavailable in the current virtual environment; compile checks and `git diff --check` passed.

### Task P0.3: Index and optimizer governance

**Files:**
- Create: `docs/data_governance/SQLITE_INDEX_GOVERNANCE.md`
- Modify after separate production approval: `quant/data_governance/import_history.py`, `quant/data_governance/etf_store.py`, `quant/data_governance/macro_history.py`
- Create: `tests/test_sqlite_index_governance.py`

- [x] Record exact duplicate/covered index findings with byte cost.
- [x] Benchmark removal in a copied database.
- [x] Run representative symbol-range, date-cross-section, PIT adjustment, and daily-basic join queries before and after.
- [x] Test `ANALYZE`/`PRAGMA optimize` only on the copy.
- [x] Propose a production mutation separately; do not mutate the main local database as part of the audit command.

### Task P0.4: Maintenance-event write amplification, archive, and retention

**Files:**
- Modify: `quant/maintenance_orchestrator.py`
- Modify: `config.yaml`
- Create: `tests/test_maintenance_event_retention.py`
- Local-only archive target: `archive/maintenance/events/YYYY-MM.jsonl.gz` plus manifest/checksum

`maintenance_events` contains scheduler `tick_decision` operational logs, not market, policy, news, strategy, or backtest inputs. `maintain status` reads the latest row per task; `maintenance_runs` records actual executions and is outside this retention scope.

- [ ] Map and test every reader of `maintenance_events`, `maintenance_runs`, state files, and success stamps.
- [ ] Add a per-task current-state table or equivalent upserted state so current status is independent from retained history.
- [ ] Write RED tests proving unchanged decisions do not append a new detailed event on every minute tick.
- [ ] Append detailed events only when decision/reason changes, a scheduled/retry/blocked transition occurs, or a configured low-frequency heartbeat is due.
- [ ] Default detailed retention to 90 days and always preserve at least the newest event for each task.
- [ ] Implement a read-only dry-run report listing cutoff, rows, tasks, min/max timestamps, target archive partitions, and estimated bytes.
- [ ] Archive eligible rows by month to local-only compressed JSONL, write row count and SHA-256 manifest, reopen and verify the archive, then delete only the verified event IDs in a bounded transaction.
- [ ] Make reruns idempotent and fail closed: archive or verification failure performs no deletion.
- [ ] Preserve `maintenance_runs` and all strategy/data databases without retention changes.
- [ ] Verify `maintain status`, retries, recovery, and incident queries before and after on a copied state database.

As of 2026-08-14 the observed event history spans about 68 days, so a 90-day default would currently produce a zero-row deletion plan.

### Task P0.5: Backup and connection policy

**Files:**
- Create: `docs/data_governance/SQLITE_BACKUP_AND_CONNECTION_POLICY.md`
- Create: `quant/data_governance/sqlite_connection.py`
- Create: `tests/test_sqlite_connection.py`
- Modify consumers incrementally; no mass mechanical replacement

- [ ] Define backup retention, compression, checksum, restore-test, and local-only rules.
- [ ] Define read-only URI connections, `busy_timeout`, transaction ownership, and error reporting.
- [ ] Benchmark WAL on copied databases under scheduler plus Web-reader contention before any production enablement.
- [ ] Prohibit multiple Web dispatchers from owning the same SQLite task queue without lease/claim protection.

Storage P0 exit criteria:

- current databases can be inventoried without mutation;
- duplicate-index and backup amplification are machine-readable;
- integrity checking is opt-in and reproducible;
- retention and connection policies are documented;
- no production data has been deleted, vacuumed, or reformatted.

---

## 4. Storage P1 — Parquet/DuckDB Pilot

### Task P1.1: Dependency and experiment isolation

- [ ] Add DuckDB/Parquet dependencies only in a dedicated experiment group or worktree.
- [ ] Record versions and keep production CLI importable without optional dependencies.
- [ ] Select a bounded pilot: `market_daily_bars`, 2024-01-01 through 2026-08-14.

### Task P1.2: Canonical export contract

- [ ] Define schema, nullability, units, primary-key semantics, `market`, `symbol`, `date`, and `adjust_type` contracts.
- [ ] Partition by dataset and year; avoid per-symbol small files.
- [ ] Write partition manifests with row counts, min/max dates, schema hash, source database fingerprint, and checksum.
- [ ] Make export resumable and idempotent.

### Task P1.3: Benchmark harness

Measure on SQLite and DuckDB/Parquet:

- single-symbol history;
- one-day full-market cross section;
- two-year full-market panel;
- five-year date aggregation;
- daily bars joined to daily basic;
- `qfq_asof` construction;
- incremental append/partition replacement;
- storage size, elapsed time, and peak memory;
- backup and restore duration.

Admission thresholds:

- at least 30% measured storage reduction;
- at least 2x improvement for broad analytical scans;
- no unacceptable single-symbol regression;
- exact key/date coverage and acceptable numeric tolerance;
- unchanged strategy dates, orders, and gate outcomes;
- deterministic incremental recovery.

If these thresholds fail, remain on governed SQLite and document why.

---

## 5. Storage P2 — Store Abstraction and Shadow Reads

### Task P2.1: Introduce the interface

```text
HistoryStore
├─ SQLiteHistoryStore
└─ DuckDBParquetHistoryStore
```

Required operations:

```text
load_daily
load_daily_basic
load_adjustment_factors
load_index_bars
```

- [ ] Preserve existing return columns, dtypes, ordering, price modes, and as-of semantics.
- [ ] Centralize backend selection in configuration.
- [ ] Keep SQLite as the default until shadow-read gates pass.

### Task P2.2: Shadow comparison

- [ ] Execute both backends for bounded requests.
- [ ] Compare keys, row counts, dates, nulls, values, and ordering.
- [ ] Persist mismatch reports without silently falling back.
- [ ] Run representative strategies and compare signals, rankings, orders, and metrics.

### Task P2.3: Operational integration

- [ ] Integrate freshness and partition health into `db-health` or its successor.
- [ ] Add scheduler-safe incremental refresh.
- [ ] Document recovery when a partition or manifest is incomplete.

---

## 6. Storage P3 — Incremental Cutover

Migrate one table at a time in this order:

1. `market_daily_bars`
2. `market_daily_basic`
3. `market_adj_factors`
4. `market_index_bars`
5. `market_financial_factors`
6. ETF intraday bars

For every table:

- [ ] freeze a source as-of and source fingerprint;
- [ ] export and validate all partitions;
- [ ] run shadow reads and strategy regressions;
- [ ] switch reads behind configuration;
- [ ] run at least one normal maintenance cycle;
- [ ] verify reports, strategy gates, and simulated accounts;
- [ ] retain SQLite rollback assets according to the approved retention policy;
- [ ] document rollback and execute a restore drill before declaring cutover complete.

QFQ policy gate:

- keep BFQ and adjustment factors as canonical candidates;
- do not remove stored QFQ until current-QFQ and `qfq_asof` equivalence, performance, and all strategy regressions pass;
- treat any change in ranking, rebalance date, order, or admission result as a blocking failure.

---

## 7. PostgreSQL Escalation Gate

Re-evaluate PostgreSQL only when one or more are demonstrated:

- multiple users require concurrent writes;
- multiple Web/API instances are required;
- remote transactional access becomes a supported product boundary;
- SQLite lock contention exceeds the agreed SLO after connection governance;
- high-availability or point-in-time server recovery becomes mandatory.

PostgreSQL is not the default destination for analytical fact tables; the Parquet/DuckDB benchmark remains a separate decision.

---

## 8. Verification and Rollback

No phase is complete without fresh evidence:

- focused unit and CLI tests;
- database integrity and schema checks;
- row/key/date/null/checksum comparisons;
- PIT/as-of leakage tests;
- strategy and simulated-execution regression tests;
- performance and peak-memory measurements;
- backup restore drill;
- documented rollback command and retained source asset.

A new backend may be implemented but must not be called production-usable until the real operational chain—scheduler, storage, freshness, consumer reads, reports, and rollback—has been exercised.
