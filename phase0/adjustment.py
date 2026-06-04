from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from phase0.local_history import normalize_cn_symbol


@dataclass(frozen=True)
class AdjustmentAuditResult:
    db_path: Path
    csv_path: Path
    md_path: Path
    verdict: str
    can_build_qfq_asof: bool
    rows: int
    warnings: list[str]


PRICE_FEATURE_COLUMNS = ["mom20", "ma20", "vol20", "breakout20"]


def _safe_identifier(value: str) -> str:
    if not value.replace("_", "").isalnum() or value[:1].isdigit():
        raise ValueError(f"Unsafe SQL identifier: {value}")
    return value


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({_safe_identifier(table)})").fetchall()]


def ensure_adj_factor_table(conn: sqlite3.Connection, table: str = "market_adj_factors") -> None:
    table_name = _safe_identifier(table)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            market TEXT NOT NULL,
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            adj_factor REAL NOT NULL,
            source TEXT,
            updated_at TEXT,
            PRIMARY KEY (market, symbol, date)
        )
        """
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol_date ON {table_name}(market, symbol, date)"
    )


def upsert_adj_factors(
    conn: sqlite3.Connection,
    factors: pd.DataFrame,
    *,
    table: str = "market_adj_factors",
    market: str = "CN",
    source: str = "",
) -> int:
    if factors.empty:
        return 0
    ensure_adj_factor_table(conn, table)
    out = factors.copy()
    if "symbol" not in out.columns:
        if "ts_code" in out.columns:
            out["symbol"] = out["ts_code"].map(normalize_cn_symbol)
        else:
            return 0
    if "date" not in out.columns:
        if "trade_date" in out.columns:
            out["date"] = pd.to_datetime(out["trade_date"], format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
        else:
            return 0
    out["symbol"] = out["symbol"].map(normalize_cn_symbol)
    out["adj_factor"] = pd.to_numeric(out.get("adj_factor"), errors="coerce")
    out = out.dropna(subset=["date", "symbol", "adj_factor"])
    out = out[out["symbol"] != ""].copy()
    if out.empty:
        return 0
    out["market"] = market
    out["source"] = source
    out["updated_at"] = datetime.now().isoformat(timespec="seconds")
    rows = out[["market", "symbol", "date", "adj_factor", "source", "updated_at"]].drop_duplicates(
        ["market", "symbol", "date"]
    )
    table_name = _safe_identifier(table)
    conn.executemany(
        f"""
        INSERT INTO {table_name} (market, symbol, date, adj_factor, source, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(market, symbol, date) DO UPDATE SET
            adj_factor = excluded.adj_factor,
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        list(rows.itertuples(index=False, name=None)),
    )
    return int(len(rows))


def load_bfq_bars(
    db_path: Path,
    symbol: str,
    start: date,
    end: date,
    *,
    table: str = "market_daily_bars",
    market: str = "CN",
) -> pd.DataFrame:
    return _load_bars(db_path, symbol, start, end, adjust_type="bfq", table=table, market=market)


def load_adj_factors(
    db_path: Path,
    symbol: str,
    start: date,
    as_of_date: date,
    *,
    table: str = "market_adj_factors",
    market: str = "CN",
) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame()
    table_name = _safe_identifier(table)
    with sqlite3.connect(db_path) as conn:
        if not _table_exists(conn, table_name):
            return pd.DataFrame()
        df = pd.read_sql_query(
            f"""
            SELECT date, adj_factor
            FROM {table_name}
            WHERE market = ?
              AND symbol = ?
              AND date >= ?
              AND date <= ?
            ORDER BY date
            """,
            conn,
            params=(market, normalize_cn_symbol(symbol), start.isoformat(), as_of_date.isoformat()),
        )
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df["adj_factor"] = pd.to_numeric(df["adj_factor"], errors="coerce")
    return df.dropna(subset=["date", "adj_factor"])


def build_qfq_asof_bars(
    db_path: Path,
    symbol: str,
    start: date,
    end: date,
    as_of_date: date,
    *,
    daily_table: str = "market_daily_bars",
    factor_table: str = "market_adj_factors",
    market: str = "CN",
) -> pd.DataFrame:
    if as_of_date < end:
        end = as_of_date
    bars = load_bfq_bars(db_path, symbol, start, end, table=daily_table, market=market)
    factors = load_adj_factors(db_path, symbol, start, as_of_date, table=factor_table, market=market)
    return compute_qfq_asof(bars, factors, as_of_date)


def compute_qfq_asof(raw_ohlcv: pd.DataFrame, adj_factors: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
    if raw_ohlcv.empty or adj_factors.empty:
        return pd.DataFrame()
    bars = raw_ohlcv.copy()
    factors = adj_factors.copy()
    bars["date"] = pd.to_datetime(bars["date"])
    factors["date"] = pd.to_datetime(factors["date"])
    as_of_ts = pd.Timestamp(as_of_date)
    bars = bars[bars["date"] <= as_of_ts].copy()
    factors = factors[factors["date"] <= as_of_ts].copy()
    if bars.empty or factors.empty:
        return pd.DataFrame()
    as_of_rows = factors[factors["date"] <= as_of_ts].sort_values("date")
    if as_of_rows.empty:
        return pd.DataFrame()
    as_of_factor = float(as_of_rows.iloc[-1]["adj_factor"])
    if as_of_factor == 0:
        return pd.DataFrame()
    merged = bars.merge(factors[["date", "adj_factor"]], on="date", how="left")
    merged["adj_factor"] = merged["adj_factor"].ffill().bfill()
    for col in ["open", "high", "low", "close", "adjusted_close"]:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce") * pd.to_numeric(
                merged["adj_factor"], errors="coerce"
            ) / as_of_factor
    merged["adjust_type"] = "qfq_asof"
    merged["data_source"] = "local_history_sqlite_qfq_asof"
    return merged.drop(columns=["adj_factor"])


def compare_qfq_current_vs_qfq_asof(
    db_path: Path,
    symbols: list[str],
    start: date,
    end: date,
    as_of_date: date,
    *,
    daily_table: str = "market_daily_bars",
    factor_table: str = "market_adj_factors",
    market: str = "CN",
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        qfq = _load_bars(db_path, symbol, start, end, adjust_type="qfq", table=daily_table, market=market)
        asof = build_qfq_asof_bars(
            db_path,
            symbol,
            start,
            end,
            as_of_date,
            daily_table=daily_table,
            factor_table=factor_table,
            market=market,
        )
        if qfq.empty or asof.empty:
            rows.append({"symbol": normalize_cn_symbol(symbol), "status": "missing_comparison_data"})
            continue
        qfq_features = _price_feature_frame(qfq)
        asof_features = _price_feature_frame(asof)
        merged = qfq_features.merge(asof_features, on="date", suffixes=("_qfq_current", "_qfq_asof"))
        if merged.empty:
            rows.append({"symbol": normalize_cn_symbol(symbol), "status": "missing_overlap"})
            continue
        diff = (merged["close_qfq_current"] - merged["close_qfq_asof"]).abs()
        base = merged["close_qfq_asof"].abs().replace(0, pd.NA)
        max_idx = diff.idxmax()
        row: dict[str, Any] = {
            "symbol": normalize_cn_symbol(symbol),
            "status": "ok",
            "rows": int(len(merged)),
            "max_abs_close_diff": float(diff.max()),
            "max_abs_close_diff_ratio": float((diff / base).max()),
            "max_close_diff_date": str(pd.Timestamp(merged.loc[max_idx, "date"]).date()) if pd.notna(max_idx) else "",
        }
        for feature in PRICE_FEATURE_COLUMNS:
            left = f"{feature}_qfq_current"
            right = f"{feature}_qfq_asof"
            if left not in merged.columns or right not in merged.columns:
                continue
            feature_diff = (pd.to_numeric(merged[left], errors="coerce") - pd.to_numeric(merged[right], errors="coerce")).abs()
            row[f"max_abs_{feature}_diff"] = float(feature_diff.max(skipna=True) or 0.0)
        rows.append(
            row
        )
    return pd.DataFrame(rows)


def _price_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df[["date", "close", "high"]].copy() if "high" in df.columns else df[["date", "close"]].copy()
    out["date"] = pd.to_datetime(out["date"])
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    if "high" in out.columns:
        out["high"] = pd.to_numeric(out["high"], errors="coerce")
    out["mom20"] = out["close"].pct_change(20)
    out["ma20"] = out["close"].rolling(20).mean()
    out["vol20"] = out["close"].pct_change().rolling(20).std() * (252**0.5)
    if "high" in out.columns:
        out["breakout20"] = (out["close"] > out["high"].rolling(20).max().shift(1)).astype(float)
    else:
        out["breakout20"] = pd.NA
    return out[["date", "close", *PRICE_FEATURE_COLUMNS]]


def run_adjustment_audit(
    *,
    config: dict[str, Any],
    root: Path,
    output_csv: Path | None = None,
    output_md: Path | None = None,
) -> AdjustmentAuditResult:
    local_cfg = config.get("local_history", {})
    db_path = Path(local_cfg.get("path", "data/manual_history/a_share_history.sqlite"))
    if not db_path.is_absolute():
        db_path = root / db_path
    daily_table = str(local_cfg.get("daily_table", "market_daily_bars"))
    factor_table = str(local_cfg.get("adj_factor_table", "market_adj_factors"))
    dividend_table = str(local_cfg.get("dividend_table", "market_dividends"))
    market = str(local_cfg.get("market", "CN"))
    current_adjust = str(local_cfg.get("adjust_type", "qfq"))
    backtest_adjust = str(local_cfg.get("price_adjustment_for_backtest", f"{current_adjust}_current"))
    output_csv = output_csv or root / "reports" / "price_adjustment_audit.csv"
    output_md = output_md or root / "reports" / "price_adjustment_audit.md"

    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    comparison_rows = pd.DataFrame()
    can_build = False
    factor_coverage_ok = False
    if not db_path.exists():
        warnings.append(f"local history database not found: {db_path}")
        rows.append({"check": "database_exists", "status": "FAIL", "detail": str(db_path)})
    else:
        with sqlite3.connect(db_path) as conn:
            daily_exists = _table_exists(conn, daily_table)
            factor_exists = _table_exists(conn, factor_table)
            dividend_exists = _table_exists(conn, dividend_table)
            rows.append({"check": "daily_table_exists", "status": "PASS" if daily_exists else "FAIL", "detail": daily_table})
            rows.append({"check": "adj_factor_table_exists", "status": "PASS" if factor_exists else "FAIL", "detail": factor_table})
            rows.append({"check": "dividend_table_exists", "status": "PASS" if dividend_exists else "WARN", "detail": dividend_table})
            if daily_exists:
                cols = _table_columns(conn, daily_table)
                has_adjust_type = "adjust_type" in cols
                rows.append(
                    {
                        "check": "daily_table_columns",
                        "status": "PASS" if has_adjust_type else "WARN",
                        "detail": ",".join(cols),
                    }
                )
                adjust_counts = pd.read_sql_query(
                    f"""
                    SELECT adjust_type, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS symbols,
                           MIN(date) AS min_date, MAX(date) AS max_date
                    FROM {_safe_identifier(daily_table)}
                    WHERE market = ?
                    GROUP BY adjust_type
                    ORDER BY adjust_type
                    """,
                    conn,
                    params=(market,),
                )
                for _, row in adjust_counts.iterrows():
                    rows.append(
                        {
                            "check": f"daily_adjust_type_{row['adjust_type']}",
                            "status": "PASS",
                            "detail": f"rows={int(row['rows'])}, symbols={int(row['symbols'])}, range={row['min_date']}..{row['max_date']}",
                        }
                    )
                adjust_types = set(adjust_counts["adjust_type"].astype(str)) if not adjust_counts.empty else set()
                has_bfq = "bfq" in adjust_types
                has_qfq = "qfq" in adjust_types
                bfq_stats = adjust_counts[adjust_counts["adjust_type"].astype(str) == "bfq"]
                bfq_min_date = str(bfq_stats["min_date"].iloc[0]) if not bfq_stats.empty else ""
                bfq_max_date = str(bfq_stats["max_date"].iloc[0]) if not bfq_stats.empty else ""
                rows.append({"check": "has_bfq_raw", "status": "PASS" if has_bfq else "FAIL", "detail": str(has_bfq)})
                rows.append({"check": "has_qfq_current", "status": "PASS" if has_qfq else "FAIL", "detail": str(has_qfq)})
            else:
                has_bfq = False
                has_qfq = False
                bfq_min_date = ""
                bfq_max_date = ""
            factor_rows = 0
            if factor_exists:
                factor_cols = _table_columns(conn, factor_table)
                factor_summary = conn.execute(
                    f"""
                    SELECT COUNT(*) AS rows, COUNT(DISTINCT symbol) AS symbols,
                           MIN(date) AS min_date, MAX(date) AS max_date
                    FROM {_safe_identifier(factor_table)}
                    WHERE market = ?
                    """,
                    (market,),
                ).fetchone()
                factor_rows = int(factor_summary[0] or 0)
                factor_symbols = int(factor_summary[1] or 0)
                factor_min_date = str(factor_summary[2] or "")
                factor_max_date = str(factor_summary[3] or "")
                factor_coverage_ok = bool(
                    factor_rows > 0
                    and bfq_min_date
                    and bfq_max_date
                    and factor_min_date <= bfq_min_date
                    and factor_max_date >= bfq_max_date
                )
                rows.append({"check": "adj_factor_columns", "status": "PASS", "detail": ",".join(factor_cols)})
                rows.append(
                    {
                        "check": "adj_factor_rows",
                        "status": "PASS" if factor_rows else "FAIL",
                        "detail": f"rows={factor_rows}, symbols={factor_symbols}, range={factor_min_date}..{factor_max_date}",
                    }
                )
                rows.append(
                    {
                        "check": "adj_factor_history_coverage",
                        "status": "PASS" if factor_coverage_ok else "FAIL",
                        "detail": f"bfq_range={bfq_min_date}..{bfq_max_date}, factor_range={factor_min_date}..{factor_max_date}",
                    }
                )
            if dividend_exists:
                dividend_rows = int(
                    conn.execute(f"SELECT COUNT(*) FROM {_safe_identifier(dividend_table)} WHERE market = ?", (market,)).fetchone()[0]
                )
                rows.append({"check": "dividend_rows", "status": "PASS" if dividend_rows else "WARN", "detail": str(dividend_rows)})
            can_build = bool(has_bfq and factor_exists and factor_rows > 0 and factor_coverage_ok)
            rows.append(
                {
                    "check": "can_build_qfq_asof",
                    "status": "PASS" if can_build else "FAIL",
                    "detail": "ok" if can_build else "cannot_build_qfq_asof_or_history_factor_incomplete",
                }
            )
            rows.append({"check": "phase0_current_adjust_type", "status": "INFO", "detail": current_adjust})
            rows.append({"check": "phase0_backtest_price_adjustment", "status": "INFO", "detail": backtest_adjust})
            if can_build and bfq_min_date and bfq_max_date:
                audit_cfg = local_cfg.get("price_adjustment_audit", {})
                comparison_as_of = _resolve_comparison_as_of(conn, bfq_min_date, bfq_max_date)
                comparison_start = max(
                    pd.Timestamp(bfq_min_date).date(),
                    comparison_as_of - pd.Timedelta(days=365),
                )
                sample_symbols = _sample_adjustment_comparison_symbols(
                    conn,
                    factor_table=factor_table,
                    market=market,
                    as_of_date=comparison_as_of,
                    latest_date=pd.Timestamp(bfq_max_date).date(),
                    sample_size=int(audit_cfg.get("sample_size", 12)),
                )
                if sample_symbols:
                    comparison_rows = compare_qfq_current_vs_qfq_asof(
                        db_path,
                        sample_symbols,
                        pd.Timestamp(comparison_start).date(),
                        comparison_as_of,
                        comparison_as_of,
                        daily_table=daily_table,
                        factor_table=factor_table,
                        market=market,
                    )
                    ok = comparison_rows[comparison_rows.get("status", "") == "ok"] if not comparison_rows.empty else pd.DataFrame()
                    max_ratio = float(pd.to_numeric(ok.get("max_abs_close_diff_ratio", pd.Series(dtype=float)), errors="coerce").max() or 0.0)
                    max_mom20 = float(pd.to_numeric(ok.get("max_abs_mom20_diff", pd.Series(dtype=float)), errors="coerce").max() or 0.0)
                    rows.append(
                        {
                            "check": "qfq_asof_comparison_sample",
                            "status": "PASS" if not ok.empty else "WARN",
                            "detail": f"as_of={comparison_as_of.isoformat()}, symbols={len(sample_symbols)}, ok={len(ok)}",
                        }
                    )
                    rows.append(
                        {
                            "check": "qfq_asof_comparison_max_close_diff_ratio",
                            "status": "INFO",
                            "detail": f"{max_ratio:.8f}",
                        }
                    )
                    rows.append(
                        {
                            "check": "qfq_asof_comparison_max_mom20_diff",
                            "status": "INFO",
                            "detail": f"{max_mom20:.8f}",
                        }
                    )
                else:
                    rows.append(
                        {
                            "check": "qfq_asof_comparison_sample",
                            "status": "WARN",
                            "detail": f"no sample symbols found for as_of={comparison_as_of.isoformat()}",
                        }
                    )
    if not can_build:
        warnings.append("cannot_build_qfq_asof: bfq raw bars or complete market_adj_factors history are missing")
    if backtest_adjust in {"qfq", "qfq_current"} and not can_build:
        warnings.append("current backtest price adjustment is not strict point-in-time until qfq_asof audit passes")

    out = pd.DataFrame(rows)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_csv, index=False)
    _write_adjustment_audit_md(
        output_md,
        out,
        db_path=db_path,
        can_build=can_build,
        warnings=warnings,
        comparison_rows=comparison_rows,
    )
    verdict = "PASS" if can_build else "WARN"
    return AdjustmentAuditResult(
        db_path=db_path,
        csv_path=output_csv,
        md_path=output_md,
        verdict=verdict,
        can_build_qfq_asof=can_build,
        rows=int(len(out)),
        warnings=warnings,
    )


def _load_bars(
    db_path: Path,
    symbol: str,
    start: date,
    end: date,
    *,
    adjust_type: str,
    table: str,
    market: str,
) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame()
    table_name = _safe_identifier(table)
    with sqlite3.connect(db_path) as conn:
        if not _table_exists(conn, table_name):
            return pd.DataFrame()
        df = pd.read_sql_query(
            f"""
            SELECT date, open, high, low, close, volume, amount, adjusted_close,
                   change_pct, change_amount, amplitude, turnover_rate, adjust_type
            FROM {table_name}
            WHERE market = ?
              AND symbol = ?
              AND date >= ?
              AND date <= ?
              AND adjust_type = ?
            ORDER BY date
            """,
            conn,
            params=(market, normalize_cn_symbol(symbol), start.isoformat(), end.isoformat(), adjust_type),
        )
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df["market"] = market
    df["symbol"] = normalize_cn_symbol(symbol)
    df["data_source"] = f"local_history_sqlite_{adjust_type}"
    return df


def _resolve_comparison_as_of(conn: sqlite3.Connection, bfq_min_date: str, bfq_max_date: str) -> date:
    min_ts = pd.Timestamp(bfq_min_date)
    max_ts = pd.Timestamp(bfq_max_date)
    desired = max_ts - pd.Timedelta(days=365 * 2)
    if desired <= min_ts:
        desired = min_ts + (max_ts - min_ts) / 2
    row = conn.execute(
        """
        SELECT MAX(date)
        FROM trading_calendar
        WHERE is_open = 1
          AND date <= ?
        """,
        (pd.Timestamp(desired).date().isoformat(),),
    ).fetchone()
    value = str(row[0]) if row and row[0] else pd.Timestamp(desired).date().isoformat()
    return pd.Timestamp(value).date()


def _sample_adjustment_comparison_symbols(
    conn: sqlite3.Connection,
    *,
    factor_table: str,
    market: str,
    as_of_date: date,
    latest_date: date,
    sample_size: int,
) -> list[str]:
    table_name = _safe_identifier(factor_table)
    half = max(1, int(sample_size) // 2)
    query = f"""
        WITH before_date AS (
            SELECT symbol, MAX(date) AS date
            FROM {table_name}
            WHERE market = ? AND date <= ?
            GROUP BY symbol
        ),
        latest_date AS (
            SELECT symbol, MAX(date) AS date
            FROM {table_name}
            WHERE market = ? AND date <= ?
            GROUP BY symbol
        ),
        before_factor AS (
            SELECT f.symbol, f.adj_factor
            FROM {table_name} f
            JOIN before_date b ON f.symbol = b.symbol AND f.date = b.date
            WHERE f.market = ?
        ),
        latest_factor AS (
            SELECT f.symbol, f.adj_factor
            FROM {table_name} f
            JOIN latest_date l ON f.symbol = l.symbol AND f.date = l.date
            WHERE f.market = ?
        )
        SELECT b.symbol,
               ABS(l.adj_factor / NULLIF(b.adj_factor, 0) - 1.0) AS future_factor_change
        FROM before_factor b
        JOIN latest_factor l ON b.symbol = l.symbol
        WHERE b.adj_factor > 0 AND l.adj_factor > 0
        ORDER BY future_factor_change DESC, b.symbol
        LIMIT ?
    """
    changed = [
        str(row[0])
        for row in conn.execute(
            query,
            (market, as_of_date.isoformat(), market, latest_date.isoformat(), market, market, half),
        ).fetchall()
    ]
    stable_query = query.replace("ORDER BY future_factor_change DESC, b.symbol", "ORDER BY future_factor_change ASC, b.symbol")
    stable = [
        str(row[0])
        for row in conn.execute(
            stable_query,
            (market, as_of_date.isoformat(), market, latest_date.isoformat(), market, market, max(1, int(sample_size) - len(changed))),
        ).fetchall()
    ]
    out: list[str] = []
    for symbol in [*changed, *stable]:
        norm = normalize_cn_symbol(symbol)
        if norm and norm not in out:
            out.append(norm)
    return out[: max(1, int(sample_size))]


def _write_adjustment_audit_md(
    path: Path,
    rows: pd.DataFrame,
    *,
    db_path: Path,
    can_build: bool,
    warnings: list[str],
    comparison_rows: pd.DataFrame | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# A 股历史 as-of 前复权审计报告",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"- Database: `{db_path}`",
        f"- Can build `qfq_asof`: `{can_build}`",
        "",
        "## 结论",
        "",
    ]
    if can_build:
        lines.append("- 当前本地库具备未复权价格和复权因子，可继续实现或运行 `qfq_asof` 对照。")
    else:
        lines.append("- 当前本地库尚不能构造严格 `qfq_asof`。在审计通过前，`qfq_current` 结果不能解释为严格 point-in-time 价格结果。")
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend([f"- {item}" for item in warnings])
    lines.extend(["", "## Checks", "", "| check | status | detail |", "| --- | --- | --- |"])
    for _, row in rows.iterrows():
        detail = str(row.get("detail", "")).replace("|", "\\|")
        lines.append(f"| {row.get('check', '')} | {row.get('status', '')} | {detail} |")
    if comparison_rows is not None and not comparison_rows.empty:
        show = comparison_rows.copy()
        numeric_cols = [
            "max_abs_close_diff",
            "max_abs_close_diff_ratio",
            "max_abs_mom20_diff",
            "max_abs_ma20_diff",
            "max_abs_vol20_diff",
            "max_abs_breakout20_diff",
        ]
        for col in numeric_cols:
            if col in show.columns:
                show[col] = pd.to_numeric(show[col], errors="coerce").map(lambda x: f"{x:.8f}" if pd.notna(x) else "")
        keep = [
            col
            for col in [
                "symbol",
                "status",
                "rows",
                "max_close_diff_date",
                "max_abs_close_diff",
                "max_abs_close_diff_ratio",
                "max_abs_mom20_diff",
                "max_abs_ma20_diff",
                "max_abs_vol20_diff",
                "max_abs_breakout20_diff",
            ]
            if col in show.columns
        ]
        lines.extend(["", "## qfq_current / qfq_asof 差异样例", ""])
        lines.append(show[keep].to_markdown(index=False))
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
