"""US / HK 独立交易日历判定。

背景
----
`maintenance_orchestrator._trading_day_decision` 对 ``market_calendar="us"/"hk"``
的任务只做 weekday 判断，交易所假日（如美股独立日、圣诞节、耶稣受难日等）会被
误判为交易日。本模块从本地行情库**推导**交易日序列：一个日期只要核心标的存在
行情记录，即为该市场的交易日；否则（周末或假日）不是。

为什么从行情库推导而不是引入第三方假日表
---------------------------------------
- 行情库只含真实交易日的记录，天然排除周末与交易所假日；
- 不需要维护假日表、不引入额外数据源、不依赖网络；
- 对半日市（如美股 7/3 提前收盘）也能正确保留为交易日（核心标的有记录）。

判定信号（每个市场一个"锚定标的"）：
- US: ``^SOX``（费城半导体指数，本项目跨市场信号的执行源）
- HK: 港股市场任意标的存在记录即视为交易日（用第一只标的行为锚）

使用时注意
----------
- 只有行情库覆盖范围内可判定；超出最后交易日的日期回退到 weekday 判断。
- 锚定标的缺失的日子会回退 weekday，避免把未知日期误判为闭市。
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Iterable

# 每市场的锚定标的：存在该标的一行记录即视为该市场交易日。
# US 用 ^SOX 是因为它是本项目跨市场信号的执行源，假日必然无数据。
MARKET_ANCHOR_SYMBOLS: dict[str, str | None] = {
    "us": "^SOX",
    "hk": None,  # None 表示"任一标的"
}


def load_market_trading_days(
    *,
    database_path: str | Path,
    daily_table: str,
    market: str,
    symbol: str | None = None,
) -> list[str]:
    """返回某市场全部交易日（升序 date 字符串列表）。

    Parameters
    ----------
    database_path : 行情库路径
    daily_table : 日线表名（如 ``us_daily_bars`` / ``hk_daily_bars``）
    market : ``us`` / ``hk``
    symbol : 锚定标的；缺省用 MARKET_ANCHOR_SYMBOLS 对应值；仍为空则用任一标的
    """
    anchor = symbol or MARKET_ANCHOR_SYMBOLS.get(market)
    db = Path(database_path)
    if not db.is_file():
        return []
    table = str(daily_table).strip()
    if not table.replace("_", "").isalnum():
        return []
    try:
        with sqlite3.connect(str(db)) as conn:
            if anchor:
                rows = conn.execute(
                    f"SELECT DISTINCT date FROM {table} WHERE symbol = ? ORDER BY date",
                    (anchor,),
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT DISTINCT date FROM {table} ORDER BY date"
                ).fetchall()
    except sqlite3.Error:
        return []
    return [str(r[0]) for r in rows]


def is_market_trading_day(
    *,
    database_path: str | Path,
    daily_table: str,
    market: str,
    day: date | str,
    symbol: str | None = None,
) -> bool:
    """判断 ``day`` 是否为该市场交易日。

    - 日期在行情库已有交易日内 → 看当日是否有记录（有=交易日，无=假日/闭市）；
    - 日期在库覆盖范围之外（早于首日或晚于末日，如未来日期）→ 回退工作日判断，
      避免把尚未入库的未来日期误判为闭市而跳过任务。
    """
    days = load_market_trading_days(
        database_path=database_path,
        daily_table=daily_table,
        market=market,
        symbol=symbol,
    )
    day_str = str(day)
    if not days:
        # 库不可读或为空：回退 weekday
        return date.fromisoformat(day_str).isoweekday() <= 5
    if day_str in days:
        return True
    # 库覆盖范围内但当日无记录 → 假日/闭市
    if days[0] <= day_str <= days[-1]:
        return False
    # 库尚未覆盖（未来日期）→ 工作日按交易日处理
    return date.fromisoformat(day_str).isoweekday() <= 5


def map_to_next_trading_day(
    *,
    target_dates: Iterable[str],
    signal_date: date | str,
) -> str | None:
    """把信号日映射到 target_dates（升序交易日列表）中第一个严格更晚的交易日。

    与 ``cross_market_semiconductor_timing.map_us_features_to_next_cn_trading_day``
    一致：信号日在美股收盘后才可知，只能用于目标市场"下一个交易日"。
    """
    import bisect

    target = list(target_dates)
    if not target:
        return None
    idx = bisect.bisect_right(target, str(signal_date))
    if idx >= len(target):
        return None
    return target[idx]
