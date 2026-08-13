"""Per-stock traceable event timeline over the AI corpus.

Aggregates all corpus documents referencing a stock (via the ``symbols`` field)
into a time-ordered, traceable timeline.  This is the lightweight T1.7.9
deliverable — a query layer, NOT a RAG vector index.

Symbol normalization: accepts 6-digit codes (``300308``) or prefixed
(``SZ.300308``) and normalizes to the market DB convention (``SZ.300308``).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

DEFAULT_CORPUS_DB = Path("data/ai_corpus/ai_corpus.sqlite")


def normalize_symbol(raw: str) -> str | None:
    """Normalize a stock code to ``SH.xxxxxx`` / ``SZ.xxxxxx`` (or None if invalid)."""
    text = str(raw or "").strip()
    if not text:
        return None
    if text.startswith(("SH.", "SZ.")) and text[3:].isdigit() and len(text[3:]) == 6:
        return text
    if len(text) == 6 and text.isdigit():
        if text.startswith(("60", "68", "90")):
            return f"SH.{text}"
        if text.startswith(("00", "30")):
            return f"SZ.{text}"
    return None


def load_stock_timeline(
    corpus_db: Path = DEFAULT_CORPUS_DB,
    *,
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
    providers: list[str] | None = None,
) -> pd.DataFrame:
    """Return a time-ordered, traceable timeline for one stock.

    Matches documents whose ``symbols`` field contains the normalized symbol
    (the field holds comma-separated 6-digit codes).  Output columns:
    published_at, provider, event_type, title, url, source_id, parse_status.
    """
    norm = normalize_symbol(symbol)
    if norm is None:
        raise ValueError(f"invalid stock symbol: {symbol}")
    code6 = norm.split(".")[1]

    if not corpus_db.is_file():
        return pd.DataFrame()

    conn = sqlite3.connect(corpus_db)
    # symbols is comma-separated 6-digit codes; match token exactly
    sql = """
        SELECT document_id, provider, event_type, published_at, issued_at,
               ingested_at, as_of_time, title, url, source_id, parse_status, symbols
        FROM ai_corpus_documents
        WHERE symbols LIKE ?
    """
    params = [f"%{code6}%"]
    if providers:
        placeholders = ",".join("?" for _ in providers)
        sql += f" AND provider IN ({placeholders})"
        params.extend(providers)
    if start_date:
        sql += " AND published_at >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND published_at <= ?"
        params.append(end_date)
    sql += " ORDER BY published_at DESC"
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()

    if df.empty:
        return pd.DataFrame()

    # exact token match on the symbols field (avoid 300308 matching 1300308 etc)
    def _contains_code(symbols: str) -> bool:
        tokens = [t.strip() for t in str(symbols).split(",")]
        return code6 in tokens

    df = df[df["symbols"].map(_contains_code)]
    df = df.drop(columns=["symbols"])
    return df.reset_index(drop=True)


def timeline_summary(timeline: pd.DataFrame) -> dict:
    """Summarize a stock timeline: counts by provider and event type."""
    if timeline.empty:
        return {"n_events": 0, "by_provider": {}, "by_event_type": {}}
    return {
        "n_events": int(len(timeline)),
        "by_provider": timeline["provider"].value_counts().to_dict(),
        "by_event_type": timeline["event_type"].value_counts().to_dict(),
    }
