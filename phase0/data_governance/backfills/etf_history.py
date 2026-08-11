from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Protocol

import pandas as pd

from phase0.config import load_config
from phase0.data_access.providers.tushare import (
    TushareAPIError,
    TushareConfig,
    TusharePermissionError,
    TushareTokenError,
    fetch_tushare_etf_adj_factors,
    fetch_tushare_etf_daily,
    tushare_config,
)
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
    resolve_etf_universe,
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


class ETFHistoryProvider(Protocol):
    def daily(self, ts_code: str, start_date: date, end_date: date) -> pd.DataFrame:
        raise NotImplementedError

    def adj_factor(self, ts_code: str, start_date: date, end_date: date) -> pd.DataFrame:
        raise NotImplementedError


@dataclass(frozen=True)
class ETFBackfillResult:
    run_id: str
    status: str
    target_tasks: int
    succeeded_tasks: int
    empty_tasks: int
    failed_tasks: int
    inserted_rows: int
    db_path: Path

    @property
    def exit_code(self) -> int:
        return 0 if self.status == "ok" else 2


@dataclass(frozen=True)
class ETFBackfillDryRunResult:
    manifest: ETFUniverseManifest
    task_specs: tuple[ETFBackfillTaskSpec, ...]
    symbol_count: int
    chunk_count: int
    dataset_count: int
    provider_call_count: int
    effective_symbol_limit: int
    effective_task_limit: int
    symbol_headroom: int
    task_headroom: int


@dataclass
class MonotonicRateLimiter:
    max_requests_per_minute: int
    clock: Callable[[], float] = time.monotonic
    sleeper: Callable[[float], None] = time.sleep
    _last_request_at: float | None = None

    def wait(self) -> None:
        if self.max_requests_per_minute <= 0:
            raise ValueError("max_requests_per_minute must be positive")
        now = self.clock()
        if self._last_request_at is not None:
            delay = (60.0 / self.max_requests_per_minute) - (now - self._last_request_at)
            if delay > 0:
                self.sleeper(delay)
        self._last_request_at = self.clock()


@dataclass(frozen=True)
class TushareETFHistoryProvider:
    cfg: TushareConfig

    def daily(self, ts_code: str, start_date: date, end_date: date) -> pd.DataFrame:
        return fetch_tushare_etf_daily(ts_code, start_date=start_date, end_date=end_date, cfg=self.cfg)

    def adj_factor(self, ts_code: str, start_date: date, end_date: date) -> pd.DataFrame:
        return fetch_tushare_etf_adj_factors(ts_code, start_date=start_date, end_date=end_date, cfg=self.cfg)


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


def build_etf_dry_run_result(
    manifest: ETFUniverseManifest,
    specs: list[ETFBackfillTaskSpec],
    *,
    symbol_cap: int,
    task_cap: int,
) -> ETFBackfillDryRunResult:
    symbol_count = len({member.symbol for member in manifest.members})
    chunk_count = len({
        (spec.sector, spec.symbol, spec.chunk_start, spec.chunk_end)
        for spec in specs
    })
    dataset_count = len({spec.dataset for spec in specs})
    return ETFBackfillDryRunResult(
        manifest=manifest,
        task_specs=tuple(specs),
        symbol_count=symbol_count,
        chunk_count=chunk_count,
        dataset_count=dataset_count,
        provider_call_count=len(specs),
        effective_symbol_limit=symbol_cap,
        effective_task_limit=task_cap,
        symbol_headroom=symbol_cap - symbol_count,
        task_headroom=task_cap - len(specs),
    )


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


def _task_key(task: ETFBackfillTask) -> tuple[object, ...]:
    return (
        task.run_id,
        task.sector,
        task.symbol,
        task.dataset,
        task.chunk_start.isoformat(),
        task.chunk_end.isoformat(),
    )


def _sanitize_error(exc: Exception) -> str:
    text = str(exc).replace("\n", " ").strip()
    for key, value in os.environ.items():
        if value and ("TOKEN" in key.upper() or "API_KEY" in key.upper()):
            text = text.replace(value, "<redacted>")
    text = re.sub(
        r"(?i)\b(token|api[_-]?key|authorization)\s*[:=]\s*[^\s,;]+",
        lambda match: f"{match.group(1)}=<redacted>",
        text,
    )
    text = re.sub(r"(?i)\bbearer\s+[^\s,;]+", "Bearer <redacted>", text)
    return text[:1000] or exc.__class__.__name__


def _is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, (TusharePermissionError, TushareTokenError)):
        return False
    return isinstance(exc, (TushareAPIError, ConnectionError, TimeoutError, OSError))


def _validate_task_frame(task: ETFBackfillTask, frame: pd.DataFrame) -> None:
    if frame.empty:
        return
    required = {"symbol", "date"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"provider frame missing required columns: {','.join(missing)}")
    symbols = {str(value) for value in frame["symbol"].dropna().unique()}
    if symbols != {task.symbol}:
        raise ValueError(f"provider returned symbols outside task key: {sorted(symbols)}")
    if "ts_code" in frame.columns:
        ts_codes = {str(value).upper() for value in frame["ts_code"].dropna().unique()}
        if ts_codes and ts_codes != {task.ts_code.upper()}:
            raise ValueError(f"provider returned ts_codes outside task key: {sorted(ts_codes)}")
    parsed = pd.to_datetime(frame["date"], errors="coerce")
    if parsed.isna().any():
        raise ValueError("provider returned invalid task dates")
    dates = parsed.dt.date
    if dates.min() < task.chunk_start or dates.max() > task.chunk_end:
        raise ValueError("provider returned dates outside task key")
    if task.dataset == "daily" and "price_mode" in frame.columns:
        modes = {str(value).lower() for value in frame["price_mode"].dropna().unique()}
        if modes and modes != {"raw"}:
            raise ValueError("ETF history backfill accepts raw daily prices only")


def _call_provider(provider: ETFHistoryProvider, task: ETFBackfillTask) -> pd.DataFrame:
    if task.dataset == "daily":
        return provider.daily(task.ts_code, task.chunk_start, task.chunk_end)
    if task.dataset == "adj_factor":
        return provider.adj_factor(task.ts_code, task.chunk_start, task.chunk_end)
    raise ValueError(f"unsupported ETF history dataset: {task.dataset}")


def _terminal_status(counts: dict[str, int]) -> str:
    if counts["target_tasks"] > 0 and counts["succeeded_tasks"] == counts["target_tasks"]:
        return "ok"
    if counts["succeeded_tasks"] > 0:
        return "partial"
    return "failed"


def execute_etf_backfill_run(
    db_path: Path,
    run_id: str,
    *,
    provider: ETFHistoryProvider,
    max_requests_per_minute: int,
    max_retries: int,
    retry_backoff_seconds: float,
    stale_running_minutes: int,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> ETFBackfillResult:
    """Execute persisted pending/failed tasks and return terminal run counts."""
    if max_requests_per_minute <= 0:
        raise ETFBackfillPlanError("max_requests_per_minute must be positive")
    if max_retries <= 0:
        raise ETFBackfillPlanError("max_retries must be positive")
    if retry_backoff_seconds < 0:
        raise ETFBackfillPlanError("retry_backoff_seconds must not be negative")
    if stale_running_minutes < 0:
        raise ETFBackfillPlanError("stale_running_minutes must not be negative")

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    limiter = MonotonicRateLimiter(max_requests_per_minute, clock=clock, sleeper=sleeper)
    inserted_rows = 0
    with sqlite3.connect(db_path) as conn:
        ensure_etf_schema(conn)
        if conn.execute("SELECT 1 FROM etf_backfill_runs WHERE run_id=?", (run_id,)).fetchone() is None:
            raise ETFResumeMismatchError(f"unknown run_id: {run_id}")
        tasks = load_resumable_tasks(
            conn,
            run_id,
            stale_running_minutes=stale_running_minutes,
        )
        started_at = _iso(datetime.now())
        with conn:
            conn.execute(
                "UPDATE etf_backfill_runs SET status='running',started_at=COALESCE(started_at,?),finished_at=NULL,last_error=NULL WHERE run_id=?",
                (started_at, run_id),
            )

        for task in tasks:
            key = _task_key(task)
            task_started_at = _iso(datetime.now())
            with conn:
                conn.execute(
                    """UPDATE etf_backfill_tasks
                    SET status='running',attempt_count=attempt_count+1,started_at=COALESCE(started_at,?),updated_at=?,finished_at=NULL,last_error=NULL
                    WHERE run_id=? AND sector=? AND symbol=? AND dataset=? AND chunk_start=? AND chunk_end=?""",
                    (task_started_at, task_started_at, *key),
                )

            frame: pd.DataFrame | None = None
            final_error: Exception | None = None
            for attempt in range(max_retries):
                try:
                    limiter.wait()
                    frame = _call_provider(provider, task)
                    if not isinstance(frame, pd.DataFrame):
                        raise TypeError("ETF history provider must return a pandas DataFrame")
                    _validate_task_frame(task, frame)
                    final_error = None
                    break
                except Exception as exc:
                    final_error = exc
                    if attempt + 1 >= max_retries or not _is_retryable_error(exc):
                        break
                    if retry_backoff_seconds > 0:
                        sleeper(retry_backoff_seconds * (attempt + 1))

            finished_at = _iso(datetime.now())
            if final_error is not None:
                error_text = _sanitize_error(final_error)
                with conn:
                    conn.execute(
                        """UPDATE etf_backfill_tasks
                        SET status='failed',fetched_rows=0,inserted_rows=0,last_error=?,updated_at=?,finished_at=?
                        WHERE run_id=? AND sector=? AND symbol=? AND dataset=? AND chunk_start=? AND chunk_end=?""",
                        (error_text, finished_at, finished_at, *key),
                    )
                    counts = refresh_run_counts(conn, run_id)
                if progress_callback is not None:
                    progress_callback({"run_id": run_id, "task": key[1:], "status": "failed", "error": error_text, **counts})
                continue

            assert frame is not None
            fetched_rows = len(frame)
            with conn:
                task_inserted = 0
                task_status = "empty"
                if not frame.empty:
                    if task.dataset == "daily":
                        task_inserted = upsert_etf_daily_bars(conn, frame, fetched_at=finished_at)
                    else:
                        task_inserted = upsert_etf_adj_factors(conn, frame, fetched_at=finished_at)
                    task_status = "succeeded"
                conn.execute(
                    """UPDATE etf_backfill_tasks
                    SET status=?,fetched_rows=?,inserted_rows=?,last_error=NULL,updated_at=?,finished_at=?
                    WHERE run_id=? AND sector=? AND symbol=? AND dataset=? AND chunk_start=? AND chunk_end=?""",
                    (task_status, fetched_rows, task_inserted, finished_at, finished_at, *key),
                )
                counts = refresh_run_counts(conn, run_id)
            inserted_rows += task_inserted
            if progress_callback is not None:
                progress_callback({"run_id": run_id, "task": key[1:], "status": task_status, "fetched_rows": fetched_rows, "inserted_rows": task_inserted, **counts})

        with conn:
            counts = refresh_run_counts(conn, run_id)
            status = _terminal_status(counts)
            finished_at = _iso(datetime.now())
            conn.execute(
                "UPDATE etf_backfill_runs SET status=?,finished_at=?,last_error=NULL WHERE run_id=?",
                (status, finished_at, run_id),
            )
            total_inserted = conn.execute(
                "SELECT COALESCE(SUM(inserted_rows),0) FROM etf_backfill_tasks WHERE run_id=?",
                (run_id,),
            ).fetchone()[0]
    return ETFBackfillResult(
        run_id=run_id,
        status=status,
        inserted_rows=int(total_inserted),
        db_path=db_path,
        **counts,
    )


def _mapping(value: object, *, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ETFBackfillPlanError(f"{name} configuration must be a mapping")
    return value


def backfill_etf_history_from_config(
    config_path: Path,
    *,
    universe_name: str | None = None,
    sectors: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    dry_run: bool = False,
    resume_run_id: str | None = None,
    limit_symbols: int | None = None,
    limit_tasks: int | None = None,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> ETFBackfillResult | ETFBackfillDryRunResult:
    """Resolve a dry-run, create a new persisted run, or resume an immutable run."""
    config_path = Path(config_path)
    phase0_cfg = load_config(config_path)
    history_cfg = _mapping(phase0_cfg.get("etf_history"), name="phase0.etf_history")
    data_sources_cfg = _mapping(phase0_cfg.get("data_sources", {}), name="phase0.data_sources")
    configured_limits = ETFBackfillLimits(
        max_symbols=int(history_cfg.get("max_symbols_per_run", 50)),
        max_tasks=int(history_cfg.get("max_tasks_per_run", 1000)),
    )
    db_path = Path(str(history_cfg.get("path", "data/etf_history.sqlite")))
    if not db_path.is_absolute():
        db_path = config_path.parent / db_path

    provider_cfg = tushare_config(_mapping(data_sources_cfg.get("tushare", {}), name="phase0.data_sources.tushare"))
    provider = TushareETFHistoryProvider(replace(provider_cfg, max_retries=1, retry_backoff=0))
    runner_settings = {
        "max_requests_per_minute": int(history_cfg.get("max_requests_per_minute", 100)),
        "max_retries": int(history_cfg.get("max_retries", 3)),
        "retry_backoff_seconds": float(history_cfg.get("retry_backoff_seconds", 2.0)),
        "stale_running_minutes": int(history_cfg.get("stale_running_minutes", 30)),
        "progress_callback": progress_callback,
    }

    if resume_run_id is not None:
        if any(
            value is not None
            for value in (universe_name, sectors, start_date, end_date, limit_symbols, limit_tasks)
        ) or dry_run:
            raise ETFBackfillPlanError("resume rejects universe, sector, dates, limits, and dry-run")
        with sqlite3.connect(db_path) as conn:
            ensure_etf_schema(conn)
            validate_resume_contract(conn, resume_run_id, phase0_cfg=phase0_cfg)
        return execute_etf_backfill_run(db_path, resume_run_id, provider=provider, **runner_settings)

    if universe_name is None or start_date is None or end_date is None:
        raise ETFBackfillPlanError("new run requires universe, start_date, and end_date")
    try:
        requested_start = date.fromisoformat(start_date)
        requested_end = date.fromisoformat(end_date)
    except ValueError as exc:
        raise ETFBackfillPlanError("start_date and end_date must be ISO dates") from exc
    if requested_start > requested_end:
        raise ETFBackfillPlanError("start_date must not be after end_date")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        ensure_etf_schema(conn)
        manifest = resolve_etf_universe(
            conn,
            phase0_cfg=phase0_cfg,
            universe_name=universe_name,
            requested_sectors=sectors,
            start_date=requested_start,
            end_date=requested_end,
        )
        specs = plan_etf_task_specs(manifest)
        symbol_cap, task_cap = enforce_requested_limits(
            manifest,
            specs,
            configured=configured_limits,
            limit_symbols=limit_symbols,
            limit_tasks=limit_tasks,
        )
        if dry_run:
            return build_etf_dry_run_result(
                manifest,
                specs,
                symbol_cap=symbol_cap,
                task_cap=task_cap,
            )
        run_id = create_etf_backfill_run(conn, manifest, limits=configured_limits)
    return execute_etf_backfill_run(db_path, run_id, provider=provider, **runner_settings)
