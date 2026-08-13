"""跨市场对比图数据模块.

为"源市场 → 目标市场"价格对比图准备浏览器数据载荷:

- 两条序列对比: 各自按起始日归一化, 内连接对齐共同交易日
- 单日映射信号: 源市场 T 日收盘变动投影到严格晚于 T 的目标市场交易日
- 连续趋势: 识别"连续 N 个交易日、每天至少 ±X%"的连涨/连跌段
- 输出: 统一 SVG 图表模板 + JSON 数据载荷
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from quant.data_access.etf_history import ETFHistoryReader


SeriesStorage = Literal["us_daily_bars", "etf_qfq"]


@dataclass(frozen=True)
class ComparisonSeriesConfig:
    """定义一条对比序列的代码、显示名称和本地存储类型.

    ``storage`` 决定从哪个本地历史库读取:
    - ``us_daily_bars``: data/us_market_history.sqlite (美股日线)
    - ``etf_qfq``: data/etf_history.sqlite (ETF 前复权, as-of 口径)
    """

    symbol: str
    label: str
    storage: SeriesStorage = "us_daily_bars"


@dataclass(frozen=True)
class ComparisonChartConfig:
    """传入对比图所需全部配置: 标题、起始日期、原始值观察区间、
    单日映射阈值、连续趋势规则.

    ``consecutive_daily_change_pct=1.0`` means each daily change in a run must
    be at least +1.0% or at most -1.0%; ``3.0`` means at least +/-3.0%.
    """

    slug: str
    title: str
    source: ComparisonSeriesConfig
    target: ComparisonSeriesConfig
    start_date: str | date
    # 原始值观察区间 (low, high): 序列收盘价落入该区间时前端高亮观察带
    observation_band: tuple[float, float] | None = None
    # 单日映射阈值: 源市场单日涨跌幅绝对值 >= 该值才生成映射信号
    daily_mapping_pct: float | None = 0.5
    # 连续趋势规则: 连续 N 个交易日、每天至少 ±X%
    consecutive_days: int = 3
    consecutive_daily_change_pct: float = 0.0

    def __post_init__(self) -> None:
        if self.consecutive_days < 2:
            raise ValueError("consecutive_days must be at least 2")
        if self.consecutive_daily_change_pct < 0:
            raise ValueError("consecutive_daily_change_pct must not be negative")
        if self.daily_mapping_pct is not None and self.daily_mapping_pct < 0:
            raise ValueError("daily_mapping_pct must not be negative")
        if self.observation_band is not None and self.observation_band[0] >= self.observation_band[1]:
            raise ValueError("observation_band must be ordered low, high")

    @property
    def start_timestamp(self) -> pd.Timestamp:
        return pd.Timestamp(self.start_date)


def _clean_prices(frame: pd.DataFrame, *, start_date: pd.Timestamp) -> pd.DataFrame:
    required_columns = {"date", "close"}
    missing_columns = required_columns.difference(frame.columns)
    if missing_columns:
        raise ValueError(f"price series is missing columns: {sorted(missing_columns)}")
    cleaned = frame[["date", "close"]].copy()
    cleaned["date"] = pd.to_datetime(cleaned["date"], errors="coerce")
    cleaned["close"] = pd.to_numeric(cleaned["close"], errors="coerce")
    return (
        cleaned.dropna(subset=["date", "close"])
        .loc[lambda values: values["date"] >= start_date]
        .drop_duplicates(subset=["date"], keep="last")
        .sort_values("date")
        .reset_index(drop=True)
    )


def find_consecutive_move_runs(
    source: pd.DataFrame,
    *,
    direction: int,
    consecutive_days: int,
    daily_change_pct: float,
) -> list[dict[str, Any]]:
    """支持"连续 N 个交易日、每天至少 ±X%"的连涨/连跌段识别.

    按源市场自身交易日历扫描: 一段 run 需包含 ``consecutive_days`` 个
    以上同向日涨跌, 每个日涨跌幅度须满足 ``daily_change_pct``
    (0 表示任意严格同向涨跌即可). 返回每段的起止日期、天数与区间涨跌幅.
    """
    if direction not in (-1, 1):
        raise ValueError("direction must be -1 or 1")
    if consecutive_days < 2:
        raise ValueError("consecutive_days must be at least 2")
    if daily_change_pct < 0:
        raise ValueError("daily_change_pct must not be negative")

    returns = source["close"].pct_change().mul(100)
    runs: list[dict[str, Any]] = []
    run_start_index: int | None = None
    run_end_index: int | None = None

    def flush() -> None:
        nonlocal run_start_index, run_end_index
        if run_start_index is None or run_end_index is None:
            return
        move_days = run_end_index - run_start_index
        if move_days >= consecutive_days:
            start_close = float(source.iloc[run_start_index]["close"])
            end_close = float(source.iloc[run_end_index]["close"])
            runs.append(
                {
                    "start": source.iloc[run_start_index]["date"].strftime("%Y-%m-%d"),
                    "end": source.iloc[run_end_index]["date"].strftime("%Y-%m-%d"),
                    "moveDays": move_days,
                    "change": round((end_close / start_close - 1) * 100, 4),
                }
            )
        run_start_index = None
        run_end_index = None

    for index, daily_return in enumerate(returns):
        signed_change = direction * float(daily_return) if pd.notna(daily_return) else 0.0
        qualifies = signed_change >= daily_change_pct if daily_change_pct else signed_change > 0
        if qualifies:
            if run_start_index is None:
                run_start_index = index - 1
            run_end_index = index
        else:
            flush()
    flush()
    return runs


def project_daily_mapping_signals(
    source: pd.DataFrame,
    *,
    target_dates: pd.Series,
    daily_mapping_pct: float | None,
) -> list[dict[str, Any]]:
    """将源市场 T 日收盘变动投影到严格晚于 T 的下一个目标市场交易日.

    目标日期严格晚于源市场收盘日, 避免把 A 股当日开盘前尚不可见的
    美股收盘数据当作同日输入展示 (防止未来函数).
    """
    if daily_mapping_pct is None:
        return []
    target_calendar = pd.DatetimeIndex(pd.to_datetime(target_dates, errors="coerce")).dropna().sort_values().unique()
    if target_calendar.empty:
        return []

    signals: list[dict[str, Any]] = []
    returns = source["close"].pct_change().mul(100)
    for row, daily_return in zip(source.itertuples(index=False), returns, strict=True):
        if pd.isna(daily_return) or abs(float(daily_return)) < daily_mapping_pct:
            continue
        source_date = pd.Timestamp(row.date)
        target_index = target_calendar.searchsorted(source_date, side="right")
        if target_index >= len(target_calendar):
            continue
        change = round(float(daily_return), 4)
        signals.append(
            {
                "sourceDate": source_date.strftime("%Y-%m-%d"),
                "targetDate": pd.Timestamp(target_calendar[target_index]).strftime("%Y-%m-%d"),
                "change": change,
                "direction": "up" if change > 0 else "down",
            }
        )
    return signals


def build_comparison_chart_data_from_frames(
    source_frame: pd.DataFrame,
    target_frame: pd.DataFrame,
    *,
    config: ComparisonChartConfig,
) -> dict[str, Any] | None:
    """Align two series and prepare the browser payload for a comparison chart."""
    source = _clean_prices(source_frame, start_date=config.start_timestamp)
    target = _clean_prices(target_frame, start_date=config.start_timestamp)
    if source.empty or target.empty:
        return None

    paired = source.merge(target, on="date", how="inner", suffixes=("_source", "_target")).dropna()
    if paired.empty:
        return None
    paired = paired.sort_values("date").reset_index(drop=True)
    source_base = float(paired.iloc[0]["close_source"])
    target_base = float(paired.iloc[0]["close_target"])
    data = [
        [
            row.date.strftime("%Y-%m-%d"),
            round(float(row.close_source) / source_base * 100, 4),
            round(float(row.close_target) / target_base * 100, 4),
            round(float(row.close_source), 4),
            round(float(row.close_target), 4),
        ]
        for row in paired.itertuples(index=False)
    ]
    return {
        "title": config.title,
        "source": {"symbol": config.source.symbol, "label": config.source.label},
        "target": {"symbol": config.target.symbol, "label": config.target.label},
        "data": data,
        "startDate": paired.iloc[0]["date"].strftime("%Y-%m-%d"),
        "endDate": paired.iloc[-1]["date"].strftime("%Y-%m-%d"),
        "sourceLastDate": paired.iloc[-1]["date"].strftime("%Y-%m-%d"),
        "targetLastDate": paired.iloc[-1]["date"].strftime("%Y-%m-%d"),
        "tradingDays": len(data),
        "observationBand": (
            {"low": config.observation_band[0], "high": config.observation_band[1]}
            if config.observation_band is not None
            else None
        ),
        "dailyMappingPct": config.daily_mapping_pct,
        "dailyMappingSignals": project_daily_mapping_signals(
            source,
            target_dates=paired["date"],
            daily_mapping_pct=config.daily_mapping_pct,
        ),
        "consecutiveMove": {
            "days": config.consecutive_days,
            "dailyPct": config.consecutive_daily_change_pct,
        },
        "upRuns": find_consecutive_move_runs(
            source,
            direction=1,
            consecutive_days=config.consecutive_days,
            daily_change_pct=config.consecutive_daily_change_pct,
        ),
        "downRuns": find_consecutive_move_runs(
            source,
            direction=-1,
            consecutive_days=config.consecutive_days,
            daily_change_pct=config.consecutive_daily_change_pct,
        ),
    }


def _load_series(*, root: Path, series: ComparisonSeriesConfig, start_date: pd.Timestamp, end_date: date | None = None) -> pd.DataFrame:
    if series.storage == "us_daily_bars":
        database_path = root / "data" / "us_market_history.sqlite"
        if not database_path.is_file():
            return pd.DataFrame(columns=["date", "close"])
        with sqlite3.connect(database_path) as connection:
            return pd.read_sql_query(
                """
                SELECT date, close
                FROM us_daily_bars
                WHERE symbol = ? AND date >= ?
                ORDER BY date
                """,
                connection,
                params=(series.symbol, start_date.date().isoformat()),
            )
    if series.storage == "etf_qfq":
        database_path = root / "data" / "etf_history.sqlite"
        if not database_path.is_file() or end_date is None:
            return pd.DataFrame(columns=["date", "close"])
        return ETFHistoryReader(database_path).load_qfq_asof(
            series.symbol,
            start_date.date(),
            end_date,
            end_date,
        )[["date", "close"]]
    raise ValueError(f"unsupported comparison series storage: {series.storage}")


def build_comparison_chart_data(*, root: Path, config: ComparisonChartConfig) -> dict[str, Any] | None:
    """从本地历史库读取两条序列并生成浏览器数据载荷.

    按 config 指定的 storage 读取源/目标序列 (美股日线或 ETF 前复权),
    清洗对齐后交给 build_comparison_chart_data_from_frames 组装载荷.
    """
    source = _load_series(root=root, series=config.source, start_date=config.start_timestamp)
    source = _clean_prices(source, start_date=config.start_timestamp)
    if source.empty:
        return None
    target = _load_series(
        root=root,
        series=config.target,
        start_date=config.start_timestamp,
        end_date=source["date"].max().date(),
    )
    return build_comparison_chart_data_from_frames(source, target, config=config)


def _source_path() -> Path:
    return Path(__file__).with_name("static") / "research" / "market-comparison.html"


def render_comparison_chart_fragment(*, data: dict[str, Any] | None) -> str:
    """把数据载荷填入统一 SVG 图表模板, 返回可嵌入页面的 HTML 片段."""
    source_path = _source_path()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    return source_path.read_text(encoding="utf-8").replace(
        "__MARKET_COMPARISON_CHART_DATA__",
        json.dumps(data or {"data": []}, ensure_ascii=False, separators=(",", ":")),
    )
