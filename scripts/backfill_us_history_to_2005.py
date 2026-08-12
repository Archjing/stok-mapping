"""Backfill US market history: ^SOX and ^VIX from 2005-01-01 to existing data start.

Usage:
    cd /Users/aj/workspace/stok-mapping
    .venv/bin/python3 scripts/backfill_us_history_to_2005.py [--dry-run]
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import yfinance as yf

DB_PATH = Path("data/us_market_history.sqlite")
SYMBOLS = ["^SOX", "^VIX"]
BACKFILL_START = "2005-01-01"


def main():
    dry_run = "--dry-run" in sys.argv

    with sqlite3.connect(DB_PATH) as conn:
        # Check existing coverage
        for sym in SYMBOLS:
            row = conn.execute(
                "SELECT MIN(date), MAX(date), COUNT(*) FROM us_daily_bars WHERE symbol=?",
                (sym,),
            ).fetchone()
            print(f"Existing {sym}: {row[0]} ~ {row[1]}, {row[2]} rows")

        existing_min = None
        for sym in SYMBOLS:
            row = conn.execute(
                "SELECT MIN(date) FROM us_daily_bars WHERE symbol=?", (sym,)
            ).fetchone()
            if row and row[0]:
                dt = row[0]
                if existing_min is None or dt < existing_min:
                    existing_min = dt

        if existing_min:
            print(f"\nEarliest existing date across all symbols: {existing_min}")
            backfill_end_dt = pd.Timestamp(existing_min) - pd.Timedelta(days=1)
            backfill_end = backfill_end_dt.strftime("%Y-%m-%d")
        else:
            print("No existing data found, backfilling to today")
            backfill_end = date.today().strftime("%Y-%m-%d")

        print(f"Backfill range: {BACKFILL_START} → {backfill_end}")

        if dry_run:
            print("DRY RUN — no writes")
            return 0

        # Rate-limit courtesy pause
        import time
        print("\nWaiting 10s for rate-limit cooldown...")
        time.sleep(10)

        for sym in SYMBOLS:
            print(f"\nFetching {sym} from yfinance...")
            ticker = yf.Ticker(sym)
            try:
                df = ticker.history(start=BACKFILL_START, end=backfill_end)
            except Exception as e:
                print(f"  ERROR fetching {sym}: {e}")
                print("  Waiting 30s before retry...")
                time.sleep(30)
                try:
                    df = ticker.history(start=BACKFILL_START, end=backfill_end)
                except Exception as e2:
                    print(f"  RETRY also failed: {e2}")
                    continue

            if df.empty:
                print(f"  WARNING: no data returned for {sym}")
                continue

            df = df.reset_index()
            df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
            df = df.rename(
                columns={
                    "Date": "date",
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                }
            )

            fetched_at = datetime.now().isoformat(timespec="seconds")
            inserted = 0
            skipped = 0
            for _, row in df.iterrows():
                # Skip rows outside valid date range
                if row["date"] < BACKFILL_START:
                    continue
                # Check for existing
                exists = conn.execute(
                    "SELECT 1 FROM us_daily_bars WHERE symbol=? AND date=?",
                    (sym, row["date"]),
                ).fetchone()
                if exists:
                    skipped += 1
                    continue
                conn.execute(
                    """INSERT INTO us_daily_bars
                       (symbol, date, open, high, low, close, volume, source, fetched_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        sym,
                        row["date"],
                        float(row.get("open", 0) or 0),
                        float(row.get("high", 0) or 0),
                        float(row.get("low", 0) or 0),
                        float(row["close"]),
                        int(row.get("volume", 0) or 0),
                        "yfinance_backfill",
                        fetched_at,
                    ),
                )
                inserted += 1

            print(f"  {sym}: inserted={inserted}, skipped={skipped}")
            # Pause between symbols to avoid rate limiting
            if sym != SYMBOLS[-1]:
                print("  Waiting 5s...")
                time.sleep(5)

        conn.commit()

    # Verify
    print("\n=== After backfill ===")
    with sqlite3.connect(DB_PATH) as conn:
        for sym in SYMBOLS:
            row = conn.execute(
                "SELECT MIN(date), MAX(date), COUNT(*) FROM us_daily_bars WHERE symbol=?",
                (sym,),
            ).fetchone()
            print(f"{sym}: {row[0]} ~ {row[1]}, {row[2]} rows")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
