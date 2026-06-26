from __future__ import annotations

import csv
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from phase0.reporting.paths import create_report_run


VALID_SCOPES = {"all", "cn", "financial", "cross_market", "scheduler"}
SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2}
MAX_OHLC_SAMPLES = 5


@dataclass
class HealthFinding:
    severity: str
    check_id: str
    table_name: str
    symbol: str
    date: str
    field: str
    message: str
    sample_value: str
    expected_rule: str


@dataclass
class HealthSummaryRow:
    section: str
    check_id: str
    status: str
    metric: str
    value: str
    threshold: str


@dataclass
class DatabaseHealthResult:
    status: str
    summary_csv: Path
    findings_csv: Path
    summary_md: Path
    summary_rows: int
    finding_count: int
    error_count: int
    warning_count: int
    info_count: int


def _safe_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Unsafe SQL identifier: {value}")
    return value


def _resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path


def _parse_date(value: str | None) -> date:
    if not value:
        return date.today()
    return datetime.strptime(value, "%Y-%m-%d").date()


def _format_ratio(value: float) -> str:
    return f"{value:.2%}"


def _format_count_ratio(numerator: int, denominator: int) -> str:
    ratio = numerator / denominator if denominator else 0.0
    return f"{numerator}/{denominator} ({_format_ratio(ratio)})"


def _add_summary(
    rows: list[HealthSummaryRow],
    *,
    section: str,
    check_id: str,
    status: str,
    metric: str,
    value: Any,
    threshold: Any = "",
) -> None:
    rows.append(
        HealthSummaryRow(
            section=section,
            check_id=check_id,
            status=status,
            metric=metric,
            value=str(value),
            threshold=str(threshold),
        )
    )


def _add_finding(
    findings: list[HealthFinding],
    *,
    severity: str,
    check_id: str,
    message: str,
    table_name: str = "",
    symbol: str = "",
    date_value: str = "",
    field: str = "",
    sample_value: Any = "",
    expected_rule: str = "",
) -> None:
    findings.append(
        HealthFinding(
            severity=severity,
            check_id=check_id,
            table_name=table_name,
            symbol=symbol,
            date=date_value,
            field=field,
            message=message,
            sample_value=str(sample_value),
            expected_rule=expected_rule,
        )
    )


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    table = _safe_identifier(table)
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _scalar(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> Any:
    row = conn.execute(query, params).fetchone()
    return row[0] if row else None


def _dict_rows(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def _add_pe_ratio_diagnostics(
    *,
    conn: sqlite3.Connection,
    section: str,
    daily_basic_table: str,
    meta_table: str,
    market: str,
    latest_basic: str,
    latest_rows: int,
    summary: list[HealthSummaryRow],
) -> None:
    table = _safe_identifier(daily_basic_table)
    pe_missing = int(
        _scalar(
            conn,
            f"SELECT COUNT(*) FROM {table} WHERE market = ? AND date = ? AND pe_ratio IS NULL",
            (market, latest_basic),
        )
        or 0
    )
    pe_missing_pb_present = int(
        _scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM {table}
            WHERE market = ?
              AND date = ?
              AND pe_ratio IS NULL
              AND pb_ratio IS NOT NULL
            """,
            (market, latest_basic),
        )
        or 0
    )
    _add_summary(
        summary,
        section=section,
        check_id="cn.daily_basic.pe_ratio_missing",
        status="info",
        metric="missing/rows",
        value=_format_count_ratio(pe_missing, latest_rows),
        threshold="diagnostic only",
    )
    _add_summary(
        summary,
        section=section,
        check_id="cn.daily_basic.pe_ratio_missing_pb_present",
        status="info",
        metric="pb_present_among_pe_missing",
        value=_format_count_ratio(pe_missing_pb_present, pe_missing),
        threshold="diagnostic only",
    )

    if not _table_exists(conn, meta_table):
        return

    meta = _safe_identifier(meta_table)
    st_missing = int(
        _scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM {table} b
            LEFT JOIN {meta} s ON s.symbol = b.symbol AND s.market = b.market
            WHERE b.market = ?
              AND b.date = ?
              AND b.pe_ratio IS NULL
              AND s.name LIKE '%ST%'
            """,
            (market, latest_basic),
        )
        or 0
    )
    _add_summary(
        summary,
        section=section,
        check_id="cn.daily_basic.pe_ratio_missing_st",
        status="info",
        metric="st_or_star_st_among_pe_missing",
        value=_format_count_ratio(st_missing, pe_missing),
        threshold="diagnostic only",
    )


def _check_required_table(
    conn: sqlite3.Connection,
    *,
    table: str,
    required_columns: list[str],
    section: str,
    findings: list[HealthFinding],
    summary: list[HealthSummaryRow],
    required: bool = True,
) -> set[str]:
    check_id = f"{section}.{table}.schema"
    if not _table_exists(conn, table):
        severity = "error" if required else "warning"
        _add_summary(
            summary,
            section=section,
            check_id=check_id,
            status="fail" if required else "warning",
            metric="table_exists",
            value="false",
            threshold="true",
        )
        _add_finding(
            findings,
            severity=severity,
            check_id=check_id,
            table_name=table,
            message=f"required table {table} is missing",
            expected_rule="table must exist",
        )
        return set()

    columns = _table_columns(conn, table)
    missing = [col for col in required_columns if col not in columns]
    status = "fail" if missing and required else ("warning" if missing else "pass")
    _add_summary(
        summary,
        section=section,
        check_id=check_id,
        status=status,
        metric="missing_columns",
        value=",".join(missing) if missing else "none",
        threshold="none",
    )
    if missing:
        _add_finding(
            findings,
            severity="error" if required else "warning",
            check_id=check_id,
            table_name=table,
            field=",".join(missing),
            message=f"table {table} is missing required columns",
            expected_rule="all required columns must exist",
        )
    return columns


def _condition_for_daily(columns: set[str], market: str, adjust_type: str, as_of: date) -> tuple[str, tuple[Any, ...]]:
    conditions = ["market = ?", "date <= ?"]
    params: list[Any] = [market, as_of.isoformat()]
    if "adjust_type" in columns:
        conditions.append("adjust_type = ?")
        params.append(adjust_type)
    return " AND ".join(conditions), tuple(params)


def _latest_date(
    conn: sqlite3.Connection,
    *,
    table: str,
    date_column: str = "date",
    where_sql: str = "",
    params: tuple[Any, ...] = (),
) -> str:
    table = _safe_identifier(table)
    date_column = _safe_identifier(date_column)
    where = f"WHERE {where_sql}" if where_sql else ""
    value = _scalar(conn, f"SELECT MAX({date_column}) FROM {table} {where}", params)
    return str(value or "")


def _trade_day_staleness(
    conn: sqlite3.Connection,
    *,
    calendar_table: str,
    latest: str,
    as_of: date,
) -> tuple[int, str, str, str]:
    if not latest:
        return 9999, "trade_day_staleness", "N/A", "trading_calendar unavailable; latest date missing"
    try:
        latest_date = datetime.strptime(latest, "%Y-%m-%d").date()
    except ValueError:
        return 9999, "trade_day_staleness", "N/A", "trading_calendar unavailable; latest date invalid"

    try:
        table = _safe_identifier(calendar_table)
    except ValueError:
        fallback = (as_of - latest_date).days
        return fallback, "calendar_day_staleness", "N/A", "trading_calendar unavailable; invalid table name"
    if not _table_exists(conn, calendar_table):
        fallback = (as_of - latest_date).days
        return fallback, "calendar_day_staleness", "N/A", "trading_calendar unavailable; table missing"
    columns = _table_columns(conn, calendar_table)
    if not {"date", "is_open"}.issubset(columns):
        fallback = (as_of - latest_date).days
        return fallback, "calendar_day_staleness", "N/A", "trading_calendar unavailable; required columns missing"

    expected_trade_date = str(
        _scalar(
            conn,
            f"""
            SELECT MAX(date)
            FROM {table}
            WHERE is_open = 1
              AND date <= ?
            """,
            (as_of.isoformat(),),
        )
        or ""
    )
    if not expected_trade_date:
        fallback = (as_of - latest_date).days
        return fallback, "calendar_day_staleness", "N/A", "trading_calendar unavailable; no open date before as-of"

    stale_days = int(
        _scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM {table}
            WHERE is_open = 1
              AND date > ?
              AND date <= ?
            """,
            (latest, expected_trade_date),
        )
        or 0
    )
    return stale_days, "trade_day_staleness", expected_trade_date, "trading_calendar"


def _recent_date_bounds(
    conn: sqlite3.Connection,
    *,
    table: str,
    where_sql: str,
    params: tuple[Any, ...],
    days: int = 260,
) -> tuple[str, str]:
    table = _safe_identifier(table)
    latest = str(_scalar(conn, f"SELECT MAX(date) FROM {table} WHERE {where_sql}", params) or "")
    if not latest:
        return "", ""
    latest_date = datetime.strptime(latest, "%Y-%m-%d").date()
    # Calendar-day rollback avoids an expensive DISTINCT/GROUP BY over large daily-bar tables.
    start = latest_date - timedelta(days=max(int(days * 1.6), days + 30))
    return start.isoformat(), latest


def _count_recent_violations(
    conn: sqlite3.Connection,
    *,
    table: str,
    where_sql: str,
    params: tuple[Any, ...],
    recent_start: str,
    violation_sql: str,
) -> int:
    if not recent_start:
        return 0
    table = _safe_identifier(table)
    return int(
        _scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM {table}
            WHERE {where_sql}
              AND date >= ?
              AND ({violation_sql})
            """,
            (*params, recent_start),
        )
        or 0
    )


def _recent_violation_counts(
    conn: sqlite3.Connection,
    *,
    table: str,
    where_sql: str,
    params: tuple[Any, ...],
    recent_start: str,
    checks: dict[str, str],
) -> dict[str, int]:
    if not recent_start or not checks:
        return {name: 0 for name in checks}
    table = _safe_identifier(table)
    select_sql = ", ".join(
        f"SUM(CASE WHEN ({condition}) THEN 1 ELSE 0 END) AS {_safe_identifier(name)}"
        for name, condition in checks.items()
    )
    row = conn.execute(
        f"""
        SELECT {select_sql}
        FROM {table}
        WHERE {where_sql}
          AND date >= ?
        """,
        (*params, recent_start),
    ).fetchone()
    if row is None:
        return {name: 0 for name in checks}
    return {name: int(row[name] or 0) for name in checks}


def _recent_violation_samples(
    conn: sqlite3.Connection,
    *,
    table: str,
    where_sql: str,
    params: tuple[Any, ...],
    recent_start: str,
    violation_sql: str,
    columns: list[str],
    limit: int = MAX_OHLC_SAMPLES,
) -> list[dict[str, Any]]:
    if not recent_start or limit <= 0:
        return []
    table = _safe_identifier(table)
    select_columns = ", ".join(_safe_identifier(column) for column in columns)
    query = f"""
        SELECT {select_columns}
        FROM {table}
        WHERE {where_sql}
          AND date >= ?
          AND ({violation_sql})
        ORDER BY date DESC, symbol ASC
        LIMIT ?
    """
    return _dict_rows(conn, query, (*params, recent_start, int(limit)))


def _check_count_metric(
    *,
    count: int,
    section: str,
    check_id: str,
    metric: str,
    table: str,
    findings: list[HealthFinding],
    summary: list[HealthSummaryRow],
    severity: str = "error",
    expected_rule: str = "count must be zero",
) -> None:
    _add_summary(
        summary,
        section=section,
        check_id=check_id,
        status="pass" if count == 0 else ("fail" if severity == "error" else "warning"),
        metric=metric,
        value=count,
        threshold=0,
    )
    if count:
        _add_finding(
            findings,
            severity=severity,
            check_id=check_id,
            table_name=table,
            message=f"{metric} found {count} violating rows",
            sample_value=count,
            expected_rule=expected_rule,
        )


def _add_violation_sample_findings(
    *,
    findings: list[HealthFinding],
    severity: str,
    check_id: str,
    table: str,
    field: str,
    samples: list[dict[str, Any]],
    expected_rule: str,
) -> None:
    for sample in samples:
        sample_parts = []
        for key in ["open", "high", "low", "close", "volume", "amount", "source"]:
            if key in sample:
                sample_parts.append(f"{key}={sample.get(key)}")
        _add_finding(
            findings,
            severity=severity,
            check_id=f"{check_id}.sample",
            table_name=table,
            symbol=str(sample.get("symbol") or ""),
            date_value=str(sample.get("date") or ""),
            field=field,
            message="sample violating row",
            sample_value=", ".join(sample_parts),
            expected_rule=expected_rule,
        )


def _check_cn_market_data(
    *,
    conn: sqlite3.Connection,
    config: dict[str, Any],
    as_of: date,
    findings: list[HealthFinding],
    summary: list[HealthSummaryRow],
) -> None:
    section = "cn"
    local_cfg = config.get("local_history", {})
    update_cfg = config.get("manual_history_update", {})
    market = str(local_cfg.get("market", "CN"))
    adjust_type = str(local_cfg.get("adjust_type", "qfq"))
    daily_table = str(local_cfg.get("daily_table", "market_daily_bars"))
    meta_table = str(local_cfg.get("meta_table", "market_stocks"))
    daily_basic_table = str(local_cfg.get("daily_basic_table", "market_daily_basic"))
    adj_factor_table = str(local_cfg.get("adj_factor_table", "market_adj_factors"))
    calendar_table = str(local_cfg.get("calendar_table", "trading_calendar"))
    min_coverage = float(update_cfg.get("min_latest_coverage", local_cfg.get("min_snapshot_coverage", 0.80)))
    max_staleness_days = int(update_cfg.get("max_staleness_days", local_cfg.get("max_snapshot_staleness_days", 1)))

    daily_columns = _check_required_table(
        conn,
        table=daily_table,
        required_columns=["market", "symbol", "date", "open", "high", "low", "close", "volume", "amount"],
        section=section,
        findings=findings,
        summary=summary,
    )
    if daily_columns:
        where_sql, params = _condition_for_daily(daily_columns, market, adjust_type, as_of)
        latest = _latest_date(conn, table=daily_table, where_sql=where_sql, params=params)
        latest_symbols = 0
        coverage = 0.0
        total_symbols = 0
        if latest:
            total_symbols = int(
                _scalar(
                    conn,
                    f"""
                    SELECT COUNT(DISTINCT symbol)
                    FROM {_safe_identifier(meta_table)}
                    WHERE market = ?
                      AND (COALESCE(list_date, '') = '' OR list_date <= ?)
                      AND (COALESCE(delist_date, '') = '' OR delist_date > ?)
                    """,
                    (market, latest, latest),
                )
                or 0
            )
            latest_symbols = int(
                _scalar(
                    conn,
                    f"SELECT COUNT(DISTINCT symbol) FROM {_safe_identifier(daily_table)} WHERE {where_sql} AND date = ?",
                    (*params, latest),
                )
                or 0
            )
            coverage = latest_symbols / total_symbols if total_symbols else 0.0
        staleness, staleness_metric, expected_trade_date, staleness_source = _trade_day_staleness(
            conn,
            calendar_table=calendar_table,
            latest=latest,
            as_of=as_of,
        )
        _add_summary(summary, section=section, check_id="cn.daily.latest_date", status="pass" if latest else "fail", metric="latest_date", value=latest or "N/A")
        _add_summary(
            summary,
            section=section,
            check_id="cn.daily.latest_coverage",
            status="pass" if coverage >= min_coverage else "fail",
            metric="latest_symbols/total_symbols",
            value=f"{latest_symbols}/{total_symbols} ({_format_ratio(coverage)})",
            threshold=_format_ratio(min_coverage),
        )
        if coverage < min_coverage:
            _add_finding(
                findings,
                severity="error",
                check_id="cn.daily.latest_coverage",
                table_name=daily_table,
                date_value=latest,
                message="latest A-share daily bar coverage is below threshold",
                sample_value=_format_ratio(coverage),
                expected_rule=f"coverage >= {_format_ratio(min_coverage)}",
            )
        _add_summary(
            summary,
            section=section,
            check_id="cn.daily.staleness",
            status="pass" if staleness <= max_staleness_days else "fail",
            metric=staleness_metric,
            value=staleness,
            threshold=f"<= {max_staleness_days}; expected_trade_date={expected_trade_date}",
        )
        if staleness > max_staleness_days:
            _add_finding(
                findings,
                severity="error",
                check_id="cn.daily.staleness",
                table_name=daily_table,
                date_value=latest,
                message="latest A-share daily bar date is stale relative to expected trade date",
                sample_value=staleness,
                expected_rule=f"staleness <= {max_staleness_days} trading days ({staleness_source})",
            )

        recent_start, _ = _recent_date_bounds(conn, table=daily_table, where_sql=where_sql, params=params)
        daily_violation_counts = _recent_violation_counts(
            conn,
            table=daily_table,
            where_sql=where_sql,
            params=params,
            recent_start=recent_start,
            checks={
                "ohlc": "high < low OR high < open OR high < close OR low > open OR low > close",
                "positive_prices": "open <= 0 OR high <= 0 OR low <= 0 OR close <= 0",
                "non_negative_liquidity": "volume < 0 OR amount < 0",
            },
        )
        _check_count_metric(
            count=daily_violation_counts["ohlc"],
            section=section,
            check_id="cn.daily.ohlc",
            metric="recent_ohlc_violations",
            table=daily_table,
            findings=findings,
            summary=summary,
            expected_rule="high >= low/open/close and low <= open/close",
        )
        if daily_violation_counts["ohlc"] > 0:
            _add_violation_sample_findings(
                findings=findings,
                severity="error",
                check_id="cn.daily.ohlc",
                table=daily_table,
                field="open,high,low,close",
                samples=_recent_violation_samples(
                    conn,
                    table=daily_table,
                    where_sql=where_sql,
                    params=params,
                    recent_start=recent_start,
                    violation_sql="high < low OR high < open OR high < close OR low > open OR low > close",
                    columns=["symbol", "date", "open", "high", "low", "close", "volume", "amount"],
                ),
                expected_rule="high >= low/open/close and low <= open/close",
            )
        _check_count_metric(
            count=daily_violation_counts["positive_prices"],
            section=section,
            check_id="cn.daily.positive_prices",
            metric="recent_non_positive_price_rows",
            table=daily_table,
            findings=findings,
            summary=summary,
            expected_rule="open/high/low/close must be positive",
        )
        _check_count_metric(
            count=daily_violation_counts["non_negative_liquidity"],
            section=section,
            check_id="cn.daily.non_negative_liquidity",
            metric="recent_negative_volume_amount_rows",
            table=daily_table,
            findings=findings,
            summary=summary,
            expected_rule="volume and amount must be non-negative",
        )

    meta_columns = _check_required_table(
        conn,
        table=meta_table,
        required_columns=["market", "symbol", "name", "list_status", "list_date"],
        section=section,
        findings=findings,
        summary=summary,
        required=False,
    )
    if meta_columns:
        total = int(_scalar(conn, f"SELECT COUNT(*) FROM {_safe_identifier(meta_table)} WHERE market = ?", (market,)) or 0)
        active = int(
            _scalar(
                conn,
                f"""
                SELECT COUNT(*)
                FROM {_safe_identifier(meta_table)}
                WHERE market = ?
                  AND COALESCE(list_status, '') NOT LIKE '%退%'
                """,
                (market,),
            )
            or 0
        )
        missing_list_date = int(
            _scalar(
                conn,
                f"SELECT COUNT(*) FROM {_safe_identifier(meta_table)} WHERE market = ? AND (list_date IS NULL OR list_date = '')",
                (market,),
            )
            or 0
        )
        ratio = 1.0 - (missing_list_date / total) if total else 0.0
        _add_summary(summary, section=section, check_id="cn.meta.active_symbols", status="pass", metric="active/total", value=f"{active}/{total}")
        _add_summary(
            summary,
            section=section,
            check_id="cn.meta.list_date_coverage",
            status="pass" if ratio >= 0.95 else "warning",
            metric="list_date_coverage",
            value=_format_ratio(ratio),
            threshold="95.00%",
        )
        if ratio < 0.95:
            _add_finding(
                findings,
                severity="warning",
                check_id="cn.meta.list_date_coverage",
                table_name=meta_table,
                message="stock metadata has weak listing-date coverage",
                sample_value=_format_ratio(ratio),
                expected_rule="list_date coverage >= 95%",
            )

    daily_basic_columns = _check_required_table(
        conn,
        table=daily_basic_table,
        required_columns=["market", "symbol", "date", "market_cap", "pe_ratio", "pb_ratio", "turnover_rate"],
        section=section,
        findings=findings,
        summary=summary,
        required=False,
    )
    if daily_basic_columns:
        latest_basic = _latest_date(conn, table=daily_basic_table, where_sql="market = ? AND date <= ?", params=(market, as_of.isoformat()))
        latest_rows = int(
            _scalar(
                conn,
                f"SELECT COUNT(DISTINCT symbol) FROM {_safe_identifier(daily_basic_table)} WHERE market = ? AND date = ?",
                (market, latest_basic),
            )
            or 0
        )
        _add_summary(summary, section=section, check_id="cn.daily_basic.latest_date", status="pass" if latest_basic else "warning", metric="latest_date", value=latest_basic or "N/A")
        _add_summary(summary, section=section, check_id="cn.daily_basic.latest_rows", status="pass" if latest_rows else "warning", metric="latest_rows", value=latest_rows)
        hard_coverage_fields = {"market_cap", "pb_ratio", "turnover_rate"}
        for field in ["market_cap", "pe_ratio", "pb_ratio", "turnover_rate"]:
            if field in daily_basic_columns and latest_basic:
                non_null = int(
                    _scalar(
                        conn,
                        f"SELECT COUNT(*) FROM {_safe_identifier(daily_basic_table)} WHERE market = ? AND date = ? AND {field} IS NOT NULL",
                        (market, latest_basic),
                    )
                    or 0
                )
                ratio = non_null / latest_rows if latest_rows else 0.0
                threshold = "80.00%" if field in hard_coverage_fields else "diagnostic only"
                status = "pass" if field == "pe_ratio" or ratio >= 0.80 else "warning"
                _add_summary(
                    summary,
                    section=section,
                    check_id=f"cn.daily_basic.{field}",
                    status=status,
                    metric="latest_non_null_coverage",
                    value=_format_ratio(ratio),
                    threshold=threshold,
                )
                if field in hard_coverage_fields and ratio < 0.80:
                    _add_finding(
                        findings,
                        severity="warning",
                        check_id=f"cn.daily_basic.{field}",
                        table_name=daily_basic_table,
                        date_value=latest_basic,
                        field=field,
                        message="latest daily_basic field coverage is below threshold",
                        sample_value=_format_ratio(ratio),
                        expected_rule="coverage >= 80%",
                    )
        if "pe_ratio" in daily_basic_columns and latest_basic:
            _add_pe_ratio_diagnostics(
                conn=conn,
                section=section,
                daily_basic_table=daily_basic_table,
                meta_table=meta_table,
                market=market,
                latest_basic=latest_basic,
                latest_rows=latest_rows,
                summary=summary,
            )

    adj_columns = _check_required_table(
        conn,
        table=adj_factor_table,
        required_columns=["market", "symbol", "date", "adj_factor"],
        section=section,
        findings=findings,
        summary=summary,
        required=False,
    )
    if adj_columns:
        where_sql = "market = ? AND date <= ?"
        params = (market, as_of.isoformat())
        recent_start, _ = _recent_date_bounds(conn, table=adj_factor_table, where_sql=where_sql, params=params)
        _check_count_metric(
            count=_count_recent_violations(
                conn,
                table=adj_factor_table,
                where_sql=where_sql,
                params=params,
                recent_start=recent_start,
                violation_sql="adj_factor <= 0",
            ),
            section=section,
            check_id="cn.adjustment.positive_factor",
            metric="recent_non_positive_adj_factor_rows",
            table=adj_factor_table,
            findings=findings,
            summary=summary,
            expected_rule="adj_factor must be positive",
        )

    _check_required_table(
        conn,
        table=calendar_table,
        required_columns=["date", "is_open"],
        section=section,
        findings=findings,
        summary=summary,
        required=False,
    )


def _check_financial_data(
    *,
    conn: sqlite3.Connection,
    config: dict[str, Any],
    as_of: date,
    findings: list[HealthFinding],
    summary: list[HealthSummaryRow],
) -> None:
    section = "financial"
    local_cfg = config.get("local_history", {})
    financial_cfg = config.get("financial_factors", {})
    market = str(local_cfg.get("market", "CN"))
    financial_table = str(local_cfg.get("financial_table", financial_cfg.get("table", "market_financial_factors")))
    meta_table = str(local_cfg.get("meta_table", "market_stocks"))
    min_factor_coverage = float(financial_cfg.get("min_factor_coverage", 0.60))
    columns = _check_required_table(
        conn,
        table=financial_table,
        required_columns=["market", "symbol", "report_date", "announce_date", "roe", "revenue_growth", "profit_growth", "operating_cash_flow_to_net_profit", "debt_to_asset"],
        section=section,
        findings=findings,
        summary=summary,
    )
    if not columns:
        return
    table = _safe_identifier(financial_table)
    row_count = int(_scalar(conn, f"SELECT COUNT(*) FROM {table} WHERE market = ?", (market,)) or 0)
    latest_report = str(_scalar(conn, f"SELECT MAX(report_date) FROM {table} WHERE market = ? AND report_date <= ?", (market, as_of.isoformat())) or "")
    _add_summary(summary, section=section, check_id="financial.rows", status="pass" if row_count else "fail", metric="row_count", value=row_count)
    _add_summary(summary, section=section, check_id="financial.latest_report", status="pass" if latest_report else "fail", metric="latest_report_date", value=latest_report or "N/A")

    missing_announce = int(
        _scalar(
            conn,
            f"SELECT COUNT(*) FROM {table} WHERE market = ? AND (announce_date IS NULL OR announce_date = '')",
            (market,),
        )
        or 0
    )
    announce_coverage = 1.0 - (missing_announce / row_count) if row_count else 0.0
    _add_summary(
        summary,
        section=section,
        check_id="financial.announce_date_coverage",
        status="pass" if announce_coverage >= 0.95 else ("fail" if announce_coverage < min_factor_coverage else "warning"),
        metric="announce_date_coverage",
        value=_format_ratio(announce_coverage),
        threshold="95.00%",
    )
    if announce_coverage < 0.95:
        _add_finding(
            findings,
            severity="error" if announce_coverage < min_factor_coverage else "warning",
            check_id="financial.announce_date_coverage",
            table_name=financial_table,
            message="financial factors have missing announce_date values, weakening point-in-time safety",
            sample_value=_format_ratio(announce_coverage),
            expected_rule="announce_date coverage >= 95%",
        )
    impossible_announce = int(
        _scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM {table}
            WHERE market = ?
              AND announce_date IS NOT NULL
              AND announce_date != ''
              AND announce_date < report_date
            """,
            (market,),
        )
        or 0
    )
    _check_count_metric(
        count=impossible_announce,
        section=section,
        check_id="financial.announce_after_report",
        metric="announce_before_report_rows",
        table=financial_table,
        findings=findings,
        summary=summary,
        expected_rule="announce_date must not be before report_date",
    )

    if _table_exists(conn, meta_table):
        latest_sql = f"""
            WITH latest AS (
                SELECT f.*
                FROM {table} f
                JOIN (
                    SELECT market, symbol, MAX(report_date) AS report_date
                    FROM {table}
                    WHERE market = ?
                    GROUP BY market, symbol
                ) x
                  ON f.market = x.market
                 AND f.symbol = x.symbol
                 AND f.report_date = x.report_date
            ),
            eligible AS (
                SELECT symbol
                FROM {_safe_identifier(meta_table)}
                WHERE market = ?
                  AND COALESCE(list_status, '') NOT LIKE '%退%'
            )
            SELECT
                COUNT(e.symbol) AS total,
                SUM(CASE WHEN l.symbol IS NOT NULL THEN 1 ELSE 0 END) AS latest_factor,
                SUM(CASE WHEN l.roe IS NOT NULL THEN 1 ELSE 0 END) AS roe,
                SUM(CASE WHEN l.revenue_growth IS NOT NULL THEN 1 ELSE 0 END) AS revenue_growth,
                SUM(CASE WHEN l.profit_growth IS NOT NULL THEN 1 ELSE 0 END) AS profit_growth,
                SUM(CASE WHEN l.operating_cash_flow_to_net_profit IS NOT NULL THEN 1 ELSE 0 END) AS cash_flow_quality,
                SUM(CASE WHEN l.debt_to_asset IS NOT NULL THEN 1 ELSE 0 END) AS debt_to_asset
            FROM eligible e
            LEFT JOIN latest l ON l.symbol = e.symbol
        """
        row = conn.execute(latest_sql, (market, market)).fetchone()
        total = int(row["total"] or 0) if row else 0
        for field in ["latest_factor", "roe", "revenue_growth", "profit_growth", "cash_flow_quality", "debt_to_asset"]:
            covered = int(row[field] or 0) if row else 0
            ratio = covered / total if total else 0.0
            status = "pass" if ratio >= min_factor_coverage else "fail"
            _add_summary(
                summary,
                section=section,
                check_id=f"financial.coverage.{field}",
                status=status,
                metric="eligible_symbol_coverage",
                value=f"{covered}/{total} ({_format_ratio(ratio)})",
                threshold=_format_ratio(min_factor_coverage),
            )
            if ratio < min_factor_coverage:
                _add_finding(
                    findings,
                    severity="error",
                    check_id=f"financial.coverage.{field}",
                    table_name=financial_table,
                    field=field,
                    message="latest financial factor coverage is below strategy threshold",
                    sample_value=_format_ratio(ratio),
                    expected_rule=f"coverage >= {_format_ratio(min_factor_coverage)}",
                )

    task_table = "tushare_financial_backfill_tasks"
    if _table_exists(conn, task_table):
        counts = {
            str(row["status"]): int(row["count"])
            for row in conn.execute(
                f"SELECT status, COUNT(*) AS count FROM {_safe_identifier(task_table)} GROUP BY status"
            ).fetchall()
        }
        for status_name, count in sorted(counts.items()):
            severity = "warning" if status_name in {"pending", "failed"} and count else "pass"
            _add_summary(
                summary,
                section=section,
                check_id=f"financial.backfill_tasks.{status_name}",
                status=severity,
                metric="task_count",
                value=count,
            )
            if status_name in {"pending", "failed"} and count:
                _add_finding(
                    findings,
                    severity="warning",
                    check_id=f"financial.backfill_tasks.{status_name}",
                    table_name=task_table,
                    message=f"Tushare financial backfill still has {status_name} tasks",
                    sample_value=count,
                    expected_rule="long-running backfill task queue should eventually drain",
                )
    else:
        _add_finding(
            findings,
            severity="warning",
            check_id="financial.backfill_tasks.missing",
            table_name=task_table,
            message="Tushare financial backfill task table is missing",
            expected_rule="task table should exist after resumable financial backfill starts",
        )


def _check_audit_table(
    *,
    conn: sqlite3.Connection,
    table: str,
    section: str,
    as_of: date,
    max_staleness_days: int,
    findings: list[HealthFinding],
    summary: list[HealthSummaryRow],
) -> None:
    check_id = f"{section}.{table}.audit"
    if not _table_exists(conn, table):
        _add_summary(summary, section=section, check_id=check_id, status="warning", metric="audit_table_exists", value="false", threshold="true")
        _add_finding(
            findings,
            severity="warning",
            check_id=check_id,
            table_name=table,
            message="source audit table is missing",
            expected_rule="data update jobs should persist source audit rows",
        )
        return
    columns = _table_columns(conn, table)
    if "fetched_at" not in columns:
        _add_finding(
            findings,
            severity="warning",
            check_id=check_id,
            table_name=table,
            field="fetched_at",
            message="source audit table lacks fetched_at column",
            expected_rule="audit table should include fetched_at",
        )
        return
    latest_fetched = str(_scalar(conn, f"SELECT MAX(fetched_at) FROM {_safe_identifier(table)}") or "")
    latest_date = latest_fetched[:10] if latest_fetched else ""
    stale_days = (as_of - datetime.strptime(latest_date, "%Y-%m-%d").date()).days if latest_date else 9999
    _add_summary(
        summary,
        section=section,
        check_id=check_id,
        status="pass" if stale_days <= max_staleness_days else "warning",
        metric="latest_fetched_at",
        value=latest_fetched or "N/A",
        threshold=f"<= {max_staleness_days} days",
    )
    if stale_days > max_staleness_days:
        _add_finding(
            findings,
            severity="warning",
            check_id=check_id,
            table_name=table,
            message="source audit table has no recent run record",
            sample_value=latest_fetched or "N/A",
            expected_rule=f"latest fetched_at within {max_staleness_days} days",
        )


def _check_cross_market_one(
    *,
    name: str,
    raw_cfg: dict[str, Any],
    root: Path,
    as_of: date,
    findings: list[HealthFinding],
    summary: list[HealthSummaryRow],
) -> None:
    section = f"cross_market.{name}"
    if not bool(raw_cfg.get("enabled", True)):
        _add_summary(summary, section=section, check_id=f"{section}.enabled", status="info", metric="enabled", value="false")
        return
    db_path = _resolve_path(root, raw_cfg.get("path", f"data/{name}_market_history.sqlite"))
    daily_table = str(raw_cfg.get("daily_table", "market_daily_bars"))
    audit_table = str(raw_cfg.get("source_audit_table", "market_data_source_runs"))
    symbols = [str(item) for item in raw_cfg.get("symbols", [])]
    max_staleness_days = int(raw_cfg.get("max_staleness_days", 3))
    min_symbol_coverage = float(raw_cfg.get("min_symbol_coverage", 1.0))
    if not db_path.exists():
        _add_summary(summary, section=section, check_id=f"{section}.database", status="fail", metric="db_exists", value="false", threshold="true")
        _add_finding(
            findings,
            severity="error",
            check_id=f"{section}.database",
            message="cross-market database is missing",
            sample_value=db_path,
            expected_rule="database path must exist",
        )
        return
    with _connect(db_path) as conn:
        columns = _check_required_table(
            conn,
            table=daily_table,
            required_columns=["symbol", "date", "open", "high", "low", "close", "volume"],
            section=section,
            findings=findings,
            summary=summary,
        )
        if not columns:
            return
        if symbols:
            placeholders = ",".join("?" for _ in symbols)
            rows = _dict_rows(
                conn,
                f"""
                SELECT symbol, MAX(date) AS latest_date
                FROM {_safe_identifier(daily_table)}
                WHERE symbol IN ({placeholders})
                  AND date <= ?
                GROUP BY symbol
                """,
                (*symbols, as_of.isoformat()),
            )
            latest_by_symbol = {str(row["symbol"]): str(row["latest_date"] or "") for row in rows}
            cutoff = as_of - timedelta(days=max_staleness_days)
            covered = [
                symbol
                for symbol in symbols
                if latest_by_symbol.get(symbol)
                and datetime.strptime(latest_by_symbol[symbol], "%Y-%m-%d").date() >= cutoff
            ]
            coverage = len(covered) / len(symbols) if symbols else 0.0
            latest = max(latest_by_symbol.values()) if latest_by_symbol else ""
            _add_summary(
                summary,
                section=section,
                check_id=f"{section}.coverage",
                status="pass" if coverage >= min_symbol_coverage else "warning",
                metric="fresh_configured_symbols",
                value=f"{len(covered)}/{len(symbols)} ({_format_ratio(coverage)}) latest={latest or 'N/A'}",
                threshold=_format_ratio(min_symbol_coverage),
            )
            if coverage < min_symbol_coverage:
                missing = [symbol for symbol in symbols if symbol not in covered]
                _add_finding(
                    findings,
                    severity="warning",
                    check_id=f"{section}.coverage",
                    table_name=daily_table,
                    symbol=",".join(missing[:10]),
                    message="cross-market symbol freshness coverage is below threshold",
                    sample_value=_format_ratio(coverage),
                    expected_rule=f"coverage >= {_format_ratio(min_symbol_coverage)}",
                )

        where_sql = "date <= ?"
        params = (as_of.isoformat(),)
        recent_start, _ = _recent_date_bounds(conn, table=daily_table, where_sql=where_sql, params=params)
        ohlc_count = _count_recent_violations(
            conn,
            table=daily_table,
            where_sql=where_sql,
            params=params,
            recent_start=recent_start,
            violation_sql="high < low OR high < open OR high < close OR low > open OR low > close",
        )
        _check_count_metric(
            count=ohlc_count,
            section=section,
            check_id=f"{section}.ohlc",
            metric="recent_ohlc_violations",
            table=daily_table,
            findings=findings,
            summary=summary,
            severity="warning",
            expected_rule="high >= low/open/close and low <= open/close",
        )
        if ohlc_count > 0:
            _add_violation_sample_findings(
                findings=findings,
                severity="warning",
                check_id=f"{section}.ohlc",
                table=daily_table,
                field="open,high,low,close",
                samples=_recent_violation_samples(
                    conn,
                    table=daily_table,
                    where_sql=where_sql,
                    params=params,
                    recent_start=recent_start,
                    violation_sql="high < low OR high < open OR high < close OR low > open OR low > close",
                    columns=["symbol", "date", "open", "high", "low", "close", "volume", "source"],
                ),
                expected_rule="high >= low/open/close and low <= open/close",
            )
        _check_audit_table(
            conn=conn,
            table=audit_table,
            section=section,
            as_of=as_of,
            max_staleness_days=max_staleness_days + 2,
            findings=findings,
            summary=summary,
        )


def _check_scheduler(
    *,
    root: Path,
    config: dict[str, Any],
    as_of: date,
    findings: list[HealthFinding],
    summary: list[HealthSummaryRow],
) -> None:
    section = "scheduler"
    expected_last_files = {
        "a_share_history": root / "logs" / "scheduler" / "a_share_history.last",
        "us_market_history": root / "logs" / "scheduler" / "us_market_history.last",
        "hk_market_history": root / "logs" / "scheduler" / "hk_market_history.last",
        "daily_brief": root / "logs" / "scheduler" / "daily_brief.last",
    }
    for name, path in expected_last_files.items():
        check_id = f"scheduler.{name}.last_file"
        if not path.exists():
            _add_summary(summary, section=section, check_id=check_id, status="warning", metric="last_file_exists", value="false", threshold="true")
            _add_finding(
                findings,
                severity="warning",
                check_id=check_id,
                sample_value=path,
                message="scheduler last-run marker is missing",
                expected_rule="scheduled data jobs should persist last-run markers",
            )
            continue
        modified = datetime.fromtimestamp(path.stat().st_mtime).date()
        stale_days = (as_of - modified).days
        _add_summary(
            summary,
            section=section,
            check_id=check_id,
            status="pass" if stale_days <= 3 else "warning",
            metric="mtime",
            value=modified.isoformat(),
            threshold="<= 3 days",
        )
        if stale_days > 3:
            _add_finding(
                findings,
                severity="warning",
                check_id=check_id,
                sample_value=modified.isoformat(),
                message="scheduler last-run marker is stale",
                expected_rule="mtime within 3 days",
            )

    local_cfg = config.get("local_history", {})
    update_cfg = config.get("manual_history_update", {})
    db_path = _resolve_path(root, local_cfg.get("path", "data/manual_history/a_share_history.sqlite"))
    audit_table = str(update_cfg.get("source_audit_table", "market_data_source_runs"))
    if db_path.exists():
        with _connect(db_path) as conn:
            _check_audit_table(
                conn=conn,
                table=audit_table,
                section=section,
                as_of=as_of,
                max_staleness_days=int(update_cfg.get("max_staleness_days", 1)) + 2,
                findings=findings,
                summary=summary,
            )


def _write_csv(path: Path, rows: list[Any], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def _write_markdown(
    *,
    path: Path,
    status: str,
    scope: str,
    as_of: date,
    summary: list[HealthSummaryRow],
    findings: list[HealthFinding],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    counts = {severity: sum(1 for item in findings if item.severity == severity) for severity in ["error", "warning", "info"]}
    lines = [
        "# Database Health Report",
        "",
        f"- Status: {status}",
        f"- Scope: {scope}",
        f"- As-of date: {as_of.isoformat()}",
        f"- Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Findings: errors={counts['error']}, warnings={counts['warning']}, info={counts['info']}",
        "",
        "## Summary",
        "",
        "| Section | Check | Status | Metric | Value | Threshold |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in summary:
        lines.append(
            f"| {row.section} | {row.check_id} | {row.status} | {row.metric} | {row.value} | {row.threshold} |"
        )
    lines.extend(
        [
            "",
            "## Findings",
            "",
            "| Severity | Check | Table | Symbol | Date | Field | Message | Sample | Expected |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    if findings:
        for item in sorted(findings, key=lambda one: (-SEVERITY_ORDER.get(one.severity, 0), one.check_id)):
            lines.append(
                "| {severity} | {check_id} | {table_name} | {symbol} | {date} | {field} | {message} | {sample_value} | {expected_rule} |".format(
                    **asdict(item)
                )
            )
    else:
        lines.append("| info | database_health.clean |  |  |  |  | no findings |  |  |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_database_health_check(
    *,
    config: dict[str, Any],
    root: Path,
    scope: str = "all",
    as_of_date: str | None = None,
    output_dir: Path | None = None,
) -> DatabaseHealthResult:
    if scope not in VALID_SCOPES:
        raise ValueError(f"unsupported db-health scope: {scope}")
    as_of = _parse_date(as_of_date)
    if output_dir is None:
        report_run = create_report_run(root=root, config=config, command="db-health", scope=scope)
        output = report_run.run_dir
        summary_csv = report_run.artifact("database_health", "summary", "csv")
        findings_csv = report_run.artifact("database_health", "findings", "csv")
        summary_md = report_run.artifact("database_health", "report", "md")
    else:
        output = output_dir
        summary_csv = output / "database_health_summary.csv"
        findings_csv = output / "database_health_findings.csv"
        summary_md = output / "database_health_report.md"
    findings: list[HealthFinding] = []
    summary: list[HealthSummaryRow] = []

    local_cfg = config.get("local_history", {})
    local_enabled = bool(local_cfg.get("enabled", True))
    local_db_path = _resolve_path(root, local_cfg.get("path", "data/manual_history/a_share_history.sqlite"))
    needs_local_db = scope in {"all", "cn", "financial"}
    if needs_local_db and not local_enabled:
        _add_summary(summary, section="cn", check_id="cn.database.enabled", status="warning", metric="enabled", value="false", threshold="true")
        _add_finding(
            findings,
            severity="warning",
            check_id="cn.database.enabled",
            sample_value=local_db_path,
            message="local A-share history is disabled",
            expected_rule="local_history.enabled should be true for strategy research",
        )
    elif needs_local_db and not local_db_path.exists():
        _add_summary(summary, section="cn", check_id="cn.database.exists", status="fail", metric="db_exists", value="false", threshold="true")
        _add_finding(
            findings,
            severity="error",
            check_id="cn.database.exists",
            sample_value=local_db_path,
            message="local A-share history database is missing",
            expected_rule="configured SQLite database must exist",
        )
    elif needs_local_db:
        _add_summary(summary, section="cn", check_id="cn.database.exists", status="pass", metric="db_path", value=local_db_path)
        with _connect(local_db_path) as conn:
            if scope in {"all", "cn"}:
                _check_cn_market_data(conn=conn, config=config, as_of=as_of, findings=findings, summary=summary)
            if scope in {"all", "financial"}:
                _check_financial_data(conn=conn, config=config, as_of=as_of, findings=findings, summary=summary)

    if scope in {"all", "cross_market"}:
        _check_cross_market_one(
            name="us",
            raw_cfg=config.get("us_market_history", {}),
            root=root,
            as_of=as_of,
            findings=findings,
            summary=summary,
        )
        _check_cross_market_one(
            name="hk",
            raw_cfg=config.get("hk_market_history", {}),
            root=root,
            as_of=as_of,
            findings=findings,
            summary=summary,
        )

    if scope in {"all", "scheduler"}:
        _check_scheduler(root=root, config=config, as_of=as_of, findings=findings, summary=summary)

    error_count = sum(1 for item in findings if item.severity == "error")
    warning_count = sum(1 for item in findings if item.severity == "warning")
    info_count = sum(1 for item in findings if item.severity == "info")
    status = "fail" if error_count else ("warning" if warning_count else "pass")
    _write_csv(summary_csv, summary, ["section", "check_id", "status", "metric", "value", "threshold"])
    _write_csv(findings_csv, findings, ["severity", "check_id", "table_name", "symbol", "date", "field", "message", "sample_value", "expected_rule"])
    _write_markdown(path=summary_md, status=status, scope=scope, as_of=as_of, summary=summary, findings=findings)
    return DatabaseHealthResult(
        status=status,
        summary_csv=summary_csv,
        findings_csv=findings_csv,
        summary_md=summary_md,
        summary_rows=len(summary),
        finding_count=len(findings),
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
    )
