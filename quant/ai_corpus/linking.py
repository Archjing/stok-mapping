"""Event→security linking for event studies.

Two linking paths:
- **stock-level**: cninfo/research-report docs carry a ``symbols`` column with
  6-digit codes; normalized to ``SH.xxxxxx`` / ``SZ.xxxxxx`` and expanded to one
  row per security.
- **policy-level**: gov_policy docs have no symbols; linked to industry/theme
  indices via a local embedding model (cosine similarity on index names), with a
  deterministic keyword fallback when no model is available.

Linking is an association layer, not a signal: it maps a document to the
securities whose returns the event study should measure, and never enters a
strategy ranker.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

_SH_PREFIXES = ("60", "68", "90")  # 60x/68x main+STAR, 90x B-share (SH)
_SZ_PREFIXES = ("00", "30")  # 00x main + ChiNext, 30x ChiNext
_BJ_PREFIXES = ("43", "83", "87", "92")  # BSE — not in local DB, return None


def normalize_stock_symbol(raw: str) -> str | None:
    """Normalize a stock code to the project's ``SH.xxxxxx`` / ``SZ.xxxxxx`` form.

    Returns None for empty / non-numeric / unsupported (BSE) codes, since the
    local market DB has no data for them.
    """
    text = str(raw or "").strip()
    if not text:
        return None
    if text.startswith(("SH.", "SZ.")) and text[3:].isdigit() and len(text[3:]) == 6:
        return text
    if len(text) == 6 and text.isdigit():
        if text.startswith(_SH_PREFIXES):
            return f"SH.{text}"
        if text.startswith(_SZ_PREFIXES):
            return f"SZ.{text}"
        # BSE or unknown prefix — no local data
        return None
    return None


def link_stock_events(docs: pd.DataFrame) -> pd.DataFrame:
    """Expand stock-level documents (cninfo / research_report) to one row per security.

    Requires ``symbols``, ``document_id``, ``published_at`` columns.  Drops rows
    with empty symbols or unnormalizable codes.
    """
    if docs.empty:
        return pd.DataFrame(columns=["document_id", "provider", "published_at", "title", "symbol"])
    rows: list[dict[str, Any]] = []
    for _, doc in docs.iterrows():
        raw_symbols = str(doc.get("symbols", "") or "")
        for token in raw_symbols.replace("，", ",").split(","):
            symbol = normalize_stock_symbol(token)
            if symbol is None:
                continue
            rows.append({
                "document_id": doc.get("document_id"),
                "provider": doc.get("provider"),
                "published_at": doc.get("published_at"),
                "title": doc.get("title"),
                "symbol": symbol,
            })
    if not rows:
        return pd.DataFrame(columns=["document_id", "provider", "published_at", "title", "symbol"])
    return pd.DataFrame(rows)


def load_industry_indices(
    database_path: str | Path,
    *,
    category: str = "一级行业指数",
) -> pd.DataFrame:
    """Load industry/theme index symbols + names from ``market_indices``."""
    db = Path(database_path)
    if not db.is_file():
        return pd.DataFrame(columns=["symbol", "name"])
    with sqlite3.connect(str(db)) as conn:
        try:
            rows = conn.execute(
                "SELECT symbol, name FROM market_indices WHERE category = ? ORDER BY symbol",
                (category,),
            ).fetchall()
        except sqlite3.Error:
            return pd.DataFrame(columns=["symbol", "name"])
    return pd.DataFrame([{"symbol": r[0], "name": r[1]} for r in rows])


def _keyword_score(text: str, name: str) -> int:
    """Overlap score between a policy text and an index name (fallback link)."""
    if not text or not name:
        return 0
    # name terms of length >= 2 that appear in the text
    score = 0
    for ch in ["能源", "材料", "工业", "消费", "医药", "金融", "地产", "信息",
               "通信", "公用", "可选", "国防", "军工", "半导体", "芯片", "汽车",
               "新能源", "光伏", "银行", "证券", "保险", "煤炭", "钢铁", "有色"]:
        if ch in name and ch in text:
            score += 1
    return score


def link_policy_events(
    docs: pd.DataFrame,
    indices: pd.DataFrame,
    *,
    model=None,
    top_k: int = 3,
) -> pd.DataFrame:
    """Link policy documents to industry indices (embedding or keyword fallback).

    When ``model`` is None (no local embedding model), falls back to keyword
    overlap.  When ``model`` is provided, it must expose ``encode(list[str])``
    returning a matrix of vectors.
    """
    if docs.empty or indices.empty:
        return pd.DataFrame(columns=["document_id", "provider", "published_at", "title", "symbol", "score"])

    rows: list[dict[str, Any]] = []
    for _, doc in docs.iterrows():
        text = f"{doc.get('title', '')} {doc.get('raw_text', '')}".strip()
        if not text:
            continue
        names = indices["name"].astype(str).tolist()
        symbols = indices["symbol"].astype(str).tolist()
        if model is not None:
            try:
                import numpy as np

                doc_vec = np.asarray(model.encode([text])[0])
                name_vecs = np.asarray(model.encode(names))
                norms = np.linalg.norm(name_vecs, axis=1)
                doc_norm = np.linalg.norm(doc_vec)
                sims = (name_vecs @ doc_vec) / (norms * doc_norm + 1e-12)
                order = np.argsort(-sims)[:top_k]
                best = [(symbols[i], float(sims[i])) for i in order if float(sims[i]) > 0]
            except Exception:
                best = []
        else:
            scored = [(symbols[i], _keyword_score(text, names[i])) for i in range(len(names))]
            scored = [(s, v) for s, v in scored if v > 0]
            scored.sort(key=lambda x: -x[1])
            best = [(s, float(v)) for s, v in scored[:top_k]]
        for symbol, score in best:
            rows.append({
                "document_id": doc.get("document_id"),
                "provider": doc.get("provider"),
                "published_at": doc.get("published_at"),
                "title": doc.get("title"),
                "symbol": symbol,
                "score": score,
            })
    if not rows:
        return pd.DataFrame(columns=["document_id", "provider", "published_at", "title", "symbol", "score"])
    return pd.DataFrame(rows)
