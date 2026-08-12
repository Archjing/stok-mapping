from __future__ import annotations

import csv
import json
import os
import signal
import sqlite3
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from phase0.config import load_config
from phase0.reporting.paths import report_path as build_report_path


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
    market_calendar: str = "weekday"


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
    report_path: Path | None = None
    error_summary: str = ""
    key_conclusion: str = ""


@dataclass(frozen=True)
class MaintenanceStatusResult:
    state_db: Path
    generated_at: str
    rows: list[MaintenanceStatusRow]
    shards: list[MaintenanceShardStatusRow]
    report_path: Path | None = None


@dataclass(frozen=True)
class MaintenanceLongRunResult:
    status: str
    task_name: str
    run_id: int | None
    state_db: Path
    shard_rows: list[MaintenanceShardStatusRow]
    message: str = ""
    dry_run: bool = False


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


def _has_enabled_single_etf_intraday_account(config_path: Path) -> bool:
    """Return whether an intraday ETF account has a configured target to snapshot."""
    config = load_config(config_path)
    for account in config.get("accounts", {}).get("simulated", []):
        if not account.get("enabled", False):
            continue
        if account.get("execution_model") != "single_etf_intraday":
            continue
        if (account.get("strategy_params") or {}).get("target_symbol"):
            return True
    return False


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
        health_fail_on: str | None = None,
        enabled: bool = True,
        monday_only: bool = False,
        weekdays_only: bool = True,
        description: str,
        tags: list[str],
        market_calendar: str = "weekday",
        retry_window_minutes: str = "20",
        retry_interval_minutes: str = "5",
        max_retries: str = "3",
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
            health_fail_on=health_fail_on or _env_value("SCHEDULER_HEALTH_FAIL_ON", "warning"),
            enabled=enabled,
            monday_only=monday_only,
            weekdays_only=weekdays_only,
            description=description,
            tags=tags,
            retry_window_minutes=int(_env_value(f"{name.upper()}_RETRY_WINDOW_MINUTES", retry_window_minutes)),
            retry_interval_minutes=int(_env_value(f"{name.upper()}_RETRY_INTERVAL_MINUTES", retry_interval_minutes)),
            max_retries=int(_env_value(f"{name.upper()}_MAX_RETRIES", max_retries)),
            state_path=str(state_dir / f"{name}.state"),
            market_calendar=market_calendar,
        )

    return [
        make_spec(
            name="financial_factors",
            schedule_value=_env_value("FINANCIAL_FACTORS_TIME", "03:30"),
            log_path="logs/financial_factors_update.log",
            command=[str(python_bin), "-m", "phase0.cli", "update-financials", "--config", config_arg],
            health_scope=_env_value("FINANCIAL_FACTORS_HEALTH_SCOPE", "scheduler"),
            health_fail_on=_env_value("FINANCIAL_FACTORS_HEALTH_FAIL_ON", "error"),
            monday_only=True,
            weekdays_only=False,
            description="Weekly A-share financial factor refresh",
            tags=["scheduler", "financial"],
            market_calendar="cn",
        ),
        make_spec(
            name="gov_policy_fetch",
            schedule_value=_env_value("GOV_POLICY_TIME", "06:50"),
            log_path="logs/gov_policy_update.log",
            command=[
                str(python_bin),
                "-m",
                "phase0.cli",
                "ai-corpus",
                "fetch",
                "--config",
                config_arg,
                "--provider",
                "gov-policy",
                "--org",
                _env_value("GOV_POLICY_ORG", "国务院"),
                "--ptype",
                _env_value("GOV_POLICY_PTYPE", "科技"),
                "--keyword",
                _env_value("GOV_POLICY_KEYWORD", "人工智能"),
                "--limit",
                _env_value("GOV_POLICY_LIMIT", "20"),
                "--min-rows",
                _env_value("GOV_POLICY_MIN_ROWS", "1"),
                "--timeout",
                _env_value("GOV_POLICY_TIMEOUT", "20"),
                "--database-path",
                _env_value("GOV_POLICY_DATABASE_PATH", "data/ai_corpus/ai_corpus.sqlite"),
                "--raw-archive-dir",
                _env_value("GOV_POLICY_RAW_ARCHIVE_DIR", "data/raw_data/ai_corpus/gov_policy"),
                "--reference-dir",
                _env_value("GOV_POLICY_REFERENCE_DIR", "data/reference/ai_corpus/gov_policy"),
                "--refresh-reference",
                "--probe-before-fetch",
                "--probe-output-json",
                _env_value(
                    "GOV_POLICY_PROBE_OUTPUT_JSON",
                    "reports/phase0/ai_corpus/probes/gov_policy_probe_%Y%m%dT%H%M%S.json",
                ),
                "--min-probe-rows",
                _env_value("GOV_POLICY_PROBE_MIN_ROWS", "1"),
                "--min-probe-topics",
                _env_value("GOV_POLICY_PROBE_MIN_TOPICS", "1"),
                "--min-probe-departments",
                _env_value("GOV_POLICY_PROBE_MIN_DEPARTMENTS", "0"),
                "--min-probe-content-chars",
                _env_value("GOV_POLICY_PROBE_MIN_CONTENT_CHARS", "200"),
            ],
            health_scope=_env_value("GOV_POLICY_HEALTH_SCOPE", "scheduler"),
            health_fail_on=_env_value("GOV_POLICY_HEALTH_FAIL_ON", _env_value("SCHEDULER_HEALTH_FAIL_ON", "warning")),
            weekdays_only=False,
            description="Daily gov.cn AI policy corpus refresh with pre-fetch source probe",
            tags=["scheduler", "ai_corpus", "gov_policy"],
            market_calendar="all",
            retry_window_minutes="90",
            retry_interval_minutes="15",
            max_retries="4",
        ),
        make_spec(
            name="us_market_news",
            schedule_value=_env_value("US_MARKET_NEWS_TIME", "06:30"),
            log_path="logs/us_market_news_update.log",
            command=[
                str(python_bin),
                "-m",
                "phase0.cli",
                "ai-corpus",
                "fetch",
                "--config",
                config_arg,
                "--provider",
                "us-market-news",
                "--limit",
                _env_value("US_MARKET_NEWS_LIMIT", "100"),
                "--min-rows",
                _env_value("US_MARKET_NEWS_MIN_ROWS", "0"),
                "--database-path",
                _env_value("US_MARKET_NEWS_DATABASE_PATH", "data/ai_corpus/ai_corpus.sqlite"),
                "--raw-archive-dir",
                _env_value("US_MARKET_NEWS_RAW_ARCHIVE_DIR", "data/raw_data/ai_corpus/us_market_news"),
            ],
            health_scope=_env_value("US_MARKET_NEWS_HEALTH_SCOPE", "scheduler"),
            health_fail_on=_env_value("US_MARKET_NEWS_HEALTH_FAIL_ON", _env_value("SCHEDULER_HEALTH_FAIL_ON", "warning")),
            weekdays_only=False,
            description="Daily US market and semiconductor RSS metadata archive",
            tags=["scheduler", "ai_corpus", "us_market_news"],
            market_calendar="all",
            retry_window_minutes="90",
            retry_interval_minutes="15",
            max_retries="4",
        ),
        make_spec(
            name="daily_brief",
            schedule_value=_env_value("DAILY_BRIEF_TIME", "07:20"),
            log_path="logs/daily_brief_pipeline.log",
            command=[str(python_bin), "-m", "phase0.cli", "brief", "watchlist", "--config", config_arg, "--all-accounts"],
            health_scope=_env_value("DAILY_BRIEF_HEALTH_SCOPE", "cn"),
            health_fail_on=_env_value("DAILY_BRIEF_HEALTH_FAIL_ON", _env_value("SCHEDULER_HEALTH_FAIL_ON", "warning")),
            description="Premarket watchlist and brief pipeline",
            tags=["scheduler", "brief"],
            market_calendar="cn",
        ),
        make_spec(
            name="etf_opening_snapshot",
            schedule_value=_env_value("ETF_OPENING_SNAPSHOT_TIME", "09:25"),
            log_path="logs/etf_opening_snapshot.log",
            command=[
                str(python_bin),
                "scripts/fetch_etf_opening_snapshots.py",
                "--config",
                config_arg,
            ],
            health_scope=_env_value("ETF_OPENING_SNAPSHOT_HEALTH_SCOPE", "cn"),
            health_fail_on=_env_value("ETF_OPENING_SNAPSHOT_HEALTH_FAIL_ON", "error"),
            enabled=_has_enabled_single_etf_intraday_account(config_path),
            description="Post-auction ETF quote snapshot with official opening price",
            tags=["scheduler", "cn", "etf", "intraday"],
            market_calendar="cn",
            retry_window_minutes="10",
            retry_interval_minutes="1",
            max_retries="5",
        ),
        make_spec(
            name="hk_market_history",
            schedule_value=_env_value("HK_MARKET_HISTORY_TIME", "16:20"),
            log_path="logs/hk_market_history_update.log",
            command=[str(python_bin), "-m", "phase0.cli", "update-hk-market-history", "--config", config_arg],
            health_scope=_env_value("HK_MARKET_HISTORY_HEALTH_SCOPE", "scheduler"),
            health_fail_on=_env_value("HK_MARKET_HISTORY_HEALTH_FAIL_ON", "error"),
            description="Hong Kong market history refresh",
            tags=["scheduler", "hk"],
            market_calendar="hk",
        ),
        make_spec(
            name="a_share_history",
            schedule_value=_env_value("A_SHARE_HISTORY_TIME", "16:30"),
            log_path="logs/manual_history_update.log",
            command=[str(python_bin), "-m", "phase0.cli", "update-history", "--config", config_arg],
            health_scope=_env_value("A_SHARE_HISTORY_HEALTH_SCOPE", "scheduler"),
            health_fail_on=_env_value("A_SHARE_HISTORY_HEALTH_FAIL_ON", "error"),
            description="A-share local history refresh",
            tags=["scheduler", "cn"],
            market_calendar="cn",
        ),
        make_spec(
            name="account_bill_confirm",
            schedule_value=_env_value("ACCOUNT_BILL_CONFIRM_TIME", "16:45"),
            log_path="logs/account_bill_confirm.log",
            command=[
                str(python_bin),
                "-m",
                "phase0.cli",
                "brief",
                "confirm-account-bills",
                "--config",
                config_arg,
                "--all-accounts",
            ],
            health_scope=_env_value("ACCOUNT_BILL_CONFIRM_HEALTH_SCOPE", "cn"),
            health_fail_on=_env_value("ACCOUNT_BILL_CONFIRM_HEALTH_FAIL_ON", "error"),
            description="Post-close simulated account ledger confirmation and quant site publish",
            tags=["scheduler", "account", "brief", "site"],
            market_calendar="cn",
        ),
        make_spec(
            name="us_market_history",
            schedule_value=_env_value("US_MARKET_HISTORY_TIME", "17:10"),
            log_path="logs/us_market_history_update.log",
            command=[str(python_bin), "-m", "phase0.cli", "update-us-market-history", "--config", config_arg],
            health_scope=_env_value("US_MARKET_HISTORY_HEALTH_SCOPE", "scheduler"),
            health_fail_on=_env_value("US_MARKET_HISTORY_HEALTH_FAIL_ON", "error"),
            description="US market history refresh",
            tags=["scheduler", "us"],
            market_calendar="us",
        ),
        make_spec(
            name="cninfo_risk_events",
            schedule_value=_env_value("CNINFO_RISK_EVENTS_TIME", "20:20"),
            log_path="logs/cninfo_risk_events_update.log",
            command=[
                str(python_bin),
                "-m",
                "phase0.cli",
                "ai-corpus",
                "fetch",
                "--config",
                config_arg,
                "--provider",
                "cninfo",
                "--event-type",
                _env_value("CNINFO_RISK_EVENTS_EVENT_TYPE", "risk_events"),
                "--limit",
                _env_value("CNINFO_RISK_EVENTS_LIMIT", "200"),
                "--min-rows",
                _env_value("CNINFO_RISK_EVENTS_MIN_ROWS", "0"),
                "--database-path",
                _env_value("CNINFO_RISK_EVENTS_DATABASE_PATH", "data/ai_corpus/ai_corpus.sqlite"),
                "--raw-archive-dir",
                _env_value("CNINFO_RISK_EVENTS_RAW_ARCHIVE_DIR", "data/raw_data/ai_corpus/cninfo"),
            ],
            health_scope=_env_value("CNINFO_RISK_EVENTS_HEALTH_SCOPE", "scheduler"),
            health_fail_on=_env_value(
                "CNINFO_RISK_EVENTS_HEALTH_FAIL_ON",
                _env_value("SCHEDULER_HEALTH_FAIL_ON", "warning"),
            ),
            weekdays_only=False,
            description="Daily CNInfo market risk announcement archive",
            tags=["scheduler", "ai_corpus", "cninfo"],
            market_calendar="all",
            retry_window_minutes="120",
            retry_interval_minutes="30",
            max_retries="4",
        ),
        make_spec(
            name="cctv_news",
            schedule_value=_env_value("CCTV_NEWS_TIME", "20:45"),
            log_path="logs/cctv_news_update.log",
            command=[
                str(python_bin),
                "-m",
                "phase0.cli",
                "ai-corpus",
                "fetch",
                "--config",
                config_arg,
                "--provider",
                "cctv-news",
                "--limit",
                _env_value("CCTV_NEWS_LIMIT", "100"),
                "--min-rows",
                "1",
            ],
            health_scope=_env_value("CCTV_NEWS_HEALTH_SCOPE", "scheduler"),
            health_fail_on=_env_value("CCTV_NEWS_HEALTH_FAIL_ON", _env_value("SCHEDULER_HEALTH_FAIL_ON", "warning")),
            weekdays_only=False,
            description="Daily CCTV Xinwen Lianbo transcript archive",
            tags=["scheduler", "ai_corpus", "cctv"],
            market_calendar="all",
            retry_window_minutes="180",
            retry_interval_minutes="30",
            max_retries="6",
        ),
    ]


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _connect_read_only(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{quote(str(path))}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


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
            command_json TEXT NOT NULL DEFAULT '[]',
            key_conclusion TEXT NOT NULL DEFAULT ''
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
            error_summary TEXT NOT NULL DEFAULT '',
            key_conclusion TEXT NOT NULL DEFAULT ''
        )
        """
    )
    for table, migrations in {
        "maintenance_runs": [
            ("report_path", "ALTER TABLE maintenance_runs ADD COLUMN report_path TEXT NOT NULL DEFAULT ''"),
            ("key_conclusion", "ALTER TABLE maintenance_runs ADD COLUMN key_conclusion TEXT NOT NULL DEFAULT ''"),
        ],
        "maintenance_shards": [
            ("report_path", "ALTER TABLE maintenance_shards ADD COLUMN report_path TEXT NOT NULL DEFAULT ''"),
            ("error_summary", "ALTER TABLE maintenance_shards ADD COLUMN error_summary TEXT NOT NULL DEFAULT ''"),
            ("key_conclusion", "ALTER TABLE maintenance_shards ADD COLUMN key_conclusion TEXT NOT NULL DEFAULT ''"),
        ],
    }.items():
        table_columns = {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for column, ddl in migrations:
            if column not in table_columns:
                conn.execute(ddl)
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


def _decision_kwargs(
    *,
    spec: MaintenanceTaskSpec,
    log_path: Path,
    stamp_path: Path,
    lock_path: Path,
    state_path: Path,
    last_success: str,
    retry_count: int,
) -> dict[str, Any]:
    return {
        "task_name": spec.name,
        "scheduled_time": spec.schedule_value,
        "command": spec.command,
        "log_path": log_path,
        "stamp_path": stamp_path,
        "lock_path": lock_path,
        "health_scope": spec.health_scope,
        "health_fail_on": spec.health_fail_on,
        "state_path": state_path,
        "retry_window_minutes": spec.retry_window_minutes,
        "retry_interval_minutes": spec.retry_interval_minutes,
        "max_retries": spec.max_retries,
        "last_success_date": last_success,
        "retry_count": retry_count,
    }


def _trading_day_decision(*, root: Path, config_path: Path, spec: MaintenanceTaskSpec, now: datetime) -> tuple[bool, str]:
    scope = spec.market_calendar.strip().lower() or "weekday"
    weekday = now.isoweekday()
    if scope in {"all", "daily", "natural_day", "calendar_day"}:
        return True, f"natural_day_calendar(scope={scope})"
    if scope in {"", "weekday"}:
        return weekday in {1, 2, 3, 4, 5}, f"weekday_calendar(weekday={weekday})"
    if scope in {"hk", "us"}:
        if weekday not in {1, 2, 3, 4, 5}:
            return False, f"market_calendar_weekday_fallback(scope={scope}, weekday={weekday})"
        return True, f"market_calendar_weekday_fallback(scope={scope})"
    if scope != "cn":
        return weekday in {1, 2, 3, 4, 5}, f"unknown_calendar_fallback_weekday(scope={scope}, weekday={weekday})"

    cfg = load_config(config_path) if config_path.exists() else {}
    local_cfg = cfg.get("local_history", {}) if isinstance(cfg, dict) else {}
    db_path = _resolve_path(root, str(local_cfg.get("path", "data/a_share_history.sqlite")))
    table = str(local_cfg.get("calendar_table", "trading_calendar"))
    if not table.replace("_", "").isalnum():
        return weekday in {1, 2, 3, 4, 5}, f"calendar_unavailable_fallback_weekday(scope=cn, reason=invalid_table, weekday={weekday})"
    if not db_path.exists():
        return weekday in {1, 2, 3, 4, 5}, f"calendar_unavailable_fallback_weekday(scope=cn, reason=db_missing, weekday={weekday})"
    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            table_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
                (table,),
            ).fetchone()
            if not table_exists:
                return weekday in {1, 2, 3, 4, 5}, f"calendar_unavailable_fallback_weekday(scope=cn, reason=table_missing, weekday={weekday})"
            row = conn.execute(
                f"SELECT is_open FROM {table} WHERE date = ? ORDER BY exchange LIMIT 1",
                (now.date().isoformat(),),
            ).fetchone()
    except sqlite3.Error as exc:
        return weekday in {1, 2, 3, 4, 5}, f"calendar_unavailable_fallback_weekday(scope=cn, reason={type(exc).__name__}, weekday={weekday})"
    if row is None:
        return weekday in {1, 2, 3, 4, 5}, f"calendar_unavailable_fallback_weekday(scope=cn, reason=date_missing, weekday={weekday})"
    is_open = int(row["is_open"] or 0) == 1
    return is_open, f"cn_trading_calendar(is_open={1 if is_open else 0})"


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
    config_path: Path,
) -> MaintenanceDecision:
    log_path = _resolve_path(root, spec.log_path)
    stamp_path = _resolve_path(root, spec.success_stamp)
    lock_path = _resolve_path(root, spec.lock_dir)
    state_path = _resolve_path(root, spec.state_path)
    weekday = now.isoweekday()
    last_success = _read_text(stamp_path)
    state = _parse_task_state(state_path)
    retry_count = int(state.get("retry_count") or 0)
    now_hm = now.strftime("%H:%M")
    base_kwargs = _decision_kwargs(
        spec=spec,
        log_path=log_path,
        stamp_path=stamp_path,
        lock_path=lock_path,
        state_path=state_path,
        last_success=last_success,
        retry_count=retry_count,
    )

    if not spec.enabled:
        return MaintenanceDecision(decision="skipped", reason="task_disabled", **base_kwargs)

    is_trading_day, calendar_reason = _trading_day_decision(root=root, config_path=config_path, spec=spec, now=now)
    if not is_trading_day:
        return MaintenanceDecision(decision="skipped", reason=f"not_trading_day({calendar_reason})", **base_kwargs)

    if spec.monday_only and weekday != 1:
        return MaintenanceDecision(decision="skipped", reason=f"not_monday(weekday={weekday})", **base_kwargs)
    if spec.weekdays_only and weekday not in {1, 2, 3, 4, 5}:
        return MaintenanceDecision(decision="skipped", reason=f"not_weekday(weekday={weekday})", **base_kwargs)

    if last_success == today:
        decision = "skipped"
        reason = f"already_succeeded_today({today})"
    elif lock_path.exists():
        decision = "blocked"
        reason = "lock_present"
    elif now_hm == spec.schedule_value:
        decision = "will_run"
        reason = f"scheduled_run(scope={spec.health_scope}, fail_on={spec.health_fail_on}, calendar={calendar_reason})"
    elif _in_retry_window(now, spec, state):
        decision = "will_run"
        reason = (
            f"retry_window(retry_count={retry_count}, interval={spec.retry_interval_minutes}m, "
            f"window={spec.retry_window_minutes}m, calendar={calendar_reason})"
        )
    else:
        decision = "skipped"
        reason = f"outside_schedule(now={now_hm}, expected={spec.schedule_value}, calendar={calendar_reason})"
    if decision == "will_run" and not _env_flag("SCHEDULER_HEALTH_ENABLED", "1"):
        reason = "health_gate_disabled"
    return MaintenanceDecision(decision=decision, reason=reason, **base_kwargs)

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


def _tail_text(path: Path, *, max_bytes: int = 65536) -> str:
    if not path.exists():
        return ""
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(size - max_bytes, 0), os.SEEK_SET)
            return handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _command_option(command: list[str], name: str) -> str:
    if name not in command:
        return ""
    idx = command.index(name)
    if idx + 1 >= len(command):
        return ""
    return str(command[idx + 1])


def _require_command_option(command: list[str], name: str) -> str:
    value = _command_option(command, name)
    if not value:
        raise ValueError(f"Command is missing required option {name}: {command}")
    return value


def _parse_financial_backfill_command(command_json: str) -> dict[str, str | int]:
    try:
        command = json.loads(command_json)
    except json.JSONDecodeError:
        command = []
    if not isinstance(command, list):
        command = []
    command = [str(item) for item in command]
    return {
        "start_period": _command_option(command, "--start-period"),
        "end_period": _command_option(command, "--end-period"),
        "shard_index": int(_command_option(command, "--shard-index") or -1),
        "shard_count": int(_command_option(command, "--shard-count") or -1),
    }


def _compact_period(value: str) -> str:
    return value.replace("-", "")


def _read_summary_matches(path: Path, *, start_period: str, end_period: str, shard_index: int, shard_count: int) -> list[dict[str, str]]:
    if not path.exists() or not start_period or not end_period:
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, csv.Error):
        return []
    matches: list[dict[str, str]] = []
    for row in rows:
        if str(row.get("start_period") or "") != start_period:
            continue
        if str(row.get("end_period") or "") != end_period:
            continue
        if str(row.get("shard_index") or "") != str(shard_index):
            continue
        if str(row.get("shard_count") or "") != str(shard_count):
            continue
        matches.append({str(k): str(v) for k, v in row.items()})
    return matches


def _find_financial_backfill_report(root: Path, command_json: str) -> tuple[Path | None, str, str, bool]:
    meta = _parse_financial_backfill_command(command_json)
    start_period = str(meta.get("start_period") or "")
    end_period = str(meta.get("end_period") or "")
    shard_index = int(meta.get("shard_index") or -1)
    shard_count = int(meta.get("shard_count") or -1)
    summary_csv = build_report_path(root=root, category="database_health", parts=("tushare_financial_backfill_audit_summary.csv",))
    matches = _read_summary_matches(
        summary_csv,
        start_period=start_period,
        end_period=end_period,
        shard_index=shard_index,
        shard_count=shard_count,
    )
    if matches:
        row = matches[-1]
        report_raw = row.get("detail_report_md") or row.get("detail_md") or row.get("output_md") or row.get("report_md") or ""
        report_path = _resolve_path(root, report_raw) if report_raw else None
        conclusion = row.get("key_conclusion") or row.get("conclusion") or ""
        if not conclusion:
            conclusion = (
                f"{start_period}..{end_period} shard {shard_index}/{shard_count}, "
                f"processed={row.get('processed_tasks', '')}, fetched={row.get('fetched_tasks', '')}, "
                f"failed={row.get('failed_tasks', '')}, inserted_rows={row.get('inserted_rows', '')}"
            )
        status = row.get("status") or ""
        is_success = status in {"ok", "ok_with_warnings"}
        error_summary = "" if is_success else status
        return report_path, conclusion, error_summary, is_success

    range_tag = f"{_compact_period(start_period)}_{_compact_period(end_period)}"
    candidates = sorted((root / "reports").glob(f"*/tushare_financial_backfill_audit_*_{range_tag}.md"))
    if candidates:
        return candidates[-1], "", "", False
    return None, "", "", False


def _classify_backfill_shard(root: Path, *, log_path: Path, command_json: str) -> tuple[str, Path | None, str, str]:
    report_path, conclusion, report_error, summary_success = _find_financial_backfill_report(root, command_json)
    log_tail = _tail_text(log_path).lower()
    success_markers = [
        "tushare financial backfill status: ok",
        "tushare financial backfill status: ok_with_warnings",
    ]
    failure_markers = ["traceback", "status: failed", "database is locked", "frequency超限", "频率超限"]
    if report_error:
        return "failed", report_path, conclusion, report_error
    if any(marker in log_tail for marker in failure_markers):
        return "failed", report_path, conclusion, "explicit_failure_marker_in_log"
    if any(marker in log_tail for marker in success_markers) or summary_success:
        return "succeeded", report_path, conclusion or "explicit_success_marker", ""
    return "exited_unknown", report_path, conclusion, report_error or "process_not_alive_exit_code_unknown"


def _rollup_run_status(statuses: list[str]) -> tuple[str, str]:
    if not statuses:
        return "exited_unknown", "no_shards_found"
    if any(status == "running" for status in statuses):
        return "running", "some_shards_running"
    if all(status == "succeeded" for status in statuses):
        return "succeeded", "all_shards_succeeded"
    if any(status == "failed" for status in statuses):
        return "failed", "one_or_more_shards_failed"
    if any(status == "cancelled" for status in statuses):
        return "cancelled", "one_or_more_shards_cancelled"
    return "exited_unknown", "all_shards_not_running_exit_unknown"


def _refresh_shards(conn: sqlite3.Connection, root: Path, *, task_name: str | None = None, run_id: int | None = None, dry_run: bool = False) -> int:
    now_iso = datetime.now().isoformat(timespec="seconds")
    where = "status = 'running'"
    params: list[Any] = []
    if task_name is not None:
        where += " AND task_name = ?"
        params.append(task_name)
    if run_id is not None:
        where += " AND run_id = ?"
        params.append(int(run_id))
    rows = conn.execute(
        f"""
        SELECT shard_id, run_id, pid, status, log_path, command_json
        FROM maintenance_shards
        WHERE {where}
        """,
        tuple(params),
    ).fetchall()
    changed = 0
    for row in rows:
        pid = int(row["pid"]) if row["pid"] is not None else None
        if _pid_alive(pid):
            continue
        log_path = _resolve_path(root, str(row["log_path"]))
        status, report_path, conclusion, error_summary = _classify_backfill_shard(
            root,
            log_path=log_path,
            command_json=str(row["command_json"]),
        )
        if not dry_run:
            conn.execute(
                """
                UPDATE maintenance_shards
                SET status = ?, finished_at = ?, report_path = ?, error_summary = ?, key_conclusion = ?
                WHERE shard_id = ?
                """,
                (
                    status,
                    now_iso,
                    str(report_path) if report_path else "",
                    error_summary,
                    conclusion,
                    int(row["shard_id"]),
                ),
            )
        changed += 1

    run_where = "task_name = ? AND status = 'running'"
    run_params: list[Any] = [task_name or LONG_BACKFILL_TASK]
    if run_id is not None:
        run_where += " AND run_id = ?"
        run_params.append(int(run_id))
    run_rows = conn.execute(
        f"SELECT run_id FROM maintenance_runs WHERE {run_where}",
        tuple(run_params),
    ).fetchall()
    for run in run_rows:
        current_run_id = int(run["run_id"])
        shard_rows = conn.execute(
            "SELECT status, report_path, error_summary, key_conclusion FROM maintenance_shards WHERE run_id = ?",
            (current_run_id,),
        ).fetchall()
        statuses = [str(item["status"]) for item in shard_rows]
        final_status, reason = _rollup_run_status(statuses)
        if final_status == "running":
            continue
        report_path = next((str(item["report_path"]) for item in shard_rows if str(item["report_path"] or "")), "")
        conclusion = "; ".join(str(item["key_conclusion"]) for item in shard_rows if str(item["key_conclusion"] or ""))[:1000]
        error_summary = "; ".join(str(item["error_summary"]) for item in shard_rows if str(item["error_summary"] or ""))[:1000] or reason
        if not dry_run:
            conn.execute(
                """
                UPDATE maintenance_runs
                SET status = ?, finished_at = ?, report_path = ?, error_summary = ?, key_conclusion = ?
                WHERE run_id = ?
                """,
                (final_status, now_iso, report_path, error_summary, conclusion, current_run_id),
            )
        changed += 1
    if not dry_run:
        conn.commit()
    return changed

def _shard_rows(conn: sqlite3.Connection, root: Path, *, run_id: int | None = None) -> list[MaintenanceShardStatusRow]:
    query = """
        SELECT run_id, task_name, shard_index, shard_count, status, pid, started_at,
               COALESCE(finished_at, '') AS finished_at, exit_code, log_path,
               report_path, error_summary, key_conclusion
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
            report_path=_resolve_path(root, str(row["report_path"])) if str(row["report_path"] or "") else None,
            error_summary=str(row["error_summary"] or ""),
            key_conclusion=str(row["key_conclusion"] or ""),
        )
        for row in rows
    ]


def _shard_rows_read_only(conn: sqlite3.Connection, root: Path, *, run_id: int | None = None) -> list[MaintenanceShardStatusRow]:
    shard_columns = _table_columns(conn, "maintenance_shards")
    required = {"run_id", "task_name", "shard_index", "shard_count", "status", "pid", "started_at", "log_path"}
    if not required.issubset(shard_columns):
        return []
    select_columns = [
        "run_id",
        "task_name",
        "shard_index",
        "shard_count",
        "status",
        "pid",
        "started_at",
        "COALESCE(finished_at, '') AS finished_at" if "finished_at" in shard_columns else "'' AS finished_at",
        "exit_code" if "exit_code" in shard_columns else "NULL AS exit_code",
        "log_path",
        "report_path" if "report_path" in shard_columns else "'' AS report_path",
        "error_summary" if "error_summary" in shard_columns else "'' AS error_summary",
        "key_conclusion" if "key_conclusion" in shard_columns else "'' AS key_conclusion",
    ]
    query = f"SELECT {', '.join(select_columns)} FROM maintenance_shards"
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
            report_path=_resolve_path(root, str(row["report_path"])) if str(row["report_path"] or "") else None,
            error_summary=str(row["error_summary"] or ""),
            key_conclusion=str(row["key_conclusion"] or ""),
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
    config_arg = _require_command_option(decision.command, "--config")
    command = [
        decision.command[0],
        "-m",
        "phase0.cli",
        "db-health",
        "--config",
        config_arg,
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
        decisions = [_evaluate_task(spec=spec, root=root, now=now, today=now.date().isoformat(), config_path=config_path) for spec in specs]
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
        _refresh_shards(conn, root)
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
        _refresh_shards(conn, root)
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
        _refresh_shards(conn, root)
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


def _registry_rows_from_specs(root: Path, specs: list[MaintenanceTaskSpec]) -> list[MaintenanceStatusRow]:
    rows: list[MaintenanceStatusRow] = []
    for spec in specs:
        state_path_value = spec.state_path or f"logs/scheduler/{spec.name}.state"
        state_path = _resolve_path(root, state_path_value)
        task_state = _parse_task_state(state_path)
        rows.append(
            MaintenanceStatusRow(
                task_name=spec.name,
                enabled=bool(spec.enabled),
                schedule_type=spec.schedule_type,
                schedule_value=spec.schedule_value,
                last_decision="unknown",
                last_reason="",
                last_tick_at="",
                last_success_at="",
                last_run_status="unknown",
                last_error=str(task_state.get("last_error") or ""),
                retry_count=int(task_state.get("retry_count") or 0),
                log_path=_resolve_path(root, spec.log_path),
                state_path=state_path,
            )
        )
    return rows


def _read_only_status(
    config_path: Path,
    *,
    root: Path,
    state_db: Path,
    now_iso: str,
) -> MaintenanceStatusResult:
    specs = _default_registry(config_path)
    rows = _registry_rows_from_specs(root, specs)
    if not state_db.exists():
        return MaintenanceStatusResult(state_db=state_db, generated_at=now_iso, rows=rows, shards=[])

    row_map = {row.task_name: row for row in rows}
    shards: list[MaintenanceShardStatusRow] = []
    try:
        with _connect_read_only(state_db) as conn:
            registry_columns = _table_columns(conn, "maintenance_registry")
            if registry_columns:
                select_columns = ["task_name", "enabled", "schedule_type", "schedule_value", "log_path"]
                if "state_path" in registry_columns:
                    select_columns.append("state_path")
                registry_rows = conn.execute(
                    f"SELECT {', '.join(select_columns)} FROM maintenance_registry ORDER BY task_name"
                ).fetchall()
                for item in registry_rows:
                    task_name = str(item["task_name"])
                    base_row = row_map.get(task_name)
                    if base_row is None:
                        state_path_value = str(item["state_path"]) if "state_path" in registry_columns else f"logs/scheduler/{task_name}.state"
                        state_path = _resolve_path(root, state_path_value)
                        task_state = _parse_task_state(state_path)
                        base_row = MaintenanceStatusRow(
                            task_name=task_name,
                            enabled=bool(item["enabled"]) if "enabled" in registry_columns else True,
                            schedule_type=str(item["schedule_type"]) if "schedule_type" in registry_columns else "time",
                            schedule_value=str(item["schedule_value"]) if "schedule_value" in registry_columns else "",
                            last_decision="unknown",
                            last_reason="",
                            last_tick_at="",
                            last_success_at="",
                            last_run_status="unknown",
                            last_error=str(task_state.get("last_error") or ""),
                            retry_count=int(task_state.get("retry_count") or 0),
                            log_path=_resolve_path(root, str(item["log_path"])) if "log_path" in registry_columns else root / "logs" / f"{task_name}.log",
                            state_path=state_path,
                        )
                    event = None
                    event_columns = _table_columns(conn, "maintenance_events")
                    if {"task_name", "decision", "reason", "created_at"}.issubset(event_columns):
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
                    run = None
                    success_run = None
                    run_columns = _table_columns(conn, "maintenance_runs")
                    if {"task_name", "status", "started_at"}.issubset(run_columns):
                        error_expr = "error_summary" if "error_summary" in run_columns else "'' AS error_summary"
                        run = conn.execute(
                            f"""
                            SELECT status, started_at, {error_expr}
                            FROM maintenance_runs
                            WHERE task_name = ?
                            ORDER BY run_id DESC
                            LIMIT 1
                            """,
                            (task_name,),
                        ).fetchone()
                    if {"task_name", "status", "finished_at"}.issubset(run_columns):
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
                    row_map[task_name] = MaintenanceStatusRow(
                        task_name=base_row.task_name,
                        enabled=bool(item["enabled"]) if "enabled" in registry_columns else base_row.enabled,
                        schedule_type=str(item["schedule_type"]) if "schedule_type" in registry_columns else base_row.schedule_type,
                        schedule_value=str(item["schedule_value"]) if "schedule_value" in registry_columns else base_row.schedule_value,
                        last_decision=str(event["decision"]) if event else base_row.last_decision,
                        last_reason=str(event["reason"]) if event else base_row.last_reason,
                        last_tick_at=str(event["created_at"]) if event else base_row.last_tick_at,
                        last_success_at=str(success_run["finished_at"]) if success_run else base_row.last_success_at,
                        last_run_status=str(run["status"]) if run else base_row.last_run_status,
                        last_error=str(run["error_summary"]) if run and "error_summary" in run.keys() else base_row.last_error,
                        retry_count=base_row.retry_count,
                        log_path=_resolve_path(root, str(item["log_path"])) if "log_path" in registry_columns else base_row.log_path,
                        state_path=_resolve_path(root, str(item["state_path"])) if "state_path" in registry_columns else base_row.state_path,
                    )
            shards = _shard_rows_read_only(conn, root)
    except sqlite3.Error:
        return MaintenanceStatusResult(
            state_db=state_db,
            generated_at=now_iso,
            rows=sorted(row_map.values(), key=lambda row: row.task_name),
            shards=[],
        )
    return MaintenanceStatusResult(
        state_db=state_db,
        generated_at=now_iso,
        rows=sorted(row_map.values(), key=lambda row: row.task_name),
        shards=shards,
    )


def _relative_display(root: Path, path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _md_escape(value: object) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")


def _md_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(_md_escape(item) for item in row) + " |")
    return "\n".join(lines)


def write_maintenance_status_report(result: MaintenanceStatusResult, output_path: Path, *, root: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    decision_counts: dict[str, int] = {}
    run_counts: dict[str, int] = {}
    shard_counts: dict[str, int] = {}
    for row in result.rows:
        decision_counts[row.last_decision] = decision_counts.get(row.last_decision, 0) + 1
        run_counts[row.last_run_status] = run_counts.get(row.last_run_status, 0) + 1
    for shard in result.shards:
        shard_counts[shard.status] = shard_counts.get(shard.status, 0) + 1

    task_rows = [
        [
            row.task_name,
            "yes" if row.enabled else "no",
            f"{row.schedule_type}:{row.schedule_value}",
            row.last_decision,
            row.last_reason,
            row.last_run_status,
            row.last_error,
            row.retry_count,
            _relative_display(root, row.log_path),
        ]
        for row in result.rows
    ]
    shard_rows = [
        [
            shard.run_id,
            shard.task_name,
            f"{shard.shard_index}/{shard.shard_count}",
            shard.status,
            shard.pid or "",
            shard.started_at,
            shard.finished_at,
            _relative_display(root, shard.log_path),
            _relative_display(root, shard.report_path),
            shard.error_summary,
            shard.key_conclusion,
        ]
        for shard in result.shards[:100]
    ]
    risk_items = []
    for shard in result.shards:
        if shard.status in {"failed", "exited_unknown", "running"}:
            risk_items.append(
                f"- run={shard.run_id} shard={shard.shard_index}/{shard.shard_count} "
                f"status={shard.status} error={shard.error_summary or 'N/A'} log={_relative_display(root, shard.log_path)}"
            )
    lines = [
        "# Maintenance Status Report",
        "",
        f"Generated at: {result.generated_at}",
        f"State DB: {result.state_db}",
        "",
        "## Summary",
        "",
        _md_table(
            ["metric", "value"],
            [
                ["tasks", len(result.rows)],
                ["decisions", json.dumps(decision_counts, ensure_ascii=False, sort_keys=True)],
                ["latest_run_statuses", json.dumps(run_counts, ensure_ascii=False, sort_keys=True)],
                ["shard_statuses", json.dumps(shard_counts, ensure_ascii=False, sort_keys=True)],
            ],
        ),
        "",
        "## Scheduled Tasks",
        "",
        _md_table(
            ["task", "enabled", "schedule", "last_decision", "reason", "last_run", "last_error", "retry_count", "log"],
            task_rows,
        ),
        "",
        "## Long Backfill Shards",
        "",
        _md_table(
            ["run_id", "task", "shard", "status", "pid", "started_at", "finished_at", "log", "report", "error", "conclusion"],
            shard_rows,
        ) if shard_rows else "No long backfill shards recorded.",
        "",
        "## Open Risks",
        "",
    ]
    lines.extend(risk_items or ["- None"])
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def maintenance_supervise(
    config_path: Path,
    *,
    task_name: str | None = None,
    run_id: int | None = None,
    dry_run: bool = False,
) -> MaintenanceLongRunResult:
    root, orchestrator_cfg = _load_maintenance_cfg(config_path)
    state_db = _configured_state_db(root, orchestrator_cfg)
    task_name = task_name or LONG_BACKFILL_TASK
    with _connect(state_db) as conn:
        _ensure_schema(conn)
        changed = _refresh_shards(conn, root, task_name=task_name, run_id=run_id, dry_run=dry_run)
        return MaintenanceLongRunResult(
            status="dry_run" if dry_run else "ok",
            task_name=task_name,
            run_id=run_id,
            state_db=state_db,
            shard_rows=_shard_rows(conn, root, run_id=run_id),
            message=f"updated_or_candidate_rows={changed}",
            dry_run=dry_run,
        )


def maintenance_status(
    config_path: Path,
    *,
    output_md: Path | None = None,
    write_report: bool = False,
    refresh_state: bool = True,
    read_only: bool = False,
) -> MaintenanceStatusResult:
    root, orchestrator_cfg = _load_maintenance_cfg(config_path)
    state_db = _configured_state_db(root, orchestrator_cfg)
    now_iso = datetime.now().isoformat(timespec="seconds")

    if read_only:
        return _read_only_status(
            config_path,
            root=root,
            state_db=state_db,
            now_iso=now_iso,
        )

    with _connect(state_db) as conn:
        _ensure_schema(conn)
        if refresh_state:
            _refresh_shards(conn, root)
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
    result = MaintenanceStatusResult(state_db=state_db, generated_at=now_iso, rows=rows, shards=shards)
    report_path: Path | None = None
    if write_report or output_md is not None:
        report_path = output_md or build_report_path(
            root=root,
            category="database_health",
            parts=("maintenance", f"maintenance_status_{datetime.now().date().isoformat()}.md"),
        )
        write_maintenance_status_report(result, report_path, root=root)
        result = MaintenanceStatusResult(
            state_db=result.state_db,
            generated_at=result.generated_at,
            rows=result.rows,
            shards=result.shards,
            report_path=report_path,
        )
    return result
