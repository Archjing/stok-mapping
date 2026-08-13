"""Per-stock timelines: financial, valuation, and shareholder-activity.

Three query layers over existing data, all point-in-time (PIT) aware:
- financial timeline: from market_financial_factors, ordered by announce_date
  (NOT report_date — avoids lookahead)
- valuation timeline: from market_daily_basic (pe/pb/market_cap over time)
- shareholder timeline: from ai_corpus cninfo docs filtered by event_type
  (share_buyback / share_increase / share_decrease)

Research layer only — read-only queries, no writes.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from quant.ai_corpus.stock_timeline import normalize_symbol
from quant.paths import corpus_db as _default_corpus_db
from quant.paths import market_db as _default_market_db

MARKET_DB = _default_market_db()
CORPUS_DB = _default_corpus_db()

SHAREHOLDER_EVENT_TYPES = ("share_buyback", "share_increase", "share_decrease")


def load_financial_timeline(
    market_db: Path = MARKET_DB,
    *,
    symbol: str,
) -> pd.DataFrame:
    """Return the financial timeline (ROE/revenue/profit + growth) by announce date."""
    norm = normalize_symbol(symbol)
    if norm is None:
        raise ValueError(f"invalid stock symbol: {symbol}")
    if not market_db.is_file():
        return pd.DataFrame()
    conn = sqlite3.connect(market_db)
    df = pd.read_sql_query(
        """
        SELECT symbol, report_date, announce_date, fiscal_year, fiscal_quarter,
               roe, revenue, revenue_growth, net_profit, profit_growth,
               debt_to_asset, operating_cash_flow
        FROM market_financial_factors
        WHERE symbol = ?
        ORDER BY announce_date DESC, report_date DESC
        """,
        conn,
        params=(norm,),
    )
    conn.close()
    return df.reset_index(drop=True)


def load_valuation_timeline(
    market_db: Path = MARKET_DB,
    *,
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Return the valuation timeline (pe/pb/market_cap) over time."""
    norm = normalize_symbol(symbol)
    if norm is None:
        raise ValueError(f"invalid stock symbol: {symbol}")
    if not market_db.is_file():
        return pd.DataFrame()
    conn = sqlite3.connect(market_db)
    sql = """
        SELECT symbol, date, pe_ratio, pb_ratio, market_cap, circ_mv, turnover_rate
        FROM market_daily_basic
        WHERE symbol = ?
    """
    params: list = [norm]
    if start_date:
        sql += " AND date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND date <= ?"
        params.append(end_date)
    sql += " ORDER BY date DESC"
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df.reset_index(drop=True)


def load_shareholder_timeline(
    corpus_db: Path = CORPUS_DB,
    *,
    symbol: str,
) -> pd.DataFrame:
    """Return shareholder-activity events (buyback/increase/decrease) for one stock."""
    norm = normalize_symbol(symbol)
    if norm is None:
        raise ValueError(f"invalid stock symbol: {symbol}")
    code6 = norm.split(".")[1]
    if not corpus_db.is_file():
        return pd.DataFrame()
    conn = sqlite3.connect(corpus_db)
    placeholders = ",".join("?" for _ in SHAREHOLDER_EVENT_TYPES)
    df = pd.read_sql_query(
        f"""
        SELECT document_id, provider, event_type, published_at, title, url, source_id, symbols
        FROM ai_corpus_documents
        WHERE event_type IN ({placeholders}) AND symbols LIKE ?
        ORDER BY published_at DESC
        """,
        conn,
        params=[*SHAREHOLDER_EVENT_TYPES, f"%{code6}%"],
    )
    conn.close()

    if df.empty:
        return pd.DataFrame()

    def _contains_code(symbols: str) -> bool:
        tokens = [t.strip() for t in str(symbols).split(",")]
        return code6 in tokens

    df = df[df["symbols"].map(_contains_code)].drop(columns=["symbols"])
    return df.reset_index(drop=True)
