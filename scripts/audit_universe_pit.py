from __future__ import annotations

import html
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from phase0.config import load_config
from phase0.local_history import configure_local_history
from phase0.universe import load_point_in_time_universe


def _html_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "<p>No data.</p>"
    header = "".join(f"<th>{html.escape(str(col))}</th>" for col in df.columns)
    rows = []
    for _, row in df.iterrows():
        cells = "".join(f"<td>{html.escape(str('' if pd.isna(v) else v))}</td>" for v in row.tolist())
        rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def audit_universe_pit(
    *,
    config_path: Path,
    as_of_date: str,
    sample_limit: int = 30,
    report_output: Path,
) -> dict[str, Any]:
    root = config_path.parent
    cfg = load_config(config_path)
    configure_local_history(cfg.get("local_history", {}), root)
    universe = load_point_in_time_universe(cfg, root, as_of_date)
    local_cfg = cfg.get("local_history", {})
    db_path = Path(local_cfg.get("path", "data/manual_history/a_share_history.sqlite"))
    if not db_path.is_absolute():
        db_path = root / db_path
    meta_table = str(local_cfg.get("meta_table", "market_stocks"))

    universe_df = universe.universe.copy()
    universe_df["symbol"] = universe_df["symbol"].astype(str)
    sample_df = universe_df.head(sample_limit).copy()

    with sqlite3.connect(db_path) as conn:
        placeholders = ",".join("?" for _ in universe.symbols) if universe.symbols else "''"
        meta = pd.read_sql_query(
            f"""
            SELECT symbol, name, industry, list_date, delist_date, list_status
            FROM {meta_table}
            WHERE market = 'CN'
              AND symbol IN ({placeholders})
            """,
            conn,
            params=universe.symbols,
        ) if universe.symbols else pd.DataFrame(columns=["symbol", "name", "industry", "list_date", "delist_date", "list_status"])

    if not meta.empty:
        sample_df = sample_df.merge(meta, on="symbol", how="left", suffixes=("", "_meta"))

    as_of_ts = pd.Timestamp(as_of_date)
    meta["list_date"] = pd.to_datetime(meta.get("list_date"), errors="coerce")
    meta["delist_date"] = pd.to_datetime(meta.get("delist_date"), errors="coerce")
    boundary_violations = meta[
        ~((meta["list_date"].isna() | (meta["list_date"] <= as_of_ts)) & (meta["delist_date"].isna() | (meta["delist_date"] > as_of_ts)))
    ].copy()

    summary = pd.DataFrame(
        [
            ["as_of_date", as_of_date],
            ["selected_count", int(len(universe_df))],
            ["snapshot_count", int(universe.snapshot_count)],
            ["source", universe.source],
            ["warnings", "; ".join(universe.warnings) if universe.warnings else ""],
            ["industry_available_in_snapshot", bool("industry" in universe_df.columns and universe_df["industry"].replace("", pd.NA).notna().any())],
            ["historical_industry_constraint_effective", False],
            ["listing_boundary_violations", int(len(boundary_violations))],
            ["min_total_mv_effective", bool("total_mv" in universe_df.columns and universe_df["total_mv"].notna().any())],
            ["min_total_mv_selected", float(universe_df["total_mv"].min()) if "total_mv" in universe_df.columns and universe_df["total_mv"].notna().any() else ""],
        ],
        columns=["metric", "value"],
    )

    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(
        (
            "<html><head><meta charset='utf-8'><title>Universe PIT Audit</title>"
            "<style>body{font-family:Segoe UI,sans-serif;padding:24px}table{border-collapse:collapse}th,td{border:1px solid #d0d7de;padding:6px 8px;text-align:left}th{background:#f3f6fb}</style>"
            "</head><body>"
            f"<h1>Universe PIT Audit</h1><p>as_of_date={html.escape(as_of_date)}</p>"
            "<h2>Summary</h2>"
            f"{_html_table(summary)}"
            "<h2>Sample Universe Rows</h2>"
            f"{_html_table(sample_df[['symbol','name','industry','total_mv','circ_mv','amount','list_date','delist_date','list_status']])}"
            "<h2>Boundary Violations</h2>"
            f"{_html_table(boundary_violations[['symbol','name','industry','list_date','delist_date','list_status']])}"
            "</body></html>"
        ),
        encoding="utf-8",
    )
    return {
        "report": report_output,
        "selected_count": int(len(universe_df)),
        "boundary_violations": int(len(boundary_violations)),
        "industry_effective": False,
    }

