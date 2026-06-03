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
    daily_basic_table: str = "market_daily_basic"
    financial_table: str = "market_financial_factors"
    adj_factor_table: str = "market_adj_factors"
    index_table: str = "market_index_bars"
    index_meta_table: str = "market_indices"
    calendar_table: str = "trading_calendar"
    use_for_daily_fallback: bool = True
    use_for_universe_fallback: bool = True
    prefer_daily_for_backtest: bool = False
    min_history_days: int = 200
    max_snapshot_staleness_days: int = 1
    min_snapshot_coverage: float = 0.80
    allow_stale_universe_fallback: bool = False
    price_adjustment_for_backtest: str = "qfq_current"


_settings = LocalHistorySettings()


def configure_local_history(cfg: dict[str, Any] | None, root: Path | None = None) -> None:
    global _settings
    raw = cfg or {}
    path = Path(raw.get("path", _settings.path))
    if not path.is_absolute() and root is not None:
        path = root / path
    adjust_type = str(raw.get("adjust_type", "qfq"))
    default_price_adjustment = "qfq_current" if adjust_type == "qfq" else adjust_type
    _settings = LocalHistorySettings(
        enabled=bool(raw.get("enabled", True)),
        path=path,
        market=str(raw.get("market", "CN")),
        adjust_type=adjust_type,
        daily_table=str(raw.get("daily_table", "market_daily_bars")),
        meta_table=str(raw.get("meta_table", "market_stocks")),
        daily_basic_table=str(raw.get("daily_basic_table", "market_daily_basic")),
        financial_table=str(raw.get("financial_table", "market_financial_factors")),
        adj_factor_table=str(raw.get("adj_factor_table", "market_adj_factors")),
        index_table=str(raw.get("index_table", "market_index_bars")),
        index_meta_table=str(raw.get("index_meta_table", "market_indices")),
        calendar_table=str(raw.get("calendar_table", "trading_calendar")),
        use_for_daily_fallback=bool(raw.get("use_for_daily_fallback", True)),
        use_for_universe_fallback=bool(raw.get("use_for_universe_fallback", True)),
        prefer_daily_for_backtest=bool(raw.get("prefer_daily_for_backtest", False)),
        min_history_days=int(raw.get("min_history_days", 200)),
        max_snapshot_staleness_days=int(raw.get("max_snapshot_staleness_days", 1)),
        min_snapshot_coverage=float(raw.get("min_snapshot_coverage", 0.80)),
        allow_stale_universe_fallback=bool(raw.get("allow_stale_universe_fallback", False)),
        price_adjustment_for_backtest=str(raw.get("price_adjustment_for_backtest", default_price_adjustment)),
    )


def local_history_path() -> Path:
    return _settings.path


def local_history_available() -> bool:
    return bool(_settings.enabled and _settings.path.exists())


def local_history_prefer_daily_for_backtest() -> bool:
    return bool(_settings.enabled and _settings.prefer_daily_for_backtest and _settings.path.exists())


def load_daily_from_local_history(
    symbol: str,
    start: date,
    end: date,
    price_adjustment: str | None = None,
    as_of_date: date | str | None = None,
) -> pd.DataFrame:
    if not (_settings.enabled and _settings.use_for_daily_fallback and _settings.path.exists()):
        return pd.DataFrame()
    price_mode = price_adjustment or _settings.price_adjustment_for_backtest
    if price_mode == "qfq_asof":
        if as_of_date is None:
            return pd.DataFrame()
        from phase0.adjustment import build_qfq_asof_bars

        as_of = pd.to_datetime(as_of_date).date()
        return build_qfq_asof_bars(
            _settings.path,
            symbol,
            start,
            end,
            as_of,
            daily_table=_settings.daily_table,
            factor_table=_settings.adj_factor_table,
            market=_settings.market,
        )
    if price_mode in {"bfq_raw", "bfq"}:
        adjust_type = "bfq"
    elif price_mode in {"qfq_current", "qfq"}:
        adjust_type = "qfq"
    else:
        adjust_type = _settings.adjust_type
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
                params = (*params, adjust_type)
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
    daily_basic_table = _safe_identifier(_settings.daily_basic_table)
    financial_table = _safe_identifier(_settings.financial_table)
    has_adjust = _table_has_column(_settings.path, daily_table, "adjust_type")
    has_financial = _table_exists(_settings.path, financial_table)
    has_daily_basic = _table_exists(_settings.path, daily_basic_table)
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
    financial_query = f"""
        SELECT
            f.symbol,
            f.report_date AS financial_report_date,
            f.announce_date AS financial_announce_date,
            f.roe,
            f.revenue_growth,
            f.profit_growth,
            f.operating_cash_flow_to_net_profit AS cash_flow_quality,
            f.debt_to_asset
        FROM {financial_table} f
        JOIN (
            SELECT market, symbol, MAX(report_date) AS report_date
            FROM {financial_table}
            WHERE market = ?
            GROUP BY market, symbol
        ) latest
          ON f.market = latest.market
         AND f.symbol = latest.symbol
         AND f.report_date = latest.report_date
    """
    try:
        with sqlite3.connect(_settings.path) as conn:
            params: tuple[Any, ...] = (_settings.market,)
            if has_adjust:
                params = (*params, _settings.adjust_type)
            params = (*params, start_date, latest_trade_date.isoformat(), max(20, days // 3))
            df = pd.read_sql_query(bars_query, conn, params=params)
            meta = pd.read_sql_query(meta_query, conn, params=(_settings.market,))
            financial = pd.read_sql_query(financial_query, conn, params=(_settings.market,)) if has_financial else pd.DataFrame()
    except (sqlite3.Error, ValueError):
        return pd.DataFrame()
    if df.empty:
        return df
    df["symbol"] = df["symbol"].map(normalize_cn_symbol)
    if not meta.empty:
        meta["symbol"] = meta["symbol"].map(normalize_cn_symbol)
        df = df.merge(meta, on="symbol", how="left")
    if not financial.empty:
        financial["symbol"] = financial["symbol"].map(normalize_cn_symbol)
        df = df.merge(financial, on="symbol", how="left")
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
            "roe": pd.to_numeric(df.get("roe", np.nan), errors="coerce"),
            "revenue_growth": pd.to_numeric(df.get("revenue_growth", np.nan), errors="coerce"),
            "profit_growth": pd.to_numeric(df.get("profit_growth", np.nan), errors="coerce"),
            "cash_flow_quality": pd.to_numeric(df.get("cash_flow_quality", np.nan), errors="coerce"),
            "debt_to_asset": pd.to_numeric(df.get("debt_to_asset", np.nan), errors="coerce"),
            "financial_report_date": df.get("financial_report_date", ""),
            "financial_announce_date": df.get("financial_announce_date", ""),
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


def load_snapshot_from_local_history_as_of(as_of_date: date | str, days: int = 90) -> pd.DataFrame:
    """Build a point-in-time A-share snapshot from local history without writing state."""
    if not (_settings.enabled and _settings.use_for_universe_fallback and _settings.path.exists()):
        return pd.DataFrame()

    as_of = _parse_iso_date(as_of_date)
    if as_of is None:
        return pd.DataFrame()

    daily_table = _safe_identifier(_settings.daily_table)
    meta_table = _safe_identifier(_settings.meta_table)
    daily_basic_table = _safe_identifier(_settings.daily_basic_table)
    financial_table = _safe_identifier(_settings.financial_table)
    has_adjust = _table_has_column(_settings.path, daily_table, "adjust_type")
    has_daily_basic = _table_exists(_settings.path, daily_basic_table)
    has_financial = _table_exists(_settings.path, financial_table)
    adjust_filter = "AND adjust_type = ?" if has_adjust else ""
    latest_trade_date = _latest_daily_date_on_or_before(daily_table, has_adjust, as_of)
    if latest_trade_date is None:
        return pd.DataFrame()

    coverage = _latest_daily_coverage(daily_table, has_adjust, latest_trade_date)
    start_date = (latest_trade_date - timedelta(days=int(days))).isoformat()
    min_trading_days = max(20, int(days) // 3)
    attrs = {
        "as_of_date": as_of.isoformat(),
        "latest_trade_date": latest_trade_date.isoformat(),
        "expected_trade_date": latest_trade_date.isoformat(),
        "staleness_days": _trade_day_lag(latest_trade_date, as_of),
        "latest_coverage": coverage,
        "point_in_time": True,
    }

    bars_query = f"""
        WITH recent AS (
            SELECT symbol, date, close, amount, volume, turnover_rate
            FROM {daily_table}
            WHERE market = ?
              {adjust_filter}
              AND date >= ?
              AND date <= ?
        ),
        agg AS (
            SELECT
                symbol,
                MAX(date) AS latest_date,
                AVG(amount) AS amount,
                AVG(volume) AS volume,
                COUNT(*) AS trading_days
            FROM recent
            GROUP BY symbol
            HAVING COUNT(*) >= ?
        )
        SELECT
            agg.symbol,
            agg.latest_date,
            agg.amount,
            agg.volume,
            agg.trading_days,
            recent.close AS latest_price,
            recent.turnover_rate
        FROM agg
        JOIN recent
          ON recent.symbol = agg.symbol
         AND recent.date = agg.latest_date
    """
    meta_query = f"""
        SELECT symbol, name, industry, list_date, delist_date
        FROM {meta_table}
        WHERE market = ?
    """
    daily_basic_query = f"""
        SELECT
            b.symbol,
            b.date,
            b.market_cap,
            b.circ_mv,
            b.pe_ratio,
            b.pb_ratio,
            b.turnover_rate
        FROM {daily_basic_table} b
        JOIN (
            SELECT market, symbol, MAX(date) AS date
            FROM {daily_basic_table}
            WHERE market = ?
              AND date <= ?
            GROUP BY market, symbol
        ) latest
          ON b.market = latest.market
         AND b.symbol = latest.symbol
         AND b.date = latest.date
        WHERE b.market = ?
    """
    financial_query = f"""
        SELECT
            f.symbol,
            f.report_date AS financial_report_date,
            f.announce_date AS financial_announce_date,
            f.roe,
            f.revenue_growth,
            f.profit_growth,
            f.operating_cash_flow_to_net_profit AS cash_flow_quality,
            f.debt_to_asset
        FROM {financial_table} f
        JOIN (
            SELECT market, symbol, MAX(report_date) AS report_date
            FROM {financial_table}
            WHERE market = ?
              AND announce_date IS NOT NULL
              AND announce_date != ''
              AND announce_date <= ?
            GROUP BY market, symbol
        ) latest
          ON f.market = latest.market
         AND f.symbol = latest.symbol
         AND f.report_date = latest.report_date
        WHERE f.market = ?
          AND f.announce_date <= ?
    """
    try:
        with sqlite3.connect(_settings.path) as conn:
            params: tuple[Any, ...] = (_settings.market,)
            if has_adjust:
                params = (*params, _settings.adjust_type)
            params = (*params, start_date, latest_trade_date.isoformat(), min_trading_days)
            df = pd.read_sql_query(bars_query, conn, params=params)
            meta = pd.read_sql_query(meta_query, conn, params=(_settings.market,))
            daily_basic = (
                pd.read_sql_query(
                    daily_basic_query,
                    conn,
                    params=(
                        _settings.market,
                        latest_trade_date.isoformat(),
                        _settings.market,
                    ),
                )
                if has_daily_basic
                else pd.DataFrame()
            )
            financial = (
                pd.read_sql_query(
                    financial_query,
                    conn,
                    params=(
                        _settings.market,
                        latest_trade_date.isoformat(),
                        _settings.market,
                        latest_trade_date.isoformat(),
                    ),
                )
                if has_financial
                else pd.DataFrame()
            )
    except (sqlite3.Error, ValueError):
        return pd.DataFrame()
    if df.empty:
        df.attrs.update(attrs)
        return df

    df["symbol"] = df["symbol"].map(normalize_cn_symbol)
    if not meta.empty:
        meta["symbol"] = meta["symbol"].map(normalize_cn_symbol)
        df = df.merge(meta, on="symbol", how="left")
        list_dates = pd.to_datetime(df.get("list_date", ""), errors="coerce")
        delist_dates = pd.to_datetime(df.get("delist_date", ""), errors="coerce")
        as_of_ts = pd.Timestamp(latest_trade_date)
        listed = list_dates.isna() | (list_dates <= as_of_ts)
        not_delisted = delist_dates.isna() | (delist_dates > as_of_ts)
        df = df[listed & not_delisted].copy()
    if not financial.empty:
        financial["symbol"] = financial["symbol"].map(normalize_cn_symbol)
        df = df.merge(financial, on="symbol", how="left")
    if not daily_basic.empty:
        daily_basic["symbol"] = daily_basic["symbol"].map(normalize_cn_symbol)
        df = df.merge(daily_basic, on="symbol", how="left", suffixes=("", "_daily_basic"))

    out = pd.DataFrame(
        {
            "symbol": df["symbol"],
            "name": "",
            "industry": "",
            "latest_price": pd.to_numeric(df["latest_price"], errors="coerce"),
            "pct_change": np.nan,
            "amount": pd.to_numeric(df["amount"], errors="coerce"),
            "volume": pd.to_numeric(df["volume"], errors="coerce"),
            "turnover_rate": pd.to_numeric(df.get("turnover_rate_daily_basic", df.get("turnover_rate", np.nan)), errors="coerce"),
            "total_mv": pd.to_numeric(df.get("market_cap", np.nan), errors="coerce"),
            "circ_mv": pd.to_numeric(df.get("circ_mv", np.nan), errors="coerce"),
            "pe_ttm": pd.to_numeric(df.get("pe_ratio", np.nan), errors="coerce"),
            "pb": pd.to_numeric(df.get("pb_ratio", np.nan), errors="coerce"),
            "roe": pd.to_numeric(df.get("roe", np.nan), errors="coerce"),
            "revenue_growth": pd.to_numeric(df.get("revenue_growth", np.nan), errors="coerce"),
            "profit_growth": pd.to_numeric(df.get("profit_growth", np.nan), errors="coerce"),
            "cash_flow_quality": pd.to_numeric(df.get("cash_flow_quality", np.nan), errors="coerce"),
            "debt_to_asset": pd.to_numeric(df.get("debt_to_asset", np.nan), errors="coerce"),
            "financial_report_date": df.get("financial_report_date", ""),
            "financial_announce_date": df.get("financial_announce_date", ""),
            "source": "local_history_sqlite_as_of",
            "as_of_date": latest_trade_date.isoformat(),
            "expected_trade_date": latest_trade_date.isoformat(),
            "staleness_days": 0,
            "latest_coverage": coverage,
            "trading_days": pd.to_numeric(df.get("trading_days", np.nan), errors="coerce"),
        }
    )
    out.attrs.update(attrs)
    out.attrs["note"] = (
        "point-in-time universe uses historical OHLCV, nearest available daily_basic valuation snapshot, "
        "and announced financial factors as of the historical date."
    )
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


def load_trading_dates_from_local_history(start: date | str, end: date | str) -> list[date]:
    if not (_settings.enabled and _settings.path.exists()):
        return []
    parsed_start = _parse_iso_date(start)
    parsed_end = _parse_iso_date(end)
    if parsed_start is None or parsed_end is None:
        return []

    calendar_table = _safe_identifier(_settings.calendar_table)
    if _table_exists(_settings.path, calendar_table):
        query = f"""
            SELECT date
            FROM {calendar_table}
            WHERE is_open = 1
              AND date >= ?
              AND date <= ?
            ORDER BY date
        """
        try:
            with sqlite3.connect(_settings.path) as conn:
                df = pd.read_sql_query(query, conn, params=(parsed_start.isoformat(), parsed_end.isoformat()))
            dates = [_parse_iso_date(value) for value in df["date"].tolist()]
            return [value for value in dates if value is not None]
        except (sqlite3.Error, ValueError, IndexError):
            pass

    daily_table = _safe_identifier(_settings.daily_table)
    has_adjust = _table_has_column(_settings.path, daily_table, "adjust_type")
    adjust_filter = "AND adjust_type = ?" if has_adjust else ""
    query = f"""
        SELECT DISTINCT date
        FROM {daily_table}
        WHERE market = ?
          {adjust_filter}
          AND date >= ?
          AND date <= ?
        ORDER BY date
    """
    try:
        with sqlite3.connect(_settings.path) as conn:
            params: tuple[Any, ...] = (_settings.market,)
            if has_adjust:
                params = (*params, _settings.adjust_type)
            params = (*params, parsed_start.isoformat(), parsed_end.isoformat())
            df = pd.read_sql_query(query, conn, params=params)
    except (sqlite3.Error, ValueError, IndexError):
        return []
    dates = [_parse_iso_date(value) for value in df["date"].tolist()]
    return [value for value in dates if value is not None]


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


def _latest_daily_date_on_or_before(table: str, has_adjust: bool, as_of_date: date) -> date | None:
    adjust_filter = "AND adjust_type = ?" if has_adjust else ""
    query = f"""
        SELECT MAX(date) AS latest_date
        FROM {table}
        WHERE market = ?
          {adjust_filter}
          AND date <= ?
    """
    try:
        with sqlite3.connect(_settings.path) as conn:
            params: tuple[Any, ...] = (_settings.market,)
            if has_adjust:
                params = (*params, _settings.adjust_type)
            params = (*params, as_of_date.isoformat())
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
