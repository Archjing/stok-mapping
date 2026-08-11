import sqlite3
from datetime import date
from pathlib import Path

from phase0.reporting.strategy_bill import _panel_cache_key
from phase0.reporting.premarket_watchlist import _latest_trade_date


def test_panel_cache_key_includes_as_of_date() -> None:
    base = _panel_cache_key(
        config_path=Path("config.yaml"),
        config={"local_history": {"path": "data/a_share_history.sqlite"}, "universe": {"enabled": False}},
        root=Path("."),
        symbols=["SH.600519"],
        history_years=5,
        strategy_cfg={},
        as_of_date="2026-06-09",
        use_strict_asof=False,
        price_adjustment="qfq_current",
    )
    other = _panel_cache_key(
        config_path=Path("config.yaml"),
        config={"local_history": {"path": "data/a_share_history.sqlite"}, "universe": {"enabled": False}},
        root=Path("."),
        symbols=["SH.600519"],
        history_years=5,
        strategy_cfg={},
        as_of_date="2026-06-08",
        use_strict_asof=False,
        price_adjustment="qfq_current",
    )
    assert base["as_of_date"] == "2026-06-09"
    assert other["as_of_date"] == "2026-06-08"
    assert base != other


def test_panel_cache_key_distinguishes_strict_asof_mode() -> None:
    strict_key = _panel_cache_key(
        config_path=Path("config.yaml"),
        config={"local_history": {"path": "data/a_share_history.sqlite"}, "universe": {"enabled": False}},
        root=Path("."),
        symbols=["SH.600519"],
        history_years=5,
        strategy_cfg={},
        as_of_date="2026-06-09",
        use_strict_asof=True,
        price_adjustment="qfq_asof",
    )
    live_key = _panel_cache_key(
        config_path=Path("config.yaml"),
        config={"local_history": {"path": "data/a_share_history.sqlite"}, "universe": {"enabled": False}},
        root=Path("."),
        symbols=["SH.600519"],
        history_years=5,
        strategy_cfg={},
        as_of_date="2026-06-09",
        use_strict_asof=False,
        price_adjustment="qfq_current",
    )
    assert strict_key["use_strict_asof"] is True
    assert live_key["use_strict_asof"] is False
    assert strict_key != live_key
    assert strict_key["price_adjustment"] == "qfq_asof"
    assert live_key["price_adjustment"] == "qfq_current"


def test_latest_trade_date_ignores_future_calendar_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "calendar.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE trading_calendar (exchange TEXT, date TEXT, is_open INTEGER)")
        conn.executemany(
            "INSERT INTO trading_calendar(exchange, date, is_open) VALUES (?, ?, ?)",
            [
                ("SSE", "2026-06-08", 1),
                ("SSE", date.today().isoformat(), 1),
                ("SSE", "2026-12-31", 1),
            ],
        )
        conn.commit()
    assert _latest_trade_date(db_path) == date.today().isoformat()
