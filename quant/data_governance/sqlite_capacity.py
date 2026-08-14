from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PRIMARY_SUFFIXES = {".sqlite", ".sqlite3", ".db"}
_BACKUP_RE = re.compile(
    r"^(?P<primary>.+\.(?:sqlite|sqlite3|db))\.(?:bak|backup|copy|snapshot|old)(?:[-_].*)?$",
    re.IGNORECASE,
)
_DEFAULT_OUTPUT_DIR = Path("reports/database_health/sqlite_capacity")
_LARGE_DATABASE_BYTES = 5 * 1024**3
_DATE_COLUMN_CANDIDATES = (
    "date",
    "trade_date",
    "report_date",
    "created_at",
    "updated_at",
    "observed_at",
    "published_at",
    "started_at",
    "fetched_at",
)


@dataclass(frozen=True)
class SQLiteObjectStat:
    name: str
    object_type: str
    table_name: str
    bytes: int
    pages: int


@dataclass(frozen=True)
class RedundantIndexFinding:
    table_name: str
    redundant_index: str
    covering_index: str
    columns: tuple[str, ...]
    redundant_bytes: int
    reason: str


@dataclass(frozen=True)
class SQLiteDatabaseStat:
    path: str
    size_bytes: int
    modified_at: str
    page_size: int
    page_count: int
    freelist_count: int
    journal_mode: str
    has_stat1: bool
    integrity_status: str
    objects: tuple[SQLiteObjectStat, ...]
    row_counts: dict[str, int]
    date_ranges: dict[str, dict[str, str]]
    redundant_indexes: tuple[RedundantIndexFinding, ...]
    warnings: tuple[str, ...]
    error: str


@dataclass(frozen=True)
class SQLiteBackupStat:
    path: str
    primary_path: str
    size_bytes: int
    modified_at: str


@dataclass(frozen=True)
class SQLiteCapacityAuditResult:
    status: str
    database_count: int
    backup_count: int
    total_primary_bytes: int
    total_backup_bytes: int
    warning_count: int
    error_count: int
    databases: tuple[SQLiteDatabaseStat, ...]
    backups: tuple[SQLiteBackupStat, ...]
    warnings: tuple[str, ...]
    json_path: Path
    markdown_path: Path


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _modified_at(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _discover_assets(*, root: Path, data_dir: Path) -> tuple[list[Path], list[SQLiteBackupStat]]:
    primary_paths: list[Path] = []
    backups: list[SQLiteBackupStat] = []
    if not data_dir.exists():
        return primary_paths, backups

    for path in sorted(item for item in data_dir.rglob("*") if item.is_file()):
        match = _BACKUP_RE.match(path.name)
        if match:
            primary_name = match.group("primary")
            primary_path = path.with_name(primary_name)
            backups.append(
                SQLiteBackupStat(
                    path=_relative_path(path, root),
                    primary_path=_relative_path(primary_path, root),
                    size_bytes=path.stat().st_size,
                    modified_at=_modified_at(path),
                )
            )
            continue
        if path.suffix.lower() in _PRIMARY_SUFFIXES:
            primary_paths.append(path)
    return primary_paths, backups


def _index_key_signature(conn: sqlite3.Connection, index_name: str) -> tuple[tuple[str, int, str], ...] | None:
    rows = conn.execute(f"PRAGMA index_xinfo({_quote_identifier(index_name)})").fetchall()
    key_rows = [row for row in rows if int(row[5]) == 1]
    if not key_rows or any(row[2] is None for row in key_rows):
        return None
    return tuple((str(row[2]), int(row[3]), str(row[4])) for row in key_rows)


def _redundant_indexes(
    conn: sqlite3.Connection,
    *,
    object_bytes: dict[str, int],
) -> tuple[RedundantIndexFinding, ...]:
    findings: list[RedundantIndexFinding] = []
    tables = [
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    for table_name in tables:
        groups: dict[tuple[tuple[str, int, str], ...], list[dict[str, Any]]] = {}
        for row in conn.execute(f"PRAGMA index_list({_quote_identifier(table_name)})"):
            index_name = str(row[1])
            partial = bool(row[4])
            if partial:
                continue
            signature = _index_key_signature(conn, index_name)
            if signature is None:
                continue
            groups.setdefault(signature, []).append(
                {
                    "name": index_name,
                    "unique": bool(row[2]),
                    "origin": str(row[3]),
                }
            )

        for signature, indexes in groups.items():
            if len(indexes) < 2:
                continue
            indexes.sort(
                key=lambda item: (
                    not bool(item["unique"]),
                    str(item["origin"]) == "c",
                    str(item["name"]),
                )
            )
            covering = indexes[0]
            for redundant in indexes[1:]:
                reason = "same ordered key columns"
                if bool(covering["unique"]) and not bool(redundant["unique"]):
                    reason = "covered by unique or primary-key index with the same ordered key columns"
                findings.append(
                    RedundantIndexFinding(
                        table_name=table_name,
                        redundant_index=str(redundant["name"]),
                        covering_index=str(covering["name"]),
                        columns=tuple(item[0] for item in signature),
                        redundant_bytes=int(object_bytes.get(str(redundant["name"]), 0)),
                        reason=reason,
                    )
                )
    return tuple(findings)


def _object_stats(conn: sqlite3.Connection) -> tuple[SQLiteObjectStat, ...]:
    master = {
        str(name): (str(object_type), str(table_name))
        for name, object_type, table_name in conn.execute(
            "SELECT name, type, tbl_name FROM sqlite_master WHERE type IN ('table', 'index')"
        )
    }
    rows = conn.execute(
        "SELECT name, SUM(pgsize) AS bytes, COUNT(*) AS pages "
        "FROM dbstat GROUP BY name ORDER BY bytes DESC, name"
    ).fetchall()
    objects: list[SQLiteObjectStat] = []
    for name, size_bytes, pages in rows:
        object_name = str(name)
        object_type, table_name = master.get(object_name, ("internal", object_name))
        objects.append(
            SQLiteObjectStat(
                name=object_name,
                object_type=object_type,
                table_name=table_name,
                bytes=int(size_bytes or 0),
                pages=int(pages or 0),
            )
        )
    return tuple(objects)


def _table_profiles(conn: sqlite3.Connection) -> tuple[dict[str, int], dict[str, dict[str, str]]]:
    tables = [
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    row_counts: dict[str, int] = {}
    date_ranges: dict[str, dict[str, str]] = {}
    for table_name in tables:
        quoted_table = _quote_identifier(table_name)
        row_counts[table_name] = int(conn.execute(f"SELECT COUNT(*) FROM {quoted_table}").fetchone()[0])
        columns = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({quoted_table})")}
        date_column = next((item for item in _DATE_COLUMN_CANDIDATES if item in columns), None)
        if date_column is None:
            continue
        quoted_column = _quote_identifier(date_column)
        minimum, maximum = conn.execute(
            f"SELECT MIN({quoted_column}), MAX({quoted_column}) FROM {quoted_table}"
        ).fetchone()
        date_ranges[table_name] = {
            "column": date_column,
            "min": "" if minimum is None else str(minimum),
            "max": "" if maximum is None else str(maximum),
        }
    return row_counts, date_ranges


def _inspect_database(
    *,
    path: Path,
    root: Path,
    quick_check: bool,
    row_counts: bool,
) -> SQLiteDatabaseStat:
    relative = _relative_path(path, root)
    warnings: list[str] = []
    integrity_status = "not_run"
    page_size = 0
    page_count = 0
    freelist_count = 0
    journal_mode = "unknown"
    has_stat1 = False
    objects: tuple[SQLiteObjectStat, ...] = ()
    counts: dict[str, int] = {}
    date_ranges: dict[str, dict[str, str]] = {}
    redundant: tuple[RedundantIndexFinding, ...] = ()
    error = ""

    try:
        uri = f"{path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=30) as conn:
            conn.execute("PRAGMA query_only = ON")
            page_size = int(conn.execute("PRAGMA page_size").fetchone()[0])
            page_count = int(conn.execute("PRAGMA page_count").fetchone()[0])
            freelist_count = int(conn.execute("PRAGMA freelist_count").fetchone()[0])
            journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0])
            has_stat1 = bool(
                conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_stat1'").fetchone()
            )
            objects = _object_stats(conn)
            object_bytes = {item.name: item.bytes for item in objects}
            redundant = _redundant_indexes(conn, object_bytes=object_bytes)
            if row_counts:
                counts, date_ranges = _table_profiles(conn)
            if quick_check:
                messages = [str(row[0]) for row in conn.execute("PRAGMA quick_check")]
                integrity_status = "ok" if messages == ["ok"] else "; ".join(messages)
    except (OSError, sqlite3.DatabaseError) as exc:
        error = f"{type(exc).__name__}: {exc}"

    size_bytes = path.stat().st_size
    if size_bytes >= _LARGE_DATABASE_BYTES:
        warnings.append(f"database size is {size_bytes} bytes and exceeds the 5 GiB review threshold")
    for finding in redundant:
        warnings.append(
            f"redundant index {finding.redundant_index} is covered by {finding.covering_index} "
            f"on {finding.table_name}"
        )
    if page_count and freelist_count / page_count >= 0.20:
        warnings.append(f"freelist ratio is {freelist_count / page_count:.1%}")
    if quick_check and integrity_status != "ok" and not error:
        warnings.append(f"quick_check returned {integrity_status}")

    return SQLiteDatabaseStat(
        path=relative,
        size_bytes=size_bytes,
        modified_at=_modified_at(path),
        page_size=page_size,
        page_count=page_count,
        freelist_count=freelist_count,
        journal_mode=journal_mode,
        has_stat1=has_stat1,
        integrity_status=integrity_status,
        objects=objects,
        row_counts=counts,
        date_ranges=date_ranges,
        redundant_indexes=redundant,
        warnings=tuple(warnings),
        error=error,
    )


def _json_payload(
    *,
    status: str,
    databases: tuple[SQLiteDatabaseStat, ...],
    backups: tuple[SQLiteBackupStat, ...],
    warnings: tuple[str, ...],
    total_primary_bytes: int,
    total_backup_bytes: int,
    warning_count: int,
    error_count: int,
) -> dict[str, Any]:
    return {
        "schema_version": "sqlite-capacity/v1",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "status": status,
        "database_count": len(databases),
        "backup_count": len(backups),
        "total_primary_bytes": total_primary_bytes,
        "total_backup_bytes": total_backup_bytes,
        "warning_count": warning_count,
        "error_count": error_count,
        "warnings": list(warnings),
        "databases": [asdict(item) for item in databases],
        "backups": [asdict(item) for item in backups],
    }


def _format_bytes(value: int) -> str:
    if value >= 1024**3:
        return f"{value / 1024**3:.2f} GiB"
    if value >= 1024**2:
        return f"{value / 1024**2:.1f} MiB"
    if value >= 1024:
        return f"{value / 1024:.1f} KiB"
    return f"{value} B"


def _write_markdown(
    *,
    path: Path,
    status: str,
    databases: tuple[SQLiteDatabaseStat, ...],
    backups: tuple[SQLiteBackupStat, ...],
    total_primary_bytes: int,
    total_backup_bytes: int,
    warnings: tuple[str, ...],
) -> None:
    lines = [
        "# SQLite Capacity Audit",
        "",
        f"- Status: `{status}`",
        f"- Primary databases: `{len(databases)}` / `{_format_bytes(total_primary_bytes)}`",
        f"- Backups: `{len(backups)}` / `{_format_bytes(total_backup_bytes)}`",
        "- Boundary: read-only inventory; no index deletion, VACUUM, ANALYZE, or journal-mode mutation",
        "",
        "## Databases",
        "",
        "| Path | Size | Pages | Freelist | Journal | Integrity | Error |",
        "| --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for item in databases:
        lines.append(
            f"| `{item.path}` | {_format_bytes(item.size_bytes)} | {item.page_count} | "
            f"{item.freelist_count} | `{item.journal_mode}` | `{item.integrity_status}` | {item.error or '-'} |"
        )

    lines.extend(["", "## Redundant indexes", ""])
    redundant_count = sum(len(item.redundant_indexes) for item in databases)
    if redundant_count:
        lines.extend(
            [
                "| Database | Table | Redundant | Covered by | Columns | Bytes |",
                "| --- | --- | --- | --- | --- | ---: |",
            ]
        )
        for database in databases:
            for finding in database.redundant_indexes:
                lines.append(
                    f"| `{database.path}` | `{finding.table_name}` | `{finding.redundant_index}` | "
                    f"`{finding.covering_index}` | `{', '.join(finding.columns)}` | "
                    f"{_format_bytes(finding.redundant_bytes)} |"
                )
    else:
        lines.append("No exact ordered-key redundant indexes detected.")

    lines.extend(["", "## Largest objects", ""])
    for database in databases:
        lines.append(f"### `{database.path}`")
        lines.append("")
        lines.append("| Object | Type | Table | Size | Pages | Rows | Date range |")
        lines.append("| --- | --- | --- | ---: | ---: | ---: | --- |")
        for object_stat in database.objects[:20]:
            row_count = database.row_counts.get(object_stat.name, "-")
            date_range = database.date_ranges.get(object_stat.name)
            rendered_range = "-"
            if date_range is not None:
                rendered_range = (
                    f"`{date_range['column']}`: {date_range['min'] or 'N/A'}..{date_range['max'] or 'N/A'}"
                )
            lines.append(
                f"| `{object_stat.name}` | {object_stat.object_type} | `{object_stat.table_name}` | "
                f"{_format_bytes(object_stat.bytes)} | {object_stat.pages} | {row_count} | {rendered_range} |"
            )
        lines.append("")

    lines.extend(["## Backups", ""])
    if backups:
        lines.extend(["| Path | Primary | Size | Modified at |", "| --- | --- | ---: | --- |"])
        for backup in backups:
            lines.append(
                f"| `{backup.path}` | `{backup.primary_path}` | {_format_bytes(backup.size_bytes)} | "
                f"{backup.modified_at} |"
            )
    else:
        lines.append("No SQLite backup files detected under `data/`.")

    lines.extend(["", "## Warnings", ""])
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_sqlite_capacity_audit(
    *,
    root: Path,
    output_dir: Path | None = None,
    quick_check: bool = False,
    row_counts: bool = False,
) -> SQLiteCapacityAuditResult:
    root = root.resolve()
    data_dir = root / "data"
    output_dir = (output_dir or root / _DEFAULT_OUTPUT_DIR).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    primary_paths, discovered_backups = _discover_assets(root=root, data_dir=data_dir)
    databases = tuple(
        _inspect_database(
            path=path,
            root=root,
            quick_check=quick_check,
            row_counts=row_counts,
        )
        for path in primary_paths
    )
    backups = tuple(discovered_backups)
    total_primary_bytes = sum(item.size_bytes for item in databases)
    total_backup_bytes = sum(item.size_bytes for item in backups)
    global_warnings: list[str] = []
    if total_primary_bytes and total_backup_bytes > total_primary_bytes:
        global_warnings.append(
            f"backup bytes ({total_backup_bytes}) exceed primary database bytes ({total_primary_bytes})"
        )
    if not databases:
        global_warnings.append("no primary SQLite databases found under data/")

    error_count = sum(1 for item in databases if item.error)
    integrity_failures = sum(
        1 for item in databases if quick_check and not item.error and item.integrity_status != "ok"
    )
    warning_count = sum(len(item.warnings) for item in databases) + len(global_warnings)
    status = "fail" if error_count or integrity_failures else ("warning" if warning_count else "pass")
    all_warnings = tuple(
        [f"{item.path}: {warning}" for item in databases for warning in item.warnings] + global_warnings
    )

    json_path = output_dir / "sqlite_capacity_report.json"
    markdown_path = output_dir / "sqlite_capacity_report.md"
    payload = _json_payload(
        status=status,
        databases=databases,
        backups=backups,
        warnings=all_warnings,
        total_primary_bytes=total_primary_bytes,
        total_backup_bytes=total_backup_bytes,
        warning_count=warning_count,
        error_count=error_count + integrity_failures,
    )
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_markdown(
        path=markdown_path,
        status=status,
        databases=databases,
        backups=backups,
        total_primary_bytes=total_primary_bytes,
        total_backup_bytes=total_backup_bytes,
        warnings=all_warnings,
    )
    return SQLiteCapacityAuditResult(
        status=status,
        database_count=len(databases),
        backup_count=len(backups),
        total_primary_bytes=total_primary_bytes,
        total_backup_bytes=total_backup_bytes,
        warning_count=warning_count,
        error_count=error_count + integrity_failures,
        databases=databases,
        backups=backups,
        warnings=all_warnings,
        json_path=json_path,
        markdown_path=markdown_path,
    )
