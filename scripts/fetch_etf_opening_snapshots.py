"""Store current ETF quotes for enabled intraday simulated accounts.

This script is intentionally a snapshot collector, not an order runner. Run it
at 09:15 to create an audit record and again just after 09:25 to capture the
official auction open that weak-signal limit orders use at 09:30.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phase0.config import load_config
from phase0.data_access.etf_opening_snapshot import parse_eastmoney_quote, write_etf_opening_snapshot


EASTMONEY_QUOTE_URL = (
    "https://push2.eastmoney.com/api/qt/stock/get?secid={secid}"
    "&fields=f1,f2,f3,f4,f43,f46,f57,f58,f59,f60"
)


def eastmoney_secid(symbol: str) -> str:
    market, code = symbol.split(".", maxsplit=1)
    return f"{'1' if market == 'SH' else '0'}.{code}"


def enabled_intraday_targets(config: dict) -> list[tuple[str, str, Path]]:
    targets: list[tuple[str, str, Path]] = []
    for account in config.get("accounts", {}).get("simulated", []):
        if not account.get("enabled", False) or account.get("execution_model") != "single_etf_intraday":
            continue
        symbol = str((account.get("strategy_params") or {}).get("target_symbol") or "")
        if not symbol:
            continue
        targets.append(
            (
                str(account.get("account_id") or "unknown"),
                symbol,
                Path(str(account.get("intraday_data_path") or "data/etf_history.sqlite")),
            )
        )
    return targets


def fetch_quote(symbol: str) -> dict:
    result = subprocess.run(
        [
            "curl", "-4", "-s", "--noproxy", "*", "--connect-timeout", "10",
            "-H", "User-Agent: Mozilla/5.0",
            "-H", "Referer: https://quote.eastmoney.com/",
            EASTMONEY_QUOTE_URL.format(secid=eastmoney_secid(symbol)),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Eastmoney quote request failed for {symbol}: curl exit {result.returncode}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Eastmoney quote response was not JSON for {symbol}") from exc
    if payload.get("rc") != 0 or not payload.get("data"):
        raise RuntimeError(f"Eastmoney quote returned no data for {symbol}: rc={payload.get('rc')}")
    return payload


def main() -> int:
    config_path = Path("config.yaml")
    for index, value in enumerate(sys.argv):
        if value == "--config" and index + 1 < len(sys.argv):
            config_path = Path(sys.argv[index + 1])
    root = config_path.resolve().parent
    targets = enabled_intraday_targets(load_config(config_path))
    observed_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    for account_id, symbol, raw_database_path in targets:
        database_path = raw_database_path if raw_database_path.is_absolute() else root / raw_database_path
        snapshot = parse_eastmoney_quote(fetch_quote(symbol), symbol=symbol, observed_at=observed_at)
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database_path) as conn:
            write_etf_opening_snapshot(conn, snapshot)
        print(
            f"[{account_id}] {symbol} observed_at={snapshot.observed_at} "
            f"last={snapshot.last_price} open={snapshot.open_price} prev_close={snapshot.previous_close}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
