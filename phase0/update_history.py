from __future__ import annotations

import sqlite3
import time as time_module
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from phase0.adjustment import upsert_adj_factors
from phase0.data_governance.daily_basic import ensure_daily_basic_table, upsert_daily_basic_rows
from phase0.data_governance.sql import safe_identifier, to_sql_value
from phase0.env import prepare_imports
from phase0.local_history import normalize_cn_symbol
from phase0.throttle import configure_akshare_throttle, fetch_with_akshare_retries
from phase0.data_access.providers.tushare import fetch_tushare_adj_factor_trade_date, fetch_tushare_trade_date, tushare_available, tushare_config

prepare_imports()

import akshare as ak  # noqa: E402

_safe_identifier = safe_identifier
_to_sql_value = to_sql_value
_ensure_daily_basic_table = ensure_daily_basic_table
_upsert_daily_basic_rows = upsert_daily_basic_rows


@dataclass
class ManualHistoryUpdateResult:
    db_path: Path
    calendar_trade_date: str
    target_trade_date: str
    before_latest_date: str
    after_latest_date: str
    before_coverage: float
    after_coverage: float
    fetched_rows: int
    inserted_rows: int
    status: str
    metadata_updated_rows: int = 0
    metadata_coverage: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    primary_source: str = ""

    @property
    def ok(self) -> bool:
        return self.status in {"up_to_date", "updated", "check_ok", "metadata_updated"}


@dataclass
class SourceAttempt:
    source: str
    fetched_rows: int
    coverage: float
    status: str
    message: str = ""


def _parse_date(value: Any) -> date | None:
    if value is None or pd.isna(value):
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_run_time(value: Any) -> time:
    raw = str(value or "16:00").strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    return time(16, 0)


def _calendar_max_open_date(conn: sqlite3.Connection, calendar_table: str, *, before: date | None = None) -> date | None:
    table = _safe_identifier(calendar_table)
    op = "<" if before is not None else "<="
    bound = before or date.today()
    value = pd.read_sql_query(
        f"SELECT MAX(date) AS latest_date FROM {table} WHERE is_open = 1 AND date {op} ?",
        conn,
        params=(bound.isoformat(),),
    )["latest_date"].iloc[0]
    return _parse_date(value)


def _resolve_trade_dates(
    conn: sqlite3.Connection,
    *,
    calendar_table: str,
    min_run_time: time,
) -> tuple[date, date, bool]:
    today = date.today()
    calendar_trade_date = _calendar_max_open_date(conn, calendar_table) or today
    before_min_run_time = calendar_trade_date == today and datetime.now().time() < min_run_time
    if not before_min_run_time:
        return calendar_trade_date, calendar_trade_date, False
    previous_trade_date = _calendar_max_open_date(conn, calendar_table, before=today)
    return calendar_trade_date, previous_trade_date or calendar_trade_date, True


def _latest_stats(
    conn: sqlite3.Connection,
    *,
    daily_table: str,
    meta_table: str,
    market: str,
    adjust_type: str,
    date_override: date | None = None,
) -> tuple[date | None, float, int, int]:
    table = _safe_identifier(daily_table)
    meta = _safe_identifier(meta_table)
    latest_value = pd.read_sql_query(
        f"""
        SELECT MAX(date) AS latest_date
        FROM {table}
        WHERE market = ?
          AND adjust_type = ?
        """,
        conn,
        params=(market, adjust_type),
    )["latest_date"].iloc[0]
    latest_date = _parse_date(latest_value)
    coverage_date = date_override or latest_date
    if latest_date is None or coverage_date is None:
        return latest_date, 0.0, 0, 0

    row = pd.read_sql_query(
        f"""
        SELECT
            COUNT(DISTINCT CASE WHEN date = ? THEN symbol END) AS latest_symbols,
            (
                SELECT COUNT(DISTINCT m.symbol)
                FROM {meta} m
                WHERE m.market = ?
                  AND (COALESCE(m.list_date, '') = '' OR m.list_date <= ?)
                  AND (COALESCE(m.delist_date, '') = '' OR m.delist_date > ?)
            ) AS total_symbols
        FROM {table}
        WHERE market = ?
          AND adjust_type = ?
        """,
        conn,
        params=(
            coverage_date.isoformat(),
            market,
            coverage_date.isoformat(),
            coverage_date.isoformat(),
            market,
            adjust_type,
        ),
    ).iloc[0]
    latest_symbols = int(row["latest_symbols"] or 0)
    total_symbols = int(row["total_symbols"] or 0)
    coverage = latest_symbols / total_symbols if total_symbols else 0.0
    return latest_date, float(coverage), latest_symbols, total_symbols


def _metadata_coverage(conn: sqlite3.Connection, *, meta_table: str, market: str) -> dict[str, float]:
    table = _safe_identifier(meta_table)
    row = pd.read_sql_query(
        f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN market_cap IS NOT NULL THEN 1 ELSE 0 END) AS market_cap,
            SUM(CASE WHEN pe_ratio IS NOT NULL THEN 1 ELSE 0 END) AS pe_ratio,
            SUM(CASE WHEN pb_ratio IS NOT NULL THEN 1 ELSE 0 END) AS pb_ratio,
            SUM(CASE WHEN turnover_rate IS NOT NULL THEN 1 ELSE 0 END) AS turnover_rate
        FROM {table}
        WHERE market = ?
        """,
        conn,
        params=(market,),
    ).iloc[0]
    total = int(row.get("total") or 0)
    fields = ["market_cap", "pe_ratio", "pb_ratio", "turnover_rate"]
    out = {"total": float(total)}
    for field_name in fields:
        out[field_name] = float(int(row.get(field_name) or 0) / total) if total else 0.0
    out["min_field"] = min(out[field_name] for field_name in fields) if total else 0.0
    return out


def _ensure_source_audit_table(conn: sqlite3.Connection, *, table_name: str) -> None:
    table = _safe_identifier(table_name)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            latest_trade_date TEXT,
            coverage REAL,
            fetched_rows INTEGER,
            inserted_rows INTEGER,
            status TEXT,
            message TEXT
        )
        """
    )


def _record_source_audit(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    source: str,
    latest_trade_date: date,
    coverage: float,
    fetched_rows: int,
    inserted_rows: int,
    status: str,
    message: str = "",
) -> None:
    table = _safe_identifier(table_name)
    _ensure_source_audit_table(conn, table_name=table)
    conn.execute(
        f"""
        INSERT INTO {table} (
            source, fetched_at, latest_trade_date, coverage, fetched_rows, inserted_rows, status, message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source,
            datetime.now().isoformat(timespec="seconds"),
            latest_trade_date.isoformat(),
            float(coverage),
            int(fetched_rows),
            int(inserted_rows),
            status,
            message,
        ),
    )


def _trade_day_lag(
    conn: sqlite3.Connection,
    *,
    calendar_table: str,
    latest_trade_date: date | None,
    target_trade_date: date,
) -> int:
    if latest_trade_date is None:
        return 9999
    if latest_trade_date >= target_trade_date:
        return 0
    table = _safe_identifier(calendar_table)
    value = pd.read_sql_query(
        f"""
        SELECT COUNT(DISTINCT date) AS lag
        FROM {table}
        WHERE is_open = 1
          AND date > ?
          AND date <= ?
        """,
        conn,
        params=(latest_trade_date.isoformat(), target_trade_date.isoformat()),
    )["lag"].iloc[0]
    return int(value or 0)


def _series_or_empty(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    normalized = {str(col).strip().lower(): col for col in df.columns}
    for name in candidates:
        key = name.strip().lower()
        if key in normalized:
            return df[normalized[key]]
    return pd.Series(pd.NA, index=df.index)


def _clean_numeric(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace("--", "", regex=False)
        .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _clean_market_value(series: pd.Series) -> pd.Series:
    values = _clean_numeric(series)
    positive = values[values > 0]
    if positive.empty:
        return values
    # Sina mktcap/nmc are usually in 10k CNY, while Eastmoney fields are CNY.
    if positive.median() < 100_000_000:
        return values * 10_000
    return values


def _normalize_spot_symbol(value: Any) -> str:
    raw = str(value).strip().upper()
    digits = re.sub(r"\D", "", raw)
    if 0 < len(digits) < 6:
        raw = digits.zfill(6)
    return normalize_cn_symbol(raw)


def _normalize_spot_snapshot(
    raw: pd.DataFrame,
    *,
    trade_date: date,
    adjust_types: list[str],
    markets: set[str],
    max_symbols: int,
) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()

    code = _series_or_empty(raw, ["代码", "code", "symbol"])
    base = pd.DataFrame(
        {
            "market": "CN",
            "symbol": code.map(_normalize_spot_symbol),
            "date": trade_date.isoformat(),
            "open": _clean_numeric(_series_or_empty(raw, ["今开", "开盘", "open"])),
            "high": _clean_numeric(_series_or_empty(raw, ["最高", "high"])),
            "low": _clean_numeric(_series_or_empty(raw, ["最低", "low"])),
            "close": _clean_numeric(_series_or_empty(raw, ["最新价", "收盘", "close"])),
            "volume": _clean_numeric(_series_or_empty(raw, ["成交量", "volume"])),
            "amount": _clean_numeric(_series_or_empty(raw, ["成交额", "成交金额", "amount"])),
            "change_pct": _clean_numeric(_series_or_empty(raw, ["涨跌幅", "pct_chg"])),
            "change_amount": _clean_numeric(_series_or_empty(raw, ["涨跌额", "change"])),
            "amplitude": _clean_numeric(_series_or_empty(raw, ["振幅", "amplitude"])),
            "turnover_rate": _clean_numeric(_series_or_empty(raw, ["换手率", "turnover_rate"])),
        }
    )
    base = base[base["symbol"] != ""].copy()
    if markets:
        base = base[base["symbol"].str.split(".").str[0].isin(markets)].copy()
    base = base.dropna(subset=["open", "high", "low", "close"])
    base = base[(base["open"] > 0) & (base["high"] > 0) & (base["low"] > 0) & (base["close"] > 0)]
    base = base.drop_duplicates("symbol").sort_values("symbol")
    if max_symbols > 0:
        base = base.head(max_symbols)
    if base.empty:
        return base
    base["adjusted_close"] = base["close"]

    frames = []
    keep = [
        "market",
        "symbol",
        "date",
        "adjust_type",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "adjusted_close",
        "change_pct",
        "change_amount",
        "amplitude",
        "turnover_rate",
    ]
    for adjust_type in adjust_types:
        frame = base.copy()
        frame["adjust_type"] = adjust_type
        frames.append(frame[keep])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=keep)


def _fetch_sina_spot_preserve_valuation(page_delay: float = 0.5) -> pd.DataFrame:
    from akshare.stock.cons import zh_sina_a_stock_count_url, zh_sina_a_stock_payload, zh_sina_a_stock_url
    from akshare.utils import demjson

    count_response = requests.get(zh_sina_a_stock_count_url, timeout=15)
    if count_response.status_code != 200:
        raise RuntimeError(f"sina count request failed: status={count_response.status_code}")
    match = re.search(r"\d+", count_response.text)
    if not match:
        raise RuntimeError("sina count response has no page count")
    page_count = int(int(match.group(0)) / 80) + 1

    frames: list[pd.DataFrame] = []
    params = zh_sina_a_stock_payload.copy()
    for page in range(1, page_count + 1):
        params.update({"page": page})
        response = requests.get(zh_sina_a_stock_url, params=params, timeout=15)
        if response.status_code != 200:
            raise RuntimeError(f"sina page request failed: page={page}, status={response.status_code}")
        rows = demjson.decode(response.text)
        if rows:
            frames.append(pd.DataFrame(rows))
        if page < page_count:
            time_module.sleep(page_delay)
    if not frames:
        return pd.DataFrame()
    raw = pd.concat(frames, ignore_index=True)
    rename = {
        "symbol": "代码",
        "name": "名称",
        "trade": "最新价",
        "pricechange": "涨跌额",
        "changepercent": "涨跌幅",
        "settlement": "昨收",
        "open": "今开",
        "high": "最高",
        "low": "最低",
        "volume": "成交量",
        "amount": "成交额",
        "per": "市盈率-动态",
        "pb": "市净率",
        "mktcap": "总市值",
        "nmc": "流通市值",
        "turnoverratio": "换手率",
    }
    out = raw.rename(columns=rename)
    keep = [
        "代码",
        "名称",
        "最新价",
        "涨跌额",
        "涨跌幅",
        "昨收",
        "今开",
        "最高",
        "最低",
        "成交量",
        "成交额",
        "市盈率-动态",
        "市净率",
        "总市值",
        "流通市值",
        "换手率",
    ]
    for col in keep:
        if col not in out.columns:
            out[col] = pd.NA
    return out[keep]


def _fetch_spot_snapshot(warnings: list[str]) -> pd.DataFrame:
    sources = [
        ("akshare.stock_zh_a_spot_em", lambda: fetch_with_akshare_retries(lambda: ak.stock_zh_a_spot_em())),
        ("sina.raw_spot", lambda: fetch_with_akshare_retries(lambda: _fetch_sina_spot_preserve_valuation())),
    ]
    for source_name, fetcher in sources:
        try:
            df = fetcher()
        except Exception as exc:
            warnings.append(f"{source_name} snapshot failed: {exc}")
            continue
        if df is not None and not df.empty:
            df.attrs["source"] = source_name
            return df
        warnings.append(f"{source_name} snapshot returned empty data.")
    return pd.DataFrame()


def _normalize_spot_metadata(raw: pd.DataFrame, *, markets: set[str], max_symbols: int) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    code = _series_or_empty(raw, ["代码", "code", "symbol"])
    meta = pd.DataFrame(
        {
            "market": "CN",
            "symbol": code.map(_normalize_spot_symbol),
            "raw_symbol": code.astype(str),
            "name": _series_or_empty(raw, ["名称", "name"]),
            "market_cap": _clean_market_value(_series_or_empty(raw, ["总市值", "market_cap"])),
            "pe_ratio": _clean_numeric(_series_or_empty(raw, ["市盈率-动态", "市盈率", "pe", "pe_ratio"])),
            "pb_ratio": _clean_numeric(_series_or_empty(raw, ["市净率", "pb", "pb_ratio"])),
            "turnover_rate": _clean_numeric(_series_or_empty(raw, ["换手率", "turnover_rate"])),
        }
    )
    meta = meta[meta["symbol"] != ""].copy()
    if markets:
        meta = meta[meta["symbol"].str.split(".").str[0].isin(markets)].copy()
    meta = meta.drop_duplicates("symbol").sort_values("symbol")
    if max_symbols > 0:
        meta = meta.head(max_symbols)
    return meta


def _fetch_incremental_rows(
    *,
    trade_date: date,
    adjust_types: list[str],
    markets: set[str],
    max_symbols: int,
    total_symbols: int,
    min_coverage: float,
    data_cfg: dict[str, Any],
    warnings: list[str],
    allow_spot_fallback: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, int, str, list[SourceAttempt]]:
    attempts: list[SourceAttempt] = []
    tcfg = tushare_config(data_cfg.get("tushare", {}))
    if tushare_available(tcfg):
        try:
            rows, meta = fetch_tushare_trade_date(trade_date, adjust_types=adjust_types, cfg=tcfg)
            factors = fetch_tushare_adj_factor_trade_date(trade_date, cfg=tcfg)
            if markets and not rows.empty:
                rows = rows[rows["symbol"].astype(str).str.split(".").str[0].isin(markets)].copy()
            if markets and not meta.empty:
                meta = meta[meta["symbol"].astype(str).str.split(".").str[0].isin(markets)].copy()
            if max_symbols > 0:
                keep_symbols = sorted(rows["symbol"].dropna().astype(str).unique())[:max_symbols]
                rows = rows[rows["symbol"].isin(keep_symbols)].copy()
                meta = meta[meta["symbol"].isin(keep_symbols)].copy()
            fetched_rows = int(len(rows[rows["adjust_type"] == adjust_types[0]])) if adjust_types else int(len(rows))
            if not rows.empty:
                source = str(rows.attrs.get("source", "tushare.daily+daily_basic+adj_factor"))
                primary_adjust = adjust_types[0] if adjust_types else ""
                primary_rows = rows[rows["adjust_type"] == primary_adjust] if primary_adjust else rows
                coverage = primary_rows["symbol"].nunique() / total_symbols if total_symbols else 0.0
                if coverage >= min_coverage:
                    return rows, meta, factors, fetched_rows, source, attempts
                message = f"coverage={coverage:.4f}, threshold={min_coverage:.4f}"
                warnings.append(f"tushare returned undercovered rows: {message}")
                attempts.append(SourceAttempt(source=source, fetched_rows=fetched_rows, coverage=coverage, status="undercovered", message=message))
            else:
                warnings.append("tushare daily returned no usable rows.")
                attempts.append(SourceAttempt(source="tushare.daily+daily_basic+adj_factor", fetched_rows=0, coverage=0.0, status="empty"))
        except Exception as exc:
            warnings.append(f"tushare daily/daily_basic failed: {exc}")
            attempts.append(
                SourceAttempt(
                    source="tushare.daily+daily_basic+adj_factor",
                    fetched_rows=0,
                    coverage=0.0,
                    status="failed",
                    message=str(exc),
                )
            )
    elif tcfg.enabled:
        warnings.append(f"tushare enabled but token env {tcfg.token_env} is not set.")
        attempts.append(SourceAttempt(source="tushare.daily+daily_basic+adj_factor", fetched_rows=0, coverage=0.0, status="missing_token"))

    if not allow_spot_fallback:
        warnings.append("Skipped live spot fallback for a closed-date backfill before configured min_run_time.")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), 0, "tushare.daily+daily_basic+adj_factor", attempts

    raw = _fetch_spot_snapshot(warnings)
    fetched_rows = len(raw) if raw is not None else 0
    rows = _normalize_spot_snapshot(
        raw,
        trade_date=trade_date,
        adjust_types=adjust_types,
        markets=markets,
        max_symbols=max_symbols,
    )
    meta = _normalize_spot_metadata(raw, markets=markets, max_symbols=max_symbols) if raw is not None and not raw.empty else pd.DataFrame()
    source = str(raw.attrs.get("source", "akshare_or_sina_snapshot")) if raw is not None else "akshare_or_sina_snapshot"
    return rows, meta, pd.DataFrame(), fetched_rows, source, attempts


def _upsert_stock_metadata(conn: sqlite3.Connection, *, meta_table: str, rows: pd.DataFrame) -> int:
    if rows.empty:
        return 0
    table = _safe_identifier(meta_table)
    params = [
        (
            str(row.get("name") or ""),
            _to_sql_value(row.get("market_cap")),
            _to_sql_value(row.get("pe_ratio")),
            _to_sql_value(row.get("pb_ratio")),
            _to_sql_value(row.get("turnover_rate")),
            str(row.get("market") or "CN"),
            str(row.get("symbol") or ""),
        )
        for _, row in rows.iterrows()
    ]
    cursor = conn.executemany(
        f"""
        UPDATE {table}
        SET
            name = COALESCE(NULLIF(?, ''), name),
            market_cap = COALESCE(?, market_cap),
            pe_ratio = COALESCE(?, pe_ratio),
            pb_ratio = COALESCE(?, pb_ratio),
            turnover_rate = COALESCE(?, turnover_rate)
        WHERE market = ?
          AND symbol = ?
        """,
        params,
    )
    updated = int(cursor.rowcount or 0)

    existing = set(
        pd.read_sql_query(
            f"SELECT symbol FROM {table} WHERE market = ?",
            conn,
            params=(str(rows["market"].iloc[0]) if "market" in rows.columns and not rows.empty else "CN",),
        )["symbol"].astype(str)
    )
    missing = rows[~rows["symbol"].astype(str).isin(existing)].copy()
    if missing.empty:
        return updated
    insert_params = [
        (
            str(row.get("market") or "CN"),
            str(row.get("symbol") or ""),
            str(row.get("raw_symbol") or row.get("symbol") or ""),
            str(row.get("name") or ""),
            "",
            "",
            "",
            "",
            "",
            "CN",
            "CNY",
            "",
            "",
            "",
            "",
            "",
            "",
            _to_sql_value(row.get("market_cap")),
            _to_sql_value(row.get("pe_ratio")),
            _to_sql_value(row.get("pb_ratio")),
            _to_sql_value(row.get("turnover_rate")),
        )
        for _, row in missing.iterrows()
    ]
    insert_cursor = conn.executemany(
        f"""
        INSERT INTO {table} (
            market, symbol, raw_symbol, name, exchange, board, sector, industry, area, country,
            currency, list_status, list_date, delist_date, is_hs_connect, controller,
            controller_type, market_cap, pe_ratio, pb_ratio, turnover_rate
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        insert_params,
    )
    return updated + int(insert_cursor.rowcount or 0)


def _backfill_turnover_from_latest_daily(
    conn: sqlite3.Connection,
    *,
    daily_table: str,
    meta_table: str,
    market: str,
    adjust_type: str,
) -> int:
    daily = _safe_identifier(daily_table)
    meta = _safe_identifier(meta_table)
    latest = pd.read_sql_query(
        f"SELECT MAX(date) AS latest_date FROM {daily} WHERE market = ? AND adjust_type = ?",
        conn,
        params=(market, adjust_type),
    )["latest_date"].iloc[0]
    if latest is None or pd.isna(latest):
        return 0
    cursor = conn.execute(
        f"""
        UPDATE {meta}
        SET turnover_rate = (
            SELECT d.turnover_rate
            FROM {daily} d
            WHERE d.market = {meta}.market
              AND d.symbol = {meta}.symbol
              AND d.adjust_type = ?
              AND d.date = ?
              AND d.turnover_rate IS NOT NULL
            LIMIT 1
        )
        WHERE market = ?
          AND EXISTS (
              SELECT 1
              FROM {daily} d
              WHERE d.market = {meta}.market
                AND d.symbol = {meta}.symbol
                AND d.adjust_type = ?
                AND d.date = ?
                AND d.turnover_rate IS NOT NULL
          )
        """,
        (adjust_type, str(latest), market, adjust_type, str(latest)),
    )
    return int(cursor.rowcount or 0)


def _empty_result(
    *,
    db_path: Path,
    calendar_trade_date: date,
    target_trade_date: date,
    before_latest: date | None,
    before_coverage: float,
    metadata_coverage: dict[str, float] | None = None,
    metadata_updated_rows: int = 0,
    status: str,
    warnings: list[str],
    primary_source: str = "",
) -> ManualHistoryUpdateResult:
    return ManualHistoryUpdateResult(
        db_path=db_path,
        calendar_trade_date=calendar_trade_date.isoformat(),
        target_trade_date=target_trade_date.isoformat(),
        before_latest_date=before_latest.isoformat() if before_latest else "",
        after_latest_date=before_latest.isoformat() if before_latest else "",
        before_coverage=before_coverage,
        after_coverage=before_coverage,
        fetched_rows=0,
        inserted_rows=0,
        metadata_updated_rows=metadata_updated_rows,
        metadata_coverage=metadata_coverage or {},
        status=status,
        warnings=warnings,
        primary_source=primary_source,
    )


def update_manual_history_from_config(
    cfg: dict[str, Any],
    root: Path,
    *,
    check_only: bool = False,
) -> ManualHistoryUpdateResult:
    local_cfg = cfg.get("local_history", {})
    update_cfg = cfg.get("manual_history_update", {})
    data_cfg = cfg.get("data_sources", {})

    db_path = Path(update_cfg.get("path", local_cfg.get("path", "data/manual_history/a_share_history.sqlite")))
    if not db_path.is_absolute():
        db_path = root / db_path
    daily_table = str(local_cfg.get("daily_table", "market_daily_bars"))
    meta_table = str(local_cfg.get("meta_table", "market_stocks"))
    daily_basic_table = str(local_cfg.get("daily_basic_table", "market_daily_basic"))
    adj_factor_table = str(local_cfg.get("adj_factor_table", "market_adj_factors"))
    calendar_table = str(local_cfg.get("calendar_table", "trading_calendar"))
    market = str(local_cfg.get("market", "CN"))
    adjust_types = [str(item) for item in update_cfg.get("adjust_types", ["qfq"])]
    primary_adjust = adjust_types[0] if adjust_types else str(local_cfg.get("adjust_type", "qfq"))
    markets = {str(item) for item in update_cfg.get("markets", ["SH", "SZ"])}
    max_symbols = int(update_cfg.get("max_symbols", 0))
    max_staleness_days = int(update_cfg.get("max_staleness_days", local_cfg.get("max_snapshot_staleness_days", 1)))
    min_latest_coverage = float(update_cfg.get("min_latest_coverage", local_cfg.get("min_snapshot_coverage", 0.80)))
    min_run_time = _parse_run_time(update_cfg.get("min_run_time", "16:00"))
    refresh_metadata = bool(update_cfg.get("refresh_metadata", True))
    min_metadata_coverage = float(update_cfg.get("min_metadata_coverage", 0.80))
    source_audit_table = str(update_cfg.get("source_audit_table", "market_data_source_runs"))

    if not db_path.exists():
        today = date.today()
        return _empty_result(
            db_path=db_path,
            calendar_trade_date=today,
            target_trade_date=today,
            before_latest=None,
            before_coverage=0.0,
            status="missing_db",
            warnings=[f"manual history database does not exist: {db_path}"],
        )

    warnings: list[str] = []
    configure_akshare_throttle(data_cfg.get("akshare", {}))

    with sqlite3.connect(db_path) as conn:
        _ensure_daily_basic_table(conn, table_name=daily_basic_table)
        calendar_trade_date, target_trade_date, before_min_run_time = _resolve_trade_dates(
            conn,
            calendar_table=calendar_table,
            min_run_time=min_run_time,
        )
        before_latest, before_coverage, _, _ = _latest_stats(
            conn,
            daily_table=daily_table,
            meta_table=meta_table,
            market=market,
            adjust_type=primary_adjust,
        )
        before_target_coverage = _latest_stats(
            conn,
            daily_table=daily_table,
            meta_table=meta_table,
            market=market,
            adjust_type=primary_adjust,
            date_override=target_trade_date,
        )[1]
        before_staleness = _trade_day_lag(
            conn,
            calendar_table=calendar_table,
            latest_trade_date=before_latest,
            target_trade_date=calendar_trade_date,
        )
        target_is_covered = before_latest is not None and before_latest >= target_trade_date and before_target_coverage >= min_latest_coverage
        freshness_ok = before_staleness <= max_staleness_days and before_coverage >= min_latest_coverage
        target_is_today = target_trade_date == date.today()
        block_live_spot_write = before_min_run_time and target_is_today
        metadata_before = _metadata_coverage(conn, meta_table=meta_table, market=market)
        metadata_needs_refresh = refresh_metadata and metadata_before.get("min_field", 0.0) < min_metadata_coverage

        if check_only:
            status = "check_ok" if freshness_ok else "stale"
            check_warnings: list[str] = []
            if status != "check_ok":
                check_warnings.append("local history is stale or undercovered")
            if refresh_metadata and metadata_needs_refresh:
                check_warnings.append(
                    "stock metadata is undercovered: "
                    f"min_field_coverage={metadata_before.get('min_field', 0.0):.4f}, "
                    f"threshold={min_metadata_coverage:.4f}"
                )
            return _empty_result(
                db_path=db_path,
                calendar_trade_date=calendar_trade_date,
                target_trade_date=target_trade_date,
                before_latest=before_latest,
                before_coverage=before_coverage,
                metadata_coverage=metadata_before,
                status=status,
                warnings=check_warnings,
            )

        if target_is_covered and freshness_ok and not metadata_needs_refresh:
            return _empty_result(
                db_path=db_path,
                calendar_trade_date=calendar_trade_date,
                target_trade_date=target_trade_date,
                before_latest=before_latest,
                before_coverage=before_coverage,
                metadata_coverage=metadata_before,
                status="up_to_date",
                warnings=[],
            )

        if block_live_spot_write and not metadata_needs_refresh:
            warnings.append(
                f"Skipped live spot write before configured min_run_time={min_run_time.strftime('%H:%M')}; "
                "writing now could label intraday quotes as daily close."
            )
            return _empty_result(
                db_path=db_path,
                calendar_trade_date=calendar_trade_date,
                target_trade_date=target_trade_date,
                before_latest=before_latest,
                before_coverage=before_coverage,
                metadata_coverage=metadata_before,
                status="too_early",
                warnings=warnings,
            )

        local_turnover_updated_rows = 0
        if refresh_metadata and metadata_before.get("turnover_rate", 0.0) < min_metadata_coverage:
            try:
                local_turnover_updated_rows = _backfill_turnover_from_latest_daily(
                    conn,
                    daily_table=daily_table,
                    meta_table=meta_table,
                    market=market,
                    adjust_type=primary_adjust,
                )
                conn.commit()
            except sqlite3.Error as exc:
                warnings.append(f"Local daily turnover backfill failed: {exc}")

        _, _, _, total_symbols = _latest_stats(
            conn,
            daily_table=daily_table,
            meta_table=meta_table,
            market=market,
            adjust_type=primary_adjust,
        )
        rows, meta_rows, adj_factor_rows, fetched_rows, primary_source, source_attempts = _fetch_incremental_rows(
            trade_date=target_trade_date,
            adjust_types=adjust_types,
            markets=markets,
            max_symbols=max_symbols,
            total_symbols=total_symbols,
            min_coverage=min_latest_coverage,
            data_cfg=data_cfg,
            warnings=warnings,
            allow_spot_fallback=not before_min_run_time,
        )
        for attempt in source_attempts:
            _record_source_audit(
                conn,
                table_name=source_audit_table,
                source=attempt.source,
                latest_trade_date=target_trade_date,
                coverage=attempt.coverage,
                fetched_rows=attempt.fetched_rows,
                inserted_rows=0,
                status=attempt.status,
                message=attempt.message,
            )
        if source_attempts:
            conn.commit()
        metadata_updated_rows = 0
        daily_basic_updated_rows = 0
        adj_factor_updated_rows = 0
        if not adj_factor_rows.empty:
            try:
                adj_factor_updated_rows = upsert_adj_factors(
                    conn,
                    adj_factor_rows,
                    table=adj_factor_table,
                    source="tushare.adj_factor",
                )
                conn.commit()
            except sqlite3.Error as exc:
                warnings.append(f"Adjustment factor update failed: {exc}")
        if refresh_metadata and not meta_rows.empty:
            try:
                daily_basic_updated_rows = _upsert_daily_basic_rows(conn, table_name=daily_basic_table, rows=meta_rows)
                metadata_updated_rows = _upsert_stock_metadata(conn, meta_table=meta_table, rows=meta_rows)
                conn.commit()
            except sqlite3.Error as exc:
                warnings.append(f"Stock metadata update failed: {exc}")
        metadata_updated_rows += local_turnover_updated_rows
        if adj_factor_updated_rows == 0 and primary_source.startswith("tushare"):
            warnings.append("Tushare update wrote no adjustment factor rows.")
        metadata_after = _metadata_coverage(conn, meta_table=meta_table, market=market)

        if block_live_spot_write and target_is_covered and freshness_ok:
            status = "metadata_updated" if metadata_updated_rows > 0 else "up_to_date"
            if metadata_after.get("min_field", 0.0) < min_metadata_coverage:
                warnings.append(
                    "Stock metadata refresh did not reach configured coverage: "
                    f"min_field_coverage={metadata_after.get('min_field', 0.0):.4f}, "
                    f"threshold={min_metadata_coverage:.4f}."
                )
                if metadata_after.get("market_cap", 0.0) < min_metadata_coverage:
                    status = "metadata_undercovered"
            return ManualHistoryUpdateResult(
                db_path=db_path,
                calendar_trade_date=calendar_trade_date.isoformat(),
                target_trade_date=target_trade_date.isoformat(),
                before_latest_date=before_latest.isoformat() if before_latest else "",
                after_latest_date=before_latest.isoformat() if before_latest else "",
                before_coverage=before_coverage,
                after_coverage=before_coverage,
                fetched_rows=fetched_rows,
                inserted_rows=0,
                metadata_updated_rows=metadata_updated_rows,
                metadata_coverage=metadata_after,
                status=status,
                warnings=warnings,
                primary_source=primary_source,
            )

        if block_live_spot_write:
            warnings.append(
                f"Skipped live spot write before configured min_run_time={min_run_time.strftime('%H:%M')}; "
                "writing now could label intraday quotes as daily close."
            )
            status = "too_early"
            if metadata_needs_refresh and metadata_after.get("min_field", 0.0) < min_metadata_coverage:
                warnings.append(
                    "Stock metadata refresh did not reach configured coverage: "
                    f"min_field_coverage={metadata_after.get('min_field', 0.0):.4f}, "
                    f"threshold={min_metadata_coverage:.4f}."
                )
            return ManualHistoryUpdateResult(
                db_path=db_path,
                calendar_trade_date=calendar_trade_date.isoformat(),
                target_trade_date=target_trade_date.isoformat(),
                before_latest_date=before_latest.isoformat() if before_latest else "",
                after_latest_date=before_latest.isoformat() if before_latest else "",
                before_coverage=before_coverage,
                after_coverage=before_coverage,
                fetched_rows=fetched_rows,
                inserted_rows=0,
                metadata_updated_rows=metadata_updated_rows,
                metadata_coverage=metadata_after,
                status=status,
                warnings=warnings,
                primary_source=primary_source,
            )

        if rows.empty:
            warnings.append("No online source returned usable rows.")
            after_latest, after_coverage, _, _ = _latest_stats(
                conn,
                daily_table=daily_table,
                meta_table=meta_table,
                market=market,
                adjust_type=primary_adjust,
            )
            _record_source_audit(
                conn,
                table_name=source_audit_table,
                source=primary_source,
                latest_trade_date=target_trade_date,
                coverage=0.0,
                fetched_rows=fetched_rows,
                inserted_rows=0,
                status="empty",
                message="; ".join(warnings[-3:]),
            )
            conn.commit()
            return ManualHistoryUpdateResult(
                db_path=db_path,
                calendar_trade_date=calendar_trade_date.isoformat(),
                target_trade_date=target_trade_date.isoformat(),
                before_latest_date=before_latest.isoformat() if before_latest else "",
                after_latest_date=after_latest.isoformat() if after_latest else "",
                before_coverage=before_coverage,
                after_coverage=after_coverage,
                fetched_rows=fetched_rows,
                inserted_rows=0,
                metadata_updated_rows=metadata_updated_rows,
                metadata_coverage=metadata_after,
                status="metadata_undercovered" if metadata_updated_rows > 0 else "failed",
                warnings=warnings,
                primary_source=primary_source,
            )

        primary_rows = rows[rows["adjust_type"] == primary_adjust]
        candidate_coverage = primary_rows["symbol"].nunique() / total_symbols if total_symbols else 0.0
        if candidate_coverage < min_latest_coverage:
            warnings.append(
                f"Refused to write undercovered snapshot: coverage={candidate_coverage:.4f}, "
                f"threshold={min_latest_coverage:.4f}."
            )
            _record_source_audit(
                conn,
                table_name=source_audit_table,
                source=primary_source,
                latest_trade_date=target_trade_date,
                coverage=candidate_coverage,
                fetched_rows=fetched_rows,
                inserted_rows=0,
                status="undercovered",
                message="; ".join(warnings[-3:]),
            )
            conn.commit()
            return ManualHistoryUpdateResult(
                db_path=db_path,
                calendar_trade_date=calendar_trade_date.isoformat(),
                target_trade_date=target_trade_date.isoformat(),
                before_latest_date=before_latest.isoformat() if before_latest else "",
                after_latest_date=before_latest.isoformat() if before_latest else "",
                before_coverage=before_coverage,
                after_coverage=before_coverage,
                fetched_rows=fetched_rows,
                inserted_rows=0,
                metadata_updated_rows=metadata_updated_rows,
                metadata_coverage=metadata_after,
                status="undercovered",
                warnings=warnings,
                primary_source=primary_source,
            )

        table = _safe_identifier(daily_table)
        for adjust_type in adjust_types:
            conn.execute(
                f"DELETE FROM {table} WHERE market = ? AND date = ? AND adjust_type = ?",
                (market, target_trade_date.isoformat(), adjust_type),
            )
        rows.to_sql(daily_table, conn, if_exists="append", index=False)
        _record_source_audit(
            conn,
            table_name=source_audit_table,
            source=primary_source,
            latest_trade_date=target_trade_date,
            coverage=candidate_coverage,
            fetched_rows=fetched_rows,
            inserted_rows=len(rows),
            status="written",
        )
        conn.commit()

        after_latest, after_coverage, _, _ = _latest_stats(
            conn,
            daily_table=daily_table,
            meta_table=meta_table,
            market=market,
            adjust_type=primary_adjust,
        )
        after_staleness = _trade_day_lag(
            conn,
            calendar_table=calendar_table,
            latest_trade_date=after_latest,
            target_trade_date=calendar_trade_date,
        )
        status = "updated" if after_staleness <= max_staleness_days and after_coverage >= min_latest_coverage else "stale"
        if status != "updated":
            warnings.append(
                f"Update written but freshness gate failed: staleness={after_staleness}, "
                f"coverage={after_coverage:.4f}."
            )
        return ManualHistoryUpdateResult(
            db_path=db_path,
            calendar_trade_date=calendar_trade_date.isoformat(),
            target_trade_date=target_trade_date.isoformat(),
            before_latest_date=before_latest.isoformat() if before_latest else "",
            after_latest_date=after_latest.isoformat() if after_latest else "",
            before_coverage=before_coverage,
            after_coverage=after_coverage,
            fetched_rows=fetched_rows,
            inserted_rows=len(rows),
            metadata_updated_rows=metadata_updated_rows,
            metadata_coverage=_metadata_coverage(conn, meta_table=meta_table, market=market),
            status=status,
            warnings=warnings,
            primary_source=primary_source,
        )
