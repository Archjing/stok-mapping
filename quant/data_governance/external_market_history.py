from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from quant.data_access.providers.external_market import fetch_external_market_daily


DEFAULT_US_MARKET_SYMBOLS = ["^NDX", "^SOX", "NVDA", "KWEB", "^VIX", "CNY=X"]
DEFAULT_HK_MARKET_SYMBOLS = ["HK.00700", "HK.09988"]
# Price-index series only. Do not treat their close prices as total-return data.
DEFAULT_EUROPE_MARKET_SYMBOLS = ["^FTSE", "^GDAXI", "^FCHI", "^STOXX50E", "^STOXX"]


@dataclass(frozen=True)
class MarketInstrumentGroup:
    """A named, configuration-owned group of related external-market symbols."""

    name: str
    symbols: tuple[str, ...]
    purpose: str = ""
    required_for: tuple[str, ...] = ()
    critical: bool = False
    asset_types: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketGroupHealth:
    name: str
    symbols: tuple[str, ...]
    latest_common_date: str
    covered_symbols: int
    status: str
    critical: bool
    purpose: str = ""
    missing_symbols: tuple[str, ...] = ()


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
    fetch_start_date: date | None = None
    symbol_groups: dict[str, MarketInstrumentGroup] = field(default_factory=dict)
    api_token_env: str = ""
    source_symbols: dict[str, str] = field(default_factory=dict)


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
    group_health: list[MarketGroupHealth] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in {"updated", "up_to_date", "check_ok", "disabled", "partial"}


_us_settings = MarketHistorySettings()
_hk_settings = MarketHistorySettings(
    path=Path("data/hk_market_history.sqlite"),
    provider="tushare_hk",
    symbols=list(DEFAULT_HK_MARKET_SYMBOLS),
    runtime_yfinance_fallback=False,
    market_name="hk_market",
)
_europe_settings = MarketHistorySettings(
    path=Path("data/euro_market_history.sqlite"),
    provider="yfinance",
    symbols=list(DEFAULT_EUROPE_MARKET_SYMBOLS),
    max_staleness_days=5,
    runtime_yfinance_fallback=False,
    market_name="europe_market",
)


def _safe_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Unsafe SQL identifier: {value}")
    return value


def _infer_asset_type(symbol: str) -> str:
    raw = str(symbol).upper()
    if raw.endswith("=X"):
        return "fx"
    if raw.startswith("^"):
        return "index"
    if raw in {"KWEB", "SMH"}:
        return "etf"
    return "equity"


def _parse_instrument_groups(raw: object) -> dict[str, MarketInstrumentGroup]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("us_market_history.instrument_groups must be a mapping")
    groups: dict[str, MarketInstrumentGroup] = {}
    seen_asset_types: dict[str, str] = {}
    for raw_name, raw_group in raw.items():
        name = str(raw_name).strip()
        if not name or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
            raise ValueError(f"invalid us_market_history instrument group name: {raw_name!r}")
        if not isinstance(raw_group, dict):
            raise ValueError(f"us_market_history.instrument_groups.{name} must be a mapping")
        raw_symbols = raw_group.get("symbols")
        if not isinstance(raw_symbols, list) or not raw_symbols:
            raise ValueError(f"us_market_history.instrument_groups.{name}.symbols must be a non-empty list")
        symbols: list[str] = []
        for value in raw_symbols:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"us_market_history.instrument_groups.{name}.symbols contains an invalid symbol")
            symbol = value.strip().upper()
            if symbol not in symbols:
                symbols.append(symbol)
        raw_asset_types = raw_group.get("asset_types", {})
        if raw_asset_types is None:
            raw_asset_types = {}
        if not isinstance(raw_asset_types, dict):
            raise ValueError(f"us_market_history.instrument_groups.{name}.asset_types must be a mapping")
        asset_types: dict[str, str] = {}
        for symbol in symbols:
            asset_type = str(raw_asset_types.get(symbol, _infer_asset_type(symbol))).strip().lower()
            if not asset_type:
                raise ValueError(f"us_market_history.instrument_groups.{name} has an empty asset type for {symbol}")
            previous = seen_asset_types.get(symbol)
            if previous is not None and previous != asset_type:
                raise ValueError(f"symbol {symbol} has incompatible asset types: {previous} and {asset_type}")
            seen_asset_types[symbol] = asset_type
            asset_types[symbol] = asset_type
        raw_required_for = raw_group.get("required_for", [])
        if not isinstance(raw_required_for, list) or not all(isinstance(item, str) for item in raw_required_for):
            raise ValueError(f"us_market_history.instrument_groups.{name}.required_for must be a string list")
        groups[name] = MarketInstrumentGroup(
            name=name,
            symbols=tuple(symbols),
            purpose=str(raw_group.get("purpose", "")),
            required_for=tuple(item.strip() for item in raw_required_for if item.strip()),
            critical=bool(raw_group.get("critical", False)),
            asset_types=asset_types,
        )
    return groups


def _flatten_group_symbols(groups: dict[str, MarketInstrumentGroup]) -> list[str]:
    return list(dict.fromkeys(symbol for group in groups.values() for symbol in group.symbols))


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
    symbol_groups = _parse_instrument_groups(raw.get("instrument_groups"))
    symbols = _flatten_group_symbols(symbol_groups) if symbol_groups else [str(item).strip().upper() for item in raw.get("symbols", default_symbols)]
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
        symbol_groups=symbol_groups,
        api_token_env=str(raw.get("api_token_env", defaults.api_token_env)),
        source_symbols={str(key): str(value) for key, value in (raw.get("source_symbols", defaults.source_symbols) or {}).items()},
    )


def configure_us_market_history(cfg: dict[str, Any] | None, root: Path | None = None) -> None:
    global _us_settings
    _us_settings = _build_settings(cfg, root=root, defaults=_us_settings, default_symbols=DEFAULT_US_MARKET_SYMBOLS)


def configure_hk_market_history(cfg: dict[str, Any] | None, root: Path | None = None) -> None:
    global _hk_settings
    _hk_settings = _build_settings(cfg, root=root, defaults=_hk_settings, default_symbols=DEFAULT_HK_MARKET_SYMBOLS)


def configure_europe_market_history(cfg: dict[str, Any] | None, root: Path | None = None) -> None:
    global _europe_settings
    _europe_settings = _build_settings(
        cfg,
        root=root,
        defaults=_europe_settings,
        default_symbols=DEFAULT_EUROPE_MARKET_SYMBOLS,
    )


def configured_us_market_groups(cfg: dict[str, Any] | None) -> dict[str, MarketInstrumentGroup]:
    """Return the configured US instrument groups without changing global settings."""
    return _parse_instrument_groups((cfg or {}).get("instrument_groups"))


def us_market_history_runtime_fallback_enabled() -> bool:
    return bool(_us_settings.enabled and _us_settings.runtime_yfinance_fallback)


def _ensure_tables(conn: sqlite3.Connection, settings: MarketHistorySettings) -> None:
    daily_table = _safe_identifier(settings.daily_table)
    audit_table = _safe_identifier(settings.source_audit_table)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {daily_table} (
            market TEXT NOT NULL,
            hk TEXT,
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
    # Backward-compatible migration for pre-existing databases.
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({daily_table})").fetchall()]
    if "hk" not in cols:
        conn.execute(f"ALTER TABLE {daily_table} ADD COLUMN hk TEXT")
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
    if settings.market_name != "us_market":
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS us_market_instruments (
            group_name TEXT NOT NULL,
            symbol TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            purpose TEXT NOT NULL,
            required_for TEXT NOT NULL,
            critical INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (group_name, symbol)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS us_data_source_symbol_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_run_id INTEGER,
            group_name TEXT NOT NULL,
            symbol TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            request_start_date TEXT,
            request_end_date TEXT,
            source TEXT NOT NULL,
            fetched_rows INTEGER NOT NULL,
            inserted_rows INTEGER NOT NULL,
            updated_rows INTEGER NOT NULL,
            latest_trade_date TEXT,
            status TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(parent_run_id) REFERENCES us_data_source_runs(id)
        )
        """
    )


def _market_for_symbol(symbol: str, settings: MarketHistorySettings) -> str:
    raw = symbol.upper()
    if settings.market_name == "europe_market":
        return "EU_INDEX"
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


def _group_health(conn: sqlite3.Connection, settings: MarketHistorySettings) -> list[MarketGroupHealth]:
    if not settings.symbol_groups:
        return []
    table = _safe_identifier(settings.daily_table)
    cutoff = date.today() - timedelta(days=max(0, settings.max_staleness_days))
    health: list[MarketGroupHealth] = []
    for group in settings.symbol_groups.values():
        placeholders = ",".join("?" for _ in group.symbols)
        rows = conn.execute(
            f"SELECT symbol, MAX(date) FROM {table} WHERE symbol IN ({placeholders}) GROUP BY symbol",
            group.symbols,
        ).fetchall()
        latest_by_symbol = {str(symbol): str(latest) for symbol, latest in rows if latest is not None}
        missing = tuple(symbol for symbol in group.symbols if symbol not in latest_by_symbol)
        common_row = conn.execute(
            f"""
            SELECT MAX(date) FROM (
                SELECT date FROM {table}
                WHERE symbol IN ({placeholders}) AND close IS NOT NULL
                GROUP BY date HAVING COUNT(DISTINCT symbol) = ?
            )
            """,
            (*group.symbols, len(group.symbols)),
        ).fetchone()
        latest_common = str(common_row[0] or "")
        stale = any(date.fromisoformat(latest) < cutoff for latest in latest_by_symbol.values())
        status = "ready" if not missing and latest_common and not stale else ("missing" if missing else "stale")
        health.append(
            MarketGroupHealth(
                name=group.name,
                symbols=group.symbols,
                latest_common_date=latest_common,
                covered_symbols=len(latest_by_symbol),
                status=status,
                critical=group.critical,
                purpose=group.purpose,
                missing_symbols=missing,
            )
        )
    return health


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
) -> int:
    table = _safe_identifier(settings.source_audit_table)
    cursor = conn.execute(
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
    return int(cursor.lastrowid)


def _persist_instrument_registry(conn: sqlite3.Connection, settings: MarketHistorySettings) -> None:
    if settings.market_name != "us_market" or not settings.symbol_groups:
        return
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute("DELETE FROM us_market_instruments")
    for group in settings.symbol_groups.values():
        for symbol in group.symbols:
            conn.execute(
                """
                INSERT INTO us_market_instruments
                (group_name, symbol, asset_type, purpose, required_for, critical, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    group.name,
                    symbol,
                    group.asset_types.get(symbol, _infer_asset_type(symbol)),
                    group.purpose,
                    ",".join(group.required_for),
                    int(group.critical),
                    now,
                ),
            )


def _validate_ohlc(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if frame.empty:
        return frame, 0
    numeric = frame[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    valid = (
        numeric.notna().all(axis=1)
        & (numeric > 0).all(axis=1)
        & (numeric["low"] <= numeric["open"])
        & (numeric["low"] <= numeric["close"])
        & (numeric["high"] >= numeric["open"])
        & (numeric["high"] >= numeric["close"])
        & (numeric["high"] >= numeric["low"])
    )
    return frame.loc[valid].copy(), int((~valid).sum())


def _groups_for_symbol(settings: MarketHistorySettings, symbol: str) -> tuple[MarketInstrumentGroup, ...]:
    return tuple(group for group in settings.symbol_groups.values() if symbol in group.symbols)


def _record_symbol_audits(conn: sqlite3.Connection, *, parent_run_id: int, settings: MarketHistorySettings, events: list[dict[str, Any]]) -> None:
    if settings.market_name != "us_market":
        return
    now = datetime.now().isoformat(timespec="seconds")
    for event in events:
        groups = _groups_for_symbol(settings, str(event["symbol"]))
        if not groups:
            groups = (MarketInstrumentGroup(name="legacy_symbols", symbols=(str(event["symbol"]),)),)
        for group in groups:
            conn.execute(
                """
                INSERT INTO us_data_source_symbol_runs
                (parent_run_id, group_name, symbol, asset_type, request_start_date, request_end_date, source,
                 fetched_rows, inserted_rows, updated_rows, latest_trade_date, status, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    parent_run_id,
                    group.name,
                    event["symbol"],
                    group.asset_types.get(event["symbol"], _infer_asset_type(event["symbol"])),
                    event.get("request_start_date", ""),
                    event.get("request_end_date", ""),
                    settings.provider,
                    int(event.get("fetched_rows", 0)),
                    int(event.get("inserted_rows", 0)),
                    int(event.get("updated_rows", 0)),
                    event.get("latest_trade_date", ""),
                    event["status"],
                    event.get("message", ""),
                    now,
                ),
            )


def _to_sql_value(value: Any) -> Any:
    return None if pd.isna(value) else value


def _normalize_frame(symbol: str, df: pd.DataFrame, settings: MarketHistorySettings) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    out["symbol"] = symbol
    out["market"] = _market_for_symbol(symbol, settings)
    out["hk"] = "HK" if out["market"].eq("HK").any() else None
    out["source"] = settings.provider
    out["fetched_at"] = datetime.now().isoformat(timespec="seconds")
    for col in ["open", "high", "low", "close", "adjusted_close", "volume"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
        else:
            out[col] = None
    # Keep malformed OHLC rows until the quality gate records them.  Dropping
    # them here would turn a provider corruption event into an indistinguishable
    # empty response and could hide a bad overwrite attempt.
    out = out.dropna(subset=["date"])
    keep = ["market", "hk", "symbol", "date", "open", "high", "low", "close", "adjusted_close", "volume", "source", "fetched_at"]
    return out[keep].drop_duplicates(["symbol", "date"]).astype(object).where(pd.notna(out[keep]), None)


def _update_market_history(
    settings: MarketHistorySettings,
    *,
    check_only: bool,
    force_start_date: date | None = None,
) -> MarketHistoryUpdateResult:
    if not settings.enabled:
        return MarketHistoryUpdateResult(settings.path, "disabled", "", 0, 0, 0.0, 0, 0, 0)

    symbols = list(dict.fromkeys(settings.symbols))
    warnings: list[str] = []
    if check_only:
        if not settings.path.is_file():
            return MarketHistoryUpdateResult(
                db_path=settings.path,
                status="stale",
                latest_date="",
                symbol_count=len(symbols),
                covered_symbols=0,
                coverage=0.0,
                fetched_rows=0,
                inserted_rows=0,
                updated_rows=0,
                warnings=[f"{settings.market_name} history database does not exist"],
                source=settings.provider,
            )
        try:
            with sqlite3.connect(f"file:{settings.path}?mode=ro", uri=True) as conn:
                latest, covered, coverage = _coverage(conn, settings, symbols)
                group_health = _group_health(conn, settings)
        except sqlite3.Error as exc:
            return MarketHistoryUpdateResult(
                db_path=settings.path,
                status="stale",
                latest_date="",
                symbol_count=len(symbols),
                covered_symbols=0,
                coverage=0.0,
                fetched_rows=0,
                inserted_rows=0,
                updated_rows=0,
                warnings=[f"cannot read {settings.market_name} history: {exc}"],
                source=settings.provider,
            )
        critical_unready = [group for group in group_health if group.critical and group.status != "ready"]
        status = "check_ok" if coverage >= settings.min_symbol_coverage and not critical_unready else "stale"
        check_warnings = [] if status == "check_ok" else [f"{settings.market_name} history is stale or undercovered"]
        if critical_unready:
            check_warnings.append("critical US market signal group is not ready")
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
            warnings=check_warnings,
            source=settings.provider,
            group_health=group_health,
        )

    settings.path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(settings.path) as conn:
        _ensure_tables(conn, settings)
        _persist_instrument_registry(conn, settings)
        latest, covered, coverage = _coverage(conn, settings, symbols)

        daily_table = _safe_identifier(settings.daily_table)
        fetched_rows = 0
        inserted_rows = 0
        updated_rows = 0
        latest_dates = _latest_symbol_dates(conn, settings)
        symbol_events: list[dict[str, Any]] = []
        for symbol in symbols:
            # Existing data only needs a short overlap for late corrections.
            # The initial load still uses the configured full history, while
            # routine runs avoid repeatedly downloading years of identical
            # Yahoo bars and triggering its rate limit.
            latest_symbol_date = latest_dates.get(symbol)
            if force_start_date is not None:
                # Explicit full-history backfill request: override the
                # incremental window even when local data already exists.
                fetch_settings = replace(
                    settings,
                    fetch_start_date=force_start_date,
                )
            elif latest_symbol_date:
                fetch_settings = replace(
                    settings,
                    years=1,
                    fetch_start_date=latest_symbol_date - timedelta(days=7),
                )
            else:
                fetch_settings = settings
            request_start = fetch_settings.fetch_start_date or (date.today() - timedelta(days=365 * fetch_settings.years))
            event: dict[str, Any] = {
                "symbol": symbol,
                "request_start_date": request_start.isoformat(),
                "request_end_date": date.today().isoformat(),
                "fetched_rows": 0,
                "inserted_rows": 0,
                "updated_rows": 0,
                "latest_trade_date": "",
                "status": "empty",
                "message": "",
            }
            try:
                raw = fetch_external_market_daily(symbol, fetch_settings)
            except Exception as exc:
                message = f"{settings.provider} {symbol} failed: {exc}"
                warnings.append(message)
                event.update(status="failed", message=message)
                symbol_events.append(event)
                continue
            normalized = _normalize_frame(symbol, raw, settings)
            if normalized.empty:
                message = f"{settings.provider} {symbol} returned empty data."
                warnings.append(message)
                event.update(status="empty", message=message)
                symbol_events.append(event)
                continue
            valid, invalid_rows = _validate_ohlc(normalized)
            event["fetched_rows"] = len(normalized)
            fetched_rows += len(valid)
            if invalid_rows:
                event["status"] = "invalid_data"
                event["message"] = f"rejected {invalid_rows} invalid OHLC row(s)"
                warnings.append(f"{settings.provider} {symbol} rejected {invalid_rows} invalid OHLC row(s).")
            if valid.empty:
                if not invalid_rows:
                    event.update(status="empty", message=f"{settings.provider} {symbol} returned no usable data.")
                symbol_events.append(event)
                continue
            for row in valid.itertuples(index=False):
                existed = conn.execute(
                    f"SELECT 1 FROM {daily_table} WHERE symbol = ? AND date = ?",
                    (row.symbol, row.date),
                ).fetchone()
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {daily_table} (
                        market, symbol, date, open, high, low, close, adjusted_close, volume, source, fetched_at, hk
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _to_sql_value(row.market),
                        _to_sql_value(row.symbol),
                        _to_sql_value(row.date),
                        _to_sql_value(row.open),
                        _to_sql_value(row.high),
                        _to_sql_value(row.low),
                        _to_sql_value(row.close),
                        _to_sql_value(row.adjusted_close),
                        _to_sql_value(row.volume),
                        _to_sql_value(row.source),
                        _to_sql_value(row.fetched_at),
                        _to_sql_value(row.hk),
                    ),
                )
                if existed:
                    updated_rows += 1
                    event["updated_rows"] += 1
                else:
                    inserted_rows += 1
                    event["inserted_rows"] += 1
            event["latest_trade_date"] = str(valid["date"].max())
            if not invalid_rows:
                event["status"] = "updated"
            symbol_events.append(event)

        latest, covered, coverage = _coverage(conn, settings, symbols)
        # Existing data can still satisfy the staleness grace window while the
        # provider has rejected every request.  That is not an up-to-date
        # update: surface it as a failed source run so schedulers and reports
        # do not claim freshness that was never verified in this invocation.
        critical_symbols = {
            symbol
            for group in settings.symbol_groups.values()
            if group.critical
            for symbol in group.symbols
        }
        critical_failures = [event for event in symbol_events if event["symbol"] in critical_symbols and event["status"] != "updated"]
        noncritical_failures = [
            event for event in symbol_events if event["symbol"] not in critical_symbols and event["status"] != "updated"
        ]
        if critical_failures:
            status = "critical_failed"
            warnings.append("critical US market signal group did not complete successfully")
        elif symbols and fetched_rows == 0:
            status = "source_failed"
        elif noncritical_failures:
            status = "partial"
        elif coverage >= settings.min_symbol_coverage and fetched_rows == 0:
            status = "up_to_date"
        elif coverage >= settings.min_symbol_coverage:
            status = "updated"
        else:
            status = "stale"
        if fetched_rows == 0 and not warnings:
            warnings.append(f"no {settings.market_name} rows were fetched")
        parent_run_id = _record_audit(
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
        _record_symbol_audits(conn, parent_run_id=parent_run_id, settings=settings, events=symbol_events)
        group_health = _group_health(conn, settings)
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
            group_health=group_health,
        )


def update_us_market_history_from_config(
    cfg: dict[str, Any],
    root: Path,
    *,
    check_only: bool = False,
    force_start_date: date | None = None,
) -> MarketHistoryUpdateResult:
    configure_us_market_history(cfg.get("us_market_history", {}), root)
    return _update_market_history(_us_settings, check_only=check_only, force_start_date=force_start_date)


def update_hk_market_history_from_config(
    cfg: dict[str, Any],
    root: Path,
    *,
    check_only: bool = False,
) -> MarketHistoryUpdateResult:
    configure_hk_market_history(cfg.get("hk_market_history", {}), root)
    return _update_market_history(_hk_settings, check_only=check_only)


def update_europe_market_history_from_config(
    cfg: dict[str, Any],
    root: Path,
    *,
    check_only: bool = False,
) -> MarketHistoryUpdateResult:
    configure_europe_market_history(cfg.get("europe_market_history", {}), root)
    return _update_market_history(_europe_settings, check_only=check_only)


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


def load_europe_daily_from_history(symbols: list[str], start: date, end: date) -> pd.DataFrame:
    return _load_daily_from_history(_europe_settings, symbols, start, end)
