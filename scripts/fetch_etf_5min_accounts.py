"""Fetch 5-min bars for all enabled single_etf_intraday simulated accounts.

Reads config.yaml accounts.simulated; for every account with:
  - enabled: true
  - execution_model == "single_etf_intraday"
  - strategy_params.target_symbol set

it fetches today's 5-min bars for that target_symbol from Eastmoney and
upserts into the account's intraday_data_path (default data/etf_history.sqlite).

Account disabled → symbol skipped → no data fetched. This ties the intraday
data pipeline to the simulated-account on/off switch.

Usage:
  .venv/bin/python3 scripts/fetch_etf_5min_accounts.py [--dry-run] [--config config.yaml]
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phase0.config import load_config

DB_PATH = Path("data/etf_history.sqlite")
TABLE = "market_etf_5min_bars"

EM_URL = (
    "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    "?secid={secid}"
    "&fields1=f1,f2,f3,f4,f5,f6"
    "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
    "&klt=5&fqt=0"
    "&beg={beg}&end={end}"
    "&lmt=500"
)


def eastmoney_secid(symbol: str) -> str:
    """SH.512480 → 1.512480; SZ.159995 → 0.159995"""
    market, code = symbol.split(".")
    mkt = "1" if market == "SH" else "0"
    return f"{mkt}.{code}"


def fetch_bars(secid: str, beg: str, end: str) -> list[dict]:
    url = EM_URL.format(secid=secid, beg=beg.replace("-", ""), end=end.replace("-", ""))
    for attempt in range(3):
        result = subprocess.run(
            ["curl", "-4", "-s", "--noproxy", "*", "--connect-timeout", "10",
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
        print(f"  JSON parse error: {result.stdout[:100]}")
        return []

    if data.get("rc") != 0 or not data.get("data"):
        return []

    bars = []
    for line in data["data"].get("klines", []):
        parts = line.split(",")
        if len(parts) < 7:
            continue
        t = parts[0].strip()
        if len(t) == 16:  # "YYYY-MM-DD HH:MM" → add seconds
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


def upsert_bars(conn: sqlite3.Connection, symbol: str, bars: list[dict], *, dry_run: bool) -> tuple[int, int]:
    inserted = skipped = 0
    for b in bars:
        exists = conn.execute(
            f"SELECT 1 FROM {TABLE} WHERE symbol=? AND time=?",
            (symbol, b["time"]),
        ).fetchone()
        if exists:
            skipped += 1
            continue
        if not dry_run:
            conn.execute(
                f"INSERT INTO {TABLE} (symbol,time,open,high,low,close,volume,amount) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (symbol, b["time"], b["open"], b["high"], b["low"], b["close"],
                 b["volume"], b["amount"]),
            )
        inserted += 1
    return inserted, skipped


def enabled_intraday_targets(config: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Return [(account_id, target_symbol, db_path)] for enabled intraday accounts."""
    targets = []
    accounts = config.get("accounts", {}).get("simulated", [])
    for acct in accounts:
        if not acct.get("enabled", False):
            continue
        if acct.get("execution_model") != "single_etf_intraday":
            continue
        params = acct.get("strategy_params", {}) or {}
        symbol = params.get("target_symbol", "")
        if not symbol:
            continue
        db_path = str(acct.get("intraday_data_path") or "data/etf_history.sqlite")
        targets.append((str(acct.get("account_id", "?")), symbol, db_path))
    return targets


def main():
    dry_run = "--dry-run" in sys.argv
    config_path = Path("config.yaml")
    for i, arg in enumerate(sys.argv):
        if arg == "--config" and i + 1 < len(sys.argv):
            config_path = Path(sys.argv[i + 1])

    cfg = load_config(config_path)
    targets = enabled_intraday_targets(cfg)

    if not targets:
        print("No enabled single_etf_intraday accounts — nothing to fetch.")
        return 0

    today = date.today().strftime("%Y-%m-%d")
    total_ins = total_skp = 0
    for account_id, symbol, db_path in targets:
        secid = eastmoney_secid(symbol)
        bars = fetch_bars(secid, today, today)
        print(f"[{account_id}] {symbol}: {len(bars)} bars from Eastmoney")

        if not bars:
            continue

        db = Path(db_path)
        db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db) as conn:
            ins, skp = upsert_bars(conn, symbol, bars, dry_run=dry_run)
        total_ins += ins
        total_skp += skp
        print(f"  inserted={ins}, skipped={skp}")

    if dry_run:
        print("DRY RUN — no writes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
