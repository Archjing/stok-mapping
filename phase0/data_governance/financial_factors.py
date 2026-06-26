from __future__ import annotations

import re
import sqlite3
import time as time_module
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

from phase0.data_access.local_history import normalize_cn_symbol
from phase0.data_access.throttle import configure_akshare_throttle, fetch_with_akshare_retries

EASTMONEY_DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"


@dataclass
class FinancialFactorUpdateResult:
    db_path: Path
    periods_requested: list[str]
    periods_updated: list[str]
    fetched_rows: int
    inserted_rows: int
    factor_coverage: dict[str, float] = field(default_factory=dict)
    status: str = "unknown"
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in {"updated", "up_to_date"}


def update_financial_factors_from_config(
    cfg: dict[str, Any],
    root: Path,
    *,
    periods: int | None = None,
) -> FinancialFactorUpdateResult:
    local_cfg = cfg.get("local_history", {})
    financial_cfg = cfg.get("financial_factors", {})
    data_cfg = cfg.get("data_sources", {})

    db_path = Path(financial_cfg.get("path", local_cfg.get("path", "data/manual_history/a_share_history.sqlite")))
    if not db_path.is_absolute():
        db_path = root / db_path
    table = _safe_identifier(str(financial_cfg.get("table", local_cfg.get("financial_table", "market_financial_factors"))))
    meta_table = _safe_identifier(str(local_cfg.get("meta_table", "market_stocks")))
    market = str(local_cfg.get("market", "CN"))
    markets = {str(item) for item in financial_cfg.get("markets", cfg.get("universe", {}).get("markets", ["SH", "SZ"]))}
    requested_periods = _resolve_periods(financial_cfg, periods)

    if not db_path.exists():
        return FinancialFactorUpdateResult(
            db_path=db_path,
            periods_requested=requested_periods,
            periods_updated=[],
            fetched_rows=0,
            inserted_rows=0,
            status="missing_db",
            warnings=[f"manual history database does not exist: {db_path}"],
        )

    configure_akshare_throttle(data_cfg.get("akshare", {}))
    warnings: list[str] = []
    all_rows: list[pd.DataFrame] = []
    updated_periods: list[str] = []
    fetched_rows = 0

    for period in requested_periods:
        try:
            period_rows = _fetch_period_financial_factors(period, market=market, markets=markets)
        except Exception as exc:
            warnings.append(f"financial factors fetch failed for {period}: {exc}")
            continue
        fetched_rows += len(period_rows)
        if period_rows.empty:
            warnings.append(f"financial factors source returned no rows for {period}")
            continue
        all_rows.append(period_rows)
        updated_periods.append(period)

    if all_rows:
        factors = pd.concat(all_rows, ignore_index=True)
        factors = _finalize_factors(factors)
    else:
        factors = pd.DataFrame()

    inserted_rows = 0
    coverage: dict[str, float] = {}
    with sqlite3.connect(db_path) as conn:
        ensure_financial_factor_table(conn, table=table)
        if not factors.empty:
            inserted_rows = _replace_period_rows(conn, table=table, factors=factors)
            conn.commit()
        coverage = financial_factor_coverage(conn, table=table, meta_table=meta_table, market=market)

    status = "updated" if inserted_rows > 0 else "up_to_date"
    min_coverage = float(financial_cfg.get("min_factor_coverage", 0.60))
    if coverage and coverage.get("min_field", 0.0) < min_coverage:
        warnings.append(
            "financial factor coverage below configured threshold: "
            f"min_field_coverage={coverage.get('min_field', 0.0):.4f}, threshold={min_coverage:.4f}"
        )
    return FinancialFactorUpdateResult(
        db_path=db_path,
        periods_requested=requested_periods,
        periods_updated=updated_periods,
        fetched_rows=fetched_rows,
        inserted_rows=inserted_rows,
        factor_coverage=coverage,
        status=status,
        warnings=warnings,
    )


def ensure_financial_factor_table(conn: sqlite3.Connection, *, table: str = "market_financial_factors") -> None:
    table = _safe_identifier(table)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            market TEXT NOT NULL,
            symbol TEXT NOT NULL,
            report_date TEXT NOT NULL,
            fiscal_year INTEGER,
            fiscal_quarter INTEGER,
            announce_date TEXT,
            name TEXT,
            industry TEXT,
            roe REAL,
            revenue REAL,
            revenue_growth REAL,
            net_profit REAL,
            profit_growth REAL,
            operating_cash_flow REAL,
            operating_cash_flow_to_net_profit REAL,
            debt_to_asset REAL,
            total_assets REAL,
            total_liabilities REAL,
            total_equity REAL,
            source TEXT,
            updated_at TEXT,
            PRIMARY KEY (market, symbol, report_date)
        )
        """
    )
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_symbol_report ON {table}(market, symbol, report_date)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_report ON {table}(report_date)")


def financial_factor_coverage(
    conn: sqlite3.Connection,
    *,
    table: str = "market_financial_factors",
    meta_table: str = "market_stocks",
    market: str = "CN",
) -> dict[str, float]:
    table = _safe_identifier(table)
    meta_table = _safe_identifier(meta_table)
    ensure_financial_factor_table(conn, table=table)
    row = pd.read_sql_query(
        f"""
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
            FROM {meta_table}
            WHERE market = ?
              AND symbol LIKE 'S%.%'
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
        LEFT JOIN latest l
          ON l.symbol = e.symbol
        """,
        conn,
        params=(market, market),
    ).iloc[0]
    total = int(row.get("total") or 0)
    fields = ["latest_factor", "roe", "revenue_growth", "profit_growth", "cash_flow_quality", "debt_to_asset"]
    out = {"total": float(total)}
    for field_name in fields:
        out[field_name] = float(int(row.get(field_name) or 0) / total) if total else 0.0
    factor_fields = fields[1:]
    out["min_field"] = min(out[field_name] for field_name in factor_fields) if total else 0.0
    return out


def _fetch_period_financial_factors(period: str, *, market: str, markets: set[str]) -> pd.DataFrame:
    report_date = _period_to_iso(period)
    yjbb = fetch_with_akshare_retries(lambda: _fetch_eastmoney_report("RPT_LICO_FN_CPD", report_date=report_date, page_size=500))
    balance = fetch_with_akshare_retries(
        lambda: _fetch_eastmoney_report("RPT_DMSK_FN_BALANCE", report_date=report_date, page_size=500)
    )
    cash_flow = fetch_with_akshare_retries(
        lambda: _fetch_eastmoney_report("RPT_DMSK_FN_CASHFLOW", report_date=report_date, page_size=500)
    )

    core = _normalize_yjbb(yjbb, market=market, report_date=report_date)
    if core.empty:
        return core
    core = core[core["symbol"].str.split(".").str[0].isin(markets)]
    balance_factors = _normalize_balance(balance, market=market, report_date=report_date)
    cash_factors = _normalize_cash_flow(cash_flow, market=market, report_date=report_date)

    out = core.merge(balance_factors, on=["market", "symbol", "report_date"], how="left")
    out = out.merge(cash_factors, on=["market", "symbol", "report_date"], how="left")
    out["source"] = "eastmoney.datacenter.RPT_LICO_FN_CPD/RPT_DMSK_FN_BALANCE/RPT_DMSK_FN_CASHFLOW"
    out["updated_at"] = datetime.now().isoformat(timespec="seconds")
    return out


def _fetch_eastmoney_report(report_name: str, *, report_date: str, page_size: int = 500) -> pd.DataFrame:
    params = {
        "sortColumns": _sort_columns(report_name),
        "sortTypes": "-1,-1",
        "pageSize": str(page_size),
        "pageNumber": "1",
        "reportName": report_name,
        "columns": "ALL",
        "filter": _report_filter(report_name, report_date),
    }
    first = _get_eastmoney_json(params)
    result = first.get("result") or {}
    pages = int(result.get("pages") or 0)
    if pages <= 0:
        return pd.DataFrame()
    rows = list(result.get("data") or [])
    for page in range(2, pages + 1):
        params["pageNumber"] = str(page)
        data_json = _get_eastmoney_json(params)
        rows.extend((data_json.get("result") or {}).get("data") or [])
        time_module.sleep(0.05)
    return pd.DataFrame(rows)


def _get_eastmoney_json(params: dict[str, str]) -> dict[str, Any]:
    response = requests.get(EASTMONEY_DATACENTER_URL, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()
    if not data.get("success", False):
        raise RuntimeError(f"Eastmoney request failed: {data}")
    return data


def _sort_columns(report_name: str) -> str:
    if report_name == "RPT_LICO_FN_CPD":
        return "UPDATE_DATE,SECURITY_CODE"
    return "NOTICE_DATE,SECURITY_CODE"


def _report_filter(report_name: str, report_date: str) -> str:
    if report_name == "RPT_LICO_FN_CPD":
        return f"(REPORTDATE='{report_date}')"
    return (
        '(SECURITY_TYPE_CODE in ("058001001","058001008"))'
        '(TRADE_MARKET_CODE!="069001017")'
        f"(REPORT_DATE='{report_date}')"
    )


def _normalize_yjbb(df: pd.DataFrame, *, market: str, report_date: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    out = pd.DataFrame(
        {
            "market": market,
            "symbol": df.get("SECURITY_CODE", pd.Series(index=df.index, dtype=object)).map(normalize_cn_symbol),
            "report_date": report_date,
            "name": df.get("SECURITY_NAME_ABBR", pd.Series("", index=df.index)),
            "industry": df.get("BOARD_NAME", df.get("PUBLISHNAME", pd.Series("", index=df.index))),
            "announce_date": _clean_date_series(df.get("NOTICE_DATE", df.get("UPDATE_DATE", pd.Series(index=df.index, dtype=object)))),
            "roe": _clean_numeric(df.get("WEIGHTAVG_ROE", pd.Series(index=df.index, dtype=object))),
            "revenue": _clean_numeric(df.get("TOTAL_OPERATE_INCOME", pd.Series(index=df.index, dtype=object))),
            "revenue_growth": _clean_numeric(df.get("YSTZ", pd.Series(index=df.index, dtype=object))),
            "net_profit": _clean_numeric(df.get("PARENT_NETPROFIT", pd.Series(index=df.index, dtype=object))),
            "profit_growth": _clean_numeric(df.get("SJLTZ", pd.Series(index=df.index, dtype=object))),
        }
    )
    out = _with_fiscal_parts(out)
    return out[out["symbol"] != ""].drop_duplicates(["market", "symbol", "report_date"], keep="first")


def _normalize_balance(df: pd.DataFrame, *, market: str, report_date: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["market", "symbol", "report_date", "debt_to_asset", "total_assets", "total_liabilities", "total_equity"])
    total_assets = _clean_numeric(df.get("TOTAL_ASSETS", pd.Series(index=df.index, dtype=object)))
    total_liabilities = _clean_numeric(df.get("TOTAL_LIABILITIES", pd.Series(index=df.index, dtype=object)))
    debt_to_asset = _clean_numeric(df.get("DEBT_ASSET_RATIO", pd.Series(index=df.index, dtype=object)))
    computed_debt_to_asset = np.where(total_assets.abs() > 0, total_liabilities / total_assets * 100.0, np.nan)
    out = pd.DataFrame(
        {
            "market": market,
            "symbol": df.get("SECURITY_CODE", pd.Series(index=df.index, dtype=object)).map(normalize_cn_symbol),
            "report_date": report_date,
            "debt_to_asset": debt_to_asset.where(debt_to_asset.notna(), computed_debt_to_asset),
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "total_equity": _clean_numeric(df.get("TOTAL_EQUITY", pd.Series(index=df.index, dtype=object))),
        }
    )
    return out[out["symbol"] != ""].drop_duplicates(["market", "symbol", "report_date"], keep="first")


def _normalize_cash_flow(df: pd.DataFrame, *, market: str, report_date: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["market", "symbol", "report_date", "operating_cash_flow"])
    out = pd.DataFrame(
        {
            "market": market,
            "symbol": df.get("SECURITY_CODE", pd.Series(index=df.index, dtype=object)).map(normalize_cn_symbol),
            "report_date": report_date,
            "operating_cash_flow": _clean_numeric(df.get("NETCASH_OPERATE", pd.Series(index=df.index, dtype=object))),
        }
    )
    return out[out["symbol"] != ""].drop_duplicates(["market", "symbol", "report_date"], keep="first")


def _finalize_factors(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    net_profit = pd.to_numeric(out.get("net_profit"), errors="coerce")
    operating_cash_flow = pd.to_numeric(out.get("operating_cash_flow"), errors="coerce")
    out["operating_cash_flow_to_net_profit"] = np.where(net_profit.abs() > 0, operating_cash_flow / net_profit, np.nan)
    cols = [
        "market",
        "symbol",
        "report_date",
        "fiscal_year",
        "fiscal_quarter",
        "announce_date",
        "name",
        "industry",
        "roe",
        "revenue",
        "revenue_growth",
        "net_profit",
        "profit_growth",
        "operating_cash_flow",
        "operating_cash_flow_to_net_profit",
        "debt_to_asset",
        "total_assets",
        "total_liabilities",
        "total_equity",
        "source",
        "updated_at",
    ]
    for col in cols:
        if col not in out.columns:
            out[col] = np.nan
    return out[cols].drop_duplicates(["market", "symbol", "report_date"], keep="first")


def _replace_period_rows(conn: sqlite3.Connection, *, table: str, factors: pd.DataFrame) -> int:
    table = _safe_identifier(table)
    for market, report_date in factors[["market", "report_date"]].dropna().drop_duplicates().itertuples(index=False):
        conn.execute(f"DELETE FROM {table} WHERE market = ? AND report_date = ?", (str(market), str(report_date)))
    rows = factors.where(pd.notna(factors), None)
    rows.to_sql(table, conn, if_exists="append", index=False)
    return len(factors)


def _resolve_periods(cfg: dict[str, Any], periods_override: int | None) -> list[str]:
    explicit = cfg.get("report_periods")
    if explicit:
        return [_period_to_yyyymmdd(str(item)) for item in explicit]
    periods = int(periods_override or cfg.get("periods", 8))
    return _quarter_end_periods(date.today(), periods)


def _quarter_end_periods(today: date, periods: int) -> list[str]:
    quarter_months = (3, 6, 9, 12)
    year = today.year
    eligible_months = [month for month in quarter_months if month <= today.month]
    if not eligible_months:
        year -= 1
        month = 12
    else:
        month = max(eligible_months)
        quarter_end = date(year, month, _quarter_end_day(month))
        if today < quarter_end:
            month -= 3
            if month <= 0:
                month = 12
                year -= 1
    out: list[str] = []
    while len(out) < periods:
        out.append(f"{year:04d}{month:02d}{_quarter_end_day(month):02d}")
        month -= 3
        if month <= 0:
            month = 12
            year -= 1
    return out


def _quarter_end_day(month: int) -> int:
    return 31 if month in {3, 12} else 30


def _period_to_iso(period: str) -> str:
    raw = _period_to_yyyymmdd(period)
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def _period_to_yyyymmdd(period: str) -> str:
    digits = re.sub(r"\D", "", str(period))
    if len(digits) != 8:
        raise ValueError(f"invalid report period: {period}")
    return digits


def _with_fiscal_parts(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    parsed = pd.to_datetime(out["report_date"], errors="coerce")
    out["fiscal_year"] = parsed.dt.year.astype("Int64")
    out["fiscal_quarter"] = parsed.dt.quarter.astype("Int64")
    return out


def _clean_numeric(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .replace({"": np.nan, "nan": np.nan, "None": np.nan, "NaT": np.nan})
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _clean_date_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.date.astype(str).replace({"NaT": ""})


def _safe_identifier(value: str) -> str:
    if not value or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Unsafe SQL identifier: {value}")
    return value
