"""Fetch 512480 5-min bars from Eastmoney and upsert into etf_history.sqlite.

Eastmoney K-line format per bar:
  time, open, close, high, low, volume, amount, amplitude%, change%, change_amt, turnover%

Usage:
  # Fetch today
  .venv/bin/python3 scripts/fetch_512480_5min.py

  # Fetch specific date range
  .venv/bin/python3 scripts/fetch_512480_5min.py --start 2026-08-01 --end 2026-08-12

  # Dry-run
  .venv/bin/python3 scripts/fetch_512480_5min.py --dry-run
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path("data/etf_history.sqlite")
TABLE = "market_etf_5min_bars"
SYMBOL = "SH.512480"
SECID = "1.512480"  # Eastmoney: market=1 (SH), code=512480

EM_URL = (
    "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    "?secid={secid}"
    "&fields1=f1,f2,f3,f4,f5,f6"
    "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
    "&klt=5&fqt=0"
    "&beg={beg}&end={end}"
    "&lmt=500"
)


def fetch_bars(beg: str, end: str) -> list[dict]:
    """Fetch 5-min bars from Eastmoney. Returns list of {time, open, high, low, close, volume, amount}."""
    url = EM_URL.format(secid=SECID, beg=beg.replace("-", ""), end=end.replace("-", ""))
    for attempt in range(3):
        result = subprocess.run(
            ["curl", "-s", "--noproxy", "*", "--connect-timeout", "10",
             "-H", "User-Agent: Mozilla/5.0",
             "-H", "Referer: https://quote.eastmoney.com/",
             url],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            break
        if attempt < 2:
            import time
            time.sleep(2)
    else:
        print(f"  curl failed after 3 attempts: rc={result.returncode}")
        return []
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"  JSON parse error, raw: {result.stdout[:200]}")
        return []

    if data.get("rc") != 0 or not data.get("data"):
        print(f"  API returned rc={data.get('rc')}, no data")
        return []

    klines = data["data"].get("klines", [])
    bars = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 7:
            continue
        # fields2: f51=time, f52=open, f53=close, f54=high, f55=low,
        #          f56=volume, f57=amount, ...
        t = parts[0].strip()
        # Normalize "2026-08-11 09:35" → "2026-08-11 09:35:00"
        if len(t) == 16:  # "YYYY-MM-DD HH:MM"
            t += ":00"
        bars.append({
            "time": t,
            "open": float(parts[1]),
            "close": float(parts[2]),
            "high": float(parts[3]),
            "low": float(parts[4]),
            "volume": float(parts[5]),
            "amount": float(parts[6]),
        })
    return bars


def upsert_bars(conn: sqlite3.Connection, bars: list[dict], *, dry_run: bool = False) -> tuple[int, int]:
    """Insert new bars, skip existing. Returns (inserted, skipped)."""
    inserted = 0
    skipped = 0
    for b in bars:
        exists = conn.execute(
            f"SELECT 1 FROM {TABLE} WHERE symbol=? AND time=?",
            (SYMBOL, b["time"]),
        ).fetchone()
        if exists:
            skipped += 1
            continue
        if not dry_run:
            conn.execute(
                f"""INSERT INTO {TABLE} (symbol, time, open, high, low, close, volume, amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (SYMBOL, b["time"], b["open"], b["high"], b["low"], b["close"], b["volume"], b["amount"]),
            )
        inserted += 1
    return inserted, skipped


def main():
    dry_run = "--dry-run" in sys.argv

    # Parse date range
    beg = None
    end = None
    for i, arg in enumerate(sys.argv):
        if arg == "--start" and i + 1 < len(sys.argv):
            beg = sys.argv[i + 1]
        elif arg == "--end" and i + 1 < len(sys.argv):
            end = sys.argv[i + 1]

    today = date.today()
    if beg is None:
        # Default: fetch today
        beg = today.strftime("%Y-%m-%d")
    if end is None:
        end = beg

    print(f"Fetching {SYMBOL} 5-min bars: {beg} ~ {end}")

    bars = fetch_bars(beg, end)
    print(f"  Got {len(bars)} bars from Eastmoney")

    if not bars:
        print("  (market may not have started yet, or date is non-trading day)")
        return 0

    with sqlite3.connect(DB_PATH) as conn:
        inserted, skipped = upsert_bars(conn, bars, dry_run=dry_run)
        if not dry_run:
            conn.commit()

    print(f"  Inserted: {inserted}, Skipped: {skipped}")
    if dry_run:
        print("  DRY RUN — no writes")

    # Show latest
    with sqlite3.connect(DB_PATH) as conn:
        r = conn.execute(
            f"SELECT MAX(time), COUNT(*) FROM {TABLE} WHERE symbol=?", (SYMBOL,)
        ).fetchone()
        print(f"  DB total: {r[1]} rows, latest: {r[0]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
