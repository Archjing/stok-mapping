from __future__ import annotations

import sqlite3
from pathlib import Path


def _create_trades_table(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE single_etf_intraday_trades (
                account_id TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                signal_date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                trade_time TEXT NOT NULL,
                order_type TEXT NOT NULL,
                reason TEXT NOT NULL,
                price REAL NOT NULL,
                shares REAL NOT NULL,
                amount REAL NOT NULL,
                cost REAL NOT NULL
            )
            """
        )


def test_today_filled_trades_includes_sell_fills(tmp_path: Path) -> None:
    """A sell-only T+1 exit must be read from the actual trade ledger."""
    from scripts.intraday_bill_pipeline import _today_filled_trades

    db_path = tmp_path / "simulated_accounts.sqlite"
    _create_trades_table(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO single_etf_intraday_trades
                (account_id, trade_date, signal_date, symbol, side, trade_time,
                 order_type, reason, price, shares, amount, cost)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("semiconductor_timing", "2026-08-14", "2026-08-12", "SH.512480", "sell", "2026-08-14 09:35:00", "trailing_stop", "trailing_stop", 1.082, 108500, 117397, 41.09),
                ("other_account", "2026-08-14", "2026-08-12", "SH.588200", "buy", "2026-08-14 09:35:00", "market_open", "signal", 1.215, 96700, 117490, 41.12),
            ],
        )

    trades = _today_filled_trades(db_path, "semiconductor_timing", "2026-08-14")

    assert [(trade["side"], trade["trade_time"] ) for trade in trades] == [
        ("sell", "2026-08-14 09:35:00")
    ]


def test_trade_watermark_refreshes_when_a_legacy_count_matches_a_sell_only_day(tmp_path: Path) -> None:
    """A legacy buy-count stamp of 1 cannot suppress a later one-sell refresh."""
    from scripts.intraday_bill_pipeline import _needs_bill_refresh, _today_filled_trades

    db_path = tmp_path / "simulated_accounts.sqlite"
    _create_trades_table(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO single_etf_intraday_trades
                (account_id, trade_date, signal_date, symbol, side, trade_time,
                 order_type, reason, price, shares, amount, cost)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("semiconductor_timing", "2026-08-14", "2026-08-12", "SH.512480", "sell", "2026-08-14 09:35:00", "trailing_stop", "trailing_stop", 1.082, 108500, 117397, 41.09),
        )

    trades = _today_filled_trades(db_path, "semiconductor_timing", "2026-08-14")

    assert _needs_bill_refresh(trades, prior_stamp="1") is True
