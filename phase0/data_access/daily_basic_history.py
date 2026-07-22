from __future__ import annotations

import sqlite3
from typing import Iterable

import numpy as np
import pandas as pd

from phase0.data_access.local_history import _safe_identifier, local_history_path


DAILY_BASIC_FACTOR_COLUMNS = ("market_cap", "circ_mv", "pe_ttm", "pb", "turnover_rate")


def _empty_daily_basic_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["symbol", "date", *DAILY_BASIC_FACTOR_COLUMNS])


def load_daily_basic_factor_frame(
    *,
    symbols: Iterable[str],
    start_date,
    end_date,
    as_of_date=None,
    market: str = "CN",
    table: str = "market_daily_basic",
) -> pd.DataFrame:
    table_name = _safe_identifier(str(table))
    requested_symbols = sorted(
        symbol
        for symbol in {str(value).strip() for value in symbols if pd.notna(value)}
        if symbol
    )
    if not requested_symbols:
        return _empty_daily_basic_frame()

    start = pd.to_datetime(start_date, errors="coerce")
    end = pd.to_datetime(end_date, errors="coerce")
    as_of = pd.to_datetime(as_of_date, errors="coerce") if as_of_date is not None else end
    if pd.isna(start) or pd.isna(end) or pd.isna(as_of):
        return _empty_daily_basic_frame()
    upper_bound = min(pd.Timestamp(end).normalize(), pd.Timestamp(as_of).normalize())
    start = pd.Timestamp(start).normalize()
    if upper_bound < start:
        return _empty_daily_basic_frame()

    db_path = local_history_path()
    if not db_path.exists():
        return _empty_daily_basic_frame()

    placeholders = ",".join("?" for _ in requested_symbols)
    query = f"""
        SELECT symbol, date, market_cap, circ_mv, pe_ratio, pb_ratio, turnover_rate
        FROM {table_name}
        WHERE market = ?
          AND symbol IN ({placeholders})
          AND date >= ?
          AND date <= ?
        ORDER BY date, symbol
    """
    params = [str(market), *requested_symbols, start.date().isoformat(), upper_bound.date().isoformat()]
    try:
        with sqlite3.connect(db_path) as conn:
            frame = pd.read_sql_query(query, conn, params=params)
    except (sqlite3.Error, pd.errors.DatabaseError, ValueError):
        return _empty_daily_basic_frame()

    if frame.empty:
        return _empty_daily_basic_frame()
    frame = frame.rename(columns={"pe_ratio": "pe_ttm", "pb_ratio": "pb"})
    frame["symbol"] = frame["symbol"].map(lambda value: str(value).strip() if pd.notna(value) else "")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for column in DAILY_BASIC_FACTOR_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return (
        frame.loc[frame["symbol"].ne("")]
        .dropna(subset=["date"])
        .drop_duplicates(subset=["date", "symbol"], keep="last")
        .sort_values(["date", "symbol"])
        .reset_index(drop=True)
    )


def merge_point_in_time_daily_basic(
    panel: pd.DataFrame,
    *,
    as_of_date=None,
    market: str = "CN",
    table: str = "market_daily_basic",
) -> pd.DataFrame:
    merged = panel.copy()
    for column in DAILY_BASIC_FACTOR_COLUMNS:
        if column not in merged.columns:
            merged[column] = np.nan
        else:
            merged[column] = pd.to_numeric(merged[column], errors="coerce")
    if merged.empty or "symbol" not in merged.columns or "date" not in merged.columns:
        return merged

    merged["date"] = pd.to_datetime(merged["date"], errors="coerce").dt.normalize()
    merged["symbol"] = merged["symbol"].where(merged["symbol"].isna(), merged["symbol"].astype(str))
    valid_dates = merged["date"].dropna()
    symbols = sorted(merged["symbol"].dropna().astype(str).unique().tolist())
    if valid_dates.empty or not symbols:
        return merged

    basics = load_daily_basic_factor_frame(
        symbols=symbols,
        start_date=valid_dates.min(),
        end_date=valid_dates.max(),
        as_of_date=as_of_date,
        market=market,
        table=table,
    )
    if basics.empty:
        return merged

    fetched_columns = {column: f"_daily_basic_{column}" for column in DAILY_BASIC_FACTOR_COLUMNS}
    merged = merged.merge(
        basics.rename(columns=fetched_columns),
        on=["symbol", "date"],
        how="left",
        validate="many_to_one",
    )
    for column, fetched_column in fetched_columns.items():
        merged[column] = merged[column].combine_first(merged[fetched_column])
    return merged.drop(columns=list(fetched_columns.values()))
