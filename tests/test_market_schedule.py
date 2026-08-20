from __future__ import annotations

from datetime import date, datetime

import pytest

from quant.market_schedule import (
    MarketScheduleError,
    _coerce_timezone,
    aware_now,
    default_timezone,
    load_market_schedules,
    scheduler_time,
    session_aware_datetime,
    session_local_time,
)


def test_default_market_schedules_load_without_config() -> None:
    schedules = load_market_schedules({})
    assert set(schedules) == {"cn", "us", "hk", "euro_london", "euro_frankfurt"}
    assert schedules["cn"].timezone.key == "Asia/Shanghai"
    assert schedules["us"].timezone.key == "America/New_York"
    assert schedules["cn"].sessions["open"] == "09:30"
    assert schedules["cn"].sessions["close"] == "15:00"


def test_default_timezone_reads_config() -> None:
    assert default_timezone({}).key == "Asia/Shanghai"
    cfg = {"market_schedules": {"default_timezone": "UTC"}}
    assert default_timezone(cfg).key == "UTC"


def test_session_local_time_parses_hhmm_and_window() -> None:
    assert session_local_time({}, "cn", "open").strftime("%H:%M") == "09:30"
    assert session_local_time({}, "cn", "call_auction").strftime("%H:%M") == "09:15"


def test_session_local_time_rejects_unknown_key() -> None:
    with pytest.raises(MarketScheduleError):
        session_local_time({}, "cn", "nope")


def test_cross_market_aware_comparison_no_naive_error() -> None:
    """反例回归：禁止把美国 8-13 收盘与北京 8-14 开盘当 naive 相减。

    美国 16:00 EDT（8-13）== 北京 04:00（8-14）；距 A 股 09:30 开盘是
    5.5 小时，而不是 naive 相减会得到的 17.5 小时。
    """
    us_close = session_aware_datetime({}, "us", "close", date(2026, 8, 13))
    cn_open = session_aware_datetime({}, "cn", "open", date(2026, 8, 14))
    # 两者都已归一化到 default_timezone (Asia/Shanghai)
    assert us_close.tzinfo is not None
    assert cn_open.tzinfo is not None
    diff = cn_open - us_close
    assert diff.total_seconds() == pytest.approx(5.5 * 3600, abs=60)
    # 明确展示换算结果，防止回归成 naive 相减
    assert us_close.strftime("%Y-%m-%d %H:%M %z") == "2026-08-14 04:00 +0800"


def test_session_aware_datetime_target_timezone_override() -> None:
    from zoneinfo import ZoneInfo

    us_close_utc = session_aware_datetime(
        {}, "us", "close", date(2026, 8, 13), target_timezone=ZoneInfo("UTC")
    )
    assert us_close_utc.strftime("%H:%M") == "20:00"  # 16:00 EDT == 20:00 UTC


def test_scheduler_time_defaults_match_current_hardcoded_values() -> None:
    assert scheduler_time({}, "us_market_news") == "06:30"
    assert scheduler_time({}, "daily_brief") == "07:20"
    assert scheduler_time({}, "etf_opening_snapshot") == "09:25"
    assert scheduler_time({}, "us_market_history") == "05:15"
    assert scheduler_time({}, "account_bill_confirm") == "16:45"
    assert scheduler_time({}, "etf_5min_window") == "09:35-15:00"


def test_scheduler_time_reads_config_override() -> None:
    cfg = {"market_schedules": {"scheduler": {"daily_brief": "08:00"}}}
    assert scheduler_time(cfg, "daily_brief") == "08:00"
    # 未覆盖的仍回退默认
    assert scheduler_time(cfg, "us_market_history") == "05:15"


def test_aware_now_is_timezone_aware() -> None:
    now = aware_now({})
    assert now.tzinfo is not None


def test_invalid_timezone_raises() -> None:
    with pytest.raises(MarketScheduleError):
        _coerce_timezone("Not/AZone")
