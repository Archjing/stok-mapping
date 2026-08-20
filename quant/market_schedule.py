"""市场日历与会话时间配置化 + 时区归一化。

单一事实源为 ``config.yaml`` 的 ``market_schedules`` 段（缺省时回退到
代码内置默认值，保持向后兼容）。本模块负责：

1. 加载/校验 ``market_schedules``；
2. 把各市场会话时间转成 **aware datetime**（带时区）；
3. 跨市场比较前统一时区，杜绝 naive 时间跨时区比较的错判。

硬约束（见 docs/architecture/MARKET_SCHEDULE_CONFIGURATION.md §4.1）：
任何跨市场/跨时区的时间比较，双方必须先转成 aware datetime 且统一时区。
naive 时间只允许出现在"该市场本地时钟的纯解析"入口。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "Asia/Shanghai"

# 与当前代码硬编码值保持一致的默认会话表（config 缺省时回退用）。
_DEFAULT_MARKETS: dict[str, dict[str, Any]] = {
    "cn": {
        "timezone": "Asia/Shanghai",
        "sessions": {
            "call_auction": "09:15-09:25",
            "open": "09:30",
            "morning_close": "11:30",
            "afternoon_open": "13:00",
            "close": "15:00",
        },
    },
    "us": {
        "timezone": "America/New_York",
        "sessions": {"open": "09:30", "close": "16:00"},
    },
    "hk": {
        "timezone": "Asia/Hong_Kong",
        "sessions": {"open": "09:30", "close": "16:00"},
    },
    # 欧洲按交易所拆分：伦敦（FTSE）与大陆（DAX/CAC/STOXX）本地时区差 1 小时，
    # 各自独立表达会话时间，避免把两个时区的时段混进一个键。
    "euro_london": {
        "timezone": "Europe/London",
        "sessions": {"open": "08:00", "close": "16:30"},
    },
    "euro_frankfurt": {
        "timezone": "Europe/Berlin",
        "sessions": {"open": "09:00", "close": "17:30"},
    },
}

_DEFAULT_SCHEDULER: dict[str, str] = {
    "financial_factors": "03:30",
    "us_market_news": "06:30",
    "gov_policy": "06:50",
    "daily_brief": "07:20",
    "hk_opening_snapshot": "09:40",
    "etf_opening_snapshot": "09:25",
    "cn_finance_flash_window": "09:15-15:05",
    "etf_5min_window": "09:35-15:00",
    "intraday_bill_window": "09:35-15:00",
    "core_index_daily_tail": "15:05",
    "china_options_ho": "15:10",
    "europe_london_opening_snapshot": "16:10",
    "europe_frankfurt_opening_snapshot": "16:10",
    "hk_market_history": "16:20",
    "a_share_history": "16:30",
    "account_bill_confirm": "16:45",
    "us_opening_snapshot": "22:40",
    "europe_london_market_history": "00:45",
    "europe_frankfurt_market_history": "01:45",
    "us_market_history": "05:15",
    "cn_finance_flash_daily": "17:20",
    "policy_event_extract": "17:40",
    "cninfo_risk_events": "20:20",
    "cctv_news": "20:45",
}


class MarketScheduleError(ValueError):
    """Invalid or inconsistent market_schedules configuration."""


@dataclass(frozen=True)
class MarketSession:
    """A market session with an explicit IANA timezone."""

    market: str
    timezone: ZoneInfo
    sessions: dict[str, str]


def _coerce_timezone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, KeyError) as exc:
        raise MarketScheduleError(f"unknown timezone: {value!r}") from exc


def load_market_schedules(config: Mapping[str, Any]) -> dict[str, MarketSession]:
    """从 config 加载 ``market_schedules``，缺省/空则回退内置默认值。

    返回 ``{market: MarketSession}``；session 时间保持**市场本地时间**字符串
    （"HH:MM" 或 "HH:MM-HH:MM"），不做时区换算。
    """
    raw = config.get("market_schedules", {}) or {}
    default_tz = str(raw.get("default_timezone", DEFAULT_TIMEZONE))
    markets_raw = raw.get("markets", {}) or {}
    result: dict[str, MarketSession] = {}
    for market, defaults in _DEFAULT_MARKETS.items():
        market_cfg = markets_raw.get(market, {}) or {}
        tz_name = str(market_cfg.get("timezone", defaults["timezone"]))
        sessions = {**defaults["sessions"], **dict(market_cfg.get("sessions", {}) or {})}
        result[market] = MarketSession(
            market=market,
            timezone=_coerce_timezone(tz_name),
            sessions=sessions,
        )
    # 保留未在默认表里但显式配置的市场
    for market, market_cfg in markets_raw.items():
        if market not in result and isinstance(market_cfg, dict):
            tz_name = str(market_cfg.get("timezone", default_tz))
            sessions = {str(k): str(v) for k, v in (market_cfg.get("sessions", {}) or {}).items()}
            result[market] = MarketSession(
                market=market,
                timezone=_coerce_timezone(tz_name),
                sessions=sessions,
            )
    return result


def default_timezone(config: Mapping[str, Any]) -> ZoneInfo:
    raw = config.get("market_schedules", {}) or {}
    return _coerce_timezone(str(raw.get("default_timezone", DEFAULT_TIMEZONE)))


def market_timezone(config: Mapping[str, Any], market: str) -> ZoneInfo:
    schedules = load_market_schedules(config)
    if market not in schedules:
        raise MarketScheduleError(f"unknown market: {market!r}")
    return schedules[market].timezone


def _parse_hhmm(value: str) -> time:
    text = str(value).strip()
    # 支持 "HH:MM" 与 "HH:MM-HH:MM"（取起点）
    if "-" in text:
        text = text.split("-", 1)[0].strip()
    try:
        hour, minute = text.split(":", 1)
        return time(int(hour), int(minute))
    except (ValueError, AttributeError) as exc:
        raise MarketScheduleError(f"invalid HH:MM value: {value!r}") from exc


def session_local_time(config: Mapping[str, Any], market: str, key: str) -> time:
    """返回某市场会话键的本地时间（naive ``time``，仅用于本地解析）。

    key 形如 ``open`` / ``close`` / ``morning_close`` / ``call_auction``。
    """
    schedules = load_market_schedules(config)
    if market not in schedules:
        raise MarketScheduleError(f"unknown market: {market!r}")
    value = schedules[market].sessions.get(key)
    if value is None:
        raise MarketScheduleError(f"market {market!r} has no session key {key!r}")
    return _parse_hhmm(value)


def session_aware_datetime(
    config: Mapping[str, Any],
    market: str,
    key: str,
    day: date,
    *,
    target_timezone: ZoneInfo | None = None,
) -> datetime:
    """把某市场 ``day`` 上的会话键转成 aware datetime。

    - 先按市场本地时区把 naive 本地时间贴时区（aware），
    - 再统一到 ``target_timezone``（缺省为 config 的 default_timezone）。
    返回值可直接跨市场比较/相减，不会再有时区错判。
    """
    from datetime import date as _date

    schedules = load_market_schedules(config)
    session = schedules[market]
    local_t = session_local_time(config, market, key)
    aware = datetime.combine(_date(day.year, day.month, day.day), local_t, tzinfo=session.timezone)
    target = target_timezone or default_timezone(config)
    return aware.astimezone(target)


def aware_now(config: Mapping[str, Any]) -> datetime:
    """当前时刻的 aware datetime，统一到 default_timezone。"""
    return datetime.now(timezone.utc).astimezone(default_timezone(config))


def scheduler_time(config: Mapping[str, Any], name: str) -> str:
    """返回调度任务的触发时间/窗口字符串（"HH:MM" 或 "HH:MM-HH:MM"）。

    语义：以 ``default_timezone`` 表达。config 缺省回退内置默认值。
    """
    raw = config.get("market_schedules", {}) or {}
    scheduler = raw.get("scheduler", {}) or {}
    value = scheduler.get(name, _DEFAULT_SCHEDULER.get(name, ""))
    if not value:
        raise MarketScheduleError(f"no scheduler entry for {name!r}")
    return str(value)


def close_bar_time(config: Mapping[str, Any], market: str, bar_minutes: int = 5) -> str:
    """返回某市场收盘前最后一根 bar 的开始时间（"HH:MM"）。

    语义：A 股 15:00 收盘、5 分钟 bar 时，最后一根完整 bar 是 14:55-15:00，
    其时间戳记 14:55。该值**从 ``sessions.close`` 减去 bar_minutes 推导**，
    不再硬编码。
    """
    close_t = session_local_time(config, market, "close")
    derived = (datetime.combine(date(2000, 1, 1), close_t) - timedelta(minutes=int(bar_minutes))).time()
    return derived.strftime("%H:%M")


# A 股收盘前最后一根 5 分钟 bar 的开始时间，由 sessions.close - 5min 推导。
# 作为 fallback_time 的默认值，取代原先散落的 "14:55" 字面量。
CN_CLOSE_BAR_TIME = close_bar_time({}, "cn", 5)
# A 股开盘时间（展示 fallback 用，如 trade_time 缺失时回填）。
CN_OPEN_TIME = session_local_time({}, "cn", "open").strftime("%H:%M:%S")


def session_bar_times(
    config: Mapping[str, Any],
    market: str,
    bar_minutes: int = 5,
) -> list[str]:
    """返回某市场一个完整交易日的 bar 时间戳序列（"HH:MM:SS"）。

    规则（由会话时间推导，与 Eastmoney 5 分钟 bar 时间戳语义一致）：
    - 上午：首根 = ``open`` + bar_minutes，末根 = ``morning_close``；
    - 下午：首根 = ``afternoon_open`` + bar_minutes，末根 = ``close``。

    示例（A 股 5 分钟）：09:35:00 … 11:30:00，13:05:00 … 15:00:00，共 48 根。
    若某市场未配置午休（如 us/hk），则退化为 open+bar 到 close 的连续序列。
    """
    open_t = session_local_time(config, market, "open")
    close_t = session_local_time(config, market, "close")
    try:
        morning_close_t = session_local_time(config, market, "morning_close")
        afternoon_open_t = session_local_time(config, market, "afternoon_open")
    except MarketScheduleError:
        morning_close_t = None
        afternoon_open_t = None

    step = timedelta(minutes=int(bar_minutes))
    out: list[str] = []

    def _emit(start: time, end: time) -> None:
        current = datetime.combine(date(2000, 1, 1), start)
        end_dt = datetime.combine(date(2000, 1, 1), end)
        while current <= end_dt:
            out.append(current.strftime("%H:%M:%S"))
            current += step

    if morning_close_t is not None and afternoon_open_t is not None:
        _emit((datetime.combine(date(2000, 1, 1), open_t) + step).time(), morning_close_t)
        _emit((datetime.combine(date(2000, 1, 1), afternoon_open_t) + step).time(), close_t)
    else:
        _emit((datetime.combine(date(2000, 1, 1), open_t) + step).time(), close_t)
    return out
