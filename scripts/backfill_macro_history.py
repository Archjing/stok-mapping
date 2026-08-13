"""Backfill China/US macro series into data/macro_history.sqlite.

Sources:
- China treasury yield curve: AkShare ``bond_china_yield`` (daily)
- China M2/M1, CPI, GDP, SHIBOR, social finance: Tushare
- US Treasury yields & fed funds: FRED (via fetch_fred_series)

Usage:
    .venv/bin/python3 scripts/backfill_macro_history.py [--start 2015-01-01]
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quant.data_governance.macro_history import (
    DEFAULT_DB,
    fetch_china_yield_curve,
    fetch_tushare_monthly,
    upsert_macro_series,
)


def _load_env(root: Path) -> None:
    env_path = root / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def backfill_china_yield(root: Path, start: str, end: str) -> int:
    print("抓取中国国债收益率曲线 (AkShare)...")
    rows = fetch_china_yield_curve(start, end)
    if rows.empty:
        print("  无数据")
        return 0
    n = upsert_macro_series(DEFAULT_DB, rows, source="akshare.bond_china_yield", freq="D")
    print(f"  入库 {n} 行")
    return n


def backfill_tushare_monthly(root: Path) -> int:
    from dotenv import load_dotenv

    load_dotenv(root / ".env")
    import tushare as ts

    pro = ts.pro_api(os.environ["TUSHARE_TOKEN"])
    total = 0

    series_specs = [
        ("cn_m", {"CN_M2_YOY": "m2_yoy", "CN_M1_YOY": "m1_yoy"}, "month", "M"),
        ("cn_cpi", {"CN_CPI_YOY": "nt_yoy"}, "month", "M"),
        ("cn_gdp", {"CN_GDP_YOY": "gdp_yoy"}, "quarter", "Q"),
        ("sf_month", {"CN_SOCIAL_FINANCE": "inc_month"}, "month", "M"),
    ]
    for api, field_map, date_col, freq in series_specs:
        print(f"抓取 tushare {api}...")
        try:
            rows = fetch_tushare_monthly(pro, api, field_map, date_col)
            if not rows.empty:
                n = upsert_macro_series(DEFAULT_DB, rows, source=f"tushare.{api}", freq=freq)
                total += n
                print(f"  {api} 入库 {n} 行")
        except Exception as e:
            print(f"  {api} ERR: {str(e)[:80]}")

    # SHIBOR 3M (daily)
    print("抓取 tushare shibor (3m)...")
    try:
        df = pro.shibor()
        rows = [{"symbol": "CN_SHIBOR_3M", "date": str(r["date"]), "value": r["3m"]}
                for _, r in df.iterrows() if pd.notna(r.get("3m"))]
        if rows:
            n = upsert_macro_series(DEFAULT_DB, pd.DataFrame(rows), source="tushare.shibor", freq="D")
            total += n
            print(f"  shibor 入库 {n} 行")
    except Exception as e:
        print(f"  shibor ERR: {str(e)[:80]}")

    return total


def backfill_fred(root: Path, start: str) -> int:
    from quant.data_access.connectivity import fetch_fred_series

    total = 0
    for symbol, series_id in [("US_10Y_YIELD", "DGS10"), ("US_FED_FUNDS", "DFF"), ("US_2Y_YIELD", "DGS2")]:
        print(f"抓取 FRED {series_id}...")
        try:
            df = fetch_fred_series(series_id, start=pd.Timestamp(start).date())
            if df is None or df.empty:
                print(f"  {series_id} 无数据")
                continue
            rows = pd.DataFrame({
                "symbol": [symbol] * len(df),
                "date": [str(d)[:10] for d in df["date"]],
                "value": df["value"].tolist(),
            })
            n = upsert_macro_series(DEFAULT_DB, rows, source=f"fred.{series_id}", freq="D")
            total += n
            print(f"  {series_id} 入库 {n} 行")
        except Exception as e:
            print(f"  {series_id} ERR: {str(e)[:80]}")
    return total


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    _load_env(root)
    start = "2015-01-01"
    end = (date.today() - timedelta(days=1)).isoformat()  # avoid future/partial dates
    if "--start" in sys.argv:
        start = sys.argv[sys.argv.index("--start") + 1]

    total = 0
    total += backfill_china_yield(root, start, end)
    total += backfill_tushare_monthly(root)
    total += backfill_fred(root, start)
    print(f"\n总计入库 {total} 行 → {DEFAULT_DB}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
