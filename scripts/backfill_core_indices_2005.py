"""Backfill 5 core indices to 2005 via tushare index_daily.

Indices: 全指成长(000057), 全指价值(000058), 沪深300(000300), 中证500(000905),
中证1000(000852).

Writes into market_index_bars (market/symbol/date/frequency/OHLC/volume/amount/
advances/declines/name/source).

Usage:
    .venv/bin/python3 scripts/backfill_core_indices_2005.py
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DB = Path("data/a_share_history.sqlite")

# ts_code -> (symbol, name)
INDICES = {
    "000057.SH": ("SH.000057", "全指成长"),
    "000058.SH": ("SH.000058", "全指价值"),
    "000300.SH": ("SH.000300", "沪深300"),
    "000905.SH": ("SH.000905", "中证500"),
    "000852.SH": ("SH.000852", "中证1000"),
}


def _load_env(root: Path) -> None:
    env_path = root / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _existing_min_date(conn: sqlite3.Connection, symbol: str) -> str | None:
    row = conn.execute(
        "SELECT MIN(date) FROM market_index_bars WHERE symbol=?", (symbol,)
    ).fetchone()
    return row[0] if row and row[0] else None


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    _load_env(root)
    import tushare as ts

    pro = ts.pro_api(os.environ["TUSHARE_TOKEN"])

    with sqlite3.connect(DB) as conn:
        for ts_code, (symbol, name) in INDICES.items():
            min_date = _existing_min_date(conn, symbol)
            print(f"\n=== {symbol} {name} (ts={ts_code}) ===")
            print(f"  现有最早日期: {min_date or '无'}")

            # fetch full history from 2005
            start = "20050101"
            end = datetime.now().strftime("%Y%m%d")
            df = pro.index_daily(ts_code=ts_code, start_date=start, end_date=end)
            if df.empty:
                print("  tushare 无数据")
                continue
            print(f"  tushare 返回 {len(df)} 行 ({df['trade_date'].min()}~{df['trade_date'].max()})")

            inserted = 0
            for _, r in df.iterrows():
                d = r["trade_date"]
                # only insert rows before current min_date (fill the gap)
                if min_date and d >= min_date:
                    continue
                conn.execute(
                    """INSERT OR IGNORE INTO market_index_bars
                       (market, symbol, date, frequency, open, high, low, close, volume, amount, advances, declines, name, source)
                       VALUES ('CN', ?, ?, 'D', ?, ?, ?, ?, ?, ?, NULL, NULL, ?, 'tushare.index_daily')""",
                    (
                        symbol,
                        f"{d[:4]}-{d[4:6]}-{d[6:8]}",
                        r["open"], r["high"], r["low"], r["close"],
                        r.get("vol"), r.get("amount"),
                        name,
                    ),
                )
                inserted += 1
            print(f"  新增 {inserted} 行")
            conn.commit()

    print("\n=== 回补后覆盖 ===")
    with sqlite3.connect(DB) as conn:
        for symbol in [s for _, (s, _) in INDICES.items()]:
            r = conn.execute(
                "SELECT MIN(date), MAX(date), COUNT(*) FROM market_index_bars WHERE symbol=?",
                (symbol,),
            ).fetchone()
            print(f"  {symbol}: {r[0]}~{r[1]}, {r[2]} 根")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
