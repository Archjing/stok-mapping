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
        merged = qfq[["date", "close"]].merge(asof[["date", "close"]], on="date", suffixes=("_qfq_current", "_qfq_asof"))
        if merged.empty:
            rows.append({"symbol": normalize_cn_symbol(symbol), "status": "missing_overlap"})
            continue
        diff = (merged["close_qfq_current"] - merged["close_qfq_asof"]).abs()
        base = merged["close_qfq_asof"].abs().replace(0, pd.NA)
        rows.append(
            {
                "symbol": normalize_cn_symbol(symbol),
                "status": "ok",
                "rows": int(len(merged)),
                "max_abs_close_diff": float(diff.max()),
                "max_abs_close_diff_ratio": float((diff / base).max()),
            }
        )
    return pd.DataFrame(rows)


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
    market = str(local_cfg.get("market", "CN"))
    current_adjust = str(local_cfg.get("adjust_type", "qfq"))
    backtest_adjust = str(local_cfg.get("price_adjustment_for_backtest", f"{current_adjust}_current"))
    output_csv = output_csv or root / "reports" / "price_adjustment_audit.csv"
    output_md = output_md or root / "reports" / "price_adjustment_audit.md"

    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    can_build = False
    if not db_path.exists():
        warnings.append(f"local history database not found: {db_path}")
        rows.append({"check": "database_exists", "status": "FAIL", "detail": str(db_path)})
    else:
        with sqlite3.connect(db_path) as conn:
            daily_exists = _table_exists(conn, daily_table)
            factor_exists = _table_exists(conn, factor_table)
            rows.append({"check": "daily_table_exists", "status": "PASS" if daily_exists else "FAIL", "detail": daily_table})
            rows.append({"check": "adj_factor_table_exists", "status": "PASS" if factor_exists else "FAIL", "detail": factor_table})
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
                rows.append({"check": "has_bfq_raw", "status": "PASS" if has_bfq else "FAIL", "detail": str(has_bfq)})
                rows.append({"check": "has_qfq_current", "status": "PASS" if has_qfq else "FAIL", "detail": str(has_qfq)})
            else:
                has_bfq = False
                has_qfq = False
            factor_rows = 0
            if factor_exists:
                factor_cols = _table_columns(conn, factor_table)
                factor_rows = int(
                    conn.execute(f"SELECT COUNT(*) FROM {_safe_identifier(factor_table)} WHERE market = ?", (market,)).fetchone()[0]
                )
                rows.append({"check": "adj_factor_columns", "status": "PASS", "detail": ",".join(factor_cols)})
                rows.append({"check": "adj_factor_rows", "status": "PASS" if factor_rows else "FAIL", "detail": str(factor_rows)})
            can_build = bool(has_bfq and factor_exists and factor_rows > 0)
            rows.append(
                {
                    "check": "can_build_qfq_asof",
                    "status": "PASS" if can_build else "FAIL",
                    "detail": "ok" if can_build else "cannot_build_qfq_asof",
                }
            )
            rows.append({"check": "phase0_current_adjust_type", "status": "INFO", "detail": current_adjust})
            rows.append({"check": "phase0_backtest_price_adjustment", "status": "INFO", "detail": backtest_adjust})
    if not can_build:
        warnings.append("cannot_build_qfq_asof: bfq raw bars or market_adj_factors are missing")
    if backtest_adjust in {"qfq", "qfq_current"} and not can_build:
        warnings.append("current backtest price adjustment is not strict point-in-time until qfq_asof audit passes")

    out = pd.DataFrame(rows)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_csv, index=False)
    _write_adjustment_audit_md(output_md, out, db_path=db_path, can_build=can_build, warnings=warnings)
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


def _write_adjustment_audit_md(
    path: Path,
    rows: pd.DataFrame,
    *,
    db_path: Path,
    can_build: bool,
    warnings: list[str],
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
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
