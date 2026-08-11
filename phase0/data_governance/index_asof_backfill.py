from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from phase0.config import load_config
from phase0.data_access.providers.tushare import TushareConfig, _call, tushare_available, tushare_config
from phase0.data_governance.sql import safe_identifier
from phase0.data_access.local_history import normalize_cn_symbol
from phase0.reporting.paths import report_path

_safe_identifier = safe_identifier


@dataclass(frozen=True)
class IndexAsofBackfillResult:
    db_path: Path
    index_code: str
    vendor_index_code: str
    start_date: str
    end_date: str
    status: str
    source: str
    fetched_rows: int
    inserted_weight_rows: int
    inserted_constituent_rows: int
    distinct_trade_dates: int
    min_trade_date: str
    max_trade_date: str
    audit_csv: Path
    audit_md: Path
    warnings: list[str]


def _to_vendor_index_code(index_code: str) -> str:
    raw = str(index_code).strip().upper()
    if raw.endswith(".SH") or raw.endswith(".SZ"):
        return raw
    if raw.startswith("SH.") or raw.startswith("SZ."):
        market, code = raw.split(".", 1)
        return f"{code}.{market}"
    normalized = normalize_cn_symbol(raw)
    if normalized:
        market, code = normalized.split(".", 1)
        return f"{code}.{market}"
    return raw


def _normalize_project_index_code(value: str) -> str:
    raw = str(value).strip().upper()
    if "." in raw:
        left, right = raw.split(".", 1)
        if left in {"SH", "SZ", "BJ"} and right:
            return f"{left}.{right}"
        if right in {"SH", "SZ", "BJ"} and left:
            return f"{right}.{left}"
    normalized = normalize_cn_symbol(value)
    if normalized:
        return normalized
    vendor = _to_vendor_index_code(value)
    normalized = normalize_cn_symbol(vendor)
    return normalized or str(value).strip().upper()


def _compact_date(value: str) -> str:
    return str(value).replace("-", "")[:8]


def _iso_date(value: Any) -> str:
    parsed = pd.to_datetime(value, format="%Y%m%d", errors="coerce")
    if pd.isna(parsed):
        parsed = pd.to_datetime(value, errors="coerce")
    return "" if pd.isna(parsed) else parsed.date().isoformat()


def fetch_tushare_index_weights(
    *,
    index_code: str,
    start_date: str,
    end_date: str,
    cfg: TushareConfig,
) -> pd.DataFrame:
    return _call(
        "index_weight",
        params={
            "index_code": _to_vendor_index_code(index_code),
            "start_date": _compact_date(start_date),
            "end_date": _compact_date(end_date),
        },
        fields=["index_code", "con_code", "trade_date", "weight"],
        cfg=cfg,
    )


def fetch_tushare_index_weights_monthly(
    *,
    index_code: str,
    start_date: str,
    end_date: str,
    cfg: TushareConfig,
    max_requests_per_minute: int = 180,
) -> pd.DataFrame:
    months = pd.period_range(pd.Timestamp(start_date), pd.Timestamp(end_date), freq="M")
    frames: list[pd.DataFrame] = []
    delay = max(0.0, 60.0 / float(max_requests_per_minute)) if max_requests_per_minute > 0 else 0.0
    for month in months:
        month_start = max(pd.Timestamp(start_date), month.start_time).date().isoformat()
        month_end = min(pd.Timestamp(end_date), month.end_time).date().isoformat()
        rows = fetch_tushare_index_weights(index_code=index_code, start_date=month_start, end_date=month_end, cfg=cfg)
        if not rows.empty:
            frames.append(rows)
        if delay > 0:
            time.sleep(delay)
    if not frames:
        return pd.DataFrame(columns=["index_code", "con_code", "trade_date", "weight"])
    return pd.concat(frames, ignore_index=True).drop_duplicates()


def normalize_index_weight_rows(raw: pd.DataFrame, *, default_index_code: str, source: str) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(
            columns=[
                "index_code",
                "trade_date",
                "symbol",
                "weight",
                "effective_date",
                "asof_time",
                "source",
                "vendor_index_code",
                "vendor_symbol",
            ]
        )
    frame = raw.copy()
    if "index_code" not in frame.columns:
        frame["index_code"] = _to_vendor_index_code(default_index_code)
    if "con_code" not in frame.columns and "symbol" in frame.columns:
        frame["con_code"] = frame["symbol"]
    frame["vendor_index_code"] = frame["index_code"].astype(str).str.strip().str.upper()
    frame["index_code"] = frame["vendor_index_code"].map(_normalize_project_index_code)
    frame["vendor_symbol"] = frame["con_code"].astype(str).str.strip().str.upper()
    frame["symbol"] = frame["vendor_symbol"].map(normalize_cn_symbol)
    frame["trade_date"] = frame["trade_date"].map(_iso_date)
    frame["effective_date"] = frame["trade_date"]
    frame["asof_time"] = frame["trade_date"].map(lambda value: f"{value}T18:00:00" if value else "")
    frame["weight"] = pd.to_numeric(frame.get("weight"), errors="coerce")
    frame["source"] = source
    frame = frame.dropna(subset=["weight"])
    frame = frame[
        (frame["index_code"].astype(str) != "")
        & (frame["symbol"].astype(str) != "")
        & (frame["trade_date"].astype(str) != "")
    ].copy()
    return frame[
        [
            "index_code",
            "trade_date",
            "symbol",
            "weight",
            "effective_date",
            "asof_time",
            "source",
            "vendor_index_code",
            "vendor_symbol",
        ]
    ].drop_duplicates(subset=["index_code", "trade_date", "symbol"], keep="last")


def ensure_index_asof_tables(
    conn: sqlite3.Connection,
    *,
    weights_table: str = "cn_index_weights_asof",
    constituents_table: str = "cn_index_constituents_asof",
) -> None:
    weights = _safe_identifier(weights_table)
    constituents = _safe_identifier(constituents_table)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {weights} (
            index_code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            weight REAL NOT NULL,
            effective_date TEXT,
            asof_time TEXT,
            source TEXT NOT NULL,
            vendor_index_code TEXT,
            vendor_symbol TEXT,
            ingested_at TEXT NOT NULL,
            PRIMARY KEY (index_code, trade_date, symbol)
        )
        """
    )
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{weights}_date ON {weights}(index_code, trade_date)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{weights}_symbol ON {weights}(symbol)")
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {constituents} (
            index_code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            effective_date TEXT,
            source TEXT NOT NULL,
            vendor_index_code TEXT,
            vendor_symbol TEXT,
            ingested_at TEXT NOT NULL,
            PRIMARY KEY (index_code, trade_date, symbol)
        )
        """
    )
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{constituents}_date ON {constituents}(index_code, trade_date)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{constituents}_symbol ON {constituents}(symbol)")


def upsert_index_asof_rows(
    conn: sqlite3.Connection,
    rows: pd.DataFrame,
    *,
    weights_table: str = "cn_index_weights_asof",
    constituents_table: str = "cn_index_constituents_asof",
) -> tuple[int, int]:
    if rows.empty:
        ensure_index_asof_tables(conn, weights_table=weights_table, constituents_table=constituents_table)
        return 0, 0
    ensure_index_asof_tables(conn, weights_table=weights_table, constituents_table=constituents_table)
    weights = _safe_identifier(weights_table)
    constituents = _safe_identifier(constituents_table)
    ingested_at = datetime.now().isoformat(timespec="seconds")
    weight_params = [
        (
            str(row["index_code"]),
            str(row["trade_date"]),
            str(row["symbol"]),
            float(row["weight"]),
            str(row.get("effective_date") or ""),
            str(row.get("asof_time") or ""),
            str(row.get("source") or ""),
            str(row.get("vendor_index_code") or ""),
            str(row.get("vendor_symbol") or ""),
            ingested_at,
        )
        for _, row in rows.iterrows()
    ]
    weight_cursor = conn.executemany(
        f"""
        INSERT OR REPLACE INTO {weights} (
            index_code, trade_date, symbol, weight, effective_date, asof_time,
            source, vendor_index_code, vendor_symbol, ingested_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        weight_params,
    )
    constituent_params = [
        (
            str(row["index_code"]),
            str(row["trade_date"]),
            str(row["symbol"]),
            str(row.get("effective_date") or ""),
            str(row.get("source") or ""),
            str(row.get("vendor_index_code") or ""),
            str(row.get("vendor_symbol") or ""),
            ingested_at,
        )
        for _, row in rows.drop_duplicates(subset=["index_code", "trade_date", "symbol"]).iterrows()
    ]
    constituent_cursor = conn.executemany(
        f"""
        INSERT OR REPLACE INTO {constituents} (
            index_code, trade_date, symbol, effective_date, source,
            vendor_index_code, vendor_symbol, ingested_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        constituent_params,
    )
    return int(weight_cursor.rowcount or 0), int(constituent_cursor.rowcount or 0)


def _audit_paths(root: Path, *, index_code: str, start_date: str, end_date: str) -> tuple[Path, Path]:
    date_dir = report_path(root=root, category="database_health", parts=(datetime.now().date().isoformat(),))
    compact_index = index_code.replace(".", "_")
    compact_range = f"{_compact_date(start_date)}_{_compact_date(end_date)}"
    return (
        date_dir / f"index_asof_backfill_audit_{compact_index}_{compact_range}.csv",
        date_dir / f"index_asof_backfill_audit_{compact_index}_{compact_range}.md",
    )


def _write_audit(
    *,
    csv_path: Path,
    md_path: Path,
    result_row: dict[str, Any],
    weights_table: str,
    constituents_table: str,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([result_row]).to_csv(csv_path, index=False)
    lines = [
        "# CSI300 Index As-Of Backfill Audit",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        "- task: `CSI300 historical constituents and weights as-of data backfill`",
        f"- status: `{result_row['status']}`",
        f"- db_path: `{result_row['db_path']}`",
        f"- index_code: `{result_row['index_code']}`",
        f"- vendor_index_code: `{result_row['vendor_index_code']}`",
        f"- source: `{result_row['source']}`",
        f"- date_range: `{result_row['start_date']}..{result_row['end_date']}`",
        f"- fetched_rows: `{result_row['fetched_rows']}`",
        f"- inserted_weight_rows: `{result_row['inserted_weight_rows']}`",
        f"- inserted_constituent_rows: `{result_row['inserted_constituent_rows']}`",
        f"- distinct_trade_dates: `{result_row['distinct_trade_dates']}`",
        f"- actual_trade_date_span: `{result_row['min_trade_date']}..{result_row['max_trade_date']}`",
        f"- weights_table: `{weights_table}`",
        f"- constituents_table: `{constituents_table}`",
        "",
        "## As-Of 口径",
        "",
        "- `trade_date` / `effective_date` 表示指数权重生效日。",
        "- `asof_time` 当前写为 `trade_date T18:00:00`，表示收盘后可见代理时间；不得解释为盘中可见数据。",
        "- `cn_index_constituents_asof` 由同一批权重记录派生，避免成分和权重日期口径不一致。",
        "",
    ]
    if result_row.get("warnings"):
        lines.extend(["## Warnings", ""])
        for warning in str(result_row["warnings"]).split(" | "):
            if warning:
                lines.append(f"- {warning}")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def backfill_index_asof_from_config(
    config_path: Path,
    *,
    index_code: str | None = None,
    start_date: str,
    end_date: str,
    input_csv: Path | None = None,
    max_requests_per_minute: int = 180,
    weights_table: str = "cn_index_weights_asof",
    constituents_table: str = "cn_index_constituents_asof",
) -> IndexAsofBackfillResult:
    root = config_path.parent
    cfg = load_config(config_path)
    local_cfg = cfg.get("local_history", {})
    data_cfg = cfg.get("data_sources", {})
    project_index_code = _normalize_project_index_code(index_code or str(cfg.get("benchmark_symbol", "SH.000300")))
    vendor_index_code = _to_vendor_index_code(project_index_code)
    db_path = Path(local_cfg.get("path", "data/a_share_history.sqlite"))
    if not db_path.is_absolute():
        db_path = root / db_path
    csv_path, md_path = _audit_paths(root, index_code=project_index_code, start_date=start_date, end_date=end_date)
    warnings: list[str] = []

    if input_csv is not None:
        raw = pd.read_csv(input_csv)
        source = "csv.index_weight"
    else:
        tcfg = tushare_config(data_cfg.get("tushare", {}))
        source = "tushare.index_weight"
        if not tushare_available(tcfg):
            warnings.append(f"Tushare token env {tcfg.token_env} is not available.")
            result_row = {
                "db_path": str(db_path),
                "index_code": project_index_code,
                "vendor_index_code": vendor_index_code,
                "start_date": start_date,
                "end_date": end_date,
                "status": "missing_tushare_token",
                "source": source,
                "fetched_rows": 0,
                "inserted_weight_rows": 0,
                "inserted_constituent_rows": 0,
                "distinct_trade_dates": 0,
                "min_trade_date": "",
                "max_trade_date": "",
                "warnings": " | ".join(warnings),
            }
            _write_audit(
                csv_path=csv_path,
                md_path=md_path,
                result_row=result_row,
                weights_table=weights_table,
                constituents_table=constituents_table,
            )
            return IndexAsofBackfillResult(
                db_path=db_path,
                index_code=project_index_code,
                vendor_index_code=vendor_index_code,
                start_date=start_date,
                end_date=end_date,
                status="missing_tushare_token",
                source=source,
                fetched_rows=0,
                inserted_weight_rows=0,
                inserted_constituent_rows=0,
                distinct_trade_dates=0,
                min_trade_date="",
                max_trade_date="",
                audit_csv=csv_path,
                audit_md=md_path,
                warnings=warnings,
            )
        raw = fetch_tushare_index_weights_monthly(
            index_code=project_index_code,
            start_date=start_date,
            end_date=end_date,
            cfg=tcfg,
            max_requests_per_minute=max_requests_per_minute,
        )

    normalized = normalize_index_weight_rows(raw, default_index_code=project_index_code, source=source)
    if normalized.empty:
        warnings.append("No valid index weight rows after normalization.")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        inserted_weights, inserted_constituents = upsert_index_asof_rows(
            conn,
            normalized,
            weights_table=weights_table,
            constituents_table=constituents_table,
        )
        conn.commit()

    trade_dates = sorted(normalized["trade_date"].dropna().astype(str).unique().tolist()) if not normalized.empty else []
    status = "ok" if inserted_weights > 0 and inserted_constituents > 0 else "empty"
    result_row = {
        "db_path": str(db_path),
        "index_code": project_index_code,
        "vendor_index_code": vendor_index_code,
        "start_date": start_date,
        "end_date": end_date,
        "status": status,
        "source": source,
        "fetched_rows": int(len(raw)),
        "inserted_weight_rows": inserted_weights,
        "inserted_constituent_rows": inserted_constituents,
        "distinct_trade_dates": int(len(trade_dates)),
        "min_trade_date": trade_dates[0] if trade_dates else "",
        "max_trade_date": trade_dates[-1] if trade_dates else "",
        "warnings": " | ".join(warnings),
    }
    _write_audit(
        csv_path=csv_path,
        md_path=md_path,
        result_row=result_row,
        weights_table=weights_table,
        constituents_table=constituents_table,
    )
    return IndexAsofBackfillResult(
        db_path=db_path,
        index_code=project_index_code,
        vendor_index_code=vendor_index_code,
        start_date=start_date,
        end_date=end_date,
        status=status,
        source=source,
        fetched_rows=int(len(raw)),
        inserted_weight_rows=inserted_weights,
        inserted_constituent_rows=inserted_constituents,
        distinct_trade_dates=int(len(trade_dates)),
        min_trade_date=trade_dates[0] if trade_dates else "",
        max_trade_date=trade_dates[-1] if trade_dates else "",
        audit_csv=csv_path,
        audit_md=md_path,
        warnings=warnings,
    )
