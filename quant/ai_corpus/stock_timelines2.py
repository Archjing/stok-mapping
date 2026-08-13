"""Per-stock timelines (second tier): index-constituent changes and research coverage.

Both read from existing data.  Paths are resolved via environment variables so
the a-share-deep-analysis skill can point at the project without hardcoding:

- ``STOK_MAPPING_ROOT``: project root (default: cwd); all DB paths derive from it
- individual DB paths can be overridden via ``STOK_MARKET_DB`` / ``STOK_CORPUS_DB``

Research layer only — read-only queries.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from quant.ai_corpus.stock_timeline import normalize_symbol
from quant.paths import corpus_db as _default_corpus_db
from quant.paths import market_db as _default_market_db


def _market_db() -> Path:
    return _default_market_db()


def _corpus_db() -> Path:
    return _default_corpus_db()


def load_index_membership_timeline(
    market_db: Path | None = None,
    *,
    symbol: str,
    index_code: str | None = None,
) -> pd.DataFrame:
    """Return a stock's index membership timeline (which index, effective dates).

    Detects membership CHANGES: consecutive effective dates per index mark
    entry (first appearance) and exit (gap after a run).  Ordered by index then
    effective_date.
    """
    norm = normalize_symbol(symbol)
    if norm is None:
        raise ValueError(f"invalid stock symbol: {symbol}")
    db = market_db or _market_db()
    if not db.is_file():
        return pd.DataFrame()
    conn = sqlite3.connect(db)
    sql = """
        SELECT index_code, trade_date, effective_date, source, ingested_at
        FROM cn_index_constituents_asof
        WHERE symbol = ?
    """
    params: list = [norm]
    if index_code:
        sql += " AND index_code = ?"
        params.append(index_code)
    sql += " ORDER BY index_code, effective_date"
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df.reset_index(drop=True)


def load_index_membership_changes(
    market_db: Path | None = None,
    *,
    symbol: str,
) -> pd.DataFrame:
    """Detect index entry/exit events for a stock.

    Returns one row per membership CHANGE with a ``change`` column:
    ``enter`` (first appearance) / ``exit`` (last appearance before a gap).
    Membership is tracked by consecutive ``trade_date`` snapshots; a gap of
    > 90 calendar days in trade_date means the stock left and re-entered.
    """
    timeline = load_index_membership_timeline(market_db, symbol=symbol)
    if timeline.empty:
        return pd.DataFrame()

    changes = []
    for index, grp in timeline.groupby("index_code"):
        grp = grp.sort_values("trade_date").reset_index(drop=True)
        prev_trade = None
        run_start_idx = None
        for i, r in grp.iterrows():
            td = pd.Timestamp(r["trade_date"])
            if prev_trade is None:
                run_start_idx = i
                changes.append({**r.to_dict(), "change": "enter"})
            else:
                gap = (td - prev_trade).days
                if gap > 90:
                    # previous run ended → mark its last row as exit, this as enter
                    if run_start_idx is not None and run_start_idx <= i - 1:
                        changes.append({**grp.iloc[i - 1].to_dict(), "change": "exit"})
                    changes.append({**r.to_dict(), "change": "enter"})
                    run_start_idx = i
            prev_trade = td
        # final exit: last row of the index's data (membership ends)
        if run_start_idx is not None and run_start_idx <= len(grp) - 1:
            changes.append({**grp.iloc[-1].to_dict(), "change": "exit"})

    out = pd.DataFrame(changes)
    if out.empty:
        return out
    # collapse consecutive identical (index, change) — keep first
    out = out.sort_values(["index_code", "trade_date"]).reset_index(drop=True)
    out["key"] = out["index_code"] + "|" + out["change"]
    out = out[out["key"] != out["key"].shift(1)]
    return out.drop(columns=["key"]).reset_index(drop=True)


def load_research_coverage_timeline(
    corpus_db: Path | None = None,
    *,
    symbol: str,
) -> pd.DataFrame:
    """Return research-report coverage (rating/target/org) over time.

    Data source: ai_corpus research_report provider (metadata-only, no full text).
    If no research-report data has been ingested yet, returns an empty frame
    (data backfill is a separate step).
    """
    norm = normalize_symbol(symbol)
    if norm is None:
        raise ValueError(f"invalid stock symbol: {symbol}")
    code6 = norm.split(".")[1]
    db = corpus_db or _corpus_db()
    if not db.is_file():
        return pd.DataFrame()
    conn = sqlite3.connect(db)
    df = pd.read_sql_query(
        """
        SELECT document_id, published_at, title, org, topics, url, source_id, symbols
        FROM ai_corpus_documents
        WHERE provider = 'research_report' AND symbols LIKE ?
        ORDER BY published_at DESC
        """,
        conn,
        params=(f"%{code6}%",),
    )
    conn.close()
    if df.empty:
        return pd.DataFrame()
    # exact token match on symbols
    def _contains(s: str) -> bool:
        return code6 in [t.strip() for t in str(s).split(",")]
    df = df[df["symbols"].map(_contains)]
    return df.drop(columns=["symbols"]).reset_index(drop=True)
