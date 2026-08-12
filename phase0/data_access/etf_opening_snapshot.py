"""Opening-auction ETF quote snapshots for intraday simulated accounts."""
from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3
from typing import Any


EASTMONEY_PRICE_SCALE = 1000.0


@dataclass(frozen=True)
class EtfOpeningSnapshot:
    symbol: str
    observed_at: str
    last_price: float | None
    open_price: float | None
    previous_close: float | None
    provider: str
    raw_payload: str


def _eastmoney_price(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed / EASTMONEY_PRICE_SCALE


def parse_eastmoney_quote(
    payload: dict[str, Any],
    *,
    symbol: str,
    observed_at: str,
) -> EtfOpeningSnapshot:
    """Normalize Eastmoney's scaled quote fields without inferring a price."""
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("Eastmoney quote payload has no data object")
    return EtfOpeningSnapshot(
        symbol=str(symbol),
        observed_at=str(observed_at),
        last_price=_eastmoney_price(data.get("f43")),
        open_price=_eastmoney_price(data.get("f46")),
        previous_close=_eastmoney_price(data.get("f60")),
        provider="eastmoney_quote",
        raw_payload=json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    )


def ensure_etf_opening_snapshot_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS market_etf_opening_snapshots (
            symbol TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            last_price REAL,
            open_price REAL,
            previous_close REAL,
            provider TEXT NOT NULL,
            raw_payload TEXT NOT NULL,
            PRIMARY KEY (symbol, observed_at, provider)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_market_etf_opening_snapshots_symbol_time
        ON market_etf_opening_snapshots(symbol, observed_at DESC)
        """
    )


def write_etf_opening_snapshot(conn: sqlite3.Connection, snapshot: EtfOpeningSnapshot) -> None:
    ensure_etf_opening_snapshot_schema(conn)
    conn.execute(
        """
        INSERT OR REPLACE INTO market_etf_opening_snapshots
        (symbol, observed_at, last_price, open_price, previous_close, provider, raw_payload)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot.symbol,
            snapshot.observed_at,
            snapshot.last_price,
            snapshot.open_price,
            snapshot.previous_close,
            snapshot.provider,
            snapshot.raw_payload,
        ),
    )
