from __future__ import annotations

import argparse
import html
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0.config import load_config
from phase0.local_history import configure_local_history, local_history_path, normalize_cn_symbol


FIELD_ALIASES: dict[str, list[str]] = {
    "symbol": ["symbol", "ts_code", "code", "证券代码", "股票代码"],
    "date": ["date", "trade_date", "datetime", "交易日期", "日期"],
    "open": ["open", "开盘价", "open_price"],
    "high": ["high", "最高价", "high_price"],
    "low": ["low", "最低价", "low_price"],
    "close": ["close", "收盘价", "close_price"],
    "volume": ["volume", "vol", "成交量"],
    "amount": ["amount", "amt", "成交额"],
}


def _find_column(columns: list[str], aliases: list[str]) -> str | None:
    lowered = {col.lower(): col for col in columns}
    for alias in aliases:
        if alias in columns:
            return alias
        found = lowered.get(alias.lower())
        if found is not None:
            return found
    return None


def _resolve_columns(df: pd.DataFrame) -> dict[str, str]:
    resolved: dict[str, str] = {}
    columns = list(df.columns)
    for target, aliases in FIELD_ALIASES.items():
        found = _find_column(columns, aliases)
        if found is not None:
            resolved[target] = found
    missing = [field for field in ("symbol", "date") if field not in resolved]
    if missing:
        raise ValueError(f"snapshot missing required columns: {missing}")
    return resolved


def _load_snapshot(path: Path) -> tuple[pd.DataFrame, dict[str, str]]:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)
    if df.empty:
        raise ValueError("snapshot file is empty")

    column_map = _resolve_columns(df)
    renamed = pd.DataFrame()
    renamed["symbol"] = df[column_map["symbol"]].map(normalize_cn_symbol)
    renamed["date"] = pd.to_datetime(df[column_map["date"]], errors="coerce").dt.normalize()
    for field in ("open", "high", "low", "close", "volume", "amount"):
        source = column_map.get(field)
        renamed[field] = pd.to_numeric(df[source], errors="coerce") if source else np.nan

    renamed = renamed.dropna(subset=["symbol", "date"]).reset_index(drop=True)
    if renamed.empty:
        raise ValueError("snapshot has no usable symbol/date rows after normalization")
    return renamed, column_map


def _load_local_rows(
    db_path: Path,
    *,
    table: str,
    market: str,
    adjust_type: str,
    symbols: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    placeholders = ",".join("?" for _ in symbols)
    query = f"""
        SELECT symbol, date, open, high, low, close, volume, amount
        FROM {table}
        WHERE market = ?
          AND symbol IN ({placeholders})
          AND date >= ?
          AND date <= ?
          AND adjust_type = ?
        ORDER BY symbol, date
    """
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(
            query,
            conn,
            params=[market, *symbols, start_date.date().isoformat(), end_date.date().isoformat(), adjust_type],
        )
    if df.empty:
        return df
    df["symbol"] = df["symbol"].map(normalize_cn_symbol)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    for field in ("open", "high", "low", "close", "volume", "amount"):
        df[field] = pd.to_numeric(df[field], errors="coerce")
    return df


def _field_match(external_value: Any, local_value: Any, *, rtol: float, atol: float) -> str:
    if pd.isna(external_value) and pd.isna(local_value):
        return "both_missing"
    if pd.isna(external_value):
        return "snapshot_missing"
    if pd.isna(local_value):
        return "local_missing"
    if np.isclose(float(external_value), float(local_value), rtol=rtol, atol=atol):
        return "match"
    return "mismatch"


def _possible_reason(row: pd.Series) -> str:
    field_results = {field: row[f"{field}_result"] for field in ("open", "high", "low", "close", "volume", "amount")}
    if row["row_status"] == "local_not_found":
        return "本地库缺失该 symbol/date 记录，可能是交易日错位、导入缺口或 symbol 归一化失败"
    price_mismatches = [field for field in ("open", "high", "low", "close") if field_results[field] == "mismatch"]
    volume_mismatches = [field for field in ("volume", "amount") if field_results[field] == "mismatch"]
    if price_mismatches and not volume_mismatches:
        return "价格字段不一致，优先检查复权口径或外部快照是否使用了不同价格源"
    if volume_mismatches and not price_mismatches:
        return "量额字段不一致，优先检查外部快照单位、口径或截面时间点"
    if price_mismatches and volume_mismatches:
        return "价格与量额都不一致，优先检查日期错位、来源滞后或下载快照字段映射"
    return ""


def _build_comparison(
    snapshot: pd.DataFrame,
    local_rows: pd.DataFrame,
    *,
    rtol: float,
    atol: float,
) -> pd.DataFrame:
    merged = snapshot.merge(
        local_rows,
        on=["symbol", "date"],
        how="left",
        suffixes=("_snapshot", "_local"),
    )
    merged["row_status"] = np.where(merged["close_local"].isna(), "local_not_found", "checked")
    for field in ("open", "high", "low", "close", "volume", "amount"):
        merged[f"{field}_result"] = merged.apply(
            lambda row: _field_match(row[f"{field}_snapshot"], row[f"{field}_local"], rtol=rtol, atol=atol),
            axis=1,
        )

    result_cols = [f"{field}_result" for field in ("open", "high", "low", "close", "volume", "amount")]
    merged["matched_fields"] = merged[result_cols].eq("match").sum(axis=1)
    merged["total_checked_fields"] = merged[result_cols].ne("both_missing").sum(axis=1)
    merged["row_status"] = np.where(
        merged["row_status"].eq("local_not_found"),
        "local_not_found",
        np.where(merged[result_cols].isin(["mismatch", "local_missing"]).any(axis=1), "mismatch", "match"),
    )
    merged["possible_reason"] = merged.apply(_possible_reason, axis=1)
    return merged


def _summary_table(comparison: pd.DataFrame, *, snapshot_path: Path, adjust_type: str) -> pd.DataFrame:
    total_rows = int(len(comparison))
    matched_rows = int(comparison["row_status"].eq("match").sum())
    mismatched_rows = int(comparison["row_status"].eq("mismatch").sum())
    missing_rows = int(comparison["row_status"].eq("local_not_found").sum())
    field_rates = {}
    for field in ("open", "high", "low", "close", "volume", "amount"):
        result = comparison[f"{field}_result"]
        checked = result.ne("both_missing").sum()
        matched = result.eq("match").sum()
        field_rates[field] = f"{(matched / checked * 100.0):.2f}%" if checked else "N/A"

    return pd.DataFrame(
        [
            {"项目": "外部快照文件", "值": str(snapshot_path)},
            {"项目": "校验口径", "值": f"daily_bar / adjust_type={adjust_type}"},
            {"项目": "总行数", "值": total_rows},
            {"项目": "完全一致行数", "值": matched_rows},
            {"项目": "不一致行数", "值": mismatched_rows},
            {"项目": "本地缺失行数", "值": missing_rows},
            {"项目": "open 一致率", "值": field_rates["open"]},
            {"项目": "high 一致率", "值": field_rates["high"]},
            {"项目": "low 一致率", "值": field_rates["low"]},
            {"项目": "close 一致率", "值": field_rates["close"]},
            {"项目": "volume 一致率", "值": field_rates["volume"]},
            {"项目": "amount 一致率", "值": field_rates["amount"]},
        ]
    )


def _symbol_breakdown(comparison: pd.DataFrame) -> pd.DataFrame:
    grouped = comparison.groupby("symbol", dropna=False)
    rows = []
    for symbol, part in grouped:
        rows.append(
            {
                "symbol": symbol,
                "rows": int(len(part)),
                "matches": int(part["row_status"].eq("match").sum()),
                "mismatches": int(part["row_status"].eq("mismatch").sum()),
                "local_not_found": int(part["row_status"].eq("local_not_found").sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(["mismatches", "local_not_found", "rows"], ascending=[False, False, False])


def _html_table(df: pd.DataFrame, *, table_class: str = "report-table") -> str:
    if df.empty:
        return "<p class=\"empty-note\">No data.</p>"
    header = "".join(f"<th>{html.escape(str(col))}</th>" for col in df.columns)
    rows: list[str] = []
    for _, row in df.iterrows():
        cells = "".join(f"<td>{html.escape('' if pd.isna(value) else str(value))}</td>" for value in row.tolist())
        rows.append(f"<tr>{cells}</tr>")
    return (
        f'<div class="{table_class}-wrap">'
        f'<table class="{table_class}">'
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</div>"
    )


def _build_html_report(
    summary: pd.DataFrame,
    symbol_breakdown: pd.DataFrame,
    mismatch_preview: pd.DataFrame,
    *,
    external_source: str,
    adjust_type: str,
) -> str:
    style = """
<style>
:root {
  color-scheme: light;
  --bg: #eef4fb;
  --surface: #ffffff;
  --border: #d3dbe6;
  --text: #1a2330;
  --muted: #667487;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 24px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: linear-gradient(180deg, #f8fbff 0%, #edf3fa 100%);
  color: var(--text);
}
.page { max-width: 1480px; margin: 0 auto; }
.hero, section {
  background: var(--surface);
  border: 1px solid var(--border);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
}
.hero { padding: 20px 24px; }
.hero h1 { margin: 0 0 8px; font-size: 28px; }
.hero p { margin: 0; color: var(--muted); }
section { margin-top: 18px; padding: 18px 20px; }
section h2 { margin: 0 0 12px; font-size: 20px; }
.report-table-wrap { overflow: auto; max-height: 70vh; }
.report-table {
  width: max-content;
  min-width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  line-height: 1.35;
}
.report-table th, .report-table td {
  border: 1px solid var(--border);
  padding: 7px 9px;
  white-space: nowrap;
  vertical-align: top;
  background: #fff;
}
.report-table th { position: sticky; top: 0; z-index: 1; background: #edf4ff; text-align: left; font-weight: 600; }
.report-table td:not(:first-child) { text-align: right; }
.report-table td:first-child:nth-last-child(n+2),
.report-table td:nth-child(2):nth-last-child(n+1) { font-variant-numeric: tabular-nums; }
.section-note { margin: 0 0 12px; color: var(--muted); }
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
</style>
"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Local History Consistency Report</title>
  {style}
</head>
<body>
  <div class="page">
    <div class="hero">
      <div class="title-row">
        <h1>Local History Consistency Report</h1>
        <span class="generated-at">生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}</span>
      </div>
      <p>外部来源：{html.escape(external_source)} | 校验对象：本地 SQLite 日线库 | 复权口径：{html.escape(adjust_type)}</p>
    </div>
    <section>
      <h2>摘要</h2>
      {_html_table(summary)}
    </section>
    <section>
      <h2>按股票分解</h2>
      {_html_table(symbol_breakdown)}
    </section>
    <section>
      <h2>不一致样本预览</h2>
      <p class="section-note">只展示前 50 行不一致或本地缺失记录，完整明细见 CSV。</p>
      {_html_table(mismatch_preview)}
    </section>
  </div>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare external snapshot with local SQLite daily bars")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--snapshot", type=Path, required=True, help="external snapshot csv/xlsx path")
    parser.add_argument("--external-source", default="manual_snapshot", help="label used in report")
    parser.add_argument("--adjust-type", default="", help="override local adjust_type, default from config")
    parser.add_argument("--rtol", type=float, default=1e-6)
    parser.add_argument("--atol", type=float, default=1e-4)
    parser.add_argument("--detail-output", type=Path, default=Path("reports/database_health/local_history_consistency_details.csv"))
    parser.add_argument("--report-output", type=Path, default=Path("reports/database_health/local_history_consistency_report.html"))
    args = parser.parse_args()

    config = load_config(args.config)
    local_cfg = config.get("local_history", {})
    configure_local_history(local_cfg, Path.cwd())
    db_path = local_history_path()
    if not db_path.exists():
        raise SystemExit(f"local history db not found: {db_path}")

    snapshot, column_map = _load_snapshot(args.snapshot)
    adjust_type = args.adjust_type or str(local_cfg.get("adjust_type", "qfq"))
    market = str(local_cfg.get("market", "CN"))
    table = str(local_cfg.get("daily_table", "market_daily_bars"))

    local_rows = _load_local_rows(
        db_path,
        table=table,
        market=market,
        adjust_type=adjust_type,
        symbols=sorted(snapshot["symbol"].dropna().unique().tolist()),
        start_date=pd.Timestamp(snapshot["date"].min()),
        end_date=pd.Timestamp(snapshot["date"].max()),
    )
    comparison = _build_comparison(snapshot, local_rows, rtol=args.rtol, atol=args.atol)
    comparison["snapshot_source"] = args.external_source
    comparison["adjust_type"] = adjust_type

    summary = _summary_table(comparison, snapshot_path=args.snapshot, adjust_type=adjust_type)
    summary.loc[len(summary)] = {"项目": "外部列映射", "值": ", ".join(f"{key}->{value}" for key, value in column_map.items())}
    symbol_breakdown = _symbol_breakdown(comparison)

    mismatch_preview = comparison[comparison["row_status"] != "match"].copy()
    preview_cols = [
        "symbol",
        "date",
        "row_status",
        "possible_reason",
        "open_snapshot",
        "open_local",
        "open_result",
        "close_snapshot",
        "close_local",
        "close_result",
        "volume_snapshot",
        "volume_local",
        "volume_result",
        "amount_snapshot",
        "amount_local",
        "amount_result",
    ]
    mismatch_preview = mismatch_preview[preview_cols].head(50)
    if "date" in mismatch_preview.columns:
        mismatch_preview["date"] = pd.to_datetime(mismatch_preview["date"]).dt.strftime("%Y-%m-%d")

    args.detail_output.parent.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(args.detail_output, index=False, encoding="utf-8")
    args.report_output.write_text(
        _build_html_report(
            summary,
            symbol_breakdown,
            mismatch_preview,
            external_source=args.external_source,
            adjust_type=adjust_type,
        ),
        encoding="utf-8",
    )
    print(args.report_output)
    print(args.detail_output)


if __name__ == "__main__":
    main()
