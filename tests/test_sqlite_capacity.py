from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

from quant.data_governance.sqlite_capacity import run_sqlite_capacity_audit


def _build_history_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE prices (
                market TEXT NOT NULL,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                close REAL,
                PRIMARY KEY (market, symbol, date)
            )
            """
        )
        conn.execute("CREATE INDEX idx_prices_duplicate ON prices(market, symbol, date)")
        conn.executemany(
            "INSERT INTO prices VALUES (?, ?, ?, ?)",
            [
                ("CN", "SH.600000", "2026-08-13", 10.0),
                ("CN", "SH.600000", "2026-08-14", 10.5),
            ],
        )


def test_capacity_audit_is_read_only_and_reports_objects_rows_backups_and_redundant_indexes(tmp_path: Path) -> None:
    root = tmp_path
    db_path = root / "data" / "history.sqlite"
    _build_history_db(db_path)
    backup_path = root / "data" / "history.sqlite.bak-20260814"
    shutil.copy2(db_path, backup_path)
    before = (db_path.stat().st_size, db_path.stat().st_mtime_ns)

    result = run_sqlite_capacity_audit(
        root=root,
        output_dir=root / "reports" / "capacity",
        quick_check=True,
        row_counts=True,
    )

    after = (db_path.stat().st_size, db_path.stat().st_mtime_ns)
    assert after == before
    assert not Path(f"{db_path}-wal").exists()
    assert not Path(f"{db_path}-journal").exists()
    assert result.status == "warning"
    assert result.database_count == 1
    assert result.backup_count == 1
    assert result.error_count == 0
    assert result.warning_count >= 1
    assert result.total_primary_bytes == db_path.stat().st_size
    assert result.total_backup_bytes == backup_path.stat().st_size

    database = result.databases[0]
    assert database.path == "data/history.sqlite"
    assert database.integrity_status == "ok"
    assert database.journal_mode in {"delete", "wal"}
    assert database.page_size > 0
    assert database.page_count > 0
    assert database.row_counts == {"prices": 2}
    assert database.date_ranges == {
        "prices": {"column": "date", "min": "2026-08-13", "max": "2026-08-14"}
    }
    assert any(item.name == "prices" and item.object_type == "table" for item in database.objects)
    assert any(
        item.redundant_index == "idx_prices_duplicate"
        and item.covering_index == "sqlite_autoindex_prices_1"
        and item.columns == ("market", "symbol", "date")
        for item in database.redundant_indexes
    )

    payload = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert payload["status"] == "warning"
    assert payload["databases"][0]["row_counts"] == {"prices": 2}
    assert payload["databases"][0]["date_ranges"]["prices"]["max"] == "2026-08-14"
    assert payload["backups"][0]["path"] == "data/history.sqlite.bak-20260814"
    markdown = result.markdown_path.read_text(encoding="utf-8")
    assert "SQLite Capacity Audit" in markdown
    assert "idx_prices_duplicate" in markdown
    assert "history.sqlite.bak-20260814" in markdown


def test_capacity_audit_defaults_to_metadata_only_and_records_corrupt_database_errors(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    corrupt = data_dir / "corrupt.sqlite"
    corrupt.write_text("not a sqlite database")

    result = run_sqlite_capacity_audit(root=tmp_path, output_dir=tmp_path / "out")

    assert result.status == "fail"
    assert result.database_count == 1
    assert result.error_count == 1
    database = result.databases[0]
    assert database.integrity_status == "not_run"
    assert database.row_counts == {}
    assert database.error
    assert result.json_path.exists()
    assert result.markdown_path.exists()


def test_capacity_audit_ignores_non_database_files_and_discovers_nested_databases(tmp_path: Path) -> None:
    nested = tmp_path / "data" / "nested" / "state.db"
    _build_history_db(nested)
    (tmp_path / "data" / "notes.txt").write_text("ignore")

    result = run_sqlite_capacity_audit(root=tmp_path, output_dir=tmp_path / "out")

    assert [database.path for database in result.databases] == ["data/nested/state.db"]
    assert result.backup_count == 0
