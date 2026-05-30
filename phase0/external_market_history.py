from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from phase0.data_sources import fetch_hk_daily, fetch_yf_daily


DEFAULT_US_MARKET_SYMBOLS = ["^NDX", "^SOX", "NVDA", "KWEB", "^VIX", "CNY=X"]
DEFAULT_HK_MARKET_SYMBOLS = ["HK.00700", "HK.09988"]


@dataclass
class MarketHistorySettings:
    enabled: bool = True
    path: Path = Path("data/us_market_history.sqlite")
    daily_table: str = "market_daily_bars"
    source_audit_table: str = "market_data_source_runs"
    provider: str = "yfinance"
    symbols: list[str] = field(default_factory=lambda: list(DEFAULT_US_MARKET_SYMBOLS))
    years: int = 5
    max_staleness_days: int = 3
    min_symbol_coverage: float = 1.0
    runtime_yfinance_fallback: bool = False
    market_name: str = "us_market"


@dataclass
class MarketHistoryUpdateResult:
    db_path: Path
    status: str
    latest_date: str
    symbol_count: int
    covered_symbols: int
    coverage: float
    fetched_rows: int
    inserted_rows: int
    updated_rows: int
    warnings: list[str] = field(default_factory=list)
    source: str = ""

    @property
    def ok(self) -> bool:
        return self.status in {"updated", "up_to_date", "check_ok", "disabled"}


_us_settings = MarketHistorySettings()
_hk_settings = MarketHistorySettings(
    path=Path("data/hk_market_history.sqlite"),
    provider="akshare_hk",
    symbols=list(DEFAULT_HK_MARKET_SYMBOLS),
    runtime_yfinance_fallback=False,
    market_name="hk_market",
)


def _safe_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Unsafe SQL identifier: {value}")
    return value


def _build_settings(
    cfg: dict[str, Any] | None,
    *,
    root: Path | None,
    defaults: MarketHistorySettings,
    default_symbols: list[str],
) -> MarketHistorySettings:
    raw = cfg or {}
    path = Path(raw.get("path", defaults.path))
    if not path.is_absolute() and root is not None:
        path = root / path
    symbols = [str(item) for item in raw.get("symbols", default_symbols)]
    return MarketHistorySettings(
        enabled=bool(raw.get("enabled", True)),
        path=path,
        daily_table=str(raw.get("daily_table", defaults.daily_table)),
        source_audit_table=str(raw.get("source_audit_table", defaults.source_audit_table)),
        provider=str(raw.get("provider", defaults.provider)),
        symbols=symbols,
        years=int(raw.get("years", defaults.years)),
        max_staleness_days=int(raw.get("max_staleness_days", defaults.max_staleness_days)),
        min_symbol_coverage=float(raw.get("min_symbol_coverage", defaults.min_symbol_coverage)),
        runtime_yfinance_fallback=bool(raw.get("runtime_yfinance_fallback", defaults.runtime_yfinance_fallback)),
        market_name=str(raw.get("market_name", defaults.market_name)),
    )


def configure_us_market_history(cfg: dict[str, Any] | None, root: Path | None = None) -> None:
    global _us_settings
    _us_settings = _build_settings(cfg, root=root, defaults=_us_settings, default_symbols=DEFAULT_US_MARKET_SYMBOLS)


def configure_hk_market_history(cfg: dict[str, Any] | None, root: Path | None = None) -> None:
    global _hk_settings
    _hk_settings = _build_settings(cfg, root=root, defaults=_hk_settings, default_symbols=DEFAULT_HK_MARKET_SYMBOLS)


def us_market_history_runtime_fallback_enabled() -> bool:
    return bool(_us_settings.enabled and _us_settings.runtime_yfinance_fallback)


def _ensure_tables(conn: sqlite3.Connection, settings: MarketHistorySettings) -> None:
    daily_table = _safe_identifier(settings.daily_table)
    audit_table = _safe_identifier(settings.source_audit_table)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {daily_table} (
            market TEXT NOT NULL,
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            adjusted_close REAL,
            volume REAL,
            source TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            PRIMARY KEY (symbol, date)
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {audit_table} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            latest_trade_date TEXT,
            coverage REAL,
            fetched_rows INTEGER,
            inserted_rows INTEGER,
            updated_rows INTEGER,
            status TEXT,
            message TEXT
        )
        """
    )


def _market_for_symbol(symbol: str, settings: MarketHistorySettings) -> str:
    raw = symbol.upper()
    if settings.market_name == "hk_market" or raw.startswith("HK."):
        return "HK"
    if raw.endswith("=X"):
        return "FX"
    if raw.startswith("^"):
        return "US_INDEX"
    if raw in {"KWEB"}:
        return "US_ETF"
    return "US_EQUITY"


def _latest_symbol_dates(conn: sqlite3.Connection, settings: MarketHistorySettings) -> dict[str, date]:
    table = _safe_identifier(settings.daily_table)
    rows = pd.read_sql_query(
        f"""
        SELECT symbol, MAX(date) AS latest_date
        FROM {table}
        GROUP BY symbol
        """,
        conn,
    )
    out: dict[str, date] = {}
    for _, row in rows.iterrows():
        latest = pd.to_datetime(row["latest_date"], errors="coerce")
        if not pd.isna(latest):
            out[str(row["symbol"])] = latest.date()
    return out


def _coverage(conn: sqlite3.Connection, settings: MarketHistorySettings, symbols: list[str]) -> tuple[str, int, float]:
    latest_dates = _latest_symbol_dates(conn, settings)
    if not symbols:
        return "", 0, 0.0
    cutoff = date.today() - timedelta(days=max(0, settings.max_staleness_days))
    covered = [sym for sym in symbols if latest_dates.get(sym) is not None and latest_dates[sym] >= cutoff]
    latest = max(latest_dates.values()).isoformat() if latest_dates else ""
    return latest, len(covered), len(covered) / len(symbols)


def _record_audit(
    conn: sqlite3.Connection,
    *,
    settings: MarketHistorySettings,
    latest_date: str,
    coverage: float,
    fetched_rows: int,
    inserted_rows: int,
    updated_rows: int,
    status: str,
    message: str = "",
) -> None:
    table = _safe_identifier(settings.source_audit_table)
    conn.execute(
        f"""
        INSERT INTO {table} (
            source, fetched_at, latest_trade_date, coverage, fetched_rows, inserted_rows, updated_rows, status, message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            settings.provider,
            datetime.now().isoformat(timespec="seconds"),
            latest_date,
            float(coverage),
            int(fetched_rows),
            int(inserted_rows),
            int(updated_rows),
            status,
            message,
        ),
    )


def _normalize_frame(symbol: str, df: pd.DataFrame, settings: MarketHistorySettings) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    out["symbol"] = symbol
    out["market"] = _market_for_symbol(symbol, settings)
    out["source"] = settings.provider
    out["fetched_at"] = datetime.now().isoformat(timespec="seconds")
    for col in ["open", "high", "low", "close", "adjusted_close", "volume"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
        else:
            out[col] = pd.NA
    out = out.dropna(subset=["date", "open", "high", "low", "close"])
    keep = ["market", "symbol", "date", "open", "high", "low", "close", "adjusted_close", "volume", "source", "fetched_at"]
    return out[keep].drop_duplicates(["symbol", "date"])


def _fetch_market_daily(symbol: str, settings: MarketHistorySettings) -> pd.DataFrame:
    if settings.provider == "yfinance":
        return fetch_yf_daily(symbol, years=settings.years)
    if settings.provider in {"akshare_hk", "akshare-hk"}:
        return fetch_hk_daily(symbol, years=settings.years, adjust="qfq")
    raise ValueError(f"Unsupported market history provider: {settings.provider}")


def _update_market_history(
    settings: MarketHistorySettings,
    *,
    check_only: bool,
) -> MarketHistoryUpdateResult:
    if not settings.enabled:
        return MarketHistoryUpdateResult(settings.path, "disabled", "", 0, 0, 0.0, 0, 0, 0)

    symbols = list(dict.fromkeys(settings.symbols))
    settings.path.parent.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    with sqlite3.connect(settings.path) as conn:
        _ensure_tables(conn, settings)
        latest, covered, coverage = _coverage(conn, settings, symbols)
        if check_only:
            status = "check_ok" if coverage >= settings.min_symbol_coverage else "stale"
            return MarketHistoryUpdateResult(
                db_path=settings.path,
                status=status,
                latest_date=latest,
                symbol_count=len(symbols),
                covered_symbols=covered,
                coverage=coverage,
                fetched_rows=0,
                inserted_rows=0,
                updated_rows=0,
                warnings=[] if status == "check_ok" else [f"{settings.market_name} history is stale or undercovered"],
                source=settings.provider,
            )

        daily_table = _safe_identifier(settings.daily_table)
        fetched_rows = 0
        inserted_rows = 0
        updated_rows = 0
        for symbol in symbols:
            try:
                raw = _fetch_market_daily(symbol, settings)
            except Exception as exc:
                warnings.append(f"{settings.provider} {symbol} failed: {exc}")
                continue
            normalized = _normalize_frame(symbol, raw, settings)
            if normalized.empty:
                warnings.append(f"{settings.provider} {symbol} returned empty data.")
                continue
            fetched_rows += len(normalized)
            for row in normalized.itertuples(index=False):
                existed = conn.execute(
                    f"SELECT 1 FROM {daily_table} WHERE symbol = ? AND date = ?",
                    (row.symbol, row.date),
                ).fetchone()
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {daily_table} (
                        market, symbol, date, open, high, low, close, adjusted_close, volume, source, fetched_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.market,
                        row.symbol,
                        row.date,
                        row.open,
                        row.high,
                        row.low,
                        row.close,
                        row.adjusted_close,
                        row.volume,
                        row.source,
                        row.fetched_at,
                    ),
                )
                if existed:
                    updated_rows += 1
                else:
                    inserted_rows += 1

        latest, covered, coverage = _coverage(conn, settings, symbols)
        if coverage >= settings.min_symbol_coverage and fetched_rows == 0:
            status = "up_to_date"
        elif coverage >= settings.min_symbol_coverage:
            status = "updated"
        else:
            status = "stale"
        if fetched_rows == 0 and not warnings:
            warnings.append(f"no {settings.market_name} rows were fetched")
        _record_audit(
            conn,
            settings=settings,
            latest_date=latest,
            coverage=coverage,
            fetched_rows=fetched_rows,
            inserted_rows=inserted_rows,
            updated_rows=updated_rows,
            status=status,
            message="; ".join(warnings[-3:]),
        )
        conn.commit()
        return MarketHistoryUpdateResult(
            db_path=settings.path,
            status=status,
            latest_date=latest,
            symbol_count=len(symbols),
            covered_symbols=covered,
            coverage=coverage,
            fetched_rows=fetched_rows,
            inserted_rows=inserted_rows,
            updated_rows=updated_rows,
            warnings=warnings,
            source=settings.provider,
        )


def update_us_market_history_from_config(
    cfg: dict[str, Any],
    root: Path,
    *,
    check_only: bool = False,
) -> MarketHistoryUpdateResult:
    configure_us_market_history(cfg.get("us_market_history", {}), root)
    return _update_market_history(_us_settings, check_only=check_only)


def update_hk_market_history_from_config(
    cfg: dict[str, Any],
    root: Path,
    *,
    check_only: bool = False,
) -> MarketHistoryUpdateResult:
    configure_hk_market_history(cfg.get("hk_market_history", {}), root)
    return _update_market_history(_hk_settings, check_only=check_only)


def _load_daily_from_history(settings: MarketHistorySettings, symbols: list[str], start: date, end: date) -> pd.DataFrame:
    if not (settings.enabled and settings.path.exists() and symbols):
        return pd.DataFrame()
    table = _safe_identifier(settings.daily_table)
    placeholders = ",".join("?" for _ in symbols)
    query = f"""
        SELECT date, symbol, open, high, low, close, adjusted_close, volume, source
        FROM {table}
        WHERE symbol IN ({placeholders})
          AND date >= ?
          AND date <= ?
        ORDER BY symbol, date
    """
    try:
        with sqlite3.connect(settings.path) as conn:
            df = pd.read_sql_query(query, conn, params=[*symbols, start.isoformat(), end.isoformat()])
    except (sqlite3.Error, ValueError):
        return pd.DataFrame()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_us_daily_from_history(symbols: list[str], start: date, end: date) -> pd.DataFrame:
    return _load_daily_from_history(_us_settings, symbols, start, end)


def load_hk_daily_from_history(symbols: list[str], start: date, end: date) -> pd.DataFrame:
    return _load_daily_from_history(_hk_settings, symbols, start, end)
