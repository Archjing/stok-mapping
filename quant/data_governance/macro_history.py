"""China/US macro data source: interest rates, money supply, credit, inflation.

Stores a unified long-format macro series table in ``data/macro_history.sqlite``:

- ``macro_series``: (symbol, date, value, freq, source, source_series_id, fetched_at)
- ``macro_source_runs``: audit trail of fetch runs

Data sources (per project data-source hierarchy):
- China rates/money/credit/inflation: Tushare (``shibor``, ``cn_m``, ``sf_month``,
  ``cn_cpi``, ``cn_gdp``) + AkShare ``bond_china_yield`` (国债收益率曲线).
- US rates: FRED (``DGS10``, ``DFF``/``FEDFUNDS``) via ``fetch_fred_series``.

All series are point-in-time by their publish date (no lookahead): a monthly
value is stored at its publication month.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_DB = Path("data/macro_history.sqlite")
MACRO_TABLE = "macro_series"
SOURCE_RUNS_TABLE = "macro_source_runs"


@dataclass(frozen=True)
class MacroSeriesSpec:
    symbol: str
    name: str
    market: str  # "CN" | "US"
    freq: str  # "D" | "M" | "Q"
    source: str  # "tushare" | "akshare" | "fred"
    source_series_id: str  # upstream id (tushare api / akshare column / FRED series)
    description: str = ""


# The macro series we backfill for style-rotation research.
MACRO_SERIES: list[MacroSeriesSpec] = [
    # China interest rates (10y yield is the key discount-rate proxy for growth/value)
    MacroSeriesSpec("CN_10Y_YIELD", "中国10年国债收益率", "CN", "D", "akshare", "中债国债收益率曲线:10年", "10y government bond yield"),
    MacroSeriesSpec("CN_1Y_YIELD", "中国1年国债收益率", "CN", "D", "akshare", "中债国债收益率曲线:1年", "1y government bond yield"),
    # China money supply & credit
    MacroSeriesSpec("CN_M2_YOY", "中国M2同比", "CN", "M", "tushare", "cn_m:m2_yoy", "M2 growth YoY"),
    MacroSeriesSpec("CN_M1_YOY", "中国M1同比", "CN", "M", "tushare", "cn_m:m1_yoy", "M1 growth YoY"),
    MacroSeriesSpec("CN_SOCIAL_FINANCE", "中国社融当月增量", "CN", "M", "tushare", "sf_month:inc_month", "social financing monthly increment"),
    MacroSeriesSpec("CN_CPI_YOY", "中国CPI同比", "CN", "M", "tushare", "cn_cpi:nt_yoy", "CPI YoY"),
    MacroSeriesSpec("CN_GDP_YOY", "中国GDP同比", "CN", "Q", "tushare", "cn_gdp:gdp_yoy", "GDP YoY"),
    # China interbank rate (liquidity proxy)
    MacroSeriesSpec("CN_SHIBOR_3M", "Shibor 3个月", "CN", "D", "tushare", "shibor:3m", "3-month SHIBOR"),
    # US interest rates
    MacroSeriesSpec("US_10Y_YIELD", "美国10年国债收益率", "US", "D", "fred", "DGS10", "10y Treasury yield"),
    MacroSeriesSpec("US_FED_FUNDS", "美国联邦基金利率", "US", "D", "fred", "DFF", "effective fed funds rate"),
    MacroSeriesSpec("US_2Y_YIELD", "美国2年国债收益率", "US", "D", "fred", "DGS2", "2y Treasury yield"),
]


def ensure_macro_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MACRO_TABLE} (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            value REAL,
            freq TEXT,
            source TEXT,
            source_series_id TEXT,
            fetched_at TEXT,
            PRIMARY KEY (symbol, date)
        )
        """
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_macro_symbol_date ON {MACRO_TABLE}(symbol, date)"
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SOURCE_RUNS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            fetched_at TEXT,
            fetched_rows INTEGER,
            inserted_rows INTEGER,
            status TEXT,
            message TEXT
        )
        """
    )


def upsert_macro_series(
    db_path: Path,
    rows: pd.DataFrame,
    *,
    source: str,
    freq: str = "M",
) -> int:
    """Upsert macro series rows. ``rows`` must have symbol/date/value columns."""
    if rows.empty:
        return 0
    db_path.parent.mkdir(parents=True, exist_ok=True)
    now = pd.Timestamp.now().isoformat(timespec="seconds")
    changed = 0
    with sqlite3.connect(db_path) as conn:
        ensure_macro_tables(conn)
        for _, r in rows.iterrows():
            symbol = str(r["symbol"])
            date = str(r["date"])[:10]
            value = r.get("value")
            if pd.isna(value):
                continue
            conn.execute(
                f"""
                INSERT INTO {MACRO_TABLE} (symbol, date, value, freq, source, source_series_id, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, date) DO UPDATE SET
                    value=excluded.value, source=excluded.source, fetched_at=excluded.fetched_at
                """,
                (symbol, date, float(value), freq, source, symbol, now),
            )
            changed += 1
        conn.execute(
            f"INSERT INTO {SOURCE_RUNS_TABLE} (source, fetched_at, fetched_rows, inserted_rows, status, message) VALUES (?, ?, ?, ?, ?, ?)",
            (source, now, len(rows), changed, "ok", ""),
        )
    return changed


def load_macro_series(
    db_path: Path,
    *,
    symbol: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    if not db_path.is_file():
        return pd.DataFrame()
    clauses: list[str] = []
    params: list[Any] = []
    if symbol:
        clauses.append("symbol = ?")
        params.append(symbol)
    if start:
        clauses.append("date >= ?")
        params.append(start)
    if end:
        clauses.append("date <= ?")
        params.append(end)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT symbol, date, value, freq, source FROM {MACRO_TABLE} {where} ORDER BY date"
    with sqlite3.connect(db_path) as conn:
        ensure_macro_tables(conn)
        return pd.read_sql_query(sql, conn, params=params)


def fetch_china_yield_curve(start: str, end: str) -> pd.DataFrame:
    """Fetch China + US treasury yields via AkShare ``bond_zh_us_rate``.

    One call returns both markets (2/5/10/30y) from 1990 onward — more stable
    than ``bond_china_yield`` (which returns 0 rows for long ranges).
    """
    import akshare as ak

    df = ak.bond_zh_us_rate()
    if df.empty:
        return pd.DataFrame(columns=["symbol", "date", "value"])
    df["日期"] = pd.to_datetime(df["日期"]).dt.strftime("%Y-%m-%d")
    df = df[(df["日期"] >= start) & (df["日期"] <= end)]
    rows = []
    for _, r in df.iterrows():
        if pd.notna(r.get("中国国债收益率10年")):
            rows.append({"symbol": "CN_10Y_YIELD", "date": r["日期"], "value": r["中国国债收益率10年"]})
        if pd.notna(r.get("中国国债收益率2年")):
            rows.append({"symbol": "CN_1Y_YIELD", "date": r["日期"], "value": r["中国国债收益率2年"]})
        if pd.notna(r.get("美国国债收益率10年")):
            rows.append({"symbol": "US_10Y_YIELD", "date": r["日期"], "value": r["美国国债收益率10年"]})
        if pd.notna(r.get("美国国债收益率2年")):
            rows.append({"symbol": "US_2Y_YIELD", "date": r["日期"], "value": r["美国国债收益率2年"]})
    return pd.DataFrame(rows)


def fetch_tushare_monthly(pro, api: str, field_map: dict[str, str], date_col: str) -> pd.DataFrame:
    """Fetch a monthly tushare series and map to symbol/date/value rows."""
    df = getattr(pro, api)()
    rows = []
    for _, r in df.iterrows():
        month = str(r[date_col])
        date = f"{month[:4]}-{month[4:6]}-01" if len(month) >= 6 else month
        for symbol, src_field in field_map.items():
            val = r.get(src_field)
            if val is None or pd.isna(val):
                continue
            rows.append({"symbol": symbol, "date": date, "value": val})
    return pd.DataFrame(rows)
