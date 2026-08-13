"""Tests for US / HK independent trading calendar.

Covers:
- `market_calendar.load_market_trading_days` derivation from a local market DB.
- `market_calendar.is_market_trading_day` holiday / weekend / future-date rules.
- `market_calendar.map_to_next_trading_day` signal-day mapping.
- `maintenance_orchestrator._trading_day_decision` integration for `us`/`hk`.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from quant.data_governance.market_calendar import (
    is_market_trading_day,
    load_market_trading_days,
    map_to_next_trading_day,
)
from quant.maintenance_orchestrator import MaintenanceTaskSpec, _trading_day_decision


def _make_us_db(tmp_path: Path) -> Path:
    """Build a small US market DB with a known holiday gap."""
    db = tmp_path / "us_market_history.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE us_daily_bars (symbol TEXT, date TEXT, close REAL)")
    # Week: 2026-07-02 Thu (open), 2026-07-03 Fri (holiday, absent), 2026-07-06 Mon (open)
    for day in ("2026-07-02", "2026-07-06", "2026-07-07", "2026-07-08"):
        conn.execute("INSERT INTO us_daily_bars VALUES (?, ?, ?)", ("^SOX", day, 1.0))
    conn.commit()
    conn.close()
    return db


def _make_hk_db(tmp_path: Path) -> Path:
    db = tmp_path / "hk_market_history.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE hk_daily_bars (symbol TEXT, date TEXT, close REAL)")
    for day in ("2026-01-02", "2026-01-05"):
        conn.execute("INSERT INTO hk_daily_bars VALUES (?, ?, ?)", ("0005.HK", day, 1.0))
    conn.commit()
    conn.close()
    return db


def _spec(market_calendar: str) -> MaintenanceTaskSpec:
    return MaintenanceTaskSpec(
        name="test",
        schedule_type="time",
        schedule_value="17:10",
        command=["echo"],
        log_path="x.log",
        success_stamp="x",
        lock_dir="x",
        market_calendar=market_calendar,
    )


def test_load_market_trading_days_derives_only_open_days(tmp_path: Path) -> None:
    db = _make_us_db(tmp_path)
    days = load_market_trading_days(
        database_path=db, daily_table="us_daily_bars", market="us"
    )
    assert days == ["2026-07-02", "2026-07-06", "2026-07-07", "2026-07-08"]
    # 2026-07-03 (holiday) is absent even though it is a weekday.


def test_is_market_trading_day_holiday_weekend_and_future(tmp_path: Path) -> None:
    db = _make_us_db(tmp_path)
    # Holiday within covered range -> closed.
    assert is_market_trading_day(
        database_path=db, daily_table="us_daily_bars", market="us", day="2026-07-03"
    ) is False
    # Open day -> open.
    assert is_market_trading_day(
        database_path=db, daily_table="us_daily_bars", market="us", day="2026-07-06"
    ) is True
    # Weekend outside covered range -> closed (weekday fallback still says closed).
    assert is_market_trading_day(
        database_path=db, daily_table="us_daily_bars", market="us", day="2026-07-04"
    ) is False
    # Future weekday beyond DB coverage -> treated as trading day (not falsely closed).
    assert is_market_trading_day(
        database_path=db, daily_table="us_daily_bars", market="us", day="2026-12-31"
    ) is True


def test_is_market_trading_day_hk_uses_any_symbol(tmp_path: Path) -> None:
    db = _make_hk_db(tmp_path)
    assert is_market_trading_day(
        database_path=db, daily_table="hk_daily_bars", market="hk", day="2026-01-02"
    ) is True
    assert is_market_trading_day(
        database_path=db, daily_table="hk_daily_bars", market="hk", day="2026-01-03"
    ) is False


def test_map_to_next_trading_day() -> None:
    target = ["2026-07-06", "2026-07-07", "2026-07-08"]
    # US close on 07-02 -> next A-share trading day 07-06.
    assert map_to_next_trading_day(target_dates=target, signal_date="2026-07-02") == "2026-07-06"
    # US close on a covered trading day 07-06 -> next 07-07.
    assert map_to_next_trading_day(target_dates=target, signal_date="2026-07-06") == "2026-07-07"
    # Beyond last target -> None.
    assert map_to_next_trading_day(target_dates=target, signal_date="2026-07-08") is None
    assert map_to_next_trading_day(target_dates=[], signal_date="2026-07-02") is None


def test_trading_day_decision_us_uses_market_calendar(tmp_path: Path, monkeypatch) -> None:
    db = _make_us_db(tmp_path)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "quant:\n"
        "  us_market_history:\n"
        "    path: " + str(db).replace("\\", "/") + "\n"
        "    daily_table: us_daily_bars\n",
        encoding="utf-8",
    )
    spec = _spec("us")
    root = tmp_path

    ok, reason = _trading_day_decision(root=root, config_path=config_path, spec=spec, now=datetime(2026, 7, 3, 17, 10))
    assert ok is False
    assert "us_market_calendar(is_open=0)" in reason

    ok, reason = _trading_day_decision(root=root, config_path=config_path, spec=spec, now=datetime(2026, 7, 6, 17, 10))
    assert ok is True
    assert "us_market_calendar(is_open=1)" in reason


def test_trading_day_decision_hk_uses_market_calendar(tmp_path: Path) -> None:
    db = _make_hk_db(tmp_path)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "quant:\n"
        "  hk_market_history:\n"
        "    path: " + str(db).replace("\\", "/") + "\n"
        "    daily_table: hk_daily_bars\n",
        encoding="utf-8",
    )
    spec = _spec("hk")
    root = tmp_path

    ok, reason = _trading_day_decision(root=root, config_path=config_path, spec=spec, now=datetime(2026, 1, 3, 16, 20))
    assert ok is False
    assert "hk_market_calendar(is_open=0)" in reason

    ok, reason = _trading_day_decision(root=root, config_path=config_path, spec=spec, now=datetime(2026, 1, 5, 16, 20))
    assert ok is True
    assert "hk_market_calendar(is_open=1)" in reason
