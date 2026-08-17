"""SQLite journal-mode governance for local market-data databases.

The local data directory holds several SQLite databases that are written by
background backfill/update jobs while being read concurrently by the API,
health checks and notebooks.  ``delete`` (the SQLite default) serialises a
writer against every concurrent reader, which is the root cause of
``database is locked`` during daily backfills.  ``wal`` lets readers and the
writer proceed concurrently, so this module migrates every primary database
under ``data/`` to ``wal`` and reports any remaining non-WAL files.

The migration is deliberately idempotent and cheap: it only touches files
that are still on ``delete`` (or otherwise not ``wal``), so it is safe to run
from the scheduled governance pass every day.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_PRIMARY_SUFFIXES = {".sqlite", ".sqlite3", ".db"}
_BACKUP_RE_NAMES = (".bak", "-bak", "_bak")


def _is_backup(name: str) -> bool:
    lower = name.lower()
    return ".bak" in lower or lower.endswith(".sqlite-wal") or lower.endswith(".sqlite-shm")


def _primary_sqlite_files(data_dir: Path) -> list[Path]:
    if not data_dir.exists():
        return []
    out: list[Path] = []
    for item in sorted(p for p in data_dir.rglob("*") if p.is_file()):
        if item.suffix.lower() not in _PRIMARY_SUFFIXES:
            continue
        if _is_backup(item.name):
            continue
        out.append(item)
    return out


@dataclass
class JournalMigrationResult:
    data_dir: Path
    scanned: int
    migrated: list[str] = field(default_factory=list)
    already_wal: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed


def migrate_journal_modes(data_dir: Path) -> JournalMigrationResult:
    """Migrate every primary SQLite file under ``data_dir`` to WAL journal mode."""
    result = JournalMigrationResult(data_dir=data_dir.resolve(), scanned=0)
    for path in _primary_sqlite_files(data_dir):
        result.scanned += 1
        rel = str(path.relative_to(data_dir)) if path.is_relative_to(data_dir) else str(path)
        try:
            with sqlite3.connect(path, timeout=30) as conn:
                mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
                if mode == "wal":
                    result.already_wal.append(rel)
                    continue
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                mode_after = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
                if mode_after == "wal":
                    result.migrated.append(rel)
                else:
                    result.failed.append(rel)
        except (sqlite3.Error, OSError) as exc:
            result.failed.append(f"{rel} ({type(exc).__name__})")
    return result


def migrate_journal_modes_from_config(config: dict[str, Any], root: Path) -> JournalMigrationResult:
    data_dir = root / "data"
    return migrate_journal_modes(data_dir)
