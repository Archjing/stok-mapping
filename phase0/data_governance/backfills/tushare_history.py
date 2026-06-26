from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from phase0.data_governance.adjustment import ensure_adj_factor_table, upsert_adj_factors
from phase0.config import load_config
from phase0.data_governance.backfills.adjustment import ensure_dividend_table, upsert_dividends
from phase0.data_governance.backfills.tushare_financial_rows import (
    financial_non_null_count as _financial_non_null_count,
    merge_financial_missing_fields as _merge_financial_missing_fields,
    replace_financial_rows as _replace_financial_rows,
    upsert_financial_row_preserving_valid as _upsert_financial_row_preserving_valid,
)
from phase0.data_governance.backfills.tushare_financial_tasks import (
    FINANCIAL_FIELD_INTERFACES,
    ensure_financial_backfill_task_table as _ensure_financial_backfill_task_table,
    ensure_financial_missing_field_task_table as _ensure_financial_missing_field_task_table,
    has_existing_valid_financial_row as _has_existing_valid_financial_row,
    initialize_financial_backfill_tasks as _initialize_financial_backfill_tasks,
    initialize_financial_missing_field_tasks as _initialize_financial_missing_field_tasks,
    interfaces_for_missing_fields as _interfaces_for_missing_fields,
    load_symbols_for_period as _load_symbols_for_period,
    mark_financial_missing_field_task as _mark_financial_missing_field_task,
    mark_financial_task as _mark_financial_task,
    normalize_missing_fields as _normalize_missing_fields,
    select_financial_backfill_tasks as _select_financial_backfill_tasks,
    select_financial_missing_field_tasks as _select_financial_missing_field_tasks,
)
from phase0.data_governance.backfills.tushare_history_audit_queries import (
    coverage_audit as _coverage_audit,
    financial_backfill_audit as _financial_backfill_audit,
)
from phase0.data_governance.backfills.tushare_history_reports import (
    FINANCIAL_BACKFILL_DETAIL_COLUMNS,
    FINANCIAL_BACKFILL_SUMMARY_COLUMNS,
    HISTORY_BACKFILL_SUMMARY_COLUMNS,
    append_summary_row as _append_summary_row,
    financial_audit_paths as _financial_audit_paths,
    financial_summary_row as _financial_summary_row,
    history_audit_paths as _history_audit_paths,
    history_summary_row as _history_summary_row,
    write_financial_backfill_audit as _write_financial_backfill_audit,
    write_history_detail_audit as _write_history_detail_audit,
)
from phase0.data_governance.daily_basic import ensure_daily_basic_table, upsert_daily_basic_rows
from phase0.data_governance.financial_factors import ensure_financial_factor_table
from phase0.data_governance.sql import safe_identifier
from phase0.data_access.providers.tushare import (
    fetch_tushare_adj_factor_trade_date,
    fetch_tushare_daily_basic_trade_date,
    fetch_tushare_dividend,
    fetch_tushare_financial_period,
    tushare_available,
    tushare_config,
)

_safe_identifier = safe_identifier
_ensure_daily_basic_table = ensure_daily_basic_table
_upsert_daily_basic_rows = upsert_daily_basic_rows


@dataclass(frozen=True)
class TushareHistoryBackfillResult:
    db_path: Path
    start_date: str
    end_date: str
    status: str
    daily_basic_target_dates: int
    daily_basic_fetched_dates: int
    daily_basic_inserted_rows: int
    adj_factor_target_dates: int
    adj_factor_fetched_dates: int
    adj_factor_inserted_rows: int
    dividend_inserted_rows: int
    financial_target_periods: int
    financial_fetched_periods: int
    financial_inserted_rows: int
    audit_csv: Path
    audit_md: Path
    warnings: list[str]


@dataclass(frozen=True)
class TushareFinancialBackfillResult:
    db_path: Path
    start_period: str
    end_period: str
    status: str
    target_tasks: int
    processed_tasks: int
    fetched_tasks: int
    empty_tasks: int
    failed_tasks: int
    inserted_rows: int
    audit_csv: Path
    audit_md: Path
    warnings: list[str]


def _load_open_dates(conn: sqlite3.Connection, *, calendar_table: str, start_date: str, end_date: str) -> list[str]:
    table = _safe_identifier(calendar_table)
    df = pd.read_sql_query(
        f"""
        SELECT date
        FROM {table}
        WHERE is_open = 1
          AND date >= ?
          AND date <= ?
        ORDER BY date
        """,
        conn,
        params=(start_date, end_date),
    )
    return [str(value) for value in df["date"].dropna().tolist()]


def _existing_dates(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    start_date: str,
    end_date: str,
    date_column: str = "date",
) -> set[str]:
    table = _safe_identifier(table_name)
    column = _safe_identifier(date_column)
    df = pd.read_sql_query(
        f"""
        SELECT DISTINCT {column} AS date
        FROM {table}
        WHERE market = 'CN'
          AND {column} >= ?
          AND {column} <= ?
        """,
        conn,
        params=(start_date, end_date),
    )
    return {str(value)[:10] for value in df["date"].dropna().tolist()}


def _quarter_periods(start_date: str, end_date: str) -> list[str]:
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    periods: list[str] = []
    for year in range(start.year, end.year + 1):
        for month_day in ["03-31", "06-30", "09-30", "12-31"]:
            period = pd.Timestamp(f"{year}-{month_day}")
            if start <= period <= end:
                periods.append(period.date().isoformat())
    return periods


def _load_symbols(conn: sqlite3.Connection, *, meta_table: str, markets: set[str]) -> list[str]:
    table = _safe_identifier(meta_table)
    df = pd.read_sql_query(
        f"""
        SELECT DISTINCT symbol
        FROM {table}
        WHERE market = 'CN'
          AND symbol IS NOT NULL
        ORDER BY symbol
        """,
        conn,
    )
    symbols = [str(value) for value in df["symbol"].dropna().tolist()]
    if markets:
        symbols = [symbol for symbol in symbols if symbol.split(".")[0] in markets]
    return symbols


def _sleep_for_rate(last_request_at: float, max_requests_per_minute: int) -> float:
    min_interval = 60.0 / max(1, int(max_requests_per_minute))
    now = time.monotonic()
    sleep_for = min_interval - (now - last_request_at)
    if sleep_for > 0:
        time.sleep(sleep_for)
    return time.monotonic()


def backfill_tushare_financials_from_config(
    config_path: Path,
    *,
    start_period: str = "2016-03-31",
    end_period: str = "2018-03-31",
    period: str | None = None,
    max_requests_per_minute: int = 120,
    max_runtime_minutes: int | None = None,
    limit_symbols: int | None = None,
    limit_tasks: int | None = None,
    retry_failed: bool = False,
    replace_existing: bool = False,
    missing_fields_only: bool = False,
    missing_fields: list[str] | tuple[str, ...] | set[str] | None = None,
    shard_index: int = 0,
    shard_count: int = 1,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    progress_interval_seconds: float = 30.0,
) -> TushareFinancialBackfillResult:
    root = config_path.parent
    cfg = load_config(config_path)
    local_cfg = cfg.get("local_history", {})
    data_cfg = cfg.get("data_sources", {})
    tcfg = tushare_config(data_cfg.get("tushare", {}))
    db_path = Path(local_cfg.get("path", "data/manual_history/a_share_history.sqlite"))
    if not db_path.is_absolute():
        db_path = root / db_path
    meta_table = str(local_cfg.get("meta_table", "market_stocks"))
    financial_table = str(local_cfg.get("financial_table", "market_financial_factors"))
    task_table = "tushare_financial_missing_field_tasks" if missing_fields_only else "tushare_financial_backfill_tasks"
    output_csv, output_md, summary_csv, summary_md = _financial_audit_paths(
        root,
        start_period=start_period,
        end_period=end_period,
        period=period,
    )
    warnings: list[str] = []
    periods = [period] if period else _quarter_periods(start_period, end_period)
    if not periods:
        periods = [start_period]
    missing_field_list = _normalize_missing_fields(missing_fields) if missing_fields_only else []
    markets = {str(item) for item in cfg.get("universe", {}).get("markets", ["SH", "SZ"])}
    run_started_at = datetime.now().isoformat(timespec="seconds")

    if not tushare_available(tcfg):
        warnings.append(f"Tushare token env {tcfg.token_env} is not available.")
        with sqlite3.connect(db_path) as conn:
            if missing_fields_only:
                _ensure_financial_missing_field_task_table(conn, table_name=task_table)
            else:
                _ensure_financial_backfill_task_table(conn, table_name=task_table)
            ensure_financial_factor_table(conn, table=financial_table)
            audit = _financial_backfill_audit(conn, task_table=task_table, financial_table=financial_table, periods=periods)
        _write_financial_backfill_audit(audit=audit, output_csv=output_csv, output_md=output_md, warnings=warnings)
        _append_summary_row(
            summary_csv=summary_csv,
            summary_md=summary_md,
            columns=FINANCIAL_BACKFILL_SUMMARY_COLUMNS,
            row=_financial_summary_row(
                status="missing_tushare_token",
                start_period=start_period,
                end_period=end_period,
                single_period=period or "",
                shard_index=shard_index,
                shard_count=shard_count,
                retry_failed=retry_failed,
                replace_existing=replace_existing,
                limit_symbols=limit_symbols,
                limit_tasks=limit_tasks,
                max_runtime_minutes=max_runtime_minutes,
                max_requests_per_minute=max_requests_per_minute,
                target_tasks=0,
                processed_tasks=0,
                fetched_tasks=0,
                empty_tasks=0,
                failed_tasks=0,
                inserted_rows=0,
                warnings=warnings,
                detail_csv=output_csv,
                detail_md=output_md,
                run_started_at=run_started_at,
            ),
            title="# Tushare 财务因子逐股票回填汇总报告",
            warnings=warnings,
        )
        return TushareFinancialBackfillResult(
            db_path=db_path,
            start_period=start_period,
            end_period=end_period,
            status="missing_tushare_token",
            target_tasks=0,
            processed_tasks=0,
            fetched_tasks=0,
            empty_tasks=0,
            failed_tasks=0,
            inserted_rows=0,
            audit_csv=output_csv,
            audit_md=output_md,
            warnings=warnings,
        )

    processed = 0
    fetched = 0
    empty = 0
    failed = 0
    inserted_rows = 0
    last_request_at = 0.0
    start_time = time.monotonic()
    last_progress_at = start_time
    max_runtime_seconds = None if max_runtime_minutes is None or max_runtime_minutes <= 0 else float(max_runtime_minutes) * 60.0

    def emit_progress(event: str, target_tasks: int, *, force: bool = False) -> None:
        nonlocal last_progress_at
        if progress_callback is None:
            return
        now = time.monotonic()
        if not force and progress_interval_seconds > 0 and now - last_progress_at < progress_interval_seconds:
            return
        progress_callback(
            {
                "event": event,
                "target_tasks": target_tasks,
                "processed_tasks": processed,
                "fetched_tasks": fetched,
                "empty_tasks": empty,
                "failed_tasks": failed,
                "inserted_rows": inserted_rows,
                "elapsed_seconds": now - start_time,
            }
        )
        last_progress_at = now

    with sqlite3.connect(db_path) as conn:
        if missing_fields_only:
            _ensure_financial_missing_field_task_table(conn, table_name=task_table)
        else:
            _ensure_financial_backfill_task_table(conn, table_name=task_table)
        ensure_financial_factor_table(conn, table=financial_table)
        if missing_fields_only:
            _initialize_financial_missing_field_tasks(
                conn,
                task_table=task_table,
                financial_table=financial_table,
                periods=periods,
                fields=missing_field_list,
                limit_symbols=limit_symbols,
            )
        else:
            _initialize_financial_backfill_tasks(
                conn,
                task_table=task_table,
                financial_table=financial_table,
                meta_table=meta_table,
                periods=periods,
                markets=markets,
                replace_existing=replace_existing,
                limit_symbols=limit_symbols,
            )
        conn.commit()
        if missing_fields_only:
            tasks = _select_financial_missing_field_tasks(
                conn,
                task_table=task_table,
                periods=periods,
                retry_failed=retry_failed,
                shard_index=shard_index,
                shard_count=shard_count,
                limit_tasks=limit_tasks,
            )
        else:
            tasks = _select_financial_backfill_tasks(
                conn,
                task_table=task_table,
                periods=periods,
                retry_failed=retry_failed,
                shard_index=shard_index,
                shard_count=shard_count,
                limit_tasks=limit_tasks,
            )
        target_tasks = int(len(tasks))
        emit_progress("start", target_tasks, force=True)
        for task in tasks.itertuples(index=False):
            if max_runtime_seconds is not None and time.monotonic() - start_time >= max_runtime_seconds:
                warnings.append(f"max runtime reached after {processed} tasks")
                break
            task_period = str(task.period)
            symbol = str(task.symbol)
            task_missing_fields = (
                [field for field in str(getattr(task, "missing_fields", "")).split(",") if field]
                if missing_fields_only
                else []
            )
            task_interfaces = (
                {value for value in str(getattr(task, "interfaces", "")).split(",") if value}
                if missing_fields_only
                else None
            )
            try:
                last_request_at = _sleep_for_rate(last_request_at, max_requests_per_minute)
                rows = fetch_tushare_financial_period(
                    pd.Timestamp(task_period).date(),
                    cfg=tcfg,
                    ts_code=symbol,
                    interfaces=task_interfaces,
                )
            except Exception as exc:
                failed += 1
                processed += 1
                if missing_fields_only:
                    _mark_financial_missing_field_task(
                        conn,
                        task_table=task_table,
                        period=task_period,
                        symbol=symbol,
                        status="failed",
                        error=str(exc),
                    )
                else:
                    _mark_financial_task(
                        conn,
                        task_table=task_table,
                        period=task_period,
                        symbol=symbol,
                        status="failed",
                        error=str(exc),
                    )
                conn.commit()
                emit_progress("progress", target_tasks, force=processed >= target_tasks)
                continue
            processed += 1
            if rows.empty or rows.apply(_financial_non_null_count, axis=1).max() == 0:
                empty += 1
                if missing_fields_only:
                    _mark_financial_missing_field_task(
                        conn,
                        task_table=task_table,
                        period=task_period,
                        symbol=symbol,
                        status="empty",
                        missing_fields=task_missing_fields,
                    )
                else:
                    _mark_financial_task(conn, task_table=task_table, period=task_period, symbol=symbol, status="empty")
                conn.commit()
                emit_progress("progress", target_tasks, force=processed >= target_tasks)
                continue
            row = rows.iloc[0]
            if missing_fields_only:
                before = pd.read_sql_query(
                    f"""
                    SELECT {", ".join(_safe_identifier(field) for field in task_missing_fields)}
                    FROM {_safe_identifier(financial_table)}
                    WHERE market = 'CN'
                      AND symbol = ?
                      AND report_date = ?
                    """,
                    conn,
                    params=(symbol, task_period),
                )
                inserted_rows += _merge_financial_missing_fields(
                    conn,
                    table_name=financial_table,
                    row=row,
                    fields=task_missing_fields,
                )
                after = pd.read_sql_query(
                    f"""
                    SELECT {", ".join(_safe_identifier(field) for field in task_missing_fields)}
                    FROM {_safe_identifier(financial_table)}
                    WHERE market = 'CN'
                      AND symbol = ?
                      AND report_date = ?
                    """,
                    conn,
                    params=(symbol, task_period),
                )
                remaining_missing = task_missing_fields
                if not after.empty:
                    remaining_missing = [field for field in task_missing_fields if pd.isna(after.iloc[0].get(field))]
                if before.empty:
                    empty += 1
                    _mark_financial_missing_field_task(
                        conn,
                        task_table=task_table,
                        period=task_period,
                        symbol=symbol,
                        status="empty",
                        missing_fields=remaining_missing,
                    )
                elif remaining_missing:
                    before_missing = sum(1 for field in task_missing_fields if pd.isna(before.iloc[0].get(field)))
                    after_missing = sum(1 for field in task_missing_fields if pd.isna(after.iloc[0].get(field)))
                    if after_missing < before_missing:
                        fetched += 1
                        _mark_financial_missing_field_task(
                            conn,
                            task_table=task_table,
                            period=task_period,
                            symbol=symbol,
                            status="pending",
                            missing_fields=remaining_missing,
                        )
                    else:
                        empty += 1
                        _mark_financial_missing_field_task(
                            conn,
                            task_table=task_table,
                            period=task_period,
                            symbol=symbol,
                            status="empty",
                            missing_fields=remaining_missing,
                        )
                else:
                    fetched += 1
                    _mark_financial_missing_field_task(
                        conn,
                        task_table=task_table,
                        period=task_period,
                        symbol=symbol,
                        status="fetched",
                        missing_fields=[],
                    )
            else:
                inserted_rows += _upsert_financial_row_preserving_valid(
                    conn,
                    table_name=financial_table,
                    row=row,
                    replace_existing=replace_existing,
                )
                fetched += 1
                _mark_financial_task(conn, task_table=task_table, period=task_period, symbol=symbol, status="fetched")
            conn.commit()
            emit_progress("progress", target_tasks, force=processed >= target_tasks)
        audit = _financial_backfill_audit(conn, task_table=task_table, financial_table=financial_table, periods=periods)

    status = "ok" if not warnings and failed == 0 else "ok_with_warnings"
    _write_financial_backfill_audit(audit=audit, output_csv=output_csv, output_md=output_md, warnings=warnings)
    _append_summary_row(
        summary_csv=summary_csv,
        summary_md=summary_md,
        columns=FINANCIAL_BACKFILL_SUMMARY_COLUMNS,
        row=_financial_summary_row(
            status=status,
            start_period=start_period,
            end_period=end_period,
            single_period=period or "",
            shard_index=shard_index,
            shard_count=shard_count,
            retry_failed=retry_failed,
            replace_existing=replace_existing,
            limit_symbols=limit_symbols,
            limit_tasks=limit_tasks,
            max_runtime_minutes=max_runtime_minutes,
            max_requests_per_minute=max_requests_per_minute,
            target_tasks=target_tasks if "target_tasks" in locals() else 0,
            processed_tasks=processed,
            fetched_tasks=fetched,
            empty_tasks=empty,
            failed_tasks=failed,
            inserted_rows=inserted_rows,
            warnings=warnings,
            detail_csv=output_csv,
            detail_md=output_md,
            run_started_at=run_started_at,
        ),
        title="# Tushare 财务因子逐股票回填汇总报告",
        warnings=warnings,
    )
    return TushareFinancialBackfillResult(
        db_path=db_path,
        start_period=start_period,
        end_period=end_period,
        status=status,
        target_tasks=target_tasks if "target_tasks" in locals() else 0,
        processed_tasks=processed,
        fetched_tasks=fetched,
        empty_tasks=empty,
        failed_tasks=failed,
        inserted_rows=inserted_rows,
        audit_csv=output_csv,
        audit_md=output_md,
        warnings=warnings,
    )


def backfill_tushare_history_from_config(
    config_path: Path,
    *,
    start_date: str,
    end_date: str,
    max_requests_per_minute: int = 180,
    limit_dates: int | None = None,
    limit_periods: int | None = None,
    skip_existing: bool = True,
    include_daily_basic: bool = True,
    include_adj_factor: bool = True,
    include_dividends: bool = True,
    include_financial: bool = True,
) -> TushareHistoryBackfillResult:
    root = config_path.parent
    cfg = load_config(config_path)
    local_cfg = cfg.get("local_history", {})
    data_cfg = cfg.get("data_sources", {})
    tcfg = tushare_config(data_cfg.get("tushare", {}))
    db_path = Path(local_cfg.get("path", "data/manual_history/a_share_history.sqlite"))
    if not db_path.is_absolute():
        db_path = root / db_path
    calendar_table = str(local_cfg.get("calendar_table", "trading_calendar"))
    daily_basic_table = str(local_cfg.get("daily_basic_table", "market_daily_basic"))
    meta_table = str(local_cfg.get("meta_table", "market_stocks"))
    adj_factor_table = str(local_cfg.get("adj_factor_table", "market_adj_factors"))
    dividend_table = str(local_cfg.get("dividend_table", "market_dividends"))
    financial_table = str(local_cfg.get("financial_table", "market_financial_factors"))
    warnings: list[str] = []

    output_csv, output_md, summary_csv, summary_md = _history_audit_paths(
        root,
        start_date=start_date,
        end_date=end_date,
    )
    run_started_at = datetime.now().isoformat(timespec="seconds")
    if not tushare_available(tcfg):
        warnings.append(f"Tushare token env {tcfg.token_env} is not available.")
        with sqlite3.connect(db_path) as conn:
            audit = _coverage_audit(conn, local_cfg=local_cfg, start_date=start_date, end_date=end_date)
        _write_history_detail_audit(audit=audit, output_csv=output_csv, output_md=output_md, warnings=warnings)
        _append_summary_row(
            summary_csv=summary_csv,
            summary_md=summary_md,
            columns=HISTORY_BACKFILL_SUMMARY_COLUMNS,
            row=_history_summary_row(
                status="missing_tushare_token",
                start_date=start_date,
                end_date=end_date,
                limit_dates=limit_dates,
                limit_periods=limit_periods,
                skip_existing=skip_existing,
                include_daily_basic=include_daily_basic,
                include_adj_factor=include_adj_factor,
                include_dividends=include_dividends,
                include_financial=include_financial,
                max_requests_per_minute=max_requests_per_minute,
                daily_basic_target_dates=0,
                daily_basic_fetched_dates=0,
                daily_basic_inserted_rows=0,
                adj_factor_target_dates=0,
                adj_factor_fetched_dates=0,
                adj_factor_inserted_rows=0,
                dividend_inserted_rows=0,
                financial_target_periods=0,
                financial_fetched_periods=0,
                financial_inserted_rows=0,
                warnings=warnings,
                detail_csv=output_csv,
                detail_md=output_md,
                run_started_at=run_started_at,
            ),
            title="# Tushare 历史数据补全汇总报告",
            warnings=warnings,
        )
        return TushareHistoryBackfillResult(
            db_path=db_path,
            start_date=start_date,
            end_date=end_date,
            status="missing_tushare_token",
            daily_basic_target_dates=0,
            daily_basic_fetched_dates=0,
            daily_basic_inserted_rows=0,
            adj_factor_target_dates=0,
            adj_factor_fetched_dates=0,
            adj_factor_inserted_rows=0,
            dividend_inserted_rows=0,
            financial_target_periods=0,
            financial_fetched_periods=0,
            financial_inserted_rows=0,
            audit_csv=output_csv,
            audit_md=output_md,
            warnings=warnings,
        )

    daily_basic_fetched = 0
    daily_basic_inserted = 0
    adj_factor_fetched = 0
    adj_factor_inserted = 0
    dividend_inserted = 0
    financial_fetched = 0
    financial_inserted = 0
    last_request_at = 0.0

    with sqlite3.connect(db_path) as conn:
        _ensure_daily_basic_table(conn, table_name=daily_basic_table)
        ensure_adj_factor_table(conn, adj_factor_table)
        ensure_dividend_table(conn, table_name=dividend_table)
        ensure_financial_factor_table(conn, table=financial_table)
        open_dates = _load_open_dates(conn, calendar_table=calendar_table, start_date=start_date, end_date=end_date)
        existing_basic = _existing_dates(conn, table_name=daily_basic_table, start_date=start_date, end_date=end_date)
        existing_adj = _existing_dates(conn, table_name=adj_factor_table, start_date=start_date, end_date=end_date)
        pending_basic = [value for value in open_dates if include_daily_basic and (not skip_existing or value not in existing_basic)]
        pending_adj = [value for value in open_dates if include_adj_factor and (not skip_existing or value not in existing_adj)]
        if limit_dates is not None and limit_dates > 0:
            pending_basic = pending_basic[: int(limit_dates)]
            pending_adj = pending_adj[: int(limit_dates)]

        for one_date in pending_basic:
            try:
                last_request_at = _sleep_for_rate(last_request_at, max_requests_per_minute)
                rows = fetch_tushare_daily_basic_trade_date(pd.Timestamp(one_date).date(), cfg=tcfg)
            except Exception as exc:
                warnings.append(f"{one_date}: daily_basic failed: {exc}")
                continue
            if rows.empty:
                warnings.append(f"{one_date}: daily_basic returned empty")
                continue
            daily_basic_inserted += _upsert_daily_basic_rows(conn, table_name=daily_basic_table, rows=rows)
            daily_basic_fetched += 1
            conn.commit()

        for one_date in pending_adj:
            try:
                last_request_at = _sleep_for_rate(last_request_at, max_requests_per_minute)
                rows = fetch_tushare_adj_factor_trade_date(pd.Timestamp(one_date).date(), cfg=tcfg)
            except Exception as exc:
                warnings.append(f"{one_date}: adj_factor failed: {exc}")
                continue
            if rows.empty:
                warnings.append(f"{one_date}: adj_factor returned empty")
                continue
            adj_factor_inserted += upsert_adj_factors(conn, rows, table=adj_factor_table, source="tushare.adj_factor")
            adj_factor_fetched += 1
            conn.commit()

        if include_dividends:
            try:
                last_request_at = _sleep_for_rate(last_request_at, max_requests_per_minute)
                dividends = fetch_tushare_dividend(start_date=start_date, end_date=end_date, cfg=tcfg)
                dividend_inserted = upsert_dividends(conn, dividends, table_name=dividend_table)
                conn.commit()
            except Exception as exc:
                warnings.append(f"dividend failed: {exc}")

        periods = _quarter_periods(start_date, end_date)
        markets = {str(item) for item in cfg.get("universe", {}).get("markets", ["SH", "SZ"])}
        symbols = _load_symbols(conn, meta_table=meta_table, markets=markets)
        existing_periods = _existing_dates(
            conn,
            table_name=financial_table,
            start_date=start_date,
            end_date=end_date,
            date_column="report_date",
        )
        pending_periods = [value for value in periods if include_financial and (not skip_existing or value not in existing_periods)]
        if limit_periods is not None and limit_periods > 0:
            pending_periods = pending_periods[: int(limit_periods)]
        for period in pending_periods:
            period_frames: list[pd.DataFrame] = []
            failed_symbols = 0
            for symbol in symbols:
                try:
                    last_request_at = _sleep_for_rate(last_request_at, max_requests_per_minute)
                    one_symbol = fetch_tushare_financial_period(pd.Timestamp(period).date(), cfg=tcfg, ts_code=symbol)
                except Exception as exc:
                    failed_symbols += 1
                    if failed_symbols <= 5:
                        warnings.append(f"{period} {symbol}: financial factors failed: {exc}")
                    continue
                if not one_symbol.empty:
                    period_frames.append(one_symbol)
            if not period_frames:
                warnings.append(f"{period}: financial factors returned empty for {len(symbols)} symbols")
                continue
            rows = pd.concat(period_frames, ignore_index=True)
            financial_inserted += _replace_financial_rows(conn, table_name=financial_table, rows=rows)
            financial_fetched += 1
            conn.commit()

        audit = _coverage_audit(conn, local_cfg=local_cfg, start_date=start_date, end_date=end_date)

    status = "ok" if not warnings else "ok_with_warnings"
    _write_history_detail_audit(audit=audit, output_csv=output_csv, output_md=output_md, warnings=warnings)
    _append_summary_row(
        summary_csv=summary_csv,
        summary_md=summary_md,
        columns=HISTORY_BACKFILL_SUMMARY_COLUMNS,
        row=_history_summary_row(
            status=status,
            start_date=start_date,
            end_date=end_date,
            limit_dates=limit_dates,
            limit_periods=limit_periods,
            skip_existing=skip_existing,
            include_daily_basic=include_daily_basic,
            include_adj_factor=include_adj_factor,
            include_dividends=include_dividends,
            include_financial=include_financial,
            max_requests_per_minute=max_requests_per_minute,
            daily_basic_target_dates=len(open_dates) if "open_dates" in locals() else 0,
            daily_basic_fetched_dates=daily_basic_fetched,
            daily_basic_inserted_rows=daily_basic_inserted,
            adj_factor_target_dates=len(open_dates) if "open_dates" in locals() else 0,
            adj_factor_fetched_dates=adj_factor_fetched,
            adj_factor_inserted_rows=adj_factor_inserted,
            dividend_inserted_rows=dividend_inserted,
            financial_target_periods=len(periods) if "periods" in locals() else 0,
            financial_fetched_periods=financial_fetched,
            financial_inserted_rows=financial_inserted,
            warnings=warnings,
            detail_csv=output_csv,
            detail_md=output_md,
            run_started_at=run_started_at,
        ),
        title="# Tushare 历史数据补全汇总报告",
        warnings=warnings,
    )
    return TushareHistoryBackfillResult(
        db_path=db_path,
        start_date=start_date,
        end_date=end_date,
        status=status,
        daily_basic_target_dates=len(open_dates) if "open_dates" in locals() else 0,
        daily_basic_fetched_dates=daily_basic_fetched,
        daily_basic_inserted_rows=daily_basic_inserted,
        adj_factor_target_dates=len(open_dates) if "open_dates" in locals() else 0,
        adj_factor_fetched_dates=adj_factor_fetched,
        adj_factor_inserted_rows=adj_factor_inserted,
        dividend_inserted_rows=dividend_inserted,
        financial_target_periods=len(periods) if "periods" in locals() else 0,
        financial_fetched_periods=financial_fetched,
        financial_inserted_rows=financial_inserted,
        audit_csv=output_csv,
        audit_md=output_md,
        warnings=warnings,
    )
