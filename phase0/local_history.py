from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def normalize_cn_symbol(value: Any) -> str:
    raw = str(value).strip().upper()
    if not raw:
        return ""
    raw = raw.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    raw = raw.replace("SH", "").replace("SZ", "").replace("BJ", "")
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 6:
        return ""
    code = digits[-6:]
    if code.startswith(("6", "9")):
        return f"SH.{code}"
    if code.startswith(("0", "2", "3")):
        return f"SZ.{code}"
    if code.startswith(("4", "8")):
        return f"BJ.{code}"
    return ""


def _safe_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Unsafe SQL identifier: {value}")
    return value


@dataclass
class LocalHistorySettings:
    enabled: bool = True
    path: Path = Path("data/manual_history/a_share_history.sqlite")
    market: str = "CN"
    adjust_type: str = "qfq"
    daily_table: str = "market_daily_bars"
    meta_table: str = "market_stocks"
    index_table: str = "market_index_bars"
    index_meta_table: str = "market_indices"
    calendar_table: str = "trading_calendar"
    use_for_daily_fallback: bool = True
    use_for_universe_fallback: bool = True
    min_history_days: int = 200
    max_snapshot_staleness_days: int = 1
    min_snapshot_coverage: float = 0.80
    allow_stale_universe_fallback: bool = False


_settings = LocalHistorySettings()


def configure_local_history(cfg: dict[str, Any] | None, root: Path | None = None) -> None:
    global _settings
    raw = cfg or {}
    path = Path(raw.get("path", _settings.path))
    if not path.is_absolute() and root is not None:
        path = root / path
    _settings = LocalHistorySettings(
        enabled=bool(raw.get("enabled", True)),
        path=path,
        market=str(raw.get("market", "CN")),
        adjust_type=str(raw.get("adjust_type", "qfq")),
        daily_table=str(raw.get("daily_table", "market_daily_bars")),
        meta_table=str(raw.get("meta_table", "market_stocks")),
        index_table=str(raw.get("index_table", "market_index_bars")),
        index_meta_table=str(raw.get("index_meta_table", "market_indices")),
        calendar_table=str(raw.get("calendar_table", "trading_calendar")),
        use_for_daily_fallback=bool(raw.get("use_for_daily_fallback", True)),
        use_for_universe_fallback=bool(raw.get("use_for_universe_fallback", True)),
        min_history_days=int(raw.get("min_history_days", 200)),
        max_snapshot_staleness_days=int(raw.get("max_snapshot_staleness_days", 1)),
        min_snapshot_coverage=float(raw.get("min_snapshot_coverage", 0.80)),
        allow_stale_universe_fallback=bool(raw.get("allow_stale_universe_fallback", False)),
    )


def local_history_path() -> Path:
    return _settings.path


def local_history_available() -> bool:
    return bool(_settings.enabled and _settings.path.exists())


def load_daily_from_local_history(symbol: str, start: date, end: date) -> pd.DataFrame:
    if not (_settings.enabled and _settings.use_for_daily_fallback and _settings.path.exists()):
        return pd.DataFrame()
    table = _safe_identifier(_settings.daily_table)
    has_adjust = _table_has_column(_settings.path, table, "adjust_type")
    adjust_filter = "AND adjust_type = ?" if has_adjust else ""
    query = f"""
        SELECT date, open, high, low, close, volume, amount, adjusted_close
        FROM {table}
        WHERE market = ?
          AND symbol = ?
          AND date >= ?
          AND date <= ?
          {adjust_filter}
        ORDER BY date
    """
    try:
        with sqlite3.connect(_settings.path) as conn:
            params: tuple[Any, ...]
            params = (_settings.market, normalize_cn_symbol(symbol), start.isoformat(), end.isoformat())
            if has_adjust:
                params = (*params, _settings.adjust_type)
            df = pd.read_sql_query(
                query,
                conn,
                params=params,
            )
    except (sqlite3.Error, ValueError):
        return pd.DataFrame()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df["market"] = _settings.market
    df["symbol"] = normalize_cn_symbol(symbol)
    df["data_source"] = "local_history_sqlite"
    return df


def load_snapshot_from_local_history(days: int = 90) -> pd.DataFrame:
    if not (_settings.enabled and _settings.use_for_universe_fallback and _settings.path.exists()):
        return pd.DataFrame()
    daily_table = _safe_identifier(_settings.daily_table)
    meta_table = _safe_identifier(_settings.meta_table)
    has_adjust = _table_has_column(_settings.path, daily_table, "adjust_type")
    adjust_filter = "AND adjust_type = ?" if has_adjust else ""
    latest_trade_date = _latest_daily_date(daily_table, has_adjust)
    if latest_trade_date is None:
        return pd.DataFrame()
    expected_trade_date = _expected_latest_trade_date()
    staleness_days = _trade_day_lag(latest_trade_date, expected_trade_date)
    coverage = _latest_daily_coverage(daily_table, has_adjust, latest_trade_date)
    attrs = {
        "latest_trade_date": latest_trade_date.isoformat(),
        "expected_trade_date": expected_trade_date.isoformat(),
        "staleness_days": staleness_days,
        "latest_coverage": coverage,
    }
    stale = staleness_days > _settings.max_snapshot_staleness_days
    undercovered = coverage < _settings.min_snapshot_coverage
    if (stale or undercovered) and not _settings.allow_stale_universe_fallback:
        out = pd.DataFrame()
        out.attrs.update(attrs)
        out.attrs["warning"] = (
            "local history snapshot is not current enough for live universe: "
            f"latest_trade_date={latest_trade_date.isoformat()}, "
            f"expected_trade_date={expected_trade_date.isoformat()}, "
            f"staleness_days={staleness_days}, "
            f"latest_coverage={coverage:.4f}"
        )
        return out
    start_date = (latest_trade_date - timedelta(days=int(days))).isoformat()
    bars_query = f"""
        WITH recent AS (
            SELECT symbol, date, close, amount, volume
            FROM {daily_table}
            WHERE market = ?
              {adjust_filter}
              AND date >= ?
              AND date <= ?
        )
        SELECT
            symbol,
            MAX(date) AS latest_date,
            AVG(amount) AS amount,
            AVG(volume) AS volume,
            MAX(close) AS latest_price,
            COUNT(*) AS trading_days
        FROM recent
        GROUP BY symbol
        HAVING COUNT(*) >= ?
    """
    meta_query = f"""
        SELECT symbol, name, industry, market_cap, pe_ratio, pb_ratio, turnover_rate
        FROM {meta_table}
        WHERE market = ?
    """
    try:
        with sqlite3.connect(_settings.path) as conn:
            params: tuple[Any, ...] = (_settings.market,)
            if has_adjust:
                params = (*params, _settings.adjust_type)
            params = (*params, start_date, latest_trade_date.isoformat(), max(20, days // 3))
            df = pd.read_sql_query(bars_query, conn, params=params)
            meta = pd.read_sql_query(meta_query, conn, params=(_settings.market,))
    except (sqlite3.Error, ValueError):
        return pd.DataFrame()
    if df.empty:
        return df
    df["symbol"] = df["symbol"].map(normalize_cn_symbol)
    if not meta.empty:
        meta["symbol"] = meta["symbol"].map(normalize_cn_symbol)
        df = df.merge(meta, on="symbol", how="left")
    out = pd.DataFrame(
        {
            "symbol": df["symbol"],
            "name": df.get("name", ""),
            "industry": df.get("industry", ""),
            "latest_price": pd.to_numeric(df["latest_price"], errors="coerce"),
            "pct_change": np.nan,
            "amount": pd.to_numeric(df["amount"], errors="coerce"),
            "volume": pd.to_numeric(df["volume"], errors="coerce"),
            "turnover_rate": pd.to_numeric(df.get("turnover_rate", np.nan), errors="coerce"),
            "total_mv": pd.to_numeric(df.get("market_cap", np.nan), errors="coerce"),
            "circ_mv": np.nan,
            "pe_ttm": pd.to_numeric(df.get("pe_ratio", np.nan), errors="coerce"),
            "pb": pd.to_numeric(df.get("pb_ratio", np.nan), errors="coerce"),
            "source": "local_history_sqlite",
            "as_of_date": latest_trade_date.isoformat(),
            "expected_trade_date": expected_trade_date.isoformat(),
            "staleness_days": staleness_days,
            "latest_coverage": coverage,
            "trading_days": pd.to_numeric(df.get("trading_days", np.nan), errors="coerce"),
        }
    )
    out.attrs.update(attrs)
    return out


def load_index_daily_from_local_history(symbol: str, start: date, end: date) -> pd.DataFrame:
    if not (_settings.enabled and _settings.path.exists()):
        return pd.DataFrame()
    table = _safe_identifier(_settings.index_table)
    query = f"""
        SELECT date, open, high, low, close, volume, amount, advances, declines, name, source
        FROM {table}
        WHERE market = ?
          AND symbol = ?
          AND date >= ?
          AND date <= ?
          AND frequency = 'daily'
        ORDER BY date
    """
    try:
        with sqlite3.connect(_settings.path) as conn:
            df = pd.read_sql_query(query, conn, params=(_settings.market, symbol, start.isoformat(), end.isoformat()))
    except sqlite3.Error:
        return pd.DataFrame()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df["market"] = _settings.market
    df["symbol"] = symbol
    df["data_source"] = "local_history_sqlite"
    return df


def count_local_history_symbols() -> int:
    if not local_history_available():
        return 0
    table = _safe_identifier(_settings.daily_table)
    query = f"SELECT COUNT(DISTINCT symbol) AS n FROM {table} WHERE market = ?"
    try:
        with sqlite3.connect(_settings.path) as conn:
            return int(pd.read_sql_query(query, conn, params=(_settings.market,))["n"].iloc[0])
    except (sqlite3.Error, ValueError, IndexError):
        return 0


def _latest_daily_date(table: str, has_adjust: bool) -> date | None:
    adjust_filter = "AND adjust_type = ?" if has_adjust else ""
    query = f"SELECT MAX(date) AS latest_date FROM {table} WHERE market = ? {adjust_filter}"
    try:
        with sqlite3.connect(_settings.path) as conn:
            params: tuple[Any, ...] = (_settings.market,)
            if has_adjust:
                params = (*params, _settings.adjust_type)
            value = pd.read_sql_query(query, conn, params=params)["latest_date"].iloc[0]
    except (sqlite3.Error, ValueError, IndexError):
        return None
    return _parse_iso_date(value)


def _latest_daily_coverage(table: str, has_adjust: bool, latest_trade_date: date) -> float:
    adjust_filter = "AND adjust_type = ?" if has_adjust else ""
    query = f"""
        SELECT
            COUNT(DISTINCT symbol) AS latest_symbols,
            (
                SELECT COUNT(DISTINCT symbol)
                FROM {table}
                WHERE market = ?
                  {adjust_filter}
            ) AS total_symbols
        FROM {table}
        WHERE market = ?
          {adjust_filter}
          AND date = ?
    """
    try:
        with sqlite3.connect(_settings.path) as conn:
            params: tuple[Any, ...]
            if has_adjust:
                params = (
                    _settings.market,
                    _settings.adjust_type,
                    _settings.market,
                    _settings.adjust_type,
                    latest_trade_date.isoformat(),
                )
            else:
                params = (_settings.market, _settings.market, latest_trade_date.isoformat())
            row = pd.read_sql_query(query, conn, params=params).iloc[0]
    except (sqlite3.Error, ValueError, IndexError):
        return 0.0
    total = int(row.get("total_symbols") or 0)
    if total <= 0:
        return 0.0
    return float(int(row.get("latest_symbols") or 0) / total)


def _expected_latest_trade_date() -> date:
    table = _safe_identifier(_settings.calendar_table)
    if _table_exists(_settings.path, table):
        query = f"SELECT MAX(date) AS latest_date FROM {table} WHERE is_open = 1 AND date <= ?"
        try:
            with sqlite3.connect(_settings.path) as conn:
                value = pd.read_sql_query(query, conn, params=(date.today().isoformat(),))["latest_date"].iloc[0]
            parsed = _parse_iso_date(value)
            if parsed is not None:
                return parsed
        except (sqlite3.Error, ValueError, IndexError):
            pass
    return date.today()


def _trade_day_lag(latest_trade_date: date, expected_trade_date: date) -> int:
    if latest_trade_date >= expected_trade_date:
        return 0
    table = _safe_identifier(_settings.calendar_table)
    if _table_exists(_settings.path, table):
        query = f"""
            SELECT COUNT(DISTINCT date) AS lag
            FROM {table}
            WHERE is_open = 1
              AND date > ?
              AND date <= ?
        """
        try:
            with sqlite3.connect(_settings.path) as conn:
                value = pd.read_sql_query(
                    query,
                    conn,
                    params=(latest_trade_date.isoformat(), expected_trade_date.isoformat()),
                )["lag"].iloc[0]
            return int(value or 0)
        except (sqlite3.Error, ValueError, IndexError):
            pass
    return max((expected_trade_date - latest_trade_date).days, 0)


def _parse_iso_date(value: Any) -> date | None:
    if value is None or pd.isna(value):
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _table_exists(db_path: Path, table: str) -> bool:
    try:
        with sqlite3.connect(db_path) as conn:
            rows = pd.read_sql_query(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                conn,
                params=(table,),
            )
    except sqlite3.Error:
        return False
    return not rows.empty


def _table_has_column(db_path: Path, table: str, column: str) -> bool:
    try:
        with sqlite3.connect(db_path) as conn:
            cols = pd.read_sql_query(f"PRAGMA table_info({_safe_identifier(table)})", conn)
    except (sqlite3.Error, ValueError):
        return False
    return column in set(cols["name"].astype(str))
