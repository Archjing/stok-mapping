"""Import 2026 5-min bars for 512480 from ~/Downloads/etf/ETF_5min_Date/.

Files are monthly directories containing daily ZIPs. Each ZIP has per-stock CSVs.
Target: etf_history.sqlite → market_etf_5min_bars (symbol, time, open, high, low, close, volume, amount)

Usage:
    cd /Users/aj/workspace/stok-mapping
    .venv/bin/python3 scripts/import_512480_5min_2026.py [--dry-run]
"""
from __future__ import annotations

import sqlite3
import sys
import zipfile
from datetime import datetime
from io import StringIO
from pathlib import Path

SOURCE_DIR = Path.home() / "Downloads/etf/ETF_5min_Date"
DB_PATH = Path("data/etf_history.sqlite")
TARGET_TABLE = "market_etf_5min_bars"
SYMBOL_CODE = "512480.SH"
STORE_SYMBOL = "SH.512480"

COLUMN_MAP = {
    # Source CSV column (0-indexed) → target column
    0: "time",     # "2026/08/11 09:35"
    1: "_sym",     # "512480.SH" (used for filtering)
    3: "open",
    4: "high",
    5: "low",
    6: "close",
    7: "volume",
    8: "amount",
}


def parse_time(raw: str) -> str:
    """Convert various time formats to 'YYYY-MM-DD HH:MM:SS'."""
    raw = raw.strip()
    # Already in target format: "2026-01-05 09:35:00"
    if "-" in raw[:10] and ":" in raw:
        return raw
    # Slash format: "2026/08/11 09:35" → need to add seconds
    if "/" in raw[:10]:
        dt = datetime.strptime(raw, "%Y/%m/%d %H:%M")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    # Try other common formats
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S"]:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    raise ValueError(f"Unrecognized time format: {raw}")


def process_zip(zip_path: Path, conn: sqlite3.Connection, *, dry_run: bool) -> tuple[int, int]:
    """Extract 512480 rows from a zip, insert into DB. Returns (inserted, skipped)."""
    inserted = 0
    skipped = 0
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if SYMBOL_CODE not in name:
                    continue
                raw = zf.read(name).decode("utf-8", errors="replace")
                # Parse headerless CSV
                for line in raw.strip().split("\n"):
                    parts = line.split(",")
                    if len(parts) < 9:
                        continue
                    sym = parts[1].strip()
                    if sym != SYMBOL_CODE:
                        continue
                    time_str = parse_time(parts[0])
                    # Build row values
                    try:
                        row = (
                            STORE_SYMBOL,
                            time_str,
                            float(parts[3]),  # open
                            float(parts[4]),  # high
                            float(parts[5]),  # low
                            float(parts[6]),  # close
                            float(parts[7]),  # volume
                            float(parts[8]),  # amount
                        )
                    except (ValueError, IndexError):
                        continue

                    if dry_run:
                        inserted += 1
                        continue

                    # Check for existing
                    exists = conn.execute(
                        f"SELECT 1 FROM {TARGET_TABLE} WHERE symbol=? AND time=?",
                        (STORE_SYMBOL, time_str),
                    ).fetchone()
                    if exists:
                        skipped += 1
                        continue

                    conn.execute(
                        f"""INSERT INTO {TARGET_TABLE}
                            (symbol, time, open, high, low, close, volume, amount)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        row,
                    )
                    inserted += 1
    except Exception as e:
        print(f"  WARNING: {zip_path.name}: {e}")
    return inserted, skipped


def main():
    dry_run = "--dry-run" in sys.argv

    if not SOURCE_DIR.exists():
        print(f"ERROR: source directory not found: {SOURCE_DIR}")
        return 1

    zip_files = sorted(SOURCE_DIR.rglob("*_5min.zip"))
    print(f"Found {len(zip_files)} zip files across {SOURCE_DIR}")

    total_inserted = 0
    total_skipped = 0

    with sqlite3.connect(DB_PATH) as conn:
        for zf in zip_files:
            ins, skp = process_zip(zf, conn, dry_run=dry_run)
            total_inserted += ins
            total_skipped += skp
            if ins > 0 or skp > 0:
                print(f"  {zf.parent.name}/{zf.name}: +{ins}, skip={skp}")

        if not dry_run:
            conn.commit()

    print(f"\nTotal: inserted={total_inserted}, skipped={total_skipped}")
    if dry_run:
        print("DRY RUN — no writes")
    else:
        # Verify
        with sqlite3.connect(DB_PATH) as conn:
            r = conn.execute(
                f"SELECT COUNT(*), MIN(time), MAX(time) FROM {TARGET_TABLE} WHERE symbol=?",
                (STORE_SYMBOL,),
            ).fetchone()
            print(f"After import: {r[0]} rows, {r[1]} ~ {r[2]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
