"""Import ETF daily data and adjustment factors from ~/Downloads/etf/ RAR/ZIP files.

Sources:
  - 0_ETF日K(除权).rar + supplement    → market_etf_daily_bars (unadjusted)
  - 0_ETF日K(后复权).rar + supplement   → extra adj type if needed
  - 0_ETF日K(前复权).rar                → extra adj type
  - ETF_复权因子_后复权.zip              → market_etf_adj_factors (backward)
  - ETF_复权因子_前复权.zip              → market_etf_adj_factors (forward)

Unit conversions:
  - 成交量(手数) × 100 = shares
  - 成交额(千元) × 1000 = yuan
  - Symbol: 512480.SH → SH.512480

Usage:
    .venv/bin/python3 scripts/import_etf_daily.py [--dry-run] [--only-adj-factors]
"""
from __future__ import annotations

import csv
import io
import os
import sqlite3
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

DOWNLOAD_DIR = Path.home() / "Downloads/etf"
DB_PATH = Path("data/etf_history.sqlite")
TMP_DIR = Path("/tmp/etf_import")

# RARs to process (name, target_table)
DAILY_RARS = [
    "0_ETF日K(除权).rar",
    "0_ETF日K(除权)_2026年_5月后.rar",
]
ADJ_ZIPS = [
    ("ETF_复权因子_后复权.zip", "hfq"),
    ("ETF_复权因子_前复权.zip", "qfq"),
]

DAILY_TABLE = "market_etf_daily_bars"
ADJ_TABLE = "market_etf_adj_factors"


def to_symbol(raw: str) -> str:
    """512480.SH → SH.512480"""
    parts = raw.strip().split(".")
    if len(parts) == 2:
        return f"{parts[1]}.{parts[0]}"
    return raw.strip()


def parse_daily_csv(path: Path) -> list[dict]:
    """Parse a single ETF daily CSV. Returns list of row dicts."""
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for line in reader:
            try:
                sym = to_symbol(line.get("代码", ""))
                if not sym:
                    continue
                dt = line.get("日期", "").strip()
                # Normalize: 20260430 → 2026-04-30, 2026-04-30 → 2026-04-30
                if len(dt) == 8 and dt.isdigit():
                    dt = f"{dt[:4]}-{dt[4:6]}-{dt[6:8]}"
                rows.append({
                    "symbol": sym,
                    "date": dt,
                    "open": float(line.get("开盘价", 0) or 0),
                    "high": float(line.get("最高价", 0) or 0),
                    "low": float(line.get("最低价", 0) or 0),
                    "close": float(line.get("收盘价", 0) or 0),
                    "pre_close": float(line.get("上日收盘", 0) or 0),
                    "change_amount": float(line.get("涨跌", 0) or 0),
                    "change_pct": float(line.get("涨幅%", 0) or 0),
                    # Unit conversion: 手→股, 千元→元
                    "volume": float(line.get("成交量(手数)", 0) or 0) * 100,
                    "amount": float(line.get("成交额(千元)", 0) or 0) * 1000,
                })
            except (ValueError, KeyError):
                continue
    return rows


def parse_adj_csv(raw: str) -> list[dict]:
    """Parse a single adj factor CSV from ZIP. Returns list of {symbol, date, adj_factor}."""
    rows = []
    lines = raw.strip().split("\n")
    if not lines:
        return rows
    # Header: 代码,日期,复权因子
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) < 3:
            continue
        sym = to_symbol(parts[0])
        dt = parts[1].strip()
        # Normalize date format
        if len(dt) == 8 and dt.isdigit():
            dt = f"{dt[:4]}-{dt[4:6]}-{dt[6:8]}"
        try:
            factor = float(parts[2])
        except ValueError:
            continue
        rows.append({"symbol": sym, "date": dt, "adj_factor": factor})
    return rows


def upsert_daily(conn: sqlite3.Connection, rows: list[dict], *, dry_run: bool, source: str) -> tuple[int, int]:
    """Upsert daily bars. Returns (inserted, updated)."""
    ins = upd = 0
    now = datetime.now().isoformat(timespec="seconds")
    for r in rows:
        exists = conn.execute(
            f"SELECT 1 FROM {DAILY_TABLE} WHERE symbol=? AND date=?",
            (r["symbol"], r["date"]),
        ).fetchone()
        if dry_run:
            ins += 1
            continue
        if exists:
            conn.execute(
                f"""UPDATE {DAILY_TABLE} SET open=?,high=?,low=?,close=?,pre_close=?,
                    change_amount=?,change_pct=?,volume=?,amount=?,source=?,fetched_at=?
                    WHERE symbol=? AND date=?""",
                (r["open"], r["high"], r["low"], r["close"], r["pre_close"],
                 r["change_amount"], r["change_pct"], r["volume"], r["amount"],
                 source, now, r["symbol"], r["date"]),
            )
            upd += 1
        else:
            conn.execute(
                f"""INSERT INTO {DAILY_TABLE}
                    (symbol,date,open,high,low,close,pre_close,change_amount,change_pct,
                     volume,amount,source,fetched_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (r["symbol"], r["date"], r["open"], r["high"], r["low"], r["close"],
                 r["pre_close"], r["change_amount"], r["change_pct"],
                 r["volume"], r["amount"], source, now),
            )
            ins += 1
    return ins, upd


def upsert_adj(conn: sqlite3.Connection, rows: list[dict], *, dry_run: bool, source: str) -> tuple[int, int]:
    """Upsert adj factors. Returns (inserted, updated)."""
    ins = upd = 0
    now = datetime.now().isoformat(timespec="seconds")
    for r in rows:
        exists = conn.execute(
            f"SELECT 1 FROM {ADJ_TABLE} WHERE symbol=? AND date=?",
            (r["symbol"], r["date"]),
        ).fetchone()
        if dry_run:
            ins += 1
            continue
        if exists:
            conn.execute(
                f"UPDATE {ADJ_TABLE} SET adj_factor=?,source=?,fetched_at=? WHERE symbol=? AND date=?",
                (r["adj_factor"], source, now, r["symbol"], r["date"]),
            )
            upd += 1
        else:
            conn.execute(
                f"INSERT INTO {ADJ_TABLE} (symbol,date,adj_factor,source,fetched_at) VALUES (?,?,?,?,?)",
                (r["symbol"], r["date"], r["adj_factor"], source, now),
            )
            ins += 1
    return ins, upd


def main():
    dry_run = "--dry-run" in sys.argv
    only_adj = "--only-adj-factors" in sys.argv

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    extracted_dir = TMP_DIR / "daily"
    extracted_dir.mkdir(exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        # ── Daily bars ───────────────────────────────────────────
        if not only_adj:
            total_ins = total_upd = 0
            for rar_name in DAILY_RARS:
                rar_path = DOWNLOAD_DIR / rar_name
                if not rar_path.exists():
                    print(f"SKIP (not found): {rar_name}")
                    continue
                print(f"\nExtracting {rar_name}...")
                subprocess.run(
                    ["bsdtar", "-xf", str(rar_path), "-C", str(extracted_dir)],
                    capture_output=True, check=True,
                )
                # Find extracted CSVs
                inner_dir = rar_name.replace(".rar", "")
                csv_dir = extracted_dir / inner_dir
                if not csv_dir.exists():
                    # Try without prefix
                    for d in extracted_dir.iterdir():
                        if d.is_dir() and "ETF日K" in d.name:
                            csv_dir = d
                            break
                if not csv_dir.exists():
                    print(f"  WARNING: no extracted dir found for {rar_name}")
                    continue

                csv_files = sorted(csv_dir.glob("*.csv"))
                print(f"  {len(csv_files)} CSV files")
                for cf in csv_files:
                    rows = parse_daily_csv(cf)
                    if not rows:
                        continue
                    ins, upd = upsert_daily(conn, rows, dry_run=dry_run, source=f"rar_import:{rar_name}")
                    total_ins += ins
                    total_upd += upd
                print(f"  inserted={total_ins}, updated={total_upd}")

            if dry_run:
                print("\nDRY RUN — no writes for daily bars")

        # ── Adjustment factors ───────────────────────────────────
        print()
        adj_total_ins = adj_total_upd = 0
        for zip_name, adj_kind in ADJ_ZIPS:
            zip_path = DOWNLOAD_DIR / zip_name
            if not zip_path.exists():
                print(f"SKIP (not found): {zip_name}")
                continue
            print(f"Processing {zip_name}...")
            ins = upd = 0
            with zipfile.ZipFile(zip_path, "r") as zf:
                for name in zf.namelist():
                    if not name.endswith(".csv"):
                        continue
                    raw = zf.read(name).decode("utf-8-sig", errors="replace")
                    rows = parse_adj_csv(raw)
                    if not rows:
                        continue
                    i, u = upsert_adj(conn, rows, dry_run=dry_run, source=f"{adj_kind}:{zip_name}")
                    ins += i
                    upd += u
            print(f"  {zip_name}: inserted={ins}, updated={upd}")
            adj_total_ins += ins
            adj_total_upd += upd

        if not dry_run:
            conn.commit()

        # ── Summary ──────────────────────────────────────────────
        print(f"\n{'='*60}")
        daily_cnt = conn.execute(f"SELECT COUNT(*) FROM {DAILY_TABLE}").fetchone()[0]
        daily_sym = conn.execute(f"SELECT COUNT(DISTINCT symbol) FROM {DAILY_TABLE}").fetchone()[0]
        adj_cnt = conn.execute(f"SELECT COUNT(*) FROM {ADJ_TABLE}").fetchone()[0]
        adj_sym = conn.execute(f"SELECT COUNT(DISTINCT symbol) FROM {ADJ_TABLE}").fetchone()[0]
        print(f"market_etf_daily_bars:  {daily_cnt} rows, {daily_sym} symbols")
        print(f"market_etf_adj_factors: {adj_cnt} rows, {adj_sym} symbols")

        if dry_run:
            print("DRY RUN — no writes committed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
