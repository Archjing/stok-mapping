from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from quant.reporting.paths import report_path


HISTORY_BACKFILL_SUMMARY_COLUMNS = [
    "run_started_at",
    "run_finished_at",
    "status",
    "start_date",
    "end_date",
    "limit_dates",
    "limit_periods",
    "skip_existing",
    "include_daily_basic",
    "include_adj_factor",
    "include_dividends",
    "include_financial",
    "max_requests_per_minute",
    "daily_basic_target_dates",
    "daily_basic_fetched_dates",
    "daily_basic_inserted_rows",
    "adj_factor_target_dates",
    "adj_factor_fetched_dates",
    "adj_factor_inserted_rows",
    "dividend_inserted_rows",
    "financial_target_periods",
    "financial_fetched_periods",
    "financial_inserted_rows",
    "warning_count",
    "detail_report_csv",
    "detail_report_md",
    "key_conclusion",
]

FINANCIAL_BACKFILL_DETAIL_COLUMNS = [
    "period",
    "target_symbols",
    "fetched_symbols",
    "empty_symbols",
    "failed_symbols",
    "pending_symbols",
    "factor_rows",
    "announce_date_coverage",
    "roe_coverage",
    "revenue_growth_coverage",
    "profit_growth_coverage",
    "cash_flow_quality_coverage",
    "debt_to_asset_coverage",
]

FINANCIAL_BACKFILL_SUMMARY_COLUMNS = [
    "run_started_at",
    "run_finished_at",
    "status",
    "start_period",
    "end_period",
    "single_period",
    "shard_index",
    "shard_count",
    "retry_failed",
    "replace_existing",
    "limit_symbols",
    "limit_tasks",
    "max_runtime_minutes",
    "max_requests_per_minute",
    "target_tasks",
    "processed_tasks",
    "fetched_tasks",
    "empty_tasks",
    "failed_tasks",
    "inserted_rows",
    "warning_count",
    "detail_report_csv",
    "detail_report_md",
    "key_conclusion",
]


def _date_dir(root: Path) -> Path:
    return report_path(root=root, category="database_health", parts=(datetime.now().date().isoformat(),))


def _short_date_tag() -> str:
    return datetime.now().strftime("%y%m%d")


def _compact_date_tag(value: str) -> str:
    return value.replace("-", "")


def history_audit_paths(root: Path, *, start_date: str, end_date: str) -> tuple[Path, Path, Path, Path]:
    date_dir = _date_dir(root)
    date_tag = _short_date_tag()
    range_tag = f"{_compact_date_tag(start_date)}_{_compact_date_tag(end_date)}"
    detail_csv = date_dir / f"tushare_history_backfill_audit_{date_tag}_{range_tag}.csv"
    detail_md = date_dir / f"tushare_history_backfill_audit_{date_tag}_{range_tag}.md"
    summary_csv = report_path(root=root, category="database_health", parts=("tushare_history_backfill_audit_summary.csv",))
    summary_md = report_path(root=root, category="database_health", parts=("tushare_history_backfill_audit_summary.md",))
    return detail_csv, detail_md, summary_csv, summary_md


def financial_audit_paths(
    root: Path,
    *,
    start_period: str,
    end_period: str,
    period: str | None,
) -> tuple[Path, Path, Path, Path]:
    date_dir = _date_dir(root)
    date_tag = _short_date_tag()
    if period:
        range_tag = _compact_date_tag(period)
    else:
        range_tag = f"{_compact_date_tag(start_period)}_{_compact_date_tag(end_period)}"
    detail_csv = date_dir / f"tushare_financial_backfill_audit_{date_tag}_{range_tag}.csv"
    detail_md = date_dir / f"tushare_financial_backfill_audit_{date_tag}_{range_tag}.md"
    summary_csv = report_path(root=root, category="database_health", parts=("tushare_financial_backfill_audit_summary.csv",))
    summary_md = report_path(root=root, category="database_health", parts=("tushare_financial_backfill_audit_summary.md",))
    return detail_csv, detail_md, summary_csv, summary_md


def write_history_detail_audit(*, audit: pd.DataFrame, output_csv: Path, output_md: Path, warnings: list[str]) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output_csv, index=False)
    lines = [
        "# Tushare 历史数据补全验收报告",
        "",
        "## 覆盖率汇总",
        "",
        "| table | field | start_date | end_date | rows | non_null_ratio |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for _, row in audit.iterrows():
        lines.append(
            f"| {row['table']} | {row['field']} | {row.get('start_date') or ''} | {row.get('end_date') or ''} | "
            f"{int(row.get('rows') or 0)} | {float(row.get('non_null_ratio') or 0.0):.4f} |"
        )
    lines.extend(["", "## Warnings", ""])
    if warnings:
        lines.extend([f"- {item}" for item in warnings])
    else:
        lines.append("- 无。")
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_summary_row(
    *,
    summary_csv: Path,
    summary_md: Path,
    columns: list[str],
    row: dict[str, Any],
    title: str,
    warnings: list[str],
    coverage_columns: set[str] | None = None,
) -> None:
    coverage_columns = coverage_columns or set()
    summary_csv.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([row])
    for column in columns:
        if column not in frame.columns:
            frame[column] = ""
    frame = frame[columns]
    if summary_csv.exists():
        existing = pd.read_csv(summary_csv)
        for column in columns:
            if column not in existing.columns:
                existing[column] = ""
        existing = existing[columns]
        full = pd.concat([existing, frame], ignore_index=True)
    else:
        full = frame
    full.to_csv(summary_csv, index=False)

    lines = [
        title,
        "",
        "## 历次运行汇总",
        "",
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, one_row in full.iterrows():
        values = []
        for column in columns:
            value = one_row.get(column)
            if column in coverage_columns and pd.notna(value):
                values.append(f"{float(value) * 100:.2f}%")
            elif isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value if pd.notna(value) else ""))
        lines.append("| " + " | ".join(values) + " |")
    lines.extend(["", "## Latest Warnings", ""])
    if warnings:
        lines.extend([f"- {item}" for item in warnings])
    else:
        lines.append("- 无。")
    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_financial_backfill_audit(
    *,
    audit: pd.DataFrame,
    output_csv: Path,
    output_md: Path,
    warnings: list[str],
) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    audit = audit.copy()
    for column in FINANCIAL_BACKFILL_DETAIL_COLUMNS:
        if column not in audit.columns:
            audit[column] = ""
    audit = audit[FINANCIAL_BACKFILL_DETAIL_COLUMNS]
    audit.to_csv(output_csv, index=False)
    coverage_columns = {
        "announce_date_coverage",
        "roe_coverage",
        "revenue_growth_coverage",
        "profit_growth_coverage",
        "cash_flow_quality_coverage",
        "debt_to_asset_coverage",
    }
    columns = FINANCIAL_BACKFILL_DETAIL_COLUMNS
    lines = [
        "# Tushare 财务因子逐股票回填验收报告",
        "",
        "## 当次运行明细",
        "",
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in audit.iterrows():
        values = []
        for col in columns:
            value = row.get(col)
            if col in coverage_columns and pd.notna(value):
                values.append(f"{float(value) * 100:.2f}%")
            elif isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value if pd.notna(value) else ""))
        lines.append("| " + " | ".join(values) + " |")
    lines.extend(["", "## Warnings", ""])
    if warnings:
        lines.extend([f"- {warning}" for warning in warnings])
    else:
        lines.append("- 无。")
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def history_summary_row(
    *,
    status: str,
    start_date: str,
    end_date: str,
    limit_dates: int | None,
    limit_periods: int | None,
    skip_existing: bool,
    include_daily_basic: bool,
    include_adj_factor: bool,
    include_dividends: bool,
    include_financial: bool,
    max_requests_per_minute: int,
    daily_basic_target_dates: int,
    daily_basic_fetched_dates: int,
    daily_basic_inserted_rows: int,
    adj_factor_target_dates: int,
    adj_factor_fetched_dates: int,
    adj_factor_inserted_rows: int,
    dividend_inserted_rows: int,
    financial_target_periods: int,
    financial_fetched_periods: int,
    financial_inserted_rows: int,
    warnings: list[str],
    detail_csv: Path,
    detail_md: Path,
    run_started_at: str,
) -> dict[str, Any]:
    return {
        "run_started_at": run_started_at,
        "run_finished_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "start_date": start_date,
        "end_date": end_date,
        "limit_dates": limit_dates if limit_dates is not None else "",
        "limit_periods": limit_periods if limit_periods is not None else "",
        "skip_existing": skip_existing,
        "include_daily_basic": include_daily_basic,
        "include_adj_factor": include_adj_factor,
        "include_dividends": include_dividends,
        "include_financial": include_financial,
        "max_requests_per_minute": max_requests_per_minute,
        "daily_basic_target_dates": daily_basic_target_dates,
        "daily_basic_fetched_dates": daily_basic_fetched_dates,
        "daily_basic_inserted_rows": daily_basic_inserted_rows,
        "adj_factor_target_dates": adj_factor_target_dates,
        "adj_factor_fetched_dates": adj_factor_fetched_dates,
        "adj_factor_inserted_rows": adj_factor_inserted_rows,
        "dividend_inserted_rows": dividend_inserted_rows,
        "financial_target_periods": financial_target_periods,
        "financial_fetched_periods": financial_fetched_periods,
        "financial_inserted_rows": financial_inserted_rows,
        "warning_count": len(warnings),
        "detail_report_csv": str(detail_csv),
        "detail_report_md": str(detail_md),
        "key_conclusion": (
            f"daily_basic {daily_basic_fetched_dates}/{daily_basic_target_dates}, "
            f"adj_factor {adj_factor_fetched_dates}/{adj_factor_target_dates}, "
            f"financial {financial_fetched_periods}/{financial_target_periods}, "
            f"warnings={len(warnings)}"
        ),
    }


def financial_summary_row(
    *,
    status: str,
    start_period: str,
    end_period: str,
    single_period: str,
    shard_index: int,
    shard_count: int,
    retry_failed: bool,
    replace_existing: bool,
    limit_symbols: int | None,
    limit_tasks: int | None,
    max_runtime_minutes: int | None,
    max_requests_per_minute: int,
    target_tasks: int,
    processed_tasks: int,
    fetched_tasks: int,
    empty_tasks: int,
    failed_tasks: int,
    inserted_rows: int,
    warnings: list[str],
    detail_csv: Path,
    detail_md: Path,
    run_started_at: str,
) -> dict[str, Any]:
    range_label = single_period or f"{start_period}..{end_period}"
    return {
        "run_started_at": run_started_at,
        "run_finished_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "start_period": start_period,
        "end_period": end_period,
        "single_period": single_period,
        "shard_index": shard_index,
        "shard_count": shard_count,
        "retry_failed": retry_failed,
        "replace_existing": replace_existing,
        "limit_symbols": limit_symbols if limit_symbols is not None else "",
        "limit_tasks": limit_tasks if limit_tasks is not None else "",
        "max_runtime_minutes": max_runtime_minutes if max_runtime_minutes is not None else "",
        "max_requests_per_minute": max_requests_per_minute,
        "target_tasks": target_tasks,
        "processed_tasks": processed_tasks,
        "fetched_tasks": fetched_tasks,
        "empty_tasks": empty_tasks,
        "failed_tasks": failed_tasks,
        "inserted_rows": inserted_rows,
        "warning_count": len(warnings),
        "detail_report_csv": str(detail_csv),
        "detail_report_md": str(detail_md),
        "key_conclusion": (
            f"{range_label} shard {shard_index}/{shard_count}, "
            f"processed={processed_tasks}, fetched={fetched_tasks}, "
            f"failed={failed_tasks}, inserted_rows={inserted_rows}, warnings={len(warnings)}"
        ),
    }
