"""Read completed, same-session US market features from the local history store."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class CompletedMarketSnapshot:
    """Latest date on which every requested symbol has a completed close."""

    as_of_date: str
    bars: pd.DataFrame


def _safe_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Unsafe SQL identifier: {value}")
    return value


def load_completed_market_snapshot(
    database_path: Path,
    daily_table: str,
    symbols: list[str] | tuple[str, ...],
    *,
    as_of_date: date | None = None,
) -> CompletedMarketSnapshot | None:
    """Return the latest common completed session; never forward-fill a symbol."""
    normalized_symbols = list(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))
    if not database_path.is_file() or not normalized_symbols:
        return None
    table = _safe_identifier(daily_table)
    placeholders = ",".join("?" for _ in normalized_symbols)
    cutoff_clause = "AND date <= ?" if as_of_date else ""
    params: list[object] = [*normalized_symbols]
    if as_of_date:
        params.append(as_of_date.isoformat())
    query = f"""
        SELECT MAX(date) AS as_of_date
        FROM (
            SELECT date
            FROM {table}
            WHERE symbol IN ({placeholders})
              AND close IS NOT NULL
              {cutoff_clause}
            GROUP BY date
            HAVING COUNT(DISTINCT symbol) = ?
        )
    """
    params.append(len(normalized_symbols))
    try:
        with sqlite3.connect(database_path) as conn:
            row = conn.execute(query, params).fetchone()
            if row is None or not row[0]:
                return None
            snapshot_date = str(row[0])
            bars = pd.read_sql_query(
                f"""
                SELECT date, symbol, open, high, low, close, adjusted_close, volume, source
                FROM {table}
                WHERE date = ? AND symbol IN ({placeholders})
                ORDER BY symbol
                """,
                conn,
                params=[snapshot_date, *normalized_symbols],
            )
    except sqlite3.Error:
        return None
    if len(bars) != len(normalized_symbols):
        return None
    for column in ("open", "high", "low", "close", "adjusted_close", "volume"):
        bars[column] = pd.to_numeric(bars[column], errors="coerce")
    return CompletedMarketSnapshot(as_of_date=snapshot_date, bars=bars)


def load_common_market_daily_features(
    database_path: Path,
    daily_table: str,
    symbols: list[str] | tuple[str, ...],
    *,
    start: date,
    end: date,
) -> pd.DataFrame:
    """Return close and close-to-close returns for dates shared by every symbol."""
    normalized_symbols = list(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))
    if not database_path.is_file() or not normalized_symbols:
        return pd.DataFrame(columns=["date"])
    table = _safe_identifier(daily_table)
    placeholders = ",".join("?" for _ in normalized_symbols)
    try:
        with sqlite3.connect(database_path) as conn:
            raw = pd.read_sql_query(
                f"""
                SELECT date, symbol, close
                FROM {table}
                WHERE symbol IN ({placeholders})
                  AND date >= ? AND date <= ? AND close IS NOT NULL
                ORDER BY date, symbol
                """,
                conn,
                params=[*normalized_symbols, start.isoformat(), end.isoformat()],
            )
    except sqlite3.Error:
        return pd.DataFrame(columns=["date"])
    if raw.empty:
        return pd.DataFrame(columns=["date"])
    raw["date"] = pd.to_datetime(raw["date"]).dt.normalize()
    raw["close"] = pd.to_numeric(raw["close"], errors="coerce")
    # Calculate each instrument's close-to-close return before restricting to
    # shared sessions.  A missing VIX observation must not redefine SOX's
    # prior close or alter the established strategy signal.
    raw["close_return"] = raw.groupby("symbol", sort=False)["close"].pct_change()
    wide = raw.pivot(index="date", columns="symbol", values="close").reindex(columns=normalized_symbols).dropna()
    return_wide = raw.pivot(index="date", columns="symbol", values="close_return").reindex(columns=normalized_symbols)
    if wide.empty:
        return pd.DataFrame(columns=["date"])
    out = wide.reset_index()
    for symbol in normalized_symbols:
        out[f"{symbol}_return"] = return_wide.loc[wide.index, symbol].to_numpy()
    return out
