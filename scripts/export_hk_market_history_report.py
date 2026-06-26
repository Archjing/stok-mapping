from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phase0.config import load_config

HK_SYMBOL_NAME_MAP = {
    "HK.00005": "汇丰控股",
    "HK.00388": "香港交易所",
    "HK.00700": "腾讯控股",
    "HK.00728": "中国电信",
    "HK.00883": "中国海洋石油",
    "HK.00939": "建设银行",
    "HK.00941": "中国移动",
    "HK.00981": "中芯国际",
    "HK.00992": "联想集团",
    "HK.01024": "快手-W",
    "HK.01088": "中国神华",
    "HK.01211": "比亚迪股份",
    "HK.01299": "友邦保险",
    "HK.01347": "华虹半导体",
    "HK.01398": "工商银行",
    "HK.01810": "小米集团-W",
    "HK.02015": "理想汽车-W",
    "HK.02020": "安踏体育",
    "HK.02269": "药明生物",
    "HK.02318": "中国平安",
    "HK.02899": "紫金矿业",
    "HK.03690": "美团-W",
    "HK.03988": "中国银行",
    "HK.06160": "百济神州",
    "HK.09618": "京东集团-SW",
    "HK.09633": "农夫山泉",
    "HK.09868": "小鹏汽车-W",
    "HK.09888": "百度集团-SW",
    "HK.09988": "阿里巴巴-W",
    "HK.09999": "网易-S",
}


def _safe_identifier(value: str) -> str:
    if not value.replace("_", "").isalnum() or value[0].isdigit():
        raise ValueError(f"Unsafe SQL identifier: {value}")
    return value


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _read_sql(conn: sqlite3.Connection, query: str, params: tuple = ()) -> pd.DataFrame:
    return pd.read_sql_query(query, conn, params=params)


def _format_table(df: pd.DataFrame, columns: list[str] | None = None) -> str:
    if columns is not None:
        df = df[columns]
    if df.empty:
        return "_无数据_"
    return df.to_markdown(index=False)


def build_report(config_path: Path, output_path: Path) -> Path:
    root = config_path.resolve().parent
    cfg = load_config(config_path)
    hk_cfg = cfg.get("hk_market_history", {})
    db_path = _resolve(root, hk_cfg.get("path", "data/hk_market_history.sqlite"))
    output_path = _resolve(root, output_path)
    daily_table = _safe_identifier(str(hk_cfg.get("daily_table", "hk_daily_bars")))
    audit_table = _safe_identifier(str(hk_cfg.get("source_audit_table", "hk_data_source_runs")))
    symbols = [str(item) for item in hk_cfg.get("symbols", [])]
    max_staleness_days = int(hk_cfg.get("max_staleness_days", 3))
    cutoff = date.today() - timedelta(days=max(0, max_staleness_days))

    if not db_path.exists():
        raise FileNotFoundError(f"HK market history database not found: {db_path}")

    with sqlite3.connect(db_path) as conn:
        summary = _read_sql(
            conn,
            f"""
            SELECT
                symbol,
                COUNT(*) AS rows,
                MIN(date) AS first_date,
                MAX(date) AS latest_date,
                ROUND(MIN(close), 4) AS min_close,
                ROUND(MAX(close), 4) AS max_close,
                ROUND(AVG(volume), 2) AS avg_volume,
                MAX(source) AS source,
                MAX(hk) AS hk
            FROM {daily_table}
            WHERE symbol IN ({",".join("?" for _ in symbols)})
            GROUP BY symbol
            ORDER BY symbol
            """,
            tuple(symbols),
        )
        if not summary.empty:
            summary["name_zh"] = summary["symbol"].map(HK_SYMBOL_NAME_MAP).fillna("")
        audit = _read_sql(
            conn,
            f"""
            SELECT fetched_at, source, latest_trade_date, coverage, fetched_rows, inserted_rows, updated_rows, status, message
            FROM {audit_table}
            ORDER BY id DESC
            LIMIT 5
            """,
        )
        samples_head = _read_sql(
            conn,
            f"""
            SELECT symbol, date, open, high, low, close, adjusted_close, volume, source, hk
            FROM {daily_table}
            ORDER BY date ASC, symbol ASC
            LIMIT 10
            """,
        )
        if not samples_head.empty:
            samples_head["name_zh"] = samples_head["symbol"].map(HK_SYMBOL_NAME_MAP).fillna("")
        samples_tail = _read_sql(
            conn,
            f"""
            SELECT symbol, date, open, high, low, close, adjusted_close, volume, source, hk
            FROM {daily_table}
            ORDER BY date DESC, symbol ASC
            LIMIT 10
            """,
        )
        if not samples_tail.empty:
            samples_tail["name_zh"] = samples_tail["symbol"].map(HK_SYMBOL_NAME_MAP).fillna("")

    present = set(summary["symbol"].astype(str)) if not summary.empty else set()
    missing = [symbol for symbol in symbols if symbol not in present]
    latest_by_symbol = {
        str(row["symbol"]): pd.to_datetime(row["latest_date"], errors="coerce").date()
        for _, row in summary.iterrows()
        if not pd.isna(pd.to_datetime(row["latest_date"], errors="coerce"))
    }
    covered = [symbol for symbol in symbols if latest_by_symbol.get(symbol) is not None and latest_by_symbol[symbol] >= cutoff]
    stale = [symbol for symbol in symbols if symbol in present and symbol not in covered]
    coverage = len(covered) / len(symbols) if symbols else 0.0
    total_rows = int(summary["rows"].sum()) if not summary.empty else 0
    first_date = str(summary["first_date"].min()) if not summary.empty else ""
    latest_date = str(summary["latest_date"].max()) if not summary.empty else ""

    lines = [
        "# HK Market History Batch Load Report",
        "",
        f"- Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Config: `{config_path}`",
        f"- Database: `{db_path}`",
        f"- Daily table: `{daily_table}`",
        f"- Audit table: `{audit_table}`",
        f"- Provider: `{hk_cfg.get('provider', 'N/A')}`",
        f"- Configured symbols: {len(symbols)}",
        f"- Covered symbols: {len(covered)}",
        f"- Coverage: {coverage:.4f}",
        f"- Date range: {first_date or 'N/A'} -> {latest_date or 'N/A'}",
        f"- Total rows in configured pool: {total_rows}",
        f"- Freshness cutoff: {cutoff.isoformat()}",
        "",
        "## Missing Or Stale Symbols",
        "",
        f"- Missing symbols: {', '.join(missing) if missing else 'None'}",
        f"- Stale symbols: {', '.join(stale) if stale else 'None'}",
        "",
        "## Symbol Coverage",
        "",
        _format_table(
            summary,
            ["symbol", "name_zh", "hk", "rows", "first_date", "latest_date", "min_close", "max_close", "avg_volume", "source"],
        ),
        "",
        "## Recent Audit Runs",
        "",
        _format_table(audit),
        "",
        "## First 10 Rows",
        "",
        _format_table(
            samples_head,
            ["symbol", "name_zh", "date", "open", "high", "low", "close", "adjusted_close", "volume", "source", "hk"],
        ),
        "",
        "## Latest 10 Rows",
        "",
        _format_table(
            samples_tail,
            ["symbol", "name_zh", "date", "open", "high", "low", "close", "adjusted_close", "volume", "source", "hk"],
        ),
        "",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export HK market history batch load report")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--output", default="reports/database_health/hk_market_history_batch_load_report.md", help="Output markdown report")
    args = parser.parse_args()
    report_path = build_report(Path(args.config).resolve(), Path(args.output))
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
