from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from phase0.data_access.connectivity import fetch_fred_series


@dataclass(frozen=True)
class ReferenceSeriesMapping:
    symbol: str
    provider: str
    source_series_id: str


@dataclass
class CrossMarketReferenceHistorySettings:
    enabled: bool = True
    path: Path = Path("data/cross_market_reference_history.sqlite")
    daily_table: str = "cross_market_reference_daily"
    source_audit_table: str = "cross_market_reference_source_runs"
    years: int = 7
    max_staleness_days: int = 3
    min_symbol_coverage: float = 1.0
    mappings: list[ReferenceSeriesMapping] = field(default_factory=list)
    fred_enabled: bool = True
    fred_api_key_env: str = "FRED_API_KEY"
    fred_cache_enabled: bool = True
    fred_cache_dir: str = "data/cache/fred"
    fred_cache_ttl_hours: int = 24


@dataclass
class CrossMarketReferenceHistoryUpdateResult:
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

    @property
    def ok(self) -> bool:
        return self.status in {"updated", "up_to_date", "check_ok", "disabled"}


_settings = CrossMarketReferenceHistorySettings()


def _safe_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Unsafe SQL identifier: {value}")
    return value


def _resolved_path(path_value: Any, root: Path | None, default: Path) -> Path:
    path = Path(path_value or default)
    return path if path.is_absolute() or root is None else root / path


def configure_cross_market_reference_history(cfg: dict[str, Any] | None, root: Path | None = None) -> None:
    global _settings
    raw = cfg or {}
    defaults = CrossMarketReferenceHistorySettings()
    raw_series = raw.get("series", {})
    mappings: list[ReferenceSeriesMapping] = []
    if isinstance(raw_series, dict):
        for symbol, definition in raw_series.items():
            item = definition if isinstance(definition, dict) else {}
            source_series_id = str(item.get("source_series_id", "")).strip()
            if source_series_id:
                mappings.append(
                    ReferenceSeriesMapping(
                        symbol=str(symbol),
                        provider=str(item.get("provider", "fred")).strip().lower(),
                        source_series_id=source_series_id,
                    )
                )
    fred_cfg = raw.get("fred", {}) if isinstance(raw.get("fred", {}), dict) else {}
    cache_cfg = fred_cfg.get("cache", {}) if isinstance(fred_cfg.get("cache", {}), dict) else {}
    _settings = CrossMarketReferenceHistorySettings(
        enabled=bool(raw.get("enabled", defaults.enabled)),
        path=_resolved_path(raw.get("path"), root, defaults.path),
        daily_table=str(raw.get("daily_table", defaults.daily_table)),
        source_audit_table=str(raw.get("source_audit_table", defaults.source_audit_table)),
        years=int(raw.get("years", defaults.years)),
        max_staleness_days=int(raw.get("max_staleness_days", defaults.max_staleness_days)),
        min_symbol_coverage=float(raw.get("min_symbol_coverage", defaults.min_symbol_coverage)),
        mappings=mappings,
        fred_enabled=bool(fred_cfg.get("enabled", defaults.fred_enabled)),
        fred_api_key_env=str(fred_cfg.get("api_key_env", defaults.fred_api_key_env)),
        fred_cache_enabled=bool(cache_cfg.get("enabled", defaults.fred_cache_enabled)),
        fred_cache_dir=str(cache_cfg.get("dir", defaults.fred_cache_dir)),
        fred_cache_ttl_hours=int(cache_cfg.get("ttl_hours", defaults.fred_cache_ttl_hours)),
    )


def configure_cross_market_reference_history_from_config(cfg: dict[str, Any], root: Path) -> None:
    reference_cfg = dict(cfg.get("cross_market_reference_history", {}))
    fred_cfg = dict(cfg.get("data_sources", {}).get("fred", {}))
    fred_cfg.update(reference_cfg.get("fred", {}))
    reference_cfg["fred"] = fred_cfg
    configure_cross_market_reference_history(reference_cfg, root)


def _ensure_tables(conn: sqlite3.Connection, settings: CrossMarketReferenceHistorySettings) -> None:
    daily_table = _safe_identifier(settings.daily_table)
    audit_table = _safe_identifier(settings.source_audit_table)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {daily_table} (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            close REAL NOT NULL,
            source TEXT NOT NULL,
            source_series_id TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            PRIMARY KEY (symbol, date)
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {audit_table} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            source TEXT NOT NULL,
            source_series_id TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            latest_trade_date TEXT,
            fetched_rows INTEGER NOT NULL,
            inserted_rows INTEGER NOT NULL,
            updated_rows INTEGER NOT NULL,
            status TEXT NOT NULL,
            message TEXT NOT NULL
        )
        """
    )


def _latest_dates(conn: sqlite3.Connection, settings: CrossMarketReferenceHistorySettings) -> dict[str, date]:
    table = _safe_identifier(settings.daily_table)
    rows = conn.execute(f"SELECT symbol, MAX(date) FROM {table} GROUP BY symbol").fetchall()
    return {str(symbol): pd.Timestamp(latest).date() for symbol, latest in rows if latest}


def _coverage(conn: sqlite3.Connection, settings: CrossMarketReferenceHistorySettings) -> tuple[str, int, float]:
    symbols = [mapping.symbol for mapping in settings.mappings]
    if not symbols:
        return "", 0, 0.0
    latest_dates = _latest_dates(conn, settings)
    cutoff = date.today() - timedelta(days=max(0, settings.max_staleness_days))
    covered = [symbol for symbol in symbols if latest_dates.get(symbol) and latest_dates[symbol] >= cutoff]
    latest = max(latest_dates.values()).isoformat() if latest_dates else ""
    return latest, len(covered), len(covered) / len(symbols)


def _record_audit(
    conn: sqlite3.Connection,
    settings: CrossMarketReferenceHistorySettings,
    mapping: ReferenceSeriesMapping,
    *,
    latest_date: str,
    fetched_rows: int,
    inserted_rows: int,
    updated_rows: int,
    status: str,
    message: str,
) -> None:
    table = _safe_identifier(settings.source_audit_table)
    conn.execute(
        f"""
        INSERT INTO {table} (
            symbol, source, source_series_id, fetched_at, latest_trade_date,
            fetched_rows, inserted_rows, updated_rows, status, message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            mapping.symbol,
            mapping.provider,
            mapping.source_series_id,
            datetime.now().isoformat(timespec="seconds"),
            latest_date,
            fetched_rows,
            inserted_rows,
            updated_rows,
            status,
            message,
        ),
    )


def update_cross_market_reference_history_from_config(
    cfg: dict[str, Any],
    root: Path,
    *,
    check_only: bool = False,
) -> CrossMarketReferenceHistoryUpdateResult:
    configure_cross_market_reference_history_from_config(cfg, root)
    settings = _settings
    symbols = [mapping.symbol for mapping in settings.mappings]
    if not settings.enabled:
        return CrossMarketReferenceHistoryUpdateResult(settings.path, "disabled", "", 0, 0, 0.0, 0, 0, 0)

    settings.path.parent.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    with sqlite3.connect(settings.path) as conn:
        _ensure_tables(conn, settings)
        latest, covered, coverage = _coverage(conn, settings)
        if check_only:
            status = "check_ok" if coverage >= settings.min_symbol_coverage else "stale"
            return CrossMarketReferenceHistoryUpdateResult(
                settings.path,
                status,
                latest,
                len(symbols),
                covered,
                coverage,
                0,
                0,
                0,
                [] if status == "check_ok" else ["cross-market reference history is stale or undercovered"],
            )

        fetched_rows = inserted_rows = updated_rows = 0
        daily_table = _safe_identifier(settings.daily_table)
        for mapping in settings.mappings:
            if mapping.provider != "fred":
                message = f"unsupported_provider:{mapping.provider}"
                warnings.append(f"{mapping.symbol} {message}")
                _record_audit(conn, settings, mapping, latest_date="", fetched_rows=0, inserted_rows=0, updated_rows=0, status="error", message=message)
                continue
            if not settings.fred_enabled:
                message = "source_disabled:fred"
                warnings.append(f"{mapping.symbol} {message}")
                _record_audit(conn, settings, mapping, latest_date="", fetched_rows=0, inserted_rows=0, updated_rows=0, status="disabled", message=message)
                continue
            try:
                frame = fetch_fred_series(
                    mapping.source_series_id,
                    years=settings.years,
                    api_key_env=settings.fred_api_key_env,
                    cache_enabled=settings.fred_cache_enabled,
                    cache_dir=settings.fred_cache_dir,
                    cache_ttl_hours=settings.fred_cache_ttl_hours,
                )
            except Exception as exc:
                message = str(exc)
                warnings.append(f"fred {mapping.symbol} failed: {message}")
                _record_audit(conn, settings, mapping, latest_date="", fetched_rows=0, inserted_rows=0, updated_rows=0, status="error", message=message)
                continue
            normalized = frame.rename(columns={"value": "close"})[["date", "close"]].copy() if {"date", "value"}.issubset(frame.columns) else pd.DataFrame()
            if normalized.empty:
                message = "empty_or_missing_date_value"
                warnings.append(f"fred {mapping.symbol} returned empty data")
                _record_audit(conn, settings, mapping, latest_date="", fetched_rows=0, inserted_rows=0, updated_rows=0, status="empty", message=message)
                continue
            normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.strftime("%Y-%m-%d")
            normalized["close"] = pd.to_numeric(normalized["close"], errors="coerce")
            normalized = normalized.dropna(subset=["date", "close"]).drop_duplicates("date")
            mapping_fetched = len(normalized)
            mapping_inserted = mapping_updated = 0
            fetched_at = datetime.now().isoformat(timespec="seconds")
            for row in normalized.itertuples(index=False):
                exists = conn.execute(f"SELECT 1 FROM {daily_table} WHERE symbol = ? AND date = ?", (mapping.symbol, row.date)).fetchone()
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {daily_table} (symbol, date, close, source, source_series_id, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (mapping.symbol, row.date, float(row.close), mapping.provider, mapping.source_series_id, fetched_at),
                )
                if exists:
                    mapping_updated += 1
                else:
                    mapping_inserted += 1
            latest_for_mapping = str(normalized["date"].max())
            _record_audit(
                conn,
                settings,
                mapping,
                latest_date=latest_for_mapping,
                fetched_rows=mapping_fetched,
                inserted_rows=mapping_inserted,
                updated_rows=mapping_updated,
                status="updated",
                message="",
            )
            fetched_rows += mapping_fetched
            inserted_rows += mapping_inserted
            updated_rows += mapping_updated

        latest, covered, coverage = _coverage(conn, settings)
        status = "updated" if coverage >= settings.min_symbol_coverage else "stale"
        conn.commit()
        return CrossMarketReferenceHistoryUpdateResult(
            settings.path,
            status,
            latest,
            len(symbols),
            covered,
            coverage,
            fetched_rows,
            inserted_rows,
            updated_rows,
            warnings,
        )


def load_cross_market_reference_from_history(symbols: list[str], start: date, end: date) -> pd.DataFrame:
    settings = _settings
    if not settings.enabled or not settings.path.exists() or not symbols:
        return pd.DataFrame(columns=["date", "symbol", "close", "source", "source_series_id"])
    placeholders = ",".join("?" for _ in symbols)
    table = _safe_identifier(settings.daily_table)
    with sqlite3.connect(settings.path) as conn:
        frame = pd.read_sql_query(
            f"""
            SELECT date, symbol, close, source, source_series_id
            FROM {table}
            WHERE symbol IN ({placeholders}) AND date >= ? AND date <= ?
            ORDER BY symbol, date
            """,
            conn,
            params=[*symbols, start.isoformat(), end.isoformat()],
        )
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"])
    return frame
