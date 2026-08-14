from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any


@dataclass(frozen=True)
class SQLiteBenchmarkQuery:
    name: str
    sql: str
    parameters: tuple[Any, ...] = ()


@dataclass(frozen=True)
class SQLiteQueryBenchmark:
    name: str
    row_count: int
    result_sha256: str
    elapsed_ms: float
    query_plan: tuple[str, ...]


@dataclass(frozen=True)
class SQLiteIndexRemovalBenchmark:
    source_path: Path
    copy_path: Path
    removed_index: str
    removed_index_bytes: int
    before: tuple[SQLiteQueryBenchmark, ...]
    after_drop: tuple[SQLiteQueryBenchmark, ...]
    after_optimize: tuple[SQLiteQueryBenchmark, ...]
    pragma_optimize_output: tuple[tuple[Any, ...], ...]


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _read_only_uri(path: Path) -> str:
    return f"{path.resolve().as_uri()}?mode=ro"


def _copy_read_only_database(*, source_path: Path, copy_path: Path) -> None:
    copy_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_read_only_uri(source_path), uri=True) as source_conn:
        source_conn.execute("PRAGMA query_only = ON")
        with sqlite3.connect(copy_path) as copy_conn:
            source_conn.backup(copy_conn)


def _result_sha256(rows: list[tuple[Any, ...]]) -> str:
    payload = json.dumps(rows, ensure_ascii=False, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _benchmark_queries(
    conn: sqlite3.Connection,
    queries: tuple[SQLiteBenchmarkQuery, ...],
    *,
    query_plan_cache_key: str,
) -> tuple[SQLiteQueryBenchmark, ...]:
    benchmarks: list[SQLiteQueryBenchmark] = []
    for query in queries:
        query_plan = tuple(
            " | ".join(str(value) for value in row)
            for row in conn.execute(
                f"EXPLAIN QUERY PLAN /* {query_plan_cache_key} */ {query.sql}",
                query.parameters,
            ).fetchall()
        )
        started_at = perf_counter()
        rows = conn.execute(query.sql, query.parameters).fetchall()
        elapsed_ms = (perf_counter() - started_at) * 1000
        benchmarks.append(
            SQLiteQueryBenchmark(
                name=query.name,
                row_count=len(rows),
                result_sha256=_result_sha256(rows),
                elapsed_ms=elapsed_ms,
                query_plan=query_plan,
            )
        )
    return tuple(benchmarks)


def run_index_removal_benchmark(
    *,
    source_path: Path,
    copy_path: Path,
    index_name: str,
    queries: tuple[SQLiteBenchmarkQuery, ...],
) -> SQLiteIndexRemovalBenchmark:
    """Benchmark a candidate index only after taking a read-only source snapshot.

    The source is opened with SQLite URI ``mode=ro`` and ``query_only`` before the
    backup API produces the writable copy. Index removal, ANALYZE, and optimize
    are confined to that copy.
    """

    source_path = source_path.resolve()
    copy_path = copy_path.resolve()
    if source_path == copy_path:
        raise ValueError("copy_path must differ from source_path")
    if not source_path.is_file():
        raise FileNotFoundError(f"source SQLite database not found: {source_path}")
    if copy_path.exists():
        raise FileExistsError(f"copy_path already exists: {copy_path}")

    _copy_read_only_database(source_path=source_path, copy_path=copy_path)

    with sqlite3.connect(copy_path) as conn:
        index_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
            (index_name,),
        ).fetchone()
        if index_exists is None:
            raise ValueError(f"index not found in copied database: {index_name}")

        removed_index_bytes = int(
            conn.execute(
                "SELECT COALESCE(SUM(pgsize), 0) FROM dbstat WHERE name = ?",
                (index_name,),
            ).fetchone()[0]
        )
        before = _benchmark_queries(conn, queries, query_plan_cache_key="before")
        conn.execute(f"DROP INDEX {_quote_identifier(index_name)}")
        after_drop = _benchmark_queries(conn, queries, query_plan_cache_key="after_drop")
        conn.execute("ANALYZE")
        pragma_optimize_output = tuple(tuple(row) for row in conn.execute("PRAGMA optimize").fetchall())
        after_optimize = _benchmark_queries(conn, queries, query_plan_cache_key="after_optimize")

    return SQLiteIndexRemovalBenchmark(
        source_path=source_path,
        copy_path=copy_path,
        removed_index=index_name,
        removed_index_bytes=removed_index_bytes,
        before=before,
        after_drop=after_drop,
        after_optimize=after_optimize,
        pragma_optimize_output=pragma_optimize_output,
    )
