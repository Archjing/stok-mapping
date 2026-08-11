from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Protocol

import pandas as pd

from phase0.data_governance.etf_store import (
    ensure_etf_schema,
    insert_backfill_tasks,
    insert_manifest_members,
    refresh_run_counts,
    upsert_etf_adj_factors,
    upsert_etf_daily_bars,
)
from phase0.data_governance.etf_universe import (
    ETFManifestMember,
    ETFUniverseManifest,
    history_config_digest,
)


@dataclass(frozen=True)
class ETFBackfillTask:
    run_id: str
    sector: str
    symbol: str
    ts_code: str
    dataset: str
    chunk_start: date
    chunk_end: date
    status: str


@dataclass(frozen=True)
class ETFBackfillTaskSpec:
    sector: str
    symbol: str
    ts_code: str
    dataset: str
    chunk_start: date
    chunk_end: date


@dataclass(frozen=True)
class ETFBackfillLimits:
    max_symbols: int
    max_tasks: int


class ETFBackfillPlanError(RuntimeError):
    """The requested run exceeds limits or cannot produce a valid task set."""


class ETFResumeMismatchError(RuntimeError):
    """Current inputs do not match the persisted run contract."""


def annual_chunks(start: date, end: date) -> list[tuple[date, date]]:
    chunks: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(end, date(cursor.year, 12, 31))
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def plan_etf_task_specs(manifest: ETFUniverseManifest) -> list[ETFBackfillTaskSpec]:
    specs = [
        ETFBackfillTaskSpec(member.sector, member.symbol, member.ts_code, dataset, chunk_start, chunk_end)
        for member in manifest.members
        for chunk_start, chunk_end in annual_chunks(member.effective_start, member.effective_end)
        for dataset in ("daily", "adj_factor")
    ]
    return sorted(specs, key=lambda item: (item.sector, item.symbol, item.chunk_start, item.dataset))


def enforce_requested_limits(
    manifest: ETFUniverseManifest,
    specs: list[ETFBackfillTaskSpec],
    *,
    configured: ETFBackfillLimits,
    limit_symbols: int | None,
    limit_tasks: int | None,
) -> tuple[int, int]:
    if configured.max_symbols <= 0 or configured.max_tasks <= 0:
        raise ETFBackfillPlanError("configured ETF backfill limits must be positive")
    if limit_symbols is not None and limit_symbols <= 0:
        raise ETFBackfillPlanError("limit_symbols must be positive")
    if limit_tasks is not None and limit_tasks <= 0:
        raise ETFBackfillPlanError("limit_tasks must be positive")
    symbol_cap = min(configured.max_symbols, limit_symbols if limit_symbols is not None else configured.max_symbols)
    task_cap = min(configured.max_tasks, limit_tasks if limit_tasks is not None else configured.max_tasks)
    symbol_count = len({member.symbol for member in manifest.members})
    if symbol_count > symbol_cap:
        raise ETFBackfillPlanError(f"symbol count {symbol_count} exceeds max_symbols_per_run {symbol_cap}")
    if len(specs) > task_cap:
        raise ETFBackfillPlanError(f"task count {len(specs)} exceeds max_tasks_per_run {task_cap}")
    return symbol_cap, task_cap


def _iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()


def create_etf_backfill_run(
    conn: sqlite3.Connection,
    manifest: ETFUniverseManifest,
    *,
    limits: ETFBackfillLimits,
    now: datetime | None = None,
) -> str:
    specs = plan_etf_task_specs(manifest)
    enforce_requested_limits(manifest, specs, configured=limits, limit_symbols=None, limit_tasks=None)
    run_id = uuid.uuid4().hex
    timestamp = _iso(now or datetime.now())
    member_rows = [{
        "run_id": run_id, "universe_name": member.universe_name, "catalog_snapshot_id": manifest.catalog_snapshot_id,
        "sector": member.sector, "symbol": member.symbol, "ts_code": member.ts_code,
        "requested_start": member.requested_start.isoformat(), "requested_end": member.requested_end.isoformat(),
        "effective_start": member.effective_start.isoformat(), "effective_end": member.effective_end.isoformat(),
        "expected_tracking_index": member.expected_tracking_index, "resolved_tracking_index": member.resolved_tracking_index,
        "mapping_assertion_status": member.mapping_assertion_status,
    } for member in manifest.members]
    task_rows = [{
        "run_id": run_id, "sector": spec.sector, "symbol": spec.symbol, "ts_code": spec.ts_code,
        "dataset": spec.dataset, "chunk_start": spec.chunk_start.isoformat(), "chunk_end": spec.chunk_end.isoformat(),
        "status": "pending", "updated_at": timestamp,
    } for spec in specs]
    with conn:
        ensure_etf_schema(conn)
        conn.execute("INSERT INTO etf_backfill_runs(run_id,universe_name,requested_sectors_json,requested_start,requested_end,config_digest,catalog_snapshot_id,status,created_at) VALUES (?,?,?,?,?,?,?,'planned',?)", (run_id, manifest.universe_name, json.dumps(manifest.requested_sectors), manifest.requested_start.isoformat(), manifest.requested_end.isoformat(), manifest.config_digest, manifest.catalog_snapshot_id, timestamp))
        insert_manifest_members(conn, member_rows)
        insert_backfill_tasks(conn, task_rows)
        refresh_run_counts(conn, run_id)
    return run_id


def load_persisted_manifest(conn: sqlite3.Connection, run_id: str) -> ETFUniverseManifest:
    run = conn.execute("SELECT universe_name,requested_sectors_json,requested_start,requested_end,config_digest,catalog_snapshot_id FROM etf_backfill_runs WHERE run_id=?", (run_id,)).fetchone()
    if run is None:
        raise ETFResumeMismatchError(f"unknown run_id: {run_id}")
    universe, sectors_json, start_text, end_text, digest, snapshot = run
    rows = conn.execute("SELECT universe_name,catalog_snapshot_id,sector,symbol,ts_code,requested_start,requested_end,effective_start,effective_end,expected_tracking_index,resolved_tracking_index,mapping_assertion_status FROM etf_backfill_manifest_members WHERE run_id=? ORDER BY sector,symbol", (run_id,)).fetchall()
    if not rows:
        raise ETFResumeMismatchError("persisted manifest is empty")
    members: list[ETFManifestMember] = []
    for row in rows:
        if row[0] != universe or row[1] != snapshot or row[5] != start_text or row[6] != end_text:
            raise ETFResumeMismatchError("persisted manifest disagrees with run identity")
        members.append(ETFManifestMember(row[0], row[2], row[3], row[4], date.fromisoformat(row[5]), date.fromisoformat(row[6]), date.fromisoformat(row[7]), date.fromisoformat(row[8]), row[9], row[10], row[11]))
    return ETFUniverseManifest(universe, tuple(json.loads(sectors_json)), date.fromisoformat(start_text), date.fromisoformat(end_text), digest, snapshot, tuple(members))


def load_resumable_tasks(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    stale_running_minutes: int,
    now: datetime | None = None,
) -> list[ETFBackfillTask]:
    current = now or datetime.now()
    cutoff = _iso(current - timedelta(minutes=stale_running_minutes))
    with conn:
        conn.execute("UPDATE etf_backfill_tasks SET status='pending',last_error='reset stale running task',updated_at=? WHERE run_id=? AND status='running' AND updated_at<?", (_iso(current), run_id, cutoff))
    rows = conn.execute("SELECT run_id,sector,symbol,ts_code,dataset,chunk_start,chunk_end,status FROM etf_backfill_tasks WHERE run_id=? AND status IN ('pending','failed') ORDER BY sector,symbol,chunk_start,dataset", (run_id,)).fetchall()
    return [ETFBackfillTask(row[0], row[1], row[2], row[3], row[4], date.fromisoformat(row[5]), date.fromisoformat(row[6]), row[7]) for row in rows]


def validate_resume_contract(conn: sqlite3.Connection, run_id: str, *, phase0_cfg: dict[str, object]) -> ETFUniverseManifest:
    manifest = load_persisted_manifest(conn, run_id)
    status = conn.execute("SELECT status FROM etf_catalog_sync_runs WHERE snapshot_id=?", (manifest.catalog_snapshot_id,)).fetchone()
    if status is None or status[0] != "ok":
        raise ETFResumeMismatchError("catalog_snapshot_id is not a completed catalog")
    current_digest = history_config_digest(phase0_cfg, manifest.universe_name, manifest.requested_sectors)
    if current_digest != manifest.config_digest:
        raise ETFResumeMismatchError("config_digest does not match current history configuration")
    return manifest
