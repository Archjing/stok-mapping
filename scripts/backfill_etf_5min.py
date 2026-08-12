"""Extract 5-min bars for specific ETFs from ETF_5min_2005_2025.zip
and ETF_5min_Date/2026-*/ daily ZIPs, upsert into etf_history.sqlite.

Usage:
    .venv/bin/python3 scripts/backfill_etf_5min.py [--dry-run]
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
import zipfile
from datetime import datetime
from io import StringIO
from pathlib import Path

DOWNLOAD_DIR = Path.home() / "Downloads/etf"
DB_PATH = Path("data/etf_history.sqlite")
TABLE = "market_etf_5min_bars"
ZIP_2005_2025 = DOWNLOAD_DIR / "ETF_5min_2005_2025.zip"
DATE_DIR = DOWNLOAD_DIR / "ETF_5min_Date"

TARGETS = {
    "512760.SH": "SH.512760",
    "516640.SH": "SH.516640",
    "159995.SZ": "SZ.159995",
    "588200.SH": "SH.588200",
    "159801.SZ": "SZ.159801",
}


def parse_time(raw: str) -> str:
    """Normalize time to YYYY-MM-DD HH:MM:SS."""
    raw = raw.strip()
    if "-" in raw[:10] and ":" in raw:  # "2019-06-12 09:35:00"
        if len(raw) == 16:  # "2019-06-12 09:35"
            return raw + ":00"
        return raw
    if "/" in raw[:10]:  # "2026/08/11 09:35"
        if len(raw) == 16:
            raw += ":00"
        dt = datetime.strptime(raw, "%Y/%m/%d %H:%M:%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    raise ValueError(f"Unrecognized time format: {raw}")


def process_zip_csv(raw: str, store_symbol: str) -> list[tuple]:
    """Parse a single ETF 5-min CSV. Returns list of (symbol, time, open, high, low, close, volume, amount)."""
    rows = []
    lines = raw.strip().split("\n")
    header = lines[0] if lines else ""
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) < 8:
            continue
        try:
            t = parse_time(parts[0])
            # Format in ZIP: time, code, name, open, close, high, low, volume, amount, ...
            o = float(parts[3])
            c = float(parts[4])
            h = float(parts[5])
            l = float(parts[6])
            v = float(parts[7])
            a = float(parts[8]) if len(parts) > 8 else 0.0
        except (ValueError, IndexError):
            continue
        rows.append((store_symbol, t, o, h, l, c, v, a))
    return rows


def upsert_bars(conn: sqlite3.Connection, rows: list[tuple], *, dry_run: bool) -> tuple[int, int]:
    inserted = skipped = 0
    for sym, t, o, h, l, c, v, a in rows:
        exists = conn.execute(
            f"SELECT 1 FROM {TABLE} WHERE symbol=? AND time=?", (sym, t)
        ).fetchone()
        if exists:
            skipped += 1
            continue
        if not dry_run:
            conn.execute(
                f"INSERT INTO {TABLE} (symbol,time,open,high,low,close,volume,amount) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (sym, t, o, h, l, c, v, a),
            )
        inserted += 1
    return inserted, skipped


def main():
    dry_run = "--dry-run" in sys.argv

    with sqlite3.connect(DB_PATH) as conn:
        total_ins = total_skp = 0

        # ── 2005-2025 ZIP ───────────────────────────────────────
        if ZIP_2005_2025.exists():
            print(f"Extracting from {ZIP_2005_2025.name}...")
            with zipfile.ZipFile(ZIP_2005_2025, "r") as zf:
                for csv_name, store_symbol in TARGETS.items():
                    csv_path = csv_name + ".csv"
                    try:
                        raw = zf.read(csv_path).decode("utf-8-sig", errors="replace")
                    except KeyError:
                        print(f"  {csv_name}: not found in ZIP")
                        continue
                    bars = process_zip_csv(raw, store_symbol)
                    ins, skp = upsert_bars(conn, bars, dry_run=dry_run)
                    print(f"  {store_symbol}: +{ins}, skip={skp}")
                    total_ins += ins
                    total_skp += skp
        else:
            print(f"ZIP not found: {ZIP_2005_2025}")

        # ── 2026 daily ZIPs ─────────────────────────────────────
        if DATE_DIR.exists():
            print(f"\nProcessing 2026 daily ZIPs from {DATE_DIR}...")
            daily_zips = sorted(DATE_DIR.rglob("*_5min.zip"))
            for dz in daily_zips:
                with zipfile.ZipFile(dz, "r") as zf:
                    for csv_name, store_symbol in TARGETS.items():
                        csv_path = csv_name + ".csv"
                        try:
                            raw = zf.read(csv_path).decode("utf-8", errors="replace")
                        except KeyError:
                            continue
                        bars = process_zip_csv(raw, store_symbol)
                        if bars:
                            ins, skp = upsert_bars(conn, bars, dry_run=dry_run)
                            total_ins += ins
                            total_skp += skp
            print(f"  2026 dailies: +{total_ins}, skip={total_skp}")

        if not dry_run:
            conn.commit()

        # ── Summary ─────────────────────────────────────────────
        print(f"\n{'='*50}")
        for store_symbol in TARGETS.values():
            r = conn.execute(
                f"SELECT COUNT(*), MIN(time), MAX(time) FROM {TABLE} WHERE symbol=?",
                (store_symbol,),
            ).fetchone()
            if r[1]:
                print(f"  {store_symbol}: {r[0]} rows, {r[1][:10]} ~ {r[2][:10]}")
            else:
                print(f"  {store_symbol}: {r[0]} rows (no data yet)")

        if dry_run:
            print("DRY RUN — no writes")


if __name__ == "__main__":
    raise SystemExit(main())
