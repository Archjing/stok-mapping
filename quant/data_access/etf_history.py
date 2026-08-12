from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from quant.data_access.symbols import (
    from_tushare_symbol,
    normalize_etf_symbol,
    to_tushare_symbol,
)


class ETFAdjustmentCoverageError(RuntimeError):
    """Raw ETF bars cannot be adjusted without crossing the as-of boundary or imputing factors."""


def _validated_symbol(value: object) -> str:
    normalized = normalize_etf_symbol(value)
    if from_tushare_symbol(to_tushare_symbol(normalized)) != normalized:
        raise ValueError("ETF symbol cannot round-trip through the provider symbol format")
    return normalized


def _query_raw(db_path: Path, symbol: str, start: date, end: date) -> pd.DataFrame:
    query = """
        SELECT symbol,date,open,high,low,close,pre_close,change_amount,change_pct,
               volume,amount,source,fetched_at
        FROM market_etf_daily_bars
        WHERE symbol=? AND date>=? AND date<=?
        ORDER BY date
    """
    with sqlite3.connect(db_path) as conn:
        frame = pd.read_sql_query(
            query,
            conn,
            params=(symbol, start.isoformat(), end.isoformat()),
        )
    if not frame.empty:
        frame["date"] = pd.to_datetime(frame["date"])
    return frame


def _query_factors(db_path: Path, symbol: str, start: date, end: date) -> pd.DataFrame:
    query = """
        SELECT symbol,date,adj_factor,source,fetched_at
        FROM market_etf_adj_factors
        WHERE symbol=? AND date>=? AND date<=?
        ORDER BY date
    """
    with sqlite3.connect(db_path) as conn:
        frame = pd.read_sql_query(
            query,
            conn,
            params=(symbol, start.isoformat(), end.isoformat()),
        )
    if not frame.empty:
        frame["date"] = pd.to_datetime(frame["date"])
    return frame


def compute_etf_qfq_asof(
    raw: pd.DataFrame,
    factors: pd.DataFrame,
    as_of_date: date,
) -> pd.DataFrame:
    if raw.empty:
        return raw.assign(price_mode="qfq_asof")
    if factors.empty:
        raise ETFAdjustmentCoverageError("no as-of factor coverage")

    bars = raw.copy()
    fac = factors.copy()
    bars["date"] = pd.to_datetime(bars["date"], errors="coerce")
    fac["date"] = pd.to_datetime(fac["date"], errors="coerce")
    if bars["date"].isna().any() or fac["date"].isna().any():
        raise ETFAdjustmentCoverageError("invalid bar or factor date")

    cutoff = pd.Timestamp(as_of_date)
    bars = bars[bars["date"] <= cutoff].copy()
    fac = fac[fac["date"] <= cutoff].copy()
    if bars.empty:
        return bars.assign(price_mode="qfq_asof")
    if fac.empty:
        raise ETFAdjustmentCoverageError("no as-of factor at or before requested date")
    if fac["date"].duplicated().any():
        raise ETFAdjustmentCoverageError("duplicate adjustment factors for a date")

    asof_rows = fac.sort_values("date")
    asof_factor = float(asof_rows.iloc[-1]["adj_factor"])
    if not pd.notna(asof_factor) or asof_factor <= 0:
        raise ETFAdjustmentCoverageError("invalid as-of factor")

    merged = bars.merge(
        fac[["date", "adj_factor"]],
        on="date",
        how="left",
        validate="one_to_one",
    )
    missing = merged.loc[merged["adj_factor"].isna(), "date"]
    if not missing.empty:
        dates = ",".join(missing.dt.strftime("%Y-%m-%d").head(10))
        raise ETFAdjustmentCoverageError(f"missing factor for bar dates: {dates}")
    invalid = pd.to_numeric(merged["adj_factor"], errors="coerce")
    if invalid.isna().any() or (invalid <= 0).any():
        raise ETFAdjustmentCoverageError("invalid adjustment factor for bar date")

    ratio = invalid.astype(float) / asof_factor
    for column in ("open", "high", "low", "close", "pre_close"):
        if column in merged.columns:
            merged[column] = pd.to_numeric(merged[column], errors="coerce") * ratio
    merged["price_mode"] = "qfq_asof"
    return merged.drop(columns=["adj_factor"])


@dataclass(frozen=True)
class ETFHistoryReader:
    db_path: Path

    def load_raw(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        normalized = _validated_symbol(symbol)
        frame = _query_raw(Path(self.db_path), normalized, start, end)
        return frame.assign(price_mode="raw")

    def load_qfq_asof(
        self,
        symbol: str,
        start: date,
        end: date,
        as_of_date: date,
    ) -> pd.DataFrame:
        normalized = _validated_symbol(symbol)
        effective_end = min(end, as_of_date)
        raw = _query_raw(Path(self.db_path), normalized, start, effective_end)
        factors = _query_factors(Path(self.db_path), normalized, start, as_of_date)
        return compute_etf_qfq_asof(raw, factors, as_of_date)
