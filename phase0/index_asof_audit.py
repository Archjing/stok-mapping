from __future__ import annotations

import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from phase0.reporting.paths import report_path


CONSTITUENT_TABLE_CANDIDATES = [
    "cn_index_constituents_asof",
    "market_index_constituents_asof",
    "index_constituents_asof",
    "index_constituents",
    "market_index_constituents",
]

WEIGHT_TABLE_CANDIDATES = [
    "cn_index_weights_asof",
    "market_index_weights_asof",
    "index_weights_asof",
    "index_weights",
    "market_index_weights",
]

REQUIRED_CONSTITUENT_COLUMNS = ["index_code", "trade_date", "symbol"]
REQUIRED_WEIGHT_COLUMNS = ["index_code", "trade_date", "symbol", "weight"]
ASOF_COLUMNS = ["asof_time", "effective_date", "ingested_at", "source"]


@dataclass(frozen=True)
class IndexAsofAuditResult:
    benchmark_symbol: str
    db_path: Path
    capability_csv_path: Path
    fold_coverage_csv_path: Path
    report_md_path: Path
    run_log_md_path: Path
    constituent_status: str
    weight_status: str
    fold_rows: int


def _safe_identifier(value: str) -> str:
    if not value.replace("_", "").isalnum() or value[0].isdigit():
        raise ValueError(f"Unsafe SQL identifier: {value}")
    return value


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')").fetchall()
    return {str(row[0]) for row in rows}


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    safe = _safe_identifier(table)
    return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({safe})").fetchall()]


def _count_rows(conn: sqlite3.Connection, table: str) -> int:
    safe = _safe_identifier(table)
    return int(conn.execute(f"SELECT COUNT(*) FROM {safe}").fetchone()[0])


def _symbol_predicate(columns: list[str]) -> str:
    if "index_code" in columns:
        return "index_code = ?"
    if "symbol" in columns:
        return "symbol = ?"
    if "ts_code" in columns:
        return "ts_code = ?"
    return ""


def _date_column(columns: list[str]) -> str | None:
    for col in ["trade_date", "date", "cal_date"]:
        if col in columns:
            return col
    return None


def _find_table(conn: sqlite3.Connection, candidates: list[str]) -> str | None:
    existing = _table_names(conn)
    for table in candidates:
        if table in existing:
            return table
    return None


def _status_for_table(
    *,
    table: str | None,
    columns: list[str],
    required_columns: list[str],
    row_count: int,
) -> str:
    if table is None:
        return "missing_table"
    missing = [col for col in required_columns if col not in columns]
    if missing:
        return "missing_required_columns"
    if row_count <= 0:
        return "empty"
    return "available"


def _table_capability_row(
    *,
    conn: sqlite3.Connection,
    label: str,
    table: str | None,
    benchmark_symbol: str,
    required_columns: list[str],
) -> dict[str, Any]:
    if table is None:
        return {
            "artifact": label,
            "status": "not_available",
            "table": "",
            "rows": 0,
            "benchmark_rows": 0,
            "min_trade_date": "",
            "max_trade_date": "",
            "coverage_ratio": "",
            "missing_open_days": "",
            "latest_lag_days": "",
            "close_non_null_ratio": "",
            "volume_non_null_ratio": "",
            "amount_non_null_ratio": "",
            "required_columns_present": False,
            "missing_required_columns": ",".join(required_columns),
            "asof_columns_present": "",
            "asof_status": "missing",
            "note": "no local as-of constituent/weight table found in sqlite schema",
        }

    columns = _table_columns(conn, table)
    row_count = _count_rows(conn, table)
    missing = [col for col in required_columns if col not in columns]
    asof_present = [col for col in ASOF_COLUMNS if col in columns]
    status = _status_for_table(table=table, columns=columns, required_columns=required_columns, row_count=row_count)
    predicate = _symbol_predicate(columns)
    date_col = _date_column(columns)
    benchmark_rows = 0
    min_trade_date = ""
    max_trade_date = ""
    if predicate and date_col and row_count > 0:
        safe = _safe_identifier(table)
        rows = conn.execute(
            f"SELECT COUNT(*), MIN({date_col}), MAX({date_col}) FROM {safe} WHERE {predicate}",
            (benchmark_symbol,),
        ).fetchone()
        benchmark_rows = int(rows[0] or 0)
        min_trade_date = str(rows[1] or "")
        max_trade_date = str(rows[2] or "")
    note = "available for audit" if status == "available" else "table exists but cannot pass minimum as-of audit"
    if status == "missing_required_columns":
        note = "required columns missing: " + ",".join(missing)
    if status == "empty":
        note = "table exists but has no rows"
    return {
        "artifact": label,
        "status": status,
        "table": table,
        "rows": row_count,
        "benchmark_rows": benchmark_rows,
        "min_trade_date": min_trade_date,
        "max_trade_date": max_trade_date,
        "coverage_ratio": "",
        "missing_open_days": "",
        "latest_lag_days": "",
        "close_non_null_ratio": "",
        "volume_non_null_ratio": "",
        "amount_non_null_ratio": "",
        "required_columns_present": not missing,
        "missing_required_columns": ",".join(missing),
        "asof_columns_present": ",".join(asof_present),
        "asof_status": "available" if any(col in columns for col in ["asof_time", "effective_date"]) else "missing",
        "note": note,
    }


def _benchmark_metadata_row(conn: sqlite3.Connection, *, meta_table: str, benchmark_symbol: str) -> dict[str, Any]:
    existing = _table_names(conn)
    if meta_table not in existing:
        return {
            "artifact": "benchmark_index_metadata",
            "status": "missing_table",
            "table": meta_table,
            "rows": 0,
            "benchmark_rows": 0,
            "min_trade_date": "",
            "max_trade_date": "",
            "coverage_ratio": "",
            "missing_open_days": "",
            "latest_lag_days": "",
            "close_non_null_ratio": "",
            "volume_non_null_ratio": "",
            "amount_non_null_ratio": "",
            "required_columns_present": False,
            "missing_required_columns": "symbol,name",
            "asof_columns_present": "",
            "asof_status": "not_applicable",
            "note": "benchmark index metadata table is missing",
        }
    columns = _table_columns(conn, meta_table)
    missing = [col for col in ["symbol", "name"] if col not in columns]
    safe = _safe_identifier(meta_table)
    row_count = _count_rows(conn, meta_table)
    benchmark_rows = 0
    list_date = ""
    if not missing:
        date_expr = "MIN(list_date), MAX(list_date)" if "list_date" in columns else "'',''"
        row = conn.execute(
            f"SELECT COUNT(*), {date_expr} FROM {safe} WHERE symbol = ?",
            (benchmark_symbol,),
        ).fetchone()
        benchmark_rows = int(row[0] or 0)
        list_date = str(row[1] or row[2] or "")
    status = "available" if benchmark_rows > 0 and not missing else "not_available"
    return {
        "artifact": "benchmark_index_metadata",
        "status": status,
        "table": meta_table,
        "rows": row_count,
        "benchmark_rows": benchmark_rows,
        "min_trade_date": list_date,
        "max_trade_date": list_date,
        "coverage_ratio": "",
        "missing_open_days": "",
        "latest_lag_days": "",
        "close_non_null_ratio": "",
        "volume_non_null_ratio": "",
        "amount_non_null_ratio": "",
        "required_columns_present": not missing,
        "missing_required_columns": ",".join(missing),
        "asof_columns_present": "",
        "asof_status": "not_applicable",
        "note": "index metadata identifies the benchmark but does not provide constituents",
    }


def _calendar_exchange_for_symbol(symbol: str) -> str:
    if symbol.upper().startswith("SH."):
        return "SSE"
    if symbol.upper().startswith("SZ."):
        return "SZSE"
    return ""


def _index_price_row(conn: sqlite3.Connection, *, index_table: str, benchmark_symbol: str) -> dict[str, Any]:
    existing = _table_names(conn)
    if index_table not in existing:
        return {
            "artifact": "benchmark_index_price",
            "status": "missing_table",
            "table": index_table,
            "rows": 0,
            "benchmark_rows": 0,
            "min_trade_date": "",
            "max_trade_date": "",
            "coverage_ratio": "",
            "missing_open_days": "",
            "latest_lag_days": "",
            "close_non_null_ratio": "",
            "volume_non_null_ratio": "",
            "amount_non_null_ratio": "",
            "required_columns_present": False,
            "missing_required_columns": "symbol,date,close",
            "asof_columns_present": "",
            "asof_status": "not_applicable",
            "note": "benchmark index price table is missing",
        }
    columns = _table_columns(conn, index_table)
    missing = [col for col in ["symbol", "date", "close"] if col not in columns]
    safe = _safe_identifier(index_table)
    row_count = _count_rows(conn, index_table)
    benchmark_rows = 0
    min_date = ""
    max_date = ""
    if not missing:
        volume_expr = "AVG(CASE WHEN volume IS NOT NULL THEN 1.0 ELSE 0.0 END)" if "volume" in columns else "NULL"
        amount_expr = "AVG(CASE WHEN amount IS NOT NULL THEN 1.0 ELSE 0.0 END)" if "amount" in columns else "NULL"
        rows = conn.execute(
            f"""
            SELECT
                COUNT(*),
                MIN(date),
                MAX(date),
                AVG(CASE WHEN close IS NOT NULL THEN 1.0 ELSE 0.0 END),
                {volume_expr},
                {amount_expr}
            FROM {safe}
            WHERE symbol = ?
            """,
            (benchmark_symbol,),
        ).fetchone()
        benchmark_rows = int(rows[0] or 0)
        min_date = str(rows[1] or "")
        max_date = str(rows[2] or "")
        close_ratio = float(rows[3] or 0.0)
        volume_ratio = float(rows[4] or 0.0)
        amount_ratio = float(rows[5] or 0.0)
    else:
        close_ratio = 0.0
        volume_ratio = 0.0
        amount_ratio = 0.0
    latest_lag_days = ""
    if max_date:
        try:
            latest_lag_days = str((pd.Timestamp.today().normalize() - pd.to_datetime(max_date)).days)
        except Exception:
            latest_lag_days = ""
    status = "available" if benchmark_rows > 0 and not missing else "missing_required_columns"
    return {
        "artifact": "benchmark_index_price",
        "status": status,
        "table": index_table,
        "rows": row_count,
        "benchmark_rows": benchmark_rows,
        "min_trade_date": min_date,
        "max_trade_date": max_date,
        "coverage_ratio": "",
        "missing_open_days": "",
        "latest_lag_days": latest_lag_days,
        "close_non_null_ratio": f"{close_ratio:.6f}",
        "volume_non_null_ratio": f"{volume_ratio:.6f}",
        "amount_non_null_ratio": f"{amount_ratio:.6f}",
        "required_columns_present": not missing,
        "missing_required_columns": ",".join(missing),
        "asof_columns_present": "",
        "asof_status": "not_applicable",
        "note": "index prices support benchmark return context, not constituent/weight attribution",
    }


def _trading_calendar_coverage_row(
    conn: sqlite3.Connection,
    *,
    calendar_table: str,
    index_table: str,
    benchmark_symbol: str,
) -> dict[str, Any]:
    existing = _table_names(conn)
    if calendar_table not in existing:
        return {
            "artifact": "benchmark_open_day_coverage",
            "status": "missing_table",
            "table": calendar_table,
            "rows": 0,
            "benchmark_rows": 0,
            "min_trade_date": "",
            "max_trade_date": "",
            "coverage_ratio": "",
            "missing_open_days": "",
            "latest_lag_days": "",
            "close_non_null_ratio": "",
            "volume_non_null_ratio": "",
            "amount_non_null_ratio": "",
            "required_columns_present": False,
            "missing_required_columns": "exchange,date,is_open",
            "asof_columns_present": "",
            "asof_status": "not_applicable",
            "note": "trading calendar table is missing",
        }
    if index_table not in existing:
        return {
            "artifact": "benchmark_open_day_coverage",
            "status": "blocked_no_price_table",
            "table": calendar_table,
            "rows": _count_rows(conn, calendar_table),
            "benchmark_rows": 0,
            "min_trade_date": "",
            "max_trade_date": "",
            "coverage_ratio": "",
            "missing_open_days": "",
            "latest_lag_days": "",
            "close_non_null_ratio": "",
            "volume_non_null_ratio": "",
            "amount_non_null_ratio": "",
            "required_columns_present": True,
            "missing_required_columns": "",
            "asof_columns_present": "",
            "asof_status": "not_applicable",
            "note": "cannot compare calendar coverage without benchmark price table",
        }
    cal_columns = _table_columns(conn, calendar_table)
    missing = [col for col in ["exchange", "date", "is_open"] if col not in cal_columns]
    row_count = _count_rows(conn, calendar_table)
    if missing:
        return {
            "artifact": "benchmark_open_day_coverage",
            "status": "missing_required_columns",
            "table": calendar_table,
            "rows": row_count,
            "benchmark_rows": 0,
            "min_trade_date": "",
            "max_trade_date": "",
            "coverage_ratio": "",
            "missing_open_days": "",
            "latest_lag_days": "",
            "close_non_null_ratio": "",
            "volume_non_null_ratio": "",
            "amount_non_null_ratio": "",
            "required_columns_present": False,
            "missing_required_columns": ",".join(missing),
            "asof_columns_present": "",
            "asof_status": "not_applicable",
            "note": "trading calendar is missing required columns",
        }

    index_safe = _safe_identifier(index_table)
    cal_safe = _safe_identifier(calendar_table)
    date_range = conn.execute(
        f"SELECT MIN(date), MAX(date), COUNT(DISTINCT date) FROM {index_safe} WHERE symbol = ?",
        (benchmark_symbol,),
    ).fetchone()
    min_date = str(date_range[0] or "")
    max_date = str(date_range[1] or "")
    benchmark_rows = int(date_range[2] or 0)
    exchange = _calendar_exchange_for_symbol(benchmark_symbol)
    if not min_date or not max_date or not exchange:
        return {
            "artifact": "benchmark_open_day_coverage",
            "status": "not_available",
            "table": calendar_table,
            "rows": row_count,
            "benchmark_rows": benchmark_rows,
            "min_trade_date": min_date,
            "max_trade_date": max_date,
            "coverage_ratio": "",
            "missing_open_days": "",
            "latest_lag_days": "",
            "close_non_null_ratio": "",
            "volume_non_null_ratio": "",
            "amount_non_null_ratio": "",
            "required_columns_present": True,
            "missing_required_columns": "",
            "asof_columns_present": "",
            "asof_status": "not_applicable",
            "note": "benchmark price date range or exchange mapping is unavailable",
        }
    rows = conn.execute(
        f"""
        WITH open_days AS (
            SELECT date
            FROM {cal_safe}
            WHERE exchange = ?
              AND is_open = 1
              AND date >= ?
              AND date <= ?
        ),
        index_days AS (
            SELECT DISTINCT date
            FROM {index_safe}
            WHERE symbol = ?
        )
        SELECT
            COUNT(open_days.date) AS expected_open_days,
            COUNT(index_days.date) AS covered_open_days,
            COUNT(open_days.date) - COUNT(index_days.date) AS missing_open_days
        FROM open_days
        LEFT JOIN index_days ON open_days.date = index_days.date
        """,
        (exchange, min_date, max_date, benchmark_symbol),
    ).fetchone()
    expected = int(rows[0] or 0)
    covered = int(rows[1] or 0)
    missing_days = int(rows[2] or 0)
    coverage_ratio = (covered / expected) if expected else 0.0
    return {
        "artifact": "benchmark_open_day_coverage",
        "status": "available" if expected and coverage_ratio >= 0.99 else "coverage_gap",
        "table": calendar_table,
        "rows": row_count,
        "benchmark_rows": benchmark_rows,
        "min_trade_date": min_date,
        "max_trade_date": max_date,
        "coverage_ratio": f"{coverage_ratio:.6f}",
        "missing_open_days": missing_days,
        "latest_lag_days": "",
        "close_non_null_ratio": "",
        "volume_non_null_ratio": "",
        "amount_non_null_ratio": "",
        "required_columns_present": True,
        "missing_required_columns": "",
        "asof_columns_present": "",
        "asof_status": "not_applicable",
        "note": "open trading day coverage for benchmark price rows; this is not constituent coverage",
    }


def _candidate_fold_coverage(
    *,
    candidate_folds_path: Path | None,
    capability_df: pd.DataFrame,
) -> pd.DataFrame:
    if candidate_folds_path is None:
        return pd.DataFrame(
            [
                {
                    "walk_forward_preset": "",
                    "fold": "",
                    "valid_start": "",
                    "valid_end": "",
                    "universe_as_of_date": "",
                    "constituent_status": str(capability_df.loc[capability_df["artifact"].eq("benchmark_constituents"), "status"].iloc[0]),
                    "weight_status": str(capability_df.loc[capability_df["artifact"].eq("benchmark_weights"), "status"].iloc[0]),
                    "coverage_status": "not_checked",
                    "note": "candidate folds path not provided",
                }
            ]
        )
    folds = pd.read_csv(candidate_folds_path)
    if folds.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    constituent_status = str(capability_df.loc[capability_df["artifact"].eq("benchmark_constituents"), "status"].iloc[0])
    weight_status = str(capability_df.loc[capability_df["artifact"].eq("benchmark_weights"), "status"].iloc[0])
    available = constituent_status == "available" and weight_status == "available"
    for _, row in folds.iterrows():
        coverage_status = "covered_by_schema" if available else "blocked_missing_asof_tables"
        rows.append(
            {
                "walk_forward_preset": row.get("walk_forward_preset", ""),
                "fold": row.get("fold", ""),
                "valid_start": row.get("valid_start", ""),
                "valid_end": row.get("valid_end", ""),
                "universe_as_of_date": row.get("universe_as_of_date", ""),
                "constituent_status": constituent_status,
                "weight_status": weight_status,
                "coverage_status": coverage_status,
                "note": (
                    "fold can be audited once constituent and weight rows cover validation dates"
                    if available
                    else "cannot audit CSI300 constituent/weight exposure for this fold"
                ),
            }
        )
    return pd.DataFrame(rows)


def _markdown_table(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return ["No rows."]
    header = "| " + " | ".join(df.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(df.columns)) + " |"
    lines = [header, sep]
    for _, row in df.iterrows():
        values = [str(row.get(col, "")).replace("\n", " ") for col in df.columns]
        lines.append("| " + " | ".join(values) + " |")
    return lines


def _git(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=False)
    except OSError:
        return ""
    return (result.stdout or result.stderr).strip()


def _write_report(
    path: Path,
    *,
    benchmark_symbol: str,
    db_path: Path,
    capability_df: pd.DataFrame,
    fold_coverage_df: pd.DataFrame,
    candidate_folds_path: Path | None,
) -> None:
    constituent_status = str(capability_df.loc[capability_df["artifact"].eq("benchmark_constituents"), "status"].iloc[0])
    weight_status = str(capability_df.loc[capability_df["artifact"].eq("benchmark_weights"), "status"].iloc[0])
    ready = constituent_status == "available" and weight_status == "available"
    conclusion = (
        "CSI300 成分和权重 as-of 审计表已具备最小 schema，可进入覆盖率细查。"
        if ready
        else "本地库尚不具备 CSI300 成分/权重 as-of 审计能力；当前只能做指数价格对比，不能做成分或主动权重归因。"
    )
    lines = [
        "# Index As-Of Data Audit",
        "",
        "This is a research-only data capability audit. It does not change strategies, admission, paper-review status, daily brief, watchlist, or trading signals.",
        "",
        "## Metadata",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- benchmark_symbol: `{benchmark_symbol}`",
        f"- sqlite_db: `{db_path}`",
        f"- candidate_folds: `{candidate_folds_path or ''}`",
        "",
        "## Plain Conclusion",
        "",
        conclusion,
        "",
        "## Capability Summary",
        "",
    ]
    capability_cols = [
        "artifact",
        "status",
        "table",
        "rows",
        "benchmark_rows",
        "min_trade_date",
        "max_trade_date",
        "coverage_ratio",
        "missing_open_days",
        "latest_lag_days",
        "close_non_null_ratio",
        "volume_non_null_ratio",
        "amount_non_null_ratio",
        "asof_status",
        "note",
    ]
    lines.extend(_markdown_table(capability_df[[col for col in capability_cols if col in capability_df.columns]]))
    lines.extend(["", "## Fold Coverage", ""])
    fold_cols = [
        "walk_forward_preset",
        "fold",
        "valid_start",
        "valid_end",
        "universe_as_of_date",
        "coverage_status",
        "note",
    ]
    lines.extend(_markdown_table(fold_coverage_df[[col for col in fold_cols if col in fold_coverage_df.columns]]))
    lines.extend(
        [
            "",
            "## Decision Boundary",
            "",
            "- `benchmark_index_price` can support CSI300 return and trend context only.",
            "- `benchmark_constituents` and `benchmark_weights` must be available before claiming CSI300 constituent exposure, active weight, or missed top-weight names.",
            "- Any future ingestion must carry an auditable as-of field such as `asof_time` or `effective_date`.",
            "- Current result does not authorize a new strong-market strategy or any promotion of existing candidates.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_run_log(
    path: Path,
    *,
    root: Path,
    config_path: Path | None,
    db_path: Path,
    benchmark_symbol: str,
    candidate_folds_path: Path | None,
    output_dir: Path,
    command: str | None,
) -> None:
    lines = [
        "# Index As-Of Data Audit Run Log",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        "- iteration_id: `I23`",
        "- diagnostic_type: `index_asof_data_capability_audit`",
        "- promotion_boundary: `research_only; no strategy change; no admission rerun; no trading signal`",
        f"- config_path: `{config_path or ''}`",
        f"- sqlite_db: `{db_path}`",
        f"- benchmark_symbol: `{benchmark_symbol}`",
        f"- candidate_folds_path: `{candidate_folds_path or ''}`",
        f"- output_dir: `{output_dir}`",
        f"- command: `{command or ''}`",
        f"- git_head: `{_git(['rev-parse', '--short', 'HEAD'], root)}`",
        "",
        "## Git Status",
        "",
        "```text",
        _git(["status", "--short"], root),
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_index_asof_audit(
    *,
    config: dict[str, Any],
    root: Path,
    config_path: Path | None = None,
    benchmark_symbol: str | None = None,
    candidate_folds_path: Path | None = None,
    output_dir: Path | None = None,
    command: str | None = None,
) -> IndexAsofAuditResult:
    benchmark = benchmark_symbol or str(config.get("benchmark_symbol", "SH.000300"))
    local_history = dict(config.get("local_history", {}))
    db_path = Path(local_history.get("path", "data/manual_history/a_share_history.sqlite"))
    if not db_path.is_absolute():
        db_path = root / db_path
    index_table = str(local_history.get("index_table", "market_index_bars"))
    index_meta_table = str(local_history.get("index_meta_table", "market_indices"))
    calendar_table = str(local_history.get("calendar_table", "trading_calendar"))
    out_dir = output_dir or report_path(root=root, config=config, category="database_health", parts=("index_asof_audit",))
    out_dir.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        raise FileNotFoundError(f"local history sqlite not found: {db_path}")

    with sqlite3.connect(db_path) as conn:
        constituent_table = _find_table(conn, CONSTITUENT_TABLE_CANDIDATES)
        weight_table = _find_table(conn, WEIGHT_TABLE_CANDIDATES)
        capability_rows = [
            _benchmark_metadata_row(conn, meta_table=index_meta_table, benchmark_symbol=benchmark),
            _index_price_row(conn, index_table=index_table, benchmark_symbol=benchmark),
            _trading_calendar_coverage_row(
                conn,
                calendar_table=calendar_table,
                index_table=index_table,
                benchmark_symbol=benchmark,
            ),
            _table_capability_row(
                conn=conn,
                label="benchmark_constituents",
                table=constituent_table,
                benchmark_symbol=benchmark,
                required_columns=REQUIRED_CONSTITUENT_COLUMNS,
            ),
            _table_capability_row(
                conn=conn,
                label="benchmark_weights",
                table=weight_table,
                benchmark_symbol=benchmark,
                required_columns=REQUIRED_WEIGHT_COLUMNS,
            ),
        ]

    capability_df = pd.DataFrame(capability_rows)
    fold_coverage_df = _candidate_fold_coverage(candidate_folds_path=candidate_folds_path, capability_df=capability_df)

    capability_csv = out_dir / "index_asof_capability_audit.csv"
    fold_coverage_csv = out_dir / "index_asof_fold_coverage.csv"
    report_md = out_dir / "index_asof_audit_report.md"
    run_log_md = out_dir / "index_asof_audit_run_log.md"
    capability_df.to_csv(capability_csv, index=False)
    fold_coverage_df.to_csv(fold_coverage_csv, index=False)
    _write_report(
        report_md,
        benchmark_symbol=benchmark,
        db_path=db_path,
        capability_df=capability_df,
        fold_coverage_df=fold_coverage_df,
        candidate_folds_path=candidate_folds_path,
    )
    _write_run_log(
        run_log_md,
        root=root,
        config_path=config_path,
        db_path=db_path,
        benchmark_symbol=benchmark,
        candidate_folds_path=candidate_folds_path,
        output_dir=out_dir,
        command=command,
    )

    constituent_status = str(capability_df.loc[capability_df["artifact"].eq("benchmark_constituents"), "status"].iloc[0])
    weight_status = str(capability_df.loc[capability_df["artifact"].eq("benchmark_weights"), "status"].iloc[0])
    return IndexAsofAuditResult(
        benchmark_symbol=benchmark,
        db_path=db_path,
        capability_csv_path=capability_csv,
        fold_coverage_csv_path=fold_coverage_csv,
        report_md_path=report_md,
        run_log_md_path=run_log_md,
        constituent_status=constituent_status,
        weight_status=weight_status,
        fold_rows=int(len(fold_coverage_df)),
    )
