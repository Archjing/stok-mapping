from __future__ import annotations

import argparse
import html
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0.config import load_config


def _resolve_path(root: Path, value: Any) -> Path:
    path = Path(str(value or ""))
    return path if path.is_absolute() else root / path


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def _format_html(summary: dict[str, Any], sample_df: pd.DataFrame) -> str:
    style = """
<style>
body {
  margin: 0;
  padding: 24px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #1f2937;
  background: #f5f7fb;
}
.page {
  max-width: 1120px;
  margin: 0 auto;
}
h1 {
  margin: 0 0 8px;
  font-size: 24px;
}
.title-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}
.title-row h1 {
  margin: 0;
}
.generated-at {
  color: #8b95a1;
  font-size: 13px;
}
p {
  margin: 0 0 18px;
  color: #4b5563;
}
.status-ok {
  color: #0f7a3a;
  font-weight: 700;
}
.status-warn {
  color: #9a6700;
  font-weight: 700;
}
.table-wrap {
  overflow: auto;
  max-height: 70vh;
  border: 1px solid #d0d7de;
  background: #fff;
  margin-bottom: 24px;
}
table {
  border-collapse: collapse;
  width: max-content;
  min-width: 100%;
  font-size: 13px;
}
th,
td {
  border: 1px solid #d0d7de;
  padding: 7px 9px;
  white-space: nowrap;
}
th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #eef3f9;
  text-align: left;
}
</style>
"""
    summary_rows = "\n".join(
        f"<tr><td>{html.escape(str(key))}</td><td>{html.escape(str(value))}</td></tr>"
        for key, value in summary.items()
    )
    sample_rows = []
    for _, row in sample_df.iterrows():
        sample_rows.append(
            "<tr>"
            + "".join(f"<td>{html.escape(str(row.get(col, '')))}</td>" for col in sample_df.columns)
            + "</tr>"
        )
    status_class = "status-ok" if summary.get("pti_verdict") == "PASS" else "status-warn"
    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>Financial PTI Audit</title>\n"
        + style
        + "</head>\n<body>\n<div class=\"page\">\n"
        "<div class=\"title-row\"><h1>Financial Point-in-Time Audit</h1>"
        f"<span class=\"generated-at\">生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</span></div>\n"
        f"<p class=\"{status_class}\">Verdict: {html.escape(str(summary.get('pti_verdict', 'UNKNOWN')))}</p>\n"
        "<p>检查财务因子是否具备公告日、是否可按公告日加滞后天数做 point-in-time 对齐。</p>\n"
        "<h2>Summary</h2><div class=\"table-wrap\"><table><thead><tr><th>metric</th><th>value</th></tr></thead><tbody>"
        + summary_rows
        + "</tbody></table></div>\n"
        "<h2>Problem Samples</h2><div class=\"table-wrap\"><table><thead><tr>"
        + "".join(f"<th>{html.escape(str(col))}</th>" for col in sample_df.columns)
        + "</tr></thead><tbody>"
        + "\n".join(sample_rows)
        + "</tbody></table></div>\n"
        "</div>\n</body>\n</html>\n"
    )


def audit_financial_pti(
    *,
    config_path: Path,
    summary_output: Path,
    sample_output: Path,
    html_output: Path,
) -> dict[str, Any]:
    root = Path.cwd()
    cfg = load_config(config_path)
    strategy_cfg = cfg.get("walk_forward", {}).get("strategy_v2", {})
    qcfg = strategy_cfg.get("local_factor", {}).get("quality_growth", {})
    table = str(qcfg.get("financial_table", "market_financial_factors"))
    lag_days = int(qcfg.get("financial_lag_days", 1))
    db_path = _resolve_path(root, cfg.get("local_history", {}).get("path", "data/manual_history/a_share_history.sqlite"))

    with sqlite3.connect(db_path) as conn:
        if not _table_exists(conn, table):
            raise ValueError(f"financial table does not exist: {table}")
        df = pd.read_sql_query(
            f"""
            SELECT symbol, market, report_date, announce_date, roe, revenue_growth,
                   profit_growth, operating_cash_flow_to_net_profit, debt_to_asset
            FROM {table}
            """,
            conn,
        )

    if df.empty:
        summary = {"pti_verdict": "FAIL", "reason": "financial factor table is empty"}
        sample_df = pd.DataFrame()
    else:
        df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce")
        df["announce_date"] = pd.to_datetime(df["announce_date"], errors="coerce")
        df["available_date"] = df["announce_date"] + pd.to_timedelta(lag_days, unit="D")
        missing_announce = df["announce_date"].isna()
        missing_report = df["report_date"].isna()
        announce_before_report = df["announce_date"].notna() & df["report_date"].notna() & (df["announce_date"] < df["report_date"])
        duplicate_versions = df.duplicated(subset=["symbol", "market", "report_date", "announce_date"], keep=False)
        unresolved_available = df["available_date"].isna()
        problem_mask = missing_announce | missing_report | announce_before_report | duplicate_versions | unresolved_available
        coverage = 1.0 - float(missing_announce.mean())
        verdict = "PASS" if coverage >= 0.99 and not bool(announce_before_report.any()) and not bool(unresolved_available.any()) else "WARN"
        summary = {
            "pti_verdict": verdict,
            "rows": int(len(df)),
            "symbols": int(df["symbol"].nunique()),
            "financial_lag_days": lag_days,
            "announce_date_coverage": f"{coverage:.4f}",
            "missing_announce_date_rows": int(missing_announce.sum()),
            "missing_report_date_rows": int(missing_report.sum()),
            "announce_before_report_rows": int(announce_before_report.sum()),
            "duplicate_same_announce_rows": int(duplicate_versions.sum()),
            "unresolved_available_date_rows": int(unresolved_available.sum()),
            "earliest_report_date": df["report_date"].min().date().isoformat() if df["report_date"].notna().any() else "",
            "latest_report_date": df["report_date"].max().date().isoformat() if df["report_date"].notna().any() else "",
            "earliest_available_date": df["available_date"].min().date().isoformat() if df["available_date"].notna().any() else "",
            "latest_available_date": df["available_date"].max().date().isoformat() if df["available_date"].notna().any() else "",
            "pti_rule": "strategy may use a financial row only when trade_date >= announce_date + financial_lag_days",
        }
        sample_cols = ["symbol", "market", "report_date", "announce_date", "available_date"]
        sample_df = df.loc[problem_mask, sample_cols].head(100).copy()

    summary_df = pd.DataFrame([summary])
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    sample_output.parent.mkdir(parents=True, exist_ok=True)
    html_output.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(summary_output, index=False, encoding="utf-8-sig")
    sample_df.to_csv(sample_output, index=False, encoding="utf-8-sig")
    html_output.write_text(_format_html(summary, sample_df), encoding="utf-8")
    return {"summary": summary_output, "samples": sample_output, "html": html_output, "verdict": summary.get("pti_verdict")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--summary-output", default="reports/phase0_financial_pti_summary.csv")
    parser.add_argument("--sample-output", default="reports/phase0_financial_pti_problem_samples.csv")
    parser.add_argument("--html-output", default="reports/phase0_financial_pti_report.html")
    args = parser.parse_args()
    result = audit_financial_pti(
        config_path=Path(args.config),
        summary_output=Path(args.summary_output),
        sample_output=Path(args.sample_output),
        html_output=Path(args.html_output),
    )
    print(f"verdict={result['verdict']}")
    print(f"summary={result['summary']}")
    print(f"samples={result['samples']}")
    print(f"html={result['html']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
