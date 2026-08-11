from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from phase0.data_governance.backfills.etf_history import (
    ETFBackfillLimits,
    ETFBackfillPlanError,
    ETFResumeMismatchError,
    MonotonicRateLimiter,
    annual_chunks,
    backfill_etf_history_from_config,
    create_etf_backfill_run,
    execute_etf_backfill_run,
    enforce_requested_limits,
    load_resumable_tasks,
    plan_etf_task_specs,
    validate_resume_contract,
)
from phase0.data_access.providers.tushare import TusharePermissionError
from phase0.data_governance.etf_store import ensure_etf_schema
from phase0.data_governance.etf_universe import ETFManifestMember, ETFUniverseManifest, history_config_digest


def _cfg() -> dict[str, object]:
    return {"etf_history": {"catalog_max_age_days": 7, "chunk_years": 1, "max_symbols_per_run": 50, "max_tasks_per_run": 1000, "universes": {"u": {"sectors": {"broad": [{"symbol": "SH.510300"}], "semi": [{"symbol": "SH.512480"}]}}}}}


def _manifest(cfg=None) -> ETFUniverseManifest:
    cfg = cfg or _cfg()
    members = (
        ETFManifestMember("u", "broad", "SH.510300", "510300.SH", date(2025, 1, 1), date(2026, 8, 11), date(2025, 1, 1), date(2026, 8, 11), None, "SH.000300", "not_configured"),
        ETFManifestMember("u", "semi", "SH.512480", "512480.SH", date(2025, 1, 1), date(2026, 8, 11), date(2025, 6, 1), date(2026, 8, 11), None, "CSI.931865", "not_configured"),
    )
    sectors = ("broad", "semi")
    return ETFUniverseManifest("u", sectors, date(2025, 1, 1), date(2026, 8, 11), history_config_digest(cfg, "u", sectors), "snap", members)


def _conn():
    conn = sqlite3.connect(":memory:")
    ensure_etf_schema(conn)
    conn.execute("INSERT INTO etf_catalog_sync_runs VALUES (?,?,?,?,?,?,?,?,?)", ("snap", "ok", "ok", "ok", 2, 0, "2026-08-10T00:00:00", "2026-08-10T00:01:00", None))
    return conn


def test_annual_chunks_and_symbol_year_dataset_tasks():
    assert annual_chunks(date(2025, 6, 1), date(2026, 2, 1)) == [(date(2025, 6, 1), date(2025, 12, 31)), (date(2026, 1, 1), date(2026, 2, 1))]
    tasks = plan_etf_task_specs(_manifest())
    assert len(tasks) == 8
    assert {task.dataset for task in tasks} == {"daily", "adj_factor"}
    assert [
        (task.sector, task.symbol, task.chunk_start, task.dataset)
        for task in tasks
    ] == sorted(
        (task.sector, task.symbol, task.chunk_start, task.dataset)
        for task in tasks
    )


def test_monotonic_rate_limiter_spaces_requests():
    now = [0.0]
    sleeps = []

    def clock():
        return now[0]

    def sleeper(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    limiter = MonotonicRateLimiter(120, clock=clock, sleeper=sleeper)
    limiter.wait()
    limiter.wait()
    now[0] += 0.2
    limiter.wait()
    assert sleeps == pytest.approx([0.5, 0.3])


@pytest.mark.parametrize(("limit_symbols", "limit_tasks"), [(0, None), (-1, None), (None, 0), (None, -1)])
def test_non_positive_cli_limits_fail_closed(limit_symbols, limit_tasks):
    manifest = _manifest()
    with pytest.raises(ETFBackfillPlanError, match="must be positive"):
        enforce_requested_limits(manifest, plan_etf_task_specs(manifest), configured=ETFBackfillLimits(50, 1000), limit_symbols=limit_symbols, limit_tasks=limit_tasks)


def test_task_count_limit_fails_before_run_insert():
    conn = _conn()
    with pytest.raises(ETFBackfillPlanError, match="max_tasks_per_run"):
        create_etf_backfill_run(conn, _manifest(), limits=ETFBackfillLimits(50, 2))
    assert conn.execute("SELECT COUNT(*) FROM etf_backfill_runs").fetchone()[0] == 0


def test_resume_contract_and_task_selection():
    cfg = _cfg()
    conn = _conn()
    run_id = create_etf_backfill_run(conn, _manifest(cfg), limits=ETFBackfillLimits(50, 1000), now=datetime(2026, 8, 11, 10))
    keys = conn.execute("SELECT dataset,chunk_start FROM etf_backfill_tasks WHERE run_id=? ORDER BY sector,symbol,chunk_start,dataset", (run_id,)).fetchall()
    conn.execute("UPDATE etf_backfill_tasks SET status='succeeded' WHERE run_id=? AND dataset=? AND chunk_start=?", (run_id, *keys[0]))
    conn.execute("UPDATE etf_backfill_tasks SET status='failed' WHERE run_id=? AND dataset=? AND chunk_start=?", (run_id, *keys[1]))
    conn.execute("UPDATE etf_backfill_tasks SET status='running',updated_at=? WHERE run_id=? AND dataset=? AND chunk_start=?", ((datetime(2026, 8, 11, 8)).isoformat(), run_id, *keys[2]))
    assert validate_resume_contract(conn, run_id, phase0_cfg=cfg).catalog_snapshot_id == "snap"
    resumable = load_resumable_tasks(conn, run_id, stale_running_minutes=30, now=datetime(2026, 8, 11, 10))
    assert "succeeded" not in [task.status for task in resumable]
    assert {task.status for task in resumable} <= {"failed", "pending"}


def test_resume_rejects_config_and_persisted_manifest_drift():
    cfg = _cfg()
    conn = _conn()
    run_id = create_etf_backfill_run(conn, _manifest(cfg), limits=ETFBackfillLimits(50, 1000))
    changed = _cfg()
    changed["etf_history"]["universes"]["u"]["sectors"]["semi"] = []
    with pytest.raises(ETFResumeMismatchError, match="config_digest"):
        validate_resume_contract(conn, run_id, phase0_cfg=changed)
    conn.execute("UPDATE etf_backfill_manifest_members SET catalog_snapshot_id='wrong' WHERE rowid=(SELECT rowid FROM etf_backfill_manifest_members WHERE run_id=? LIMIT 1)", (run_id,))
    with pytest.raises(ETFResumeMismatchError, match="manifest"):
        validate_resume_contract(conn, run_id, phase0_cfg=cfg)


class FakeProvider:
    def __init__(self, failures=(), empties=(), exceptions=None):
        self.failures = set(failures)
        self.empties = set(empties)
        self.exceptions = exceptions or {}
        self.calls = []

    def _frame(self, dataset, ts_code, start_date, end_date):
        key = (dataset, ts_code, start_date, end_date)
        self.calls.append(key)
        if key in self.exceptions:
            raise self.exceptions[key]
        if key in self.failures:
            raise ConnectionError("temporary provider failure token=secret")
        if key in self.empties:
            return pd.DataFrame()
        symbol = f"{ts_code.split('.')[1]}.{ts_code.split('.')[0]}"
        if dataset == "daily":
            return pd.DataFrame([{"symbol": symbol, "date": start_date.isoformat(), "open": 4, "high": 4.1, "low": 3.9, "close": 4.05, "pre_close": 4, "change_amount": .05, "change_pct": 1.25, "volume": 100, "amount": 1000, "source": "fake"}])
        return pd.DataFrame([{"symbol": symbol, "date": start_date.isoformat(), "adj_factor": 1.0, "source": "fake"}])

    def daily(self, ts_code, start_date, end_date):
        return self._frame("daily", ts_code, start_date, end_date)

    def adj_factor(self, ts_code, start_date, end_date):
        return self._frame("adj_factor", ts_code, start_date, end_date)


def _prepared_db(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "etf.sqlite"
    cfg = _cfg()
    with sqlite3.connect(db_path) as conn:
        ensure_etf_schema(conn)
        conn.execute("INSERT INTO etf_catalog_sync_runs VALUES (?,?,?,?,?,?,?,?,?)", ("snap", "ok", "ok", "ok", 2, 0, "2026-08-10T00:00:00", "2026-08-10T00:01:00", None))
        run_id = create_etf_backfill_run(conn, _manifest(cfg), limits=ETFBackfillLimits(50, 1000))
    return db_path, run_id


def test_failure_continues_other_tasks_but_run_is_partial(tmp_path):
    db_path, run_id = _prepared_db(tmp_path)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT dataset,ts_code,chunk_start,chunk_end FROM etf_backfill_tasks WHERE run_id=? ORDER BY sector,symbol,chunk_start,dataset LIMIT 1", (run_id,)).fetchone()
    failure = {(row[0], row[1], date.fromisoformat(row[2]), date.fromisoformat(row[3]))}
    result = execute_etf_backfill_run(db_path, run_id, provider=FakeProvider(failures=failure), max_requests_per_minute=100000, max_retries=1, retry_backoff_seconds=0, stale_running_minutes=30)
    assert result.status == "partial"
    assert result.succeeded_tasks > 0
    assert result.failed_tasks == 1
    with sqlite3.connect(db_path) as conn:
        assert "secret" not in (conn.execute("SELECT last_error FROM etf_backfill_tasks WHERE status='failed'").fetchone()[0])


def test_retryable_failure_retries_but_permission_failure_does_not(tmp_path):
    db_path, run_id = _prepared_db(tmp_path)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT dataset,ts_code,chunk_start,chunk_end FROM etf_backfill_tasks WHERE run_id=? ORDER BY sector,symbol,chunk_start,dataset LIMIT 1", (run_id,)).fetchone()
    key = (row[0], row[1], date.fromisoformat(row[2]), date.fromisoformat(row[3]))
    retrying = FakeProvider(failures={key})
    execute_etf_backfill_run(db_path, run_id, provider=retrying, max_requests_per_minute=1000000, max_retries=3, retry_backoff_seconds=0, stale_running_minutes=30)
    assert retrying.calls.count(key) == 3

    db_path, run_id = _prepared_db(tmp_path / "permission")
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT dataset,ts_code,chunk_start,chunk_end FROM etf_backfill_tasks WHERE run_id=? ORDER BY sector,symbol,chunk_start,dataset LIMIT 1", (run_id,)).fetchone()
    key = (row[0], row[1], date.fromisoformat(row[2]), date.fromisoformat(row[3]))
    denied = FakeProvider(exceptions={key: TusharePermissionError("fund_daily", 40203, "permission denied")})
    execute_etf_backfill_run(db_path, run_id, provider=denied, max_requests_per_minute=1000000, max_retries=3, retry_backoff_seconds=0, stale_running_minutes=30)
    assert denied.calls.count(key) == 1


def test_resume_does_not_call_provider_for_succeeded_tasks(tmp_path):
    db_path, run_id = _prepared_db(tmp_path)
    first = FakeProvider()
    assert execute_etf_backfill_run(db_path, run_id, provider=first, max_requests_per_minute=100000, max_retries=1, retry_backoff_seconds=0, stale_running_minutes=30).status == "ok"
    resumed = FakeProvider()
    assert execute_etf_backfill_run(db_path, run_id, provider=resumed, max_requests_per_minute=100000, max_retries=1, retry_backoff_seconds=0, stale_running_minutes=30).status == "ok"
    assert resumed.calls == []
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM market_etf_daily_bars").fetchone()[0] == 4


def test_empty_listed_chunk_is_persisted_and_blocks_ok(tmp_path):
    db_path, run_id = _prepared_db(tmp_path)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT dataset,ts_code,chunk_start,chunk_end FROM etf_backfill_tasks WHERE run_id=? AND dataset='daily' LIMIT 1", (run_id,)).fetchone()
    empty = {(row[0], row[1], date.fromisoformat(row[2]), date.fromisoformat(row[3]))}
    result = execute_etf_backfill_run(db_path, run_id, provider=FakeProvider(empties=empty), max_requests_per_minute=100000, max_retries=1, retry_backoff_seconds=0, stale_running_minutes=30)
    assert result.status == "partial"
    assert result.empty_tasks == 1


@pytest.mark.parametrize(("limit_symbols", "limit_tasks"), [(1, None), (None, 2)])
def test_resume_rejects_new_run_limits(monkeypatch, tmp_path, limit_symbols, limit_tasks):
    monkeypatch.setattr(
        "phase0.data_governance.backfills.etf_history.load_config",
        lambda _path: {
            "etf_history": {"path": str(tmp_path / "etf.sqlite")},
            "data_sources": {"tushare": {}},
        },
    )
    with pytest.raises(ETFBackfillPlanError, match="resume rejects"):
        backfill_etf_history_from_config(
            tmp_path / "config.yaml",
            resume_run_id="run",
            limit_symbols=limit_symbols,
            limit_tasks=limit_tasks,
        )
