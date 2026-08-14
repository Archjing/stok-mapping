"""Fetch 5-min bars for all enabled single_etf_intraday simulated accounts.

Reads config.yaml accounts.simulated; for every account with:
  - enabled: true
  - execution_model == "single_etf_intraday"
  - strategy_params.target_symbol set

it fetches 5-min bars for that target_symbol from Eastmoney and upserts into
the account's intraday_data_path (default data/etf_history.sqlite).

Account disabled → symbol skipped → no data fetched. This ties the intraday
data pipeline to the simulated-account on/off switch.

Live-run boundary (P1): each invocation writes an audit row to
``etf_5min_fetch_runs`` recording accounts touched, bars inserted/skipped,
expected-vs-actual coverage gap for the requested window, and a status. A
non-zero exit code signals failure so an orchestrator can retry / alert.
This makes a fetch traceable from run row -> symbols -> inserted bars.

Usage:
  .venv/bin/python3 scripts/fetch_etf_5min_accounts.py [--dry-run] [--config config.yaml] [--since YYYY-MM-DD]
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quant.config import load_config

DB_PATH = Path("data/etf_history.sqlite")
TABLE = "market_etf_5min_bars"
RUNS_TABLE = "etf_5min_fetch_runs"

EM_URL = (
    "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    "?secid={secid}"
    "&fields1=f1,f2,f3,f4,f5,f6"
    "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
    "&klt=5&fqt=0"
    "&beg={beg}&end={end}"
    "&lmt=500"
)

# A-share session: 48 five-minute bars per full trading day, derived from
# market_schedules (09:35..11:30, 13:05..15:00) instead of hardcoded tuples.
def _session_bar_times() -> list[str]:
    from quant.market_schedule import session_bar_times

    return session_bar_times({}, "cn", 5)


SESSION_BAR_TIMES = _session_bar_times()


def eastmoney_secid(symbol: str) -> str:
    """SH.512480 → 1.512480; SZ.159995 → 0.159995"""
    market, code = symbol.split(".")
    mkt = "1" if market == "SH" else "0"
    return f"{mkt}.{code}"


def fetch_bars(secid: str, beg: str, end: str) -> list[dict]:
    url = EM_URL.format(secid=secid, beg=beg.replace("-", ""), end=end.replace("-", ""))
    result = None
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


def ensure_runs_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {RUNS_TABLE} (
            run_id TEXT PRIMARY KEY,
            invoked_at TEXT NOT NULL,
            requested_window_start TEXT NOT NULL,
            requested_window_end TEXT NOT NULL,
            account_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            status TEXT NOT NULL,
            inserted_bars INTEGER NOT NULL DEFAULT 0,
            skipped_bars INTEGER NOT NULL DEFAULT 0,
            expected_bars INTEGER NOT NULL DEFAULT 0,
            missing_bars INTEGER NOT NULL DEFAULT 0,
            missing_bar_times TEXT NOT NULL DEFAULT '[]',
            error_summary TEXT NOT NULL DEFAULT '',
            dry_run INTEGER NOT NULL DEFAULT 0
        )
        """
    )


def expected_bar_count(since: date, now: datetime) -> int:
    """Number of 5-min bars expected from ``since`` 09:35 up to the current bar."""
    now_ts = now.time()
    # Bars with bar-time <= now, within session windows (derived from market_schedules).
    count = 0
    for bar_str in SESSION_BAR_TIMES:
        hh, mm, _ss = bar_str.split(":")
        if time(int(hh), int(mm)) <= now_ts:
            count += 1
    # For a full completed session this equals 48.
    return count


def missing_bar_times(conn: sqlite3.Connection, symbol: str, since: date, now: datetime) -> list[str]:
    """Return bar times (HH:MM:SS) expected up to ``now`` but missing for the day."""
    present = {
        str(row[0]).split(" ")[1]  # "YYYY-MM-DD HH:MM:SS" -> "HH:MM:SS"
        for row in conn.execute(
            f"SELECT time FROM {TABLE} WHERE symbol=? AND time >= ? AND time <= ?",
            (symbol, f"{since.isoformat()} 00:00:00", f"{since.isoformat()} 23:59:59"),
        ).fetchall()
    }
    missing = []
    for hm in SESSION_BAR_TIMES:
        bar_ts = datetime.strptime(hm, "%H:%M:%S").time()
        if bar_ts > now.time():
            continue
        if hm not in present:
            missing.append(hm)
    return missing


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    config_path = Path("config.yaml")
    for i, arg in enumerate(sys.argv):
        if arg == "--config" and i + 1 < len(sys.argv):
            config_path = Path(sys.argv[i + 1])

    since = None
    for i, arg in enumerate(sys.argv):
        if arg == "--since" and i + 1 < len(sys.argv):
            since = date.fromisoformat(sys.argv[i + 1])

    cfg = load_config(config_path)
    targets = enabled_intraday_targets(cfg)

    if not targets:
        print("No enabled single_etf_intraday accounts — nothing to fetch.")
        return 0

    today = since or date.today()
    now = datetime.now()
    total_ins = total_skp = 0
    any_failure = False
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_rows = []

    for account_id, symbol, db_path in targets:
        secid = eastmoney_secid(symbol)
        bars = fetch_bars(secid, today.isoformat(), today.isoformat())
        print(f"[{account_id}] {symbol}: {len(bars)} bars from Eastmoney")

        db = Path(db_path)
        db.parent.mkdir(parents=True, exist_ok=True)
        inserted = skipped = 0
        missing = []
        status = "ok"
        error_summary = ""
        with sqlite3.connect(db) as conn:
            ensure_runs_table(conn)
            if bars:
                inserted, skipped = upsert_bars(conn, symbol, bars, dry_run=dry_run)
            # Expected coverage for the requested window (today).
            expected = expected_bar_count(today, now)
            if bars:
                missing = missing_bar_times(conn, symbol, today, now)
            elif expected > 0:
                status = "failed"
                error_summary = "fetch returned no bars"
                any_failure = True
            if not dry_run:
                run_rows.append(
                    (run_id, now.isoformat(timespec="seconds"), today.isoformat(), today.isoformat(),
                     account_id, symbol, status, inserted, skipped, expected, len(missing),
                     json.dumps(missing, ensure_ascii=True), error_summary, 0)
                )
            else:
                run_rows.append(
                    (run_id, now.isoformat(timespec="seconds"), today.isoformat(), today.isoformat(),
                     account_id, symbol, status, inserted, skipped, expected, len(missing),
                     json.dumps(missing, ensure_ascii=True), error_summary, 1)
                )
        total_ins += inserted
        total_skp += skipped
        print(f"  inserted={inserted}, skipped={skipped}, expected={expected}, missing={len(missing)}")
        if missing:
            print(f"  missing bar times: {', '.join(missing[:8])}{'...' if len(missing) > 8 else ''}")

    # Write run rows in a single transaction (only if at least one account touched).
    if run_rows and not dry_run:
        first_db = Path(targets[0][2])
        with sqlite3.connect(first_db) as conn:
            ensure_runs_table(conn)
            conn.executemany(
                f"INSERT OR REPLACE INTO {RUNS_TABLE} "
                "(run_id, invoked_at, requested_window_start, requested_window_end, account_id, symbol, "
                "status, inserted_bars, skipped_bars, expected_bars, missing_bars, missing_bar_times, "
                "error_summary, dry_run) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                run_rows,
            )

    if dry_run:
        print("DRY RUN — no writes")
    # Non-zero exit when any target failed to fetch bars.
    return 1 if any_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
