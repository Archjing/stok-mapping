from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from phase0.config import load_config
from phase0.data_governance.backfills.etf_history import (
    load_persisted_manifest,
    plan_etf_task_specs,
)


@dataclass(frozen=True)
class ETFAuditResult:
    status: str
    run_id: str
    universe_name: str
    config_digest: str
    catalog_snapshot_id: str
    target_tasks: int
    succeeded_tasks: int
    empty_tasks: int
    failed_tasks: int
    factor_missing_bar_dates: int
    blocking_findings: tuple[str, ...]
    json_path: Path
    markdown_path: Path

    @property
    def exit_code(self) -> int:
        return 0 if self.status == "PASS" else 2


def _iso_now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _task_identity(row: tuple[object, ...]) -> str:
    sector, symbol, dataset, chunk_start, chunk_end, status = row
    return f"{sector}/{symbol}/{dataset}/{chunk_start}:{chunk_end} [{status}]"


def _write_reports(
    *,
    report_dir: Path,
    run_id: str,
    payload: dict[str, object],
) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / f"etf_history_audit_{run_id}.json"
    markdown_path = report_dir / f"etf_history_audit_{run_id}.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    run = payload["run"]
    counts = payload["task_counts"]
    lines = [
        "# ETF History Audit",
        "",
        f"- Status: `{payload['status']}`",
        f"- Run ID: `{run['run_id']}`",
        f"- Universe: `{run['universe_name']}`",
        f"- Requested sectors: `{', '.join(run['requested_sectors'])}`",
        f"- Requested dates: `{run['requested_start']}` to `{run['requested_end']}`",
        f"- Config digest: `{run['config_digest']}`",
        f"- Catalog snapshot: `{run['catalog_snapshot_id']}`",
        f"- Task status: `{run['task_status']}`",
        f"- Audit status persisted: `{payload['audit_status']}`",
        "",
        "## Task Counts",
        "",
        f"- Target: {counts['target_tasks']}",
        f"- Succeeded: {counts['succeeded_tasks']}",
        f"- Empty: {counts['empty_tasks']}",
        f"- Failed: {counts['failed_tasks']}",
        f"- Pending: {counts['pending_tasks']}",
        f"- Running: {counts['running_tasks']}",
        "",
        "## Manifest",
        "",
    ]
    for member in payload["manifest_members"]:
        lines.append(
            "- `{sector}` `{symbol}` (`{ts_code}`), effective `{effective_start}` to "
            "`{effective_end}`, tracking `{tracking}`".format(
                sector=member["sector"],
                symbol=member["symbol"],
                ts_code=member["ts_code"],
                effective_start=member["effective_start"],
                effective_end=member["effective_end"],
                tracking=member["resolved_tracking_index"] or "unavailable",
            )
        )
    lines.extend(["", "## Blocking Findings", ""])
    findings = payload["blocking_findings"]
    lines.extend([f"- {finding}" for finding in findings] or ["- None"])
    lines.extend(["", "## Task Exceptions", ""])
    exceptions = payload["task_exceptions"]
    lines.extend([f"- `{item}`" for item in exceptions] or ["- None"])
    lines.extend(["", "## Data Ranges", ""])
    for item in payload["data_ranges"]:
        lines.append(
            f"- `{item['symbol']}` bars `{item['bar_min']}` to `{item['bar_max']}`; "
            f"factors `{item['factor_min']}` to `{item['factor_max']}`"
        )
    lines.extend([
        "",
        "## Factor Coverage",
        "",
        f"- Missing factor bar dates: {payload['factor_missing_bar_dates']}",
    ])
    for item in payload["factor_gaps"]:
        lines.append(f"- `{item['symbol']}` `{item['date']}`")
    lines.extend([
        "",
        "## Metadata Boundary",
        "",
        "- Provider tracking observations without effective dates are non-PIT metadata and are not historical membership facts.",
        f"- Non-PIT tracking observation rows in the catalog snapshot: {payload['non_pit_tracking_observations']}",
        "",
    ])
    if payload.get("audit_error"):
        lines.extend(["## Audit Error", "", f"- {payload['audit_error']}", ""])
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, markdown_path


def audit_etf_history(db_path: Path, run_id: str, *, report_dir: Path) -> ETFAuditResult:
    """Evaluate blocking invariants and write deterministic JSON and Markdown reports."""
    db_path = Path(db_path)
    report_dir = Path(report_dir)
    with sqlite3.connect(db_path) as conn:
        run_row = conn.execute(
            """SELECT universe_name,requested_sectors_json,requested_start,requested_end,
                      config_digest,catalog_snapshot_id,status,target_tasks,succeeded_tasks,
                      empty_tasks,failed_tasks
               FROM etf_backfill_runs WHERE run_id=?""",
            (run_id,),
        ).fetchone()
        if run_row is None:
            raise ValueError(f"unknown ETF backfill run_id: {run_id}")

        (
            universe_name,
            sectors_json,
            requested_start,
            requested_end,
            config_digest,
            catalog_snapshot_id,
            task_status,
            stored_target,
            stored_succeeded,
            stored_empty,
            stored_failed,
        ) = run_row
        requested_sectors = tuple(json.loads(sectors_json))
        blocking: list[str] = []
        task_exceptions: list[str] = []
        factor_gaps: list[dict[str, str]] = []
        data_ranges: list[dict[str, object]] = []
        manifest_payload: list[dict[str, object]] = []
        non_pit_tracking_observations = 0
        grouped: dict[str, int] = {}
        audit_error: str | None = None

        try:
            manifest = load_persisted_manifest(conn, run_id)
            manifest_payload = [
                {
                    "sector": member.sector,
                    "symbol": member.symbol,
                    "ts_code": member.ts_code,
                    "requested_start": member.requested_start.isoformat(),
                    "requested_end": member.requested_end.isoformat(),
                    "effective_start": member.effective_start.isoformat(),
                    "effective_end": member.effective_end.isoformat(),
                    "expected_tracking_index": member.expected_tracking_index,
                    "resolved_tracking_index": member.resolved_tracking_index,
                    "mapping_assertion_status": member.mapping_assertion_status,
                }
                for member in manifest.members
            ]
            task_rows = conn.execute(
                """SELECT sector,symbol,dataset,chunk_start,chunk_end,status
                   FROM etf_backfill_tasks WHERE run_id=?
                   ORDER BY sector,symbol,chunk_start,dataset""",
                (run_id,),
            ).fetchall()
            grouped = dict(
                conn.execute(
                    "SELECT status,COUNT(*) FROM etf_backfill_tasks WHERE run_id=? GROUP BY status",
                    (run_id,),
                ).fetchall()
            )
            computed_counts = {
                "target_tasks": sum(grouped.values()),
                "succeeded_tasks": grouped.get("succeeded", 0),
                "empty_tasks": grouped.get("empty", 0),
                "failed_tasks": grouped.get("failed", 0),
            }
            stored_counts = {
                "target_tasks": stored_target,
                "succeeded_tasks": stored_succeeded,
                "empty_tasks": stored_empty,
                "failed_tasks": stored_failed,
            }
            if computed_counts != stored_counts:
                blocking.append(f"stored run counts disagree with task counts: stored={stored_counts}, computed={computed_counts}")

            expected_keys = {
                (spec.sector, spec.symbol, spec.dataset, spec.chunk_start.isoformat(), spec.chunk_end.isoformat())
                for spec in plan_etf_task_specs(manifest)
            }
            actual_keys = {tuple(row[:5]) for row in task_rows}
            missing_keys = sorted(expected_keys - actual_keys)
            unexpected_keys = sorted(actual_keys - expected_keys)
            if missing_keys:
                blocking.append(f"missing planned task identities: {len(missing_keys)}")
            if unexpected_keys:
                blocking.append(f"unexpected task identities: {len(unexpected_keys)}")

            for row in task_rows:
                if row[5] == "failed":
                    task_exceptions.append(_task_identity(row))
                    blocking.append(f"failed task: {_task_identity(row)}")
                elif row[5] == "empty":
                    task_exceptions.append(_task_identity(row))
                    blocking.append(f"empty listed chunk: {_task_identity(row)}")
                elif row[5] != "succeeded":
                    task_exceptions.append(_task_identity(row))
                    blocking.append(f"incomplete task: {_task_identity(row)}")
            if task_status != "ok":
                blocking.append(f"task-level run status is {task_status}, expected ok")

            factor_gaps = [
                {"symbol": row[0], "date": row[1]}
                for row in conn.execute(
                    """SELECT DISTINCT bars.symbol,bars.date
                       FROM market_etf_daily_bars AS bars
                       JOIN etf_backfill_manifest_members AS members
                         ON members.run_id=? AND members.symbol=bars.symbol
                        AND bars.date BETWEEN members.effective_start AND members.effective_end
                       LEFT JOIN market_etf_adj_factors AS factors
                         ON factors.symbol=bars.symbol AND factors.date=bars.date
                       WHERE factors.symbol IS NULL
                       ORDER BY bars.symbol,bars.date""",
                    (run_id,),
                ).fetchall()
            ]
            if factor_gaps:
                blocking.append(f"missing factor for actual bar dates: {len(factor_gaps)}")

            duplicate_bars = conn.execute(
                """SELECT COUNT(*) FROM (
                       SELECT bars.symbol,bars.date,COUNT(*) AS n
                       FROM market_etf_daily_bars AS bars
                       JOIN etf_backfill_manifest_members AS members
                         ON members.run_id=? AND members.symbol=bars.symbol
                        AND bars.date BETWEEN members.effective_start AND members.effective_end
                       GROUP BY bars.symbol,bars.date HAVING n>1
                   )""",
                (run_id,),
            ).fetchone()[0]
            duplicate_factors = conn.execute(
                """SELECT COUNT(*) FROM (
                       SELECT factors.symbol,factors.date,COUNT(*) AS n
                       FROM market_etf_adj_factors AS factors
                       JOIN etf_backfill_manifest_members AS members
                         ON members.run_id=? AND members.symbol=factors.symbol
                        AND factors.date BETWEEN members.effective_start AND members.effective_end
                       GROUP BY factors.symbol,factors.date HAVING n>1
                   )""",
                (run_id,),
            ).fetchone()[0]
            if duplicate_bars:
                blocking.append(f"duplicate daily bar logical keys: {duplicate_bars}")
            if duplicate_factors:
                blocking.append(f"duplicate adjustment factor logical keys: {duplicate_factors}")

            for member in manifest.members:
                bar_range = conn.execute(
                    "SELECT MIN(date),MAX(date),COUNT(*) FROM market_etf_daily_bars WHERE symbol=? AND date BETWEEN ? AND ?",
                    (member.symbol, member.effective_start.isoformat(), member.effective_end.isoformat()),
                ).fetchone()
                factor_range = conn.execute(
                    "SELECT MIN(date),MAX(date),COUNT(*) FROM market_etf_adj_factors WHERE symbol=? AND date BETWEEN ? AND ?",
                    (member.symbol, member.effective_start.isoformat(), member.effective_end.isoformat()),
                ).fetchone()
                data_ranges.append({
                    "sector": member.sector,
                    "symbol": member.symbol,
                    "bar_min": bar_range[0],
                    "bar_max": bar_range[1],
                    "bar_rows": bar_range[2],
                    "factor_min": factor_range[0],
                    "factor_max": factor_range[1],
                    "factor_rows": factor_range[2],
                })
            non_pit_tracking_observations = conn.execute(
                """SELECT COUNT(*) FROM market_etf_tracking_mappings
                   WHERE catalog_snapshot_id=? AND mapping_kind='provider_observation'
                     AND (is_point_in_time=0 OR effective_from IS NULL)""",
                (catalog_snapshot_id,),
            ).fetchone()[0]
        except Exception as exc:
            audit_error = f"{exc.__class__.__name__}: {str(exc)[:500]}"

        if audit_error is not None:
            status = "ERROR"
            audit_status = "error"
        elif blocking:
            status = "FAIL"
            audit_status = "blocking"
        else:
            status = "PASS"
            audit_status = "pass"

        task_counts = {
            "target_tasks": int(sum(grouped.values())) if grouped else int(stored_target),
            "succeeded_tasks": int(grouped.get("succeeded", stored_succeeded)),
            "empty_tasks": int(grouped.get("empty", stored_empty)),
            "failed_tasks": int(grouped.get("failed", stored_failed)),
            "pending_tasks": int(grouped.get("pending", 0)),
            "running_tasks": int(grouped.get("running", 0)),
        }
        payload: dict[str, object] = {
            "schema_version": "etf-history-audit/v1",
            "status": status,
            "audit_status": audit_status,
            "run": {
                "run_id": run_id,
                "universe_name": universe_name,
                "requested_sectors": list(requested_sectors),
                "requested_start": requested_start,
                "requested_end": requested_end,
                "config_digest": config_digest,
                "catalog_snapshot_id": catalog_snapshot_id,
                "task_status": task_status,
            },
            "task_counts": task_counts,
            "manifest_members": manifest_payload,
            "task_exceptions": task_exceptions,
            "data_ranges": data_ranges,
            "factor_missing_bar_dates": len(factor_gaps),
            "factor_gaps": factor_gaps,
            "non_pit_tracking_observations": non_pit_tracking_observations,
            "blocking_findings": blocking,
            "audit_error": audit_error,
        }
        json_path, markdown_path = _write_reports(
            report_dir=report_dir,
            run_id=run_id,
            payload=payload,
        )
        with conn:
            conn.execute(
                "UPDATE etf_backfill_runs SET audit_status=?,audited_at=? WHERE run_id=?",
                (audit_status, _iso_now(), run_id),
            )

        return ETFAuditResult(
            status=status,
            run_id=run_id,
            universe_name=str(universe_name),
            config_digest=str(config_digest),
            catalog_snapshot_id=str(catalog_snapshot_id),
            target_tasks=task_counts["target_tasks"],
            succeeded_tasks=task_counts["succeeded_tasks"],
            empty_tasks=task_counts["empty_tasks"],
            failed_tasks=task_counts["failed_tasks"],
            factor_missing_bar_dates=len(factor_gaps),
            blocking_findings=tuple(blocking),
            json_path=json_path,
            markdown_path=markdown_path,
        )


def audit_etf_history_from_config(config_path: Path, run_id: str) -> ETFAuditResult:
    """Resolve local-only ETF audit paths from config and audit a persisted run."""
    config_path = Path(config_path).resolve()
    phase0_cfg = load_config(config_path)
    history_cfg = phase0_cfg.get("etf_history")
    if not isinstance(history_cfg, dict):
        raise ValueError("phase0.etf_history configuration must be a mapping")
    db_path = Path(str(history_cfg.get("path", "data/etf_history.sqlite")))
    report_dir = Path(str(history_cfg.get("report_dir", "reports/database_health/etf_history")))
    if not db_path.is_absolute():
        db_path = config_path.parent / db_path
    if not report_dir.is_absolute():
        report_dir = config_path.parent / report_dir
    return audit_etf_history(db_path, run_id, report_dir=report_dir)
