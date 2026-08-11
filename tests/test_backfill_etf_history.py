from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

import pytest

from phase0.data_governance.backfills.etf_history import (
    ETFBackfillLimits,
    ETFBackfillPlanError,
    ETFResumeMismatchError,
    annual_chunks,
    create_etf_backfill_run,
    enforce_requested_limits,
    load_resumable_tasks,
    plan_etf_task_specs,
    validate_resume_contract,
)
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
