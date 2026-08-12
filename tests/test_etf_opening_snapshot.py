from __future__ import annotations

import sqlite3

from quant.data_access.etf_opening_snapshot import (
    ensure_etf_opening_snapshot_schema,
    parse_eastmoney_quote,
    write_etf_opening_snapshot,
)


def test_parse_eastmoney_quote_keeps_opening_auction_fields() -> None:
    snapshot = parse_eastmoney_quote(
        {
            "data": {
                "f43": 1073,
                "f46": 1073,
                "f57": "512480",
                "f58": "国联安半导体ETF",
                "f60": 1068,
            }
        },
        symbol="SH.512480",
        observed_at="2026-08-12T09:25:02+08:00",
    )

    assert snapshot.symbol == "SH.512480"
    assert snapshot.observed_at == "2026-08-12T09:25:02+08:00"
    assert snapshot.last_price == 1.073
    assert snapshot.open_price == 1.073
    assert snapshot.previous_close == 1.068
    assert snapshot.provider == "eastmoney_quote"


def test_write_etf_opening_snapshot_is_idempotent_for_one_observation() -> None:
    with sqlite3.connect(":memory:") as conn:
        ensure_etf_opening_snapshot_schema(conn)
        snapshot = parse_eastmoney_quote(
            {"data": {"f43": 1073, "f46": 1073, "f57": "512480", "f60": 1068}},
            symbol="SH.512480",
            observed_at="2026-08-12T09:25:02+08:00",
        )

        write_etf_opening_snapshot(conn, snapshot)
        write_etf_opening_snapshot(conn, snapshot)

        row = conn.execute(
            "SELECT symbol, observed_at, last_price, open_price, previous_close, provider "
            "FROM market_etf_opening_snapshots"
        ).fetchone()

    assert row == (
        "SH.512480",
        "2026-08-12T09:25:02+08:00",
        1.073,
        1.073,
        1.068,
        "eastmoney_quote",
    )
