from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd

from phase0.data_governance.backfills.etf_history import (
    ETFBackfillLimits,
    create_etf_backfill_run,
)
from phase0.data_governance import etf_audit
from phase0.data_governance.etf_audit import audit_etf_history
from phase0.data_governance.etf_store import (
    ensure_etf_schema,
    refresh_run_counts,
    upsert_etf_adj_factors,
    upsert_etf_daily_bars,
)
from phase0.data_governance.etf_universe import (
    ETFManifestMember,
    ETFUniverseManifest,
)


def _prepared_run(tmp_path: Path) -> tuple[Path, str]:
    db_path = tmp_path / "etf.sqlite"
    manifest = ETFUniverseManifest(
        universe_name="sector_core_v1",
        requested_sectors=("semiconductor",),
        requested_start=date(2026, 1, 5),
        requested_end=date(2026, 1, 6),
        config_digest="digest-123",
        catalog_snapshot_id="snapshot-123",
        members=(
            ETFManifestMember(
                "sector_core_v1",
                "semiconductor",
                "SH.512480",
                "512480.SH",
                date(2026, 1, 5),
                date(2026, 1, 6),
                date(2026, 1, 5),
                date(2026, 1, 6),
                None,
                "CSI.931865",
                "not_configured",
            ),
        ),
    )
    bars = pd.DataFrame([
        {"symbol": "SH.512480", "date": "2026-01-05", "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05, "pre_close": 1.0, "change_amount": 0.05, "change_pct": 5.0, "volume": 100.0, "amount": 1000.0, "source": "fixture"},
        {"symbol": "SH.512480", "date": "2026-01-06", "open": 1.05, "high": 1.2, "low": 1.0, "close": 1.1, "pre_close": 1.05, "change_amount": 0.05, "change_pct": 4.76, "volume": 110.0, "amount": 1100.0, "source": "fixture"},
    ])
    factors = pd.DataFrame([
        {"symbol": "SH.512480", "date": "2026-01-05", "adj_factor": 1.0, "source": "fixture"},
        {"symbol": "SH.512480", "date": "2026-01-06", "adj_factor": 1.0, "source": "fixture"},
    ])
    with sqlite3.connect(db_path) as conn:
        ensure_etf_schema(conn)
        conn.execute(
            "INSERT INTO etf_catalog_sync_runs VALUES (?,?,?,?,?,?,?,?,?)",
            ("snapshot-123", "ok", "ok", "ok", 1, 0, "2026-08-11T00:00:00", "2026-08-11T00:01:00", None),
        )
        run_id = create_etf_backfill_run(
            conn,
            manifest,
            limits=ETFBackfillLimits(10, 20),
        )
        upsert_etf_daily_bars(conn, bars, fetched_at="2026-08-11T00:02:00")
        upsert_etf_adj_factors(conn, factors, fetched_at="2026-08-11T00:02:00")
        conn.execute(
            "UPDATE etf_backfill_tasks SET status='succeeded',fetched_rows=2,inserted_rows=2,finished_at='2026-08-11T00:02:00' WHERE run_id=?",
            (run_id,),
        )
        refresh_run_counts(conn, run_id)
        conn.execute("UPDATE etf_backfill_runs SET status='ok' WHERE run_id=?", (run_id,))
    return db_path, run_id


def test_audit_pass_requires_all_tasks_succeeded_and_factor_coverage_for_bar_dates(tmp_path):
    db_path, run_id = _prepared_run(tmp_path)
    report = audit_etf_history(db_path, run_id, report_dir=tmp_path / "reports")
    assert report.status == "PASS"
    assert report.factor_missing_bar_dates == 0
    assert report.json_path.exists()
    assert report.markdown_path.exists()
    with sqlite3.connect(db_path) as conn:
        stored_status, stored_audit_status = conn.execute(
            "SELECT status,audit_status FROM etf_backfill_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
    assert stored_status == "ok"
    assert stored_audit_status == "pass"


def test_failed_or_empty_task_blocks_pass(tmp_path):
    db_path, run_id = _prepared_run(tmp_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE etf_backfill_tasks SET status='empty',fetched_rows=0,inserted_rows=0 WHERE run_id=? AND dataset='daily'",
            (run_id,),
        )
        refresh_run_counts(conn, run_id)
        conn.execute("UPDATE etf_backfill_runs SET status='partial' WHERE run_id=?", (run_id,))
    report = audit_etf_history(db_path, run_id, report_dir=tmp_path / "reports")
    assert report.status == "FAIL"
    assert any("empty listed chunk" in finding for finding in report.blocking_findings)
    with sqlite3.connect(db_path) as conn:
        stored_audit_status = conn.execute(
            "SELECT audit_status FROM etf_backfill_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()[0]
    assert stored_audit_status == "blocking"


def test_audit_error_is_distinct_from_blocking_data(tmp_path):
    db_path, run_id = _prepared_run(tmp_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE market_etf_adj_factors")
    report = audit_etf_history(db_path, run_id, report_dir=tmp_path / "reports")
    assert report.status == "ERROR"
    with sqlite3.connect(db_path) as conn:
        stored_audit_status = conn.execute(
            "SELECT audit_status FROM etf_backfill_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()[0]
    assert stored_audit_status == "error"


def test_factor_coverage_uses_actual_bar_dates_not_calendar_dates(tmp_path):
    db_path, run_id = _prepared_run(tmp_path)
    report = audit_etf_history(db_path, run_id, report_dir=tmp_path / "reports")
    assert report.factor_missing_bar_dates == 0


def test_report_contains_manifest_and_task_identity(tmp_path):
    db_path, run_id = _prepared_run(tmp_path)
    report = audit_etf_history(db_path, run_id, report_dir=tmp_path / "reports")
    markdown = report.markdown_path.read_text(encoding="utf-8")
    payload = json.loads(report.json_path.read_text(encoding="utf-8"))
    assert report.run_id in markdown
    assert report.config_digest in markdown
    assert report.catalog_snapshot_id in markdown
    assert "semiconductor" in markdown
    assert "SH.512480" in markdown
    assert payload["run"]["run_id"] == run_id


def test_audit_from_config_resolves_local_database_and_report_paths(tmp_path, monkeypatch):
    captured: dict[str, object] = {}
    expected = object()
    monkeypatch.setattr(
        etf_audit,
        "load_config",
        lambda path: {
            "etf_history": {
                "path": "data/etf.sqlite",
                "report_dir": "reports/etf",
            }
        },
    )

    def fake_audit(db_path, run_id, *, report_dir):
        captured.update(db_path=db_path, run_id=run_id, report_dir=report_dir)
        return expected

    monkeypatch.setattr(etf_audit, "audit_etf_history", fake_audit)
    config_path = tmp_path / "project" / "config.yaml"
    result = etf_audit.audit_etf_history_from_config(config_path, "run-123")

    assert result is expected
    assert captured == {
        "db_path": config_path.parent / "data/etf.sqlite",
        "run_id": "run-123",
        "report_dir": config_path.parent / "reports/etf",
    }
