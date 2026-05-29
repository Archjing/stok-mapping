from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import pandas as pd

from phase0.env import prepare_imports
from phase0.local_history import normalize_cn_symbol
from phase0.throttle import configure_akshare_throttle, fetch_with_akshare_retries

prepare_imports()

import akshare as ak  # noqa: E402


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
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return self.status in {"up_to_date", "updated", "check_ok"}


def _safe_identifier(value: str) -> str:
    if not value or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Unsafe SQL identifier: {value}")
    return value


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
    market: str,
    adjust_type: str,
    date_override: date | None = None,
) -> tuple[date | None, float, int, int]:
    table = _safe_identifier(daily_table)
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
            COUNT(DISTINCT symbol) AS total_symbols
        FROM {table}
        WHERE market = ?
          AND adjust_type = ?
        """,
        conn,
        params=(coverage_date.isoformat(), market, adjust_type),
    ).iloc[0]
    latest_symbols = int(row["latest_symbols"] or 0)
    total_symbols = int(row["total_symbols"] or 0)
    coverage = latest_symbols / total_symbols if total_symbols else 0.0
    return latest_date, float(coverage), latest_symbols, total_symbols


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


def _normalize_spot_metadata(raw: pd.DataFrame, *, markets: set[str], max_symbols: int) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    code = _series_or_empty(raw, ["代码", "code", "symbol"])
    meta = pd.DataFrame(
        {
            "market": "CN",
            "symbol": code.map(_normalize_spot_symbol),
            "name": _series_or_empty(raw, ["名称", "name"]),
            "market_cap": _clean_numeric(_series_or_empty(raw, ["总市值", "market_cap"])),
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


def _to_sql_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    return value


def _update_stock_metadata(conn: sqlite3.Connection, *, meta_table: str, rows: pd.DataFrame) -> int:
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
    return int(cursor.rowcount or 0)


def _empty_result(
    *,
    db_path: Path,
    calendar_trade_date: date,
    target_trade_date: date,
    before_latest: date | None,
    before_coverage: float,
    status: str,
    warnings: list[str],
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
        status=status,
        warnings=warnings,
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
    calendar_table = str(local_cfg.get("calendar_table", "trading_calendar"))
    market = str(local_cfg.get("market", "CN"))
    adjust_types = [str(item) for item in update_cfg.get("adjust_types", ["qfq"])]
    primary_adjust = adjust_types[0] if adjust_types else str(local_cfg.get("adjust_type", "qfq"))
    markets = {str(item) for item in update_cfg.get("markets", ["SH", "SZ"])}
    max_symbols = int(update_cfg.get("max_symbols", 0))
    max_staleness_days = int(update_cfg.get("max_staleness_days", local_cfg.get("max_snapshot_staleness_days", 1)))
    min_latest_coverage = float(update_cfg.get("min_latest_coverage", local_cfg.get("min_snapshot_coverage", 0.80)))
    min_run_time = _parse_run_time(update_cfg.get("min_run_time", "16:00"))

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
        calendar_trade_date, target_trade_date, before_min_run_time = _resolve_trade_dates(
            conn,
            calendar_table=calendar_table,
            min_run_time=min_run_time,
        )
        before_latest, before_coverage, _, _ = _latest_stats(
            conn,
            daily_table=daily_table,
            market=market,
            adjust_type=primary_adjust,
        )
        before_target_coverage = _latest_stats(
            conn,
            daily_table=daily_table,
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

        if check_only:
            status = "check_ok" if freshness_ok else "stale"
            check_warnings: list[str] = []
            if status != "check_ok":
                check_warnings.append("local history is stale or undercovered")
            return _empty_result(
                db_path=db_path,
                calendar_trade_date=calendar_trade_date,
                target_trade_date=target_trade_date,
                before_latest=before_latest,
                before_coverage=before_coverage,
                status=status,
                warnings=check_warnings,
            )

        if target_is_covered and freshness_ok:
            return _empty_result(
                db_path=db_path,
                calendar_trade_date=calendar_trade_date,
                target_trade_date=target_trade_date,
                before_latest=before_latest,
                before_coverage=before_coverage,
                status="up_to_date",
                warnings=[],
            )

        if before_min_run_time:
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
                status="too_early",
                warnings=warnings,
            )

        raw = fetch_with_akshare_retries(lambda: ak.stock_zh_a_spot_em())
        fetched_rows = len(raw) if raw is not None else 0
        rows = _normalize_spot_snapshot(
            raw,
            trade_date=target_trade_date,
            adjust_types=adjust_types,
            markets=markets,
            max_symbols=max_symbols,
        )
        if rows.empty:
            warnings.append("AkShare spot snapshot returned no usable rows.")
            after_latest, after_coverage, _, _ = _latest_stats(
                conn,
                daily_table=daily_table,
                market=market,
                adjust_type=primary_adjust,
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
                inserted_rows=0,
                status="failed",
                warnings=warnings,
            )

        primary_rows = rows[rows["adjust_type"] == primary_adjust]
        _, _, _, total_symbols = _latest_stats(
            conn,
            daily_table=daily_table,
            market=market,
            adjust_type=primary_adjust,
        )
        candidate_coverage = primary_rows["symbol"].nunique() / total_symbols if total_symbols else 0.0
        if candidate_coverage < min_latest_coverage:
            warnings.append(
                f"Refused to write undercovered snapshot: coverage={candidate_coverage:.4f}, "
                f"threshold={min_latest_coverage:.4f}."
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
                status="undercovered",
                warnings=warnings,
            )

        table = _safe_identifier(daily_table)
        for adjust_type in adjust_types:
            conn.execute(
                f"DELETE FROM {table} WHERE market = ? AND date = ? AND adjust_type = ?",
                (market, target_trade_date.isoformat(), adjust_type),
            )
        rows.to_sql(daily_table, conn, if_exists="append", index=False)
        meta_rows = _normalize_spot_metadata(raw, markets=markets, max_symbols=max_symbols)
        try:
            _update_stock_metadata(conn, meta_table=meta_table, rows=meta_rows)
        except sqlite3.Error as exc:
            warnings.append(f"Daily bars updated, but stock metadata update failed: {exc}")
        conn.commit()

        after_latest, after_coverage, _, _ = _latest_stats(
            conn,
            daily_table=daily_table,
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
            status=status,
            warnings=warnings,
        )
