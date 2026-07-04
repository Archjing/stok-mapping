from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from phase0.ai_corpus.schema import AI_CORPUS_DOCUMENT_COLUMNS, normalize_documents


def ensure_ai_corpus_tables(conn: sqlite3.Connection) -> None:
    column_defs = ",\n                ".join(
        "document_id TEXT PRIMARY KEY" if column == "document_id" else f"{column} TEXT"
        for column in AI_CORPUS_DOCUMENT_COLUMNS
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS ai_corpus_documents (
                {column_defs}
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_corpus_provider_source ON ai_corpus_documents(provider, source_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_corpus_pubtime ON ai_corpus_documents(published_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_corpus_type ON ai_corpus_documents(corpus_type, event_type)")


def upsert_ai_corpus_documents(db_path: Path, rows: list[dict[str, Any]]) -> int:
    documents = normalize_documents(rows)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not documents:
        return 0
    placeholders = ", ".join(["?"] * len(AI_CORPUS_DOCUMENT_COLUMNS))
    columns = ", ".join(AI_CORPUS_DOCUMENT_COLUMNS)
    update_columns = [column for column in AI_CORPUS_DOCUMENT_COLUMNS if column != "document_id"]
    updates = ", ".join(f"{column}=excluded.{column}" for column in update_columns)
    values = [[document.get(column, "") for column in AI_CORPUS_DOCUMENT_COLUMNS] for document in documents]
    with sqlite3.connect(db_path) as conn:
        ensure_ai_corpus_tables(conn)
        before = conn.total_changes
        conn.executemany(
            f"""
            INSERT INTO ai_corpus_documents ({columns})
            VALUES ({placeholders})
            ON CONFLICT(document_id) DO UPDATE SET {updates}
            """,
            values,
        )
        return conn.total_changes - before


def query_ai_corpus_documents(
    db_path: Path,
    *,
    provider: str | None = None,
    corpus_type: str | None = None,
    event_type: str | None = None,
    keyword: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
) -> list[dict[str, str]]:
    if not db_path.exists():
        return []
    clauses: list[str] = []
    params: list[Any] = []
    if provider:
        clauses.append("provider = ?")
        params.append(provider)
    if corpus_type:
        clauses.append("corpus_type = ?")
        params.append(corpus_type)
    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    if keyword:
        clauses.append("(title LIKE ? OR summary LIKE ? OR raw_text LIKE ?)")
        needle = f"%{keyword}%"
        params.extend([needle, needle, needle])
    if start_date:
        clauses.append("published_at >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("published_at <= ?")
        params.append(end_date)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT {', '.join(AI_CORPUS_DOCUMENT_COLUMNS)}
        FROM ai_corpus_documents
        {where}
        ORDER BY published_at DESC, title
        LIMIT ?
    """
    params.append(limit)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        ensure_ai_corpus_tables(conn)
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
