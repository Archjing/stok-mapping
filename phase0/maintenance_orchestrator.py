from __future__ import annotations

import json
import os
import signal
import sqlite3
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from phase0.config import load_config


VALID_DECISIONS = {"will_run", "skipped", "blocked"}
VALID_RUN_STATUS = {"pending", "running", "succeeded", "failed", "skipped", "blocked", "cancelled", "exited_unknown"}
LONG_BACKFILL_TASK = "tushare_financial_backfill"


@dataclass(frozen=True)
class MaintenanceTaskSpec:
    name: str
    schedule_type: str
    schedule_value: str
    command: list[str]
    log_path: str
    success_stamp: str
    lock_dir: str
    health_scope: str = "scheduler"
    health_fail_on: str = "warning"
    weekdays_only: bool = True
    monday_only: bool = False
    enabled: bool = True
    description: str = ""
    tags: list[str] = field(default_factory=list)
    retry_window_minutes: int = 0
    retry_interval_minutes: int = 5
    max_retries: int = 0
    state_path: str = ""


@dataclass(frozen=True)
class MaintenanceDecision:
    task_name: str
    decision: str
    reason: str
    scheduled_time: str
    command: list[str]
    log_path: Path
    stamp_path: Path
    lock_path: Path
    health_scope: str
    health_fail_on: str
    state_path: Path
    retry_window_minutes: int
    retry_interval_minutes: int
    max_retries: int
    last_success_date: str = ""
    retry_count: int = 0


@dataclass(frozen=True)
class MaintenanceTickResult:
    status: str
    as_of: str
    dry_run: bool
    state_db: Path
    decisions: list[MaintenanceDecision]
    executed_runs: int


@dataclass(frozen=True)
class MaintenanceStatusRow:
    task_name: str
    enabled: bool
    schedule_type: str
    schedule_value: str
    last_decision: str
    last_reason: str
    last_tick_at: str
    last_success_at: str
    last_run_status: str
    last_error: str
    retry_count: int
    log_path: Path
    state_path: Path


@dataclass(frozen=True)
class MaintenanceShardStatusRow:
    run_id: int
    task_name: str
    shard_index: int
    shard_count: int
    status: str
    pid: int | None
    started_at: str
    finished_at: str
    exit_code: int | None
    log_path: Path


@dataclass(frozen=True)
class MaintenanceStatusResult:
    state_db: Path
    generated_at: str
    rows: list[MaintenanceStatusRow]
    shards: list[MaintenanceShardStatusRow]


@dataclass(frozen=True)
class MaintenanceLongRunResult:
    status: str
    task_name: str
    run_id: int | None
    state_db: Path
    shard_rows: list[MaintenanceShardStatusRow]
    message: str = ""


def _resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _load_maintenance_cfg(config_path: Path) -> tuple[Path, dict[str, Any]]:
    phase0_cfg = load_config(config_path)
    orchestrator_cfg = dict(phase0_cfg.get("maintenance_orchestrator", {}) or {})
    root = config_path.parent
    return root, orchestrator_cfg


def _env_flag(name: str, default: str = "1") -> bool:
    return str(os.environ.get(name, default)).strip() != "0"


def _env_value(name: str, default: str) -> str:
    value = str(os.environ.get(name, "")).strip()
    return value or default


def _default_registry(config_path: Path) -> list[MaintenanceTaskSpec]:
    root = config_path.parent
    python_bin = root / ".venv" / "bin" / "python"
    state_dir = root / "logs" / "scheduler"
    lock_dir = state_dir / "locks"
    config_arg = str(config_path)

    def make_spec(
        *,
        name: str,
        schedule_value: str,
        log_path: str,
        command: list[str],
        health_scope: str,
        monday_only: bool = False,
        weekdays_only: bool = True,
        description: str,
        tags: list[str],
    ) -> MaintenanceTaskSpec:
        return MaintenanceTaskSpec(
            name=name,
            schedule_type="time",
            schedule_value=schedule_value,
            command=command,
            log_path=log_path,
            success_stamp=str(state_dir / f"{name}.last"),
            lock_dir=str(lock_dir / f"{name}.lock"),
            health_scope=health_scope,
            health_fail_on=_env_value("SCHEDULER_HEALTH_FAIL_ON", "warning"),
            monday_only=monday_only,
            weekdays_only=weekdays_only,
            description=description,
            tags=tags,
            retry_window_minutes=int(_env_value(f"{name.upper()}_RETRY_WINDOW_MINUTES", "20")),
            retry_interval_minutes=int(_env_value(f"{name.upper()}_RETRY_INTERVAL_MINUTES", "5")),
            max_retries=int(_env_value(f"{name.upper()}_MAX_RETRIES", "3")),
            state_path=str(state_dir / f"{name}.state"),
        )

    return [
        make_spec(
            name="financial_factors",
            schedule_value=_env_value("FINANCIAL_FACTORS_TIME", "03:30"),
            log_path="logs/financial_factors_update.log",
            command=[str(python_bin), "-m", "phase0.cli", "update-financials", "--config", config_arg],
            health_scope=_env_value("FINANCIAL_FACTORS_HEALTH_SCOPE", "scheduler"),
            monday_only=True,
            weekdays_only=False,
            description="Weekly A-share financial factor refresh",
            tags=["scheduler", "financial"],
        ),
        make_spec(
            name="daily_brief",
            schedule_value=_env_value("DAILY_BRIEF_TIME", "07:20"),
            log_path="logs/daily_brief_pipeline.log",
            command=[str(python_bin), "-m", "phase0.cli", "brief", "watchlist", "--config", config_arg],
            health_scope=_env_value("DAILY_BRIEF_HEALTH_SCOPE", "scheduler"),
            description="Premarket watchlist and brief pipeline",
            tags=["scheduler", "brief"],
        ),
        make_spec(
            name="hk_market_history",
            schedule_value=_env_value("HK_MARKET_HISTORY_TIME", "16:20"),
            log_path="logs/hk_market_history_update.log",
            command=[str(python_bin), "-m", "phase0.cli", "update-hk-market-history", "--config", config_arg],
            health_scope=_env_value("HK_MARKET_HISTORY_HEALTH_SCOPE", "scheduler"),
            description="Hong Kong market history refresh",
            tags=["scheduler", "hk"],
        ),
        make_spec(
            name="a_share_history",
            schedule_value=_env_value("A_SHARE_HISTORY_TIME", "16:30"),
            log_path="logs/manual_history_update.log",
            command=[str(python_bin), "-m", "phase0.cli", "update-history", "--config", config_arg],
            health_scope=_env_value("A_SHARE_HISTORY_HEALTH_SCOPE", "scheduler"),
            description="A-share local history refresh",
            tags=["scheduler", "cn"],
        ),
        make_spec(
            name="us_market_history",
            schedule_value=_env_value("US_MARKET_HISTORY_TIME", "17:10"),
            log_path="logs/us_market_history_update.log",
            command=[str(python_bin), "-m", "phase0.cli", "update-us-market-history", "--config", config_arg],
            health_scope=_env_value("US_MARKET_HISTORY_HEALTH_SCOPE", "scheduler"),
            description="US market history refresh",
            tags=["scheduler", "us"],
        ),
    ]


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS maintenance_registry (
            task_name TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL,
            schedule_type TEXT NOT NULL,
            schedule_value TEXT NOT NULL,
            health_scope TEXT NOT NULL,
            health_fail_on TEXT NOT NULL,
            weekdays_only INTEGER NOT NULL,
            monday_only INTEGER NOT NULL,
            log_path TEXT NOT NULL,
            success_stamp TEXT NOT NULL,
            lock_dir TEXT NOT NULL,
            state_path TEXT NOT NULL,
            command_json TEXT NOT NULL,
            description TEXT NOT NULL,
            tags_json TEXT NOT NULL,
            retry_window_minutes INTEGER NOT NULL DEFAULT 0,
            retry_interval_minutes INTEGER NOT NULL DEFAULT 5,
            max_retries INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS maintenance_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name TEXT NOT NULL,
            status TEXT NOT NULL,
            trigger_source TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            exit_code INTEGER,
            error_summary TEXT NOT NULL DEFAULT '',
            log_path TEXT NOT NULL DEFAULT '',
            report_path TEXT NOT NULL DEFAULT '',
            command_json TEXT NOT NULL DEFAULT '[]'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS maintenance_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            decision TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS maintenance_shards (
            shard_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            task_name TEXT NOT NULL,
            shard_index INTEGER NOT NULL,
            shard_count INTEGER NOT NULL,
            status TEXT NOT NULL,
            pid INTEGER,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            exit_code INTEGER,
            log_path TEXT NOT NULL DEFAULT '',
            command_json TEXT NOT NULL DEFAULT '[]',
            report_path TEXT NOT NULL DEFAULT '',
            error_summary TEXT NOT NULL DEFAULT ''
        )
        """
    )
    existing_columns = {
        str(row["name"])
        for row in conn.execute("PRAGMA table_info(maintenance_registry)").fetchall()
    }
    for column, ddl in [
        ("state_path", "ALTER TABLE maintenance_registry ADD COLUMN state_path TEXT NOT NULL DEFAULT ''"),
        ("retry_window_minutes", "ALTER TABLE maintenance_registry ADD COLUMN retry_window_minutes INTEGER NOT NULL DEFAULT 0"),
        ("retry_interval_minutes", "ALTER TABLE maintenance_registry ADD COLUMN retry_interval_minutes INTEGER NOT NULL DEFAULT 5"),
        ("max_retries", "ALTER TABLE maintenance_registry ADD COLUMN max_retries INTEGER NOT NULL DEFAULT 0"),
    ]:
        if column not in existing_columns:
            conn.execute(ddl)
    conn.commit()


def _sync_registry(conn: sqlite3.Connection, specs: list[MaintenanceTaskSpec], *, now_iso: str) -> None:
    for spec in specs:
        conn.execute(
            """
            INSERT INTO maintenance_registry (
                task_name, enabled, schedule_type, schedule_value, health_scope, health_fail_on,
                weekdays_only, monday_only, log_path, success_stamp, lock_dir, state_path,
                command_json, description, tags_json, retry_window_minutes, retry_interval_minutes,
                max_retries, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_name) DO UPDATE SET
                enabled=excluded.enabled,
                schedule_type=excluded.schedule_type,
                schedule_value=excluded.schedule_value,
                health_scope=excluded.health_scope,
                health_fail_on=excluded.health_fail_on,
                weekdays_only=excluded.weekdays_only,
                monday_only=excluded.monday_only,
                log_path=excluded.log_path,
                success_stamp=excluded.success_stamp,
                lock_dir=excluded.lock_dir,
                state_path=excluded.state_path,
                command_json=excluded.command_json,
                description=excluded.description,
                tags_json=excluded.tags_json,
                retry_window_minutes=excluded.retry_window_minutes,
                retry_interval_minutes=excluded.retry_interval_minutes,
                max_retries=excluded.max_retries,
                updated_at=excluded.updated_at
            """,
            (
                spec.name,
                1 if spec.enabled else 0,
                spec.schedule_type,
                spec.schedule_value,
                spec.health_scope,
                spec.health_fail_on,
                1 if spec.weekdays_only else 0,
                1 if spec.monday_only else 0,
                spec.log_path,
                spec.success_stamp,
                spec.lock_dir,
                spec.state_path,
                json.dumps(spec.command, ensure_ascii=True),
                spec.description,
                json.dumps(spec.tags, ensure_ascii=True),
                spec.retry_window_minutes,
                spec.retry_interval_minutes,
                spec.max_retries,
                now_iso,
            ),
        )
    conn.commit()


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _parse_task_state(path: Path) -> dict[str, Any]:
    raw = _read_text(path)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _write_task_state(path: Path, payload: dict[str, Any]) -> None:
    _write_text(path, json.dumps(payload, ensure_ascii=True, indent=2) + "\n")


def _in_retry_window(now: datetime, spec: MaintenanceTaskSpec, state: dict[str, Any]) -> bool:
    if spec.retry_window_minutes <= 0 or spec.max_retries <= 0:
        return False
    scheduled = now.replace(hour=int(spec.schedule_value[:2]), minute=int(spec.schedule_value[3:5]), second=0, microsecond=0)
    delta_minutes = int((now - scheduled).total_seconds() // 60)
    if delta_minutes < 0 or delta_minutes > spec.retry_window_minutes:
        return False
    retry_count = int(state.get("retry_count") or 0)
    if retry_count >= spec.max_retries:
        return False
    last_failure_at = str(state.get("last_failure_at") or "")
    if not last_failure_at:
        return False
    try:
        failed_at = datetime.fromisoformat(last_failure_at)
    except ValueError:
        return False
    minutes_since_failure = int((now - failed_at).total_seconds() // 60)
    return minutes_since_failure >= spec.retry_interval_minutes


def _evaluate_task(
    *,
    spec: MaintenanceTaskSpec,
    root: Path,
    now: datetime,
    today: str,
) -> MaintenanceDecision:
    log_path = _resolve_path(root, spec.log_path)
    stamp_path = _resolve_path(root, spec.success_stamp)
    lock_path = _resolve_path(root, spec.lock_dir)
    state_path = _resolve_path(root, spec.state_path)
    weekday = now.isoweekday()
    last_success = _read_text(stamp_path)
    state = _parse_task_state(state_path)
    now_hm = now.strftime("%H:%M")

    if not spec.enabled:
        return MaintenanceDecision(
            task_name=spec.name,
            decision="skipped",
            reason="task_disabled",
            scheduled_time=spec.schedule_value,
            command=spec.command,
            log_path=log_path,
            stamp_path=stamp_path,
            lock_path=lock_path,
            health_scope=spec.health_scope,
            health_fail_on=spec.health_fail_on,
            state_path=state_path,
            retry_window_minutes=spec.retry_window_minutes,
            retry_interval_minutes=spec.retry_interval_minutes,
            max_retries=spec.max_retries,
            last_success_date=last_success,
            retry_count=int(state.get("retry_count") or 0),
        )
    if spec.monday_only and weekday != 1:
        reason = f"not_monday(weekday={weekday})"
    elif spec.weekdays_only and weekday not in {1, 2, 3, 4, 5}:
        reason = f"not_weekday(weekday={weekday})"
    else:
        reason = ""
    if reason:
        return MaintenanceDecision(
            task_name=spec.name,
            decision="skipped",
            reason=reason,
            scheduled_time=spec.schedule_value,
            command=spec.command,
            log_path=log_path,
            stamp_path=stamp_path,
            lock_path=lock_path,
            health_scope=spec.health_scope,
            health_fail_on=spec.health_fail_on,
            state_path=state_path,
            retry_window_minutes=spec.retry_window_minutes,
            retry_interval_minutes=spec.retry_interval_minutes,
            max_retries=spec.max_retries,
            last_success_date=last_success,
            retry_count=int(state.get("retry_count") or 0),
        )
    if last_success == today:
        decision = "skipped"
        reason = f"already_succeeded_today({today})"
    elif lock_path.exists():
        decision = "blocked"
        reason = "lock_present"
    elif now_hm == spec.schedule_value:
        decision = "will_run"
        reason = f"scheduled_run(scope={spec.health_scope}, fail_on={spec.health_fail_on})"
    elif _in_retry_window(now, spec, state):
        decision = "will_run"
        reason = (
            f"retry_window(retry_count={int(state.get('retry_count') or 0)}, "
            f"interval={spec.retry_interval_minutes}m, window={spec.retry_window_minutes}m)"
        )
    else:
        decision = "skipped"
        reason = f"outside_schedule(now={now_hm}, expected={spec.schedule_value})"
    if decision == "will_run" and not _env_flag("SCHEDULER_HEALTH_ENABLED", "1"):
        reason = "health_gate_disabled"
    return MaintenanceDecision(
        task_name=spec.name,
        decision=decision,
        reason=reason,
        scheduled_time=spec.schedule_value,
        command=spec.command,
        log_path=log_path,
        stamp_path=stamp_path,
        lock_path=lock_path,
        health_scope=spec.health_scope,
        health_fail_on=spec.health_fail_on,
        state_path=state_path,
        retry_window_minutes=spec.retry_window_minutes,
        retry_interval_minutes=spec.retry_interval_minutes,
        max_retries=spec.max_retries,
        last_success_date=last_success,
        retry_count=int(state.get("retry_count") or 0),
    )


def _record_decisions(conn: sqlite3.Connection, decisions: list[MaintenanceDecision], *, created_at: str) -> None:
    for decision in decisions:
        payload = {
            "scheduled_time": decision.scheduled_time,
            "command": decision.command,
            "log_path": str(decision.log_path),
            "stamp_path": str(decision.stamp_path),
            "lock_path": str(decision.lock_path),
            "state_path": str(decision.state_path),
            "health_scope": decision.health_scope,
            "health_fail_on": decision.health_fail_on,
            "last_success_date": decision.last_success_date,
            "retry_count": decision.retry_count,
        }
        conn.execute(
            """
            INSERT INTO maintenance_events (
                task_name, event_type, decision, reason, created_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                decision.task_name,
                "tick_decision",
                decision.decision,
                decision.reason,
                created_at,
                json.dumps(payload, ensure_ascii=True),
            ),
        )
    conn.commit()


def _create_run(conn: sqlite3.Connection, decision: MaintenanceDecision, *, trigger_source: str, started_at: str) -> int:
    cursor = conn.execute(
        """
        INSERT INTO maintenance_runs (
            task_name, status, trigger_source, started_at, log_path, command_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            decision.task_name,
            "running",
            trigger_source,
            started_at,
            str(decision.log_path),
            json.dumps(decision.command, ensure_ascii=True),
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def _finish_run(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    status: str,
    finished_at: str,
    exit_code: int,
    error_summary: str,
) -> None:
    if status not in VALID_RUN_STATUS:
        raise ValueError(f"Unsupported run status: {status}")
    conn.execute(
        """
        UPDATE maintenance_runs
        SET status = ?, finished_at = ?, exit_code = ?, error_summary = ?
        WHERE run_id = ?
        """,
        (status, finished_at, exit_code, error_summary, run_id),
    )
    conn.commit()


def _create_long_run(conn: sqlite3.Connection, *, task_name: str, command: list[str], started_at: str) -> int:
    cursor = conn.execute(
        """
        INSERT INTO maintenance_runs (
            task_name, status, trigger_source, started_at, command_json
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (task_name, "running", "manual_orchestrator", started_at, json.dumps(command, ensure_ascii=True)),
    )
    conn.commit()
    return int(cursor.lastrowid)


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def _refresh_shards(conn: sqlite3.Connection) -> None:
    now_iso = datetime.now().isoformat(timespec="seconds")
    rows = conn.execute(
        """
        SELECT shard_id, pid, status
        FROM maintenance_shards
        WHERE status = 'running'
        """
    ).fetchall()
    for row in rows:
        pid = int(row["pid"]) if row["pid"] is not None else None
        if not _pid_alive(pid):
            conn.execute(
                """
                UPDATE maintenance_shards
                SET status = 'exited_unknown', finished_at = ?, error_summary = ?
                WHERE shard_id = ?
                """,
                (now_iso, "process_not_alive_exit_code_unknown", int(row["shard_id"])),
            )
    run_rows = conn.execute(
        """
        SELECT run_id
        FROM maintenance_runs
        WHERE task_name = ? AND status = 'running'
        """,
        (LONG_BACKFILL_TASK,),
    ).fetchall()
    for run in run_rows:
        run_id = int(run["run_id"])
        statuses = [
            str(item["status"])
            for item in conn.execute(
                "SELECT status FROM maintenance_shards WHERE run_id = ?",
                (run_id,),
            ).fetchall()
        ]
        if statuses and all(status != "running" for status in statuses):
            final_status = "succeeded" if all(status == "succeeded" for status in statuses) else "exited_unknown"
            conn.execute(
                """
                UPDATE maintenance_runs
                SET status = ?, finished_at = ?, error_summary = ?
                WHERE run_id = ?
                """,
                (final_status, now_iso, "all_shards_not_running", run_id),
            )
    conn.commit()


def _shard_rows(conn: sqlite3.Connection, root: Path, *, run_id: int | None = None) -> list[MaintenanceShardStatusRow]:
    query = """
        SELECT run_id, task_name, shard_index, shard_count, status, pid, started_at,
               COALESCE(finished_at, '') AS finished_at, exit_code, log_path
        FROM maintenance_shards
    """
    params: tuple[Any, ...] = ()
    if run_id is not None:
        query += " WHERE run_id = ?"
        params = (run_id,)
    query += " ORDER BY run_id DESC, shard_index ASC"
    rows = conn.execute(query, params).fetchall()
    return [
        MaintenanceShardStatusRow(
            run_id=int(row["run_id"]),
            task_name=str(row["task_name"]),
            shard_index=int(row["shard_index"]),
            shard_count=int(row["shard_count"]),
            status=str(row["status"]),
            pid=int(row["pid"]) if row["pid"] is not None else None,
            started_at=str(row["started_at"]),
            finished_at=str(row["finished_at"]),
            exit_code=int(row["exit_code"]) if row["exit_code"] is not None else None,
            log_path=_resolve_path(root, str(row["log_path"])),
        )
        for row in rows
    ]


def _build_financial_backfill_command(
    *,
    config_path: Path,
    shard_index: int,
    shard_count: int,
    start_period: str,
    end_period: str,
    max_requests_per_minute: int,
    retry_failed: bool,
    missing_fields_only: bool,
    limit_tasks: int | None,
) -> list[str]:
    python_bin = config_path.parent / ".venv" / "bin" / "python"
    command = [
        str(python_bin),
        "-m",
        "phase0.cli",
        "backfill-tushare-financials",
        "--config",
        str(config_path),
        "--start-period",
        start_period,
        "--end-period",
        end_period,
        "--max-requests-per-minute",
        str(max_requests_per_minute),
        "--shard-index",
        str(shard_index),
        "--shard-count",
        str(shard_count),
    ]
    if retry_failed:
        command.append("--retry-failed")
    if missing_fields_only:
        command.append("--missing-fields-only")
    if limit_tasks is not None:
        command.extend(["--limit-tasks", str(limit_tasks)])
    return command


def _append_log_line(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S %z')}] {message}\n")


def _run_health_gate(decision: MaintenanceDecision) -> tuple[bool, str]:
    if not _env_flag("SCHEDULER_HEALTH_ENABLED", "1"):
        return True, "health_gate_disabled"
    command = [
        decision.command[0],
        "-m",
        "phase0.cli",
        "db-health",
        "--config",
        decision.command[-1],
        "--scope",
        decision.health_scope,
        "--fail-on",
        decision.health_fail_on,
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode == 0:
        return True, result.stdout.strip()
    return False, result.stdout.strip() or "db-health failed"


def _acquire_lock(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        return False
    return True


def _release_lock(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        pass


def _run_task(
    conn: sqlite3.Connection,
    *,
    decision: MaintenanceDecision,
    trigger_source: str,
    now: datetime,
) -> int:
    started_at = now.isoformat(timespec="seconds")
    run_id = _create_run(conn, decision, trigger_source=trigger_source, started_at=started_at)
    _append_log_line(decision.log_path, f"start {decision.task_name}")

    if not _acquire_lock(decision.lock_path):
        _finish_run(
            conn,
            run_id=run_id,
            status="blocked",
            finished_at=datetime.now().isoformat(timespec="seconds"),
            exit_code=0,
            error_summary="lock_present",
        )
        return 0

    try:
        ok, gate_output = _run_health_gate(decision)
        if gate_output:
            with decision.log_path.open("a", encoding="utf-8") as handle:
                handle.write(gate_output + ("\n" if not gate_output.endswith("\n") else ""))
        if not ok:
            _write_task_state(
                decision.state_path,
                {
                    "last_status": "blocked",
                    "last_failure_at": datetime.now().isoformat(timespec="seconds"),
                    "retry_count": decision.retry_count,
                    "last_error": "health_gate_failed",
                },
            )
            _append_log_line(decision.log_path, f"block {decision.task_name}: health gate failed")
            _finish_run(
                conn,
                run_id=run_id,
                status="blocked",
                finished_at=datetime.now().isoformat(timespec="seconds"),
                exit_code=2,
                error_summary="health_gate_failed",
            )
            return 0

        with decision.log_path.open("a", encoding="utf-8") as handle:
            process = subprocess.run(decision.command, stdout=handle, stderr=subprocess.STDOUT, text=True)
        finished_at = datetime.now().isoformat(timespec="seconds")
        if process.returncode == 0:
            _write_text(decision.stamp_path, now.date().isoformat())
            _write_task_state(
                decision.state_path,
                {
                    "last_status": "succeeded",
                    "last_success_at": finished_at,
                    "retry_count": 0,
                    "last_error": "",
                },
            )
            _append_log_line(decision.log_path, f"finish {decision.task_name}")
            _finish_run(conn, run_id=run_id, status="succeeded", finished_at=finished_at, exit_code=0, error_summary="")
        else:
            retry_count = decision.retry_count + 1
            _write_task_state(
                decision.state_path,
                {
                    "last_status": "failed",
                    "last_failure_at": finished_at,
                    "retry_count": retry_count,
                    "last_error": f"exit_code={process.returncode}",
                },
            )
            _append_log_line(decision.log_path, f"fail {decision.task_name} exit_code={process.returncode}")
            _finish_run(
                conn,
                run_id=run_id,
                status="failed",
                finished_at=finished_at,
                exit_code=int(process.returncode),
                error_summary=f"exit_code={process.returncode}",
            )
        return 1
    finally:
        _release_lock(decision.lock_path)


def maintenance_tick(
    config_path: Path,
    *,
    as_of: str | None = None,
    dry_run: bool = True,
) -> MaintenanceTickResult:
    root, orchestrator_cfg = _load_maintenance_cfg(config_path)
    state_db = _configured_state_db(root, orchestrator_cfg)
    now = datetime.strptime(as_of, "%Y-%m-%d %H:%M") if as_of else datetime.now()
    now_iso = now.isoformat(timespec="seconds")
    specs = _default_registry(config_path)
    executed_runs = 0

    with _connect(state_db) as conn:
        _ensure_schema(conn)
        _sync_registry(conn, specs, now_iso=now_iso)
        decisions = [_evaluate_task(spec=spec, root=root, now=now, today=now.date().isoformat()) for spec in specs]
        _record_decisions(conn, decisions, created_at=now_iso)
        if not dry_run:
            for decision in decisions:
                if decision.decision == "will_run":
                    executed_runs += _run_task(conn, decision=decision, trigger_source="scheduler_tick", now=now)

    return MaintenanceTickResult(
        status="ok",
        as_of=now_iso,
        dry_run=dry_run,
        state_db=state_db,
        decisions=decisions,
        executed_runs=executed_runs,
    )


def maintenance_run_long_task(
    config_path: Path,
    *,
    task_name: str,
    start_period: str,
    end_period: str,
    shard_count: int = 3,
    max_requests_per_minute: int = 67,
    retry_failed: bool = True,
    missing_fields_only: bool = False,
    limit_tasks: int | None = None,
    dry_run: bool = False,
) -> MaintenanceLongRunResult:
    if task_name != LONG_BACKFILL_TASK:
        raise ValueError(f"Unsupported long task: {task_name}")
    root, orchestrator_cfg = _load_maintenance_cfg(config_path)
    state_db = _configured_state_db(root, orchestrator_cfg)
    now_iso = datetime.now().isoformat(timespec="seconds")
    shard_count = max(1, int(shard_count))
    max_requests_per_minute = max(1, int(max_requests_per_minute))

    commands = [
        _build_financial_backfill_command(
            config_path=config_path,
            shard_index=idx,
            shard_count=shard_count,
            start_period=start_period,
            end_period=end_period,
            max_requests_per_minute=max_requests_per_minute,
            retry_failed=retry_failed,
            missing_fields_only=missing_fields_only,
            limit_tasks=limit_tasks,
        )
        for idx in range(shard_count)
    ]

    with _connect(state_db) as conn:
        _ensure_schema(conn)
        _refresh_shards(conn)
        running = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM maintenance_shards
            WHERE task_name = ? AND status = 'running'
            """,
            (task_name,),
        ).fetchone()
        if int(running["count"]) > 0:
            return MaintenanceLongRunResult(
                status="blocked",
                task_name=task_name,
                run_id=None,
                state_db=state_db,
                shard_rows=_shard_rows(conn, root),
                message="task_already_running",
            )
        run_id = _create_long_run(conn, task_name=task_name, command=commands[0], started_at=now_iso)
        for idx, command in enumerate(commands):
            log_path = root / "logs" / "maintenance" / f"{task_name}_run_{run_id}_shard_{idx}.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            pid: int | None = None
            status = "pending" if dry_run else "running"
            if not dry_run:
                handle = log_path.open("ab")
                process = subprocess.Popen(
                    command,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    cwd=str(root),
                    start_new_session=True,
                )
                handle.close()
                pid = int(process.pid)
            conn.execute(
                """
                INSERT INTO maintenance_shards (
                    run_id, task_name, shard_index, shard_count, status, pid,
                    started_at, log_path, command_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    task_name,
                    idx,
                    shard_count,
                    status,
                    pid,
                    now_iso,
                    str(log_path.relative_to(root)),
                    json.dumps(command, ensure_ascii=True),
                ),
            )
        if dry_run:
            conn.execute(
                """
                UPDATE maintenance_runs
                SET status = ?, finished_at = ?, error_summary = ?
                WHERE run_id = ?
                """,
                ("skipped", now_iso, "dry_run", run_id),
            )
        conn.commit()
        return MaintenanceLongRunResult(
            status="dry_run" if dry_run else "started",
            task_name=task_name,
            run_id=run_id,
            state_db=state_db,
            shard_rows=_shard_rows(conn, root, run_id=run_id),
        )


def maintenance_stop(
    config_path: Path,
    *,
    task_name: str | None = None,
    run_id: int | None = None,
    dry_run: bool = False,
) -> MaintenanceLongRunResult:
    root, orchestrator_cfg = _load_maintenance_cfg(config_path)
    state_db = _configured_state_db(root, orchestrator_cfg)
    now_iso = datetime.now().isoformat(timespec="seconds")
    task_name = task_name or LONG_BACKFILL_TASK
    with _connect(state_db) as conn:
        _ensure_schema(conn)
        _refresh_shards(conn)
        where = "status = 'running' AND task_name = ?"
        params: list[Any] = [task_name]
        if run_id is not None:
            where += " AND run_id = ?"
            params.append(int(run_id))
        rows = conn.execute(
            f"SELECT shard_id, run_id, pid FROM maintenance_shards WHERE {where}",
            tuple(params),
        ).fetchall()
        for row in rows:
            pid = int(row["pid"]) if row["pid"] is not None else None
            if pid and not dry_run:
                try:
                    os.killpg(pid, signal.SIGTERM)
                except OSError:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except OSError:
                        pass
            if not dry_run:
                conn.execute(
                    """
                    UPDATE maintenance_shards
                    SET status = 'cancelled', finished_at = ?, error_summary = ?
                    WHERE shard_id = ?
                    """,
                    (now_iso, "stopped_by_maintain_stop", int(row["shard_id"])),
                )
        if not dry_run:
            target_run_ids = {int(row["run_id"]) for row in rows}
            for item in target_run_ids:
                conn.execute(
                    """
                    UPDATE maintenance_runs
                    SET status = 'cancelled', finished_at = ?, error_summary = ?
                    WHERE run_id = ?
                    """,
                    (now_iso, "stopped_by_maintain_stop", item),
                )
            conn.commit()
        return MaintenanceLongRunResult(
            status="dry_run" if dry_run else "stopped",
            task_name=task_name,
            run_id=run_id,
            state_db=state_db,
            shard_rows=_shard_rows(conn, root, run_id=run_id),
            message=f"matched_shards={len(rows)}",
        )


def maintenance_resume(
    config_path: Path,
    *,
    task_name: str | None = None,
    run_id: int | None = None,
    dry_run: bool = False,
) -> MaintenanceLongRunResult:
    root, orchestrator_cfg = _load_maintenance_cfg(config_path)
    state_db = _configured_state_db(root, orchestrator_cfg)
    now_iso = datetime.now().isoformat(timespec="seconds")
    task_name = task_name or LONG_BACKFILL_TASK
    with _connect(state_db) as conn:
        _ensure_schema(conn)
        _refresh_shards(conn)
        where = "task_name = ? AND status != 'running' AND status != 'succeeded'"
        params: list[Any] = [task_name]
        if run_id is not None:
            where += " AND run_id = ?"
            params.append(int(run_id))
        rows = conn.execute(
            f"SELECT shard_id, run_id, shard_index, command_json, log_path FROM maintenance_shards WHERE {where}",
            tuple(params),
        ).fetchall()
        for row in rows:
            command = json.loads(str(row["command_json"]))
            log_path = _resolve_path(root, str(row["log_path"]))
            pid: int | None = None
            status = "pending" if dry_run else "running"
            if not dry_run:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                handle = log_path.open("ab")
                process = subprocess.Popen(
                    command,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    cwd=str(root),
                    start_new_session=True,
                )
                handle.close()
                pid = int(process.pid)
            if not dry_run:
                conn.execute(
                    """
                    UPDATE maintenance_shards
                    SET status = ?, pid = ?, started_at = ?, finished_at = NULL,
                        exit_code = NULL, error_summary = ?
                    WHERE shard_id = ?
                    """,
                    (status, pid, now_iso, "resumed_by_maintain_resume", int(row["shard_id"])),
                )
        if rows and not dry_run:
            target_run_ids = {int(row["run_id"]) for row in rows}
            for item in target_run_ids:
                conn.execute(
                    """
                    UPDATE maintenance_runs
                    SET status = 'running', finished_at = NULL, error_summary = ?
                    WHERE run_id = ?
                    """,
                    ("resumed_by_maintain_resume", item),
                )
            conn.commit()
        return MaintenanceLongRunResult(
            status="dry_run" if dry_run else "resumed",
            task_name=task_name,
            run_id=run_id,
            state_db=state_db,
            shard_rows=_shard_rows(conn, root, run_id=run_id),
            message=f"matched_shards={len(rows)}",
        )


def _configured_state_db(root: Path, orchestrator_cfg: dict[str, Any]) -> Path:
    return _resolve_path(root, orchestrator_cfg.get("state_db", "data/maintenance/maintenance.sqlite"))


def maintenance_status(config_path: Path) -> MaintenanceStatusResult:
    root, orchestrator_cfg = _load_maintenance_cfg(config_path)
    state_db = _configured_state_db(root, orchestrator_cfg)
    now_iso = datetime.now().isoformat(timespec="seconds")

    with _connect(state_db) as conn:
        _ensure_schema(conn)
        _refresh_shards(conn)
        _sync_registry(conn, _default_registry(config_path), now_iso=now_iso)
        registry_rows = conn.execute(
            """
            SELECT task_name, enabled, schedule_type, schedule_value, log_path, state_path
            FROM maintenance_registry
            ORDER BY task_name
            """
        ).fetchall()
        rows: list[MaintenanceStatusRow] = []
        for item in registry_rows:
            task_name = str(item["task_name"])
            event = conn.execute(
                """
                SELECT decision, reason, created_at
                FROM maintenance_events
                WHERE task_name = ?
                ORDER BY event_id DESC
                LIMIT 1
                """,
                (task_name,),
            ).fetchone()
            run = conn.execute(
                """
                SELECT status, started_at, error_summary
                FROM maintenance_runs
                WHERE task_name = ?
                ORDER BY run_id DESC
                LIMIT 1
                """,
                (task_name,),
            ).fetchone()
            success_run = conn.execute(
                """
                SELECT finished_at
                FROM maintenance_runs
                WHERE task_name = ? AND status = 'succeeded'
                ORDER BY run_id DESC
                LIMIT 1
                """,
                (task_name,),
            ).fetchone()
            state_path = _resolve_path(root, str(item["state_path"]))
            task_state = _parse_task_state(state_path)
            rows.append(
                MaintenanceStatusRow(
                    task_name=task_name,
                    enabled=bool(item["enabled"]),
                    schedule_type=str(item["schedule_type"]),
                    schedule_value=str(item["schedule_value"]),
                    last_decision=str(event["decision"]) if event else "never",
                    last_reason=str(event["reason"]) if event else "no_events",
                    last_tick_at=str(event["created_at"]) if event else "",
                    last_success_at=str(success_run["finished_at"]) if success_run else "",
                    last_run_status=str(run["status"]) if run else "never",
                    last_error=str(run["error_summary"]) if run else str(task_state.get("last_error") or ""),
                    retry_count=int(task_state.get("retry_count") or 0),
                    log_path=_resolve_path(root, str(item["log_path"])),
                    state_path=state_path,
                )
            )
        shards = _shard_rows(conn, root)
    return MaintenanceStatusResult(state_db=state_db, generated_at=now_iso, rows=rows, shards=shards)
