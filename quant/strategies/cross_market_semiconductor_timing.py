# ═══════════════════════════════════════════════════════════════════════════════
# 策略: SOX半导体指数 → A股半导体 ETF 跨市场映射择时
# 文件: phase0/strategies/cross_market_semiconductor_timing.py
# 项目: stok-mapping
# ═══════════════════════════════════════════════════════════════════════════════
#
# ■ 策略概述
#   利用美股费城半导体指数(SOX)隔夜涨跌,预测可配置 A股半导体 ETF 次日走势。
#   信号触发→次日开盘买入→再次日盘中追踪止损卖出。持仓时间严格1天,不做隔夜。
#
# ■ 信号触发条件
#   SOX隔夜涨 > 0.5%  AND  VIX < 19
#
#   参数选择逻辑:
#   - SOX阈值从1.0%降至0.5%: 放宽入口,覆盖更多隔夜强势日
#   - VIX阈值从22降至19: 收紧质量过滤,只在极平静的市场里交易
#     验证: VIX<22时含大量"假阳"信号(恐慌反弹);VIX<19排除了几乎所有噪音日
#     信号数必须按“美国收盘后第一个 A 股交易日”的交易日历映射重新计算，
#     不能用自然日 +1 的历史口径。
#   - 两个参数反向调整(SOX↓+VIX↓)实现了"更宽的入口、更高的纯度"
#
# ■ 买入规则 (T日 = 信号触发后的第一个A股交易日)
#   强信号(SOX>1.0%): 开盘价全额买入 — 强信号通常直接拉升,等回调可能踏空
#   弱信号(SOX 0.5-1.0%): 挂 open×0.99 限价买单 — 弱信号日内常回调1%,有54%概率触及
#     触及: 以限价成交,比开盘追省1%
#     未触及: 撤单,当日不交易（可执行口径不允许事后回填开盘成交）
#   资金管理: 全仓进出,100股整手,预留佣金后计算可买手数
#
# ■ 卖出规则 (T+1日)
#   追踪止损: 持仓日盘中实时跟踪 running_high,从 running_high 回落 2% 触发市价卖出
#   未触发: 14:55以当日收盘价卖出,不留隔夜
#
#   参数选择逻辑:
#   - 2%回落间距: 用512480的5分钟线实测了1.0%/1.5%/2.0%/3.0%/5.0%
#     1.0%触发率88%→几乎每笔被洗(噪音),1.5%触发率67%→仍太高
#     2.0%是待以严格交易日历、固定持仓日和成本口径复核的候选甜点；
#     历史参数扫描数字不得脱离相同口径单独引用。
#     日均振幅~3%的512480,2%回落刚好区分噪音和真正趋势反转
#   - 仅持仓1天: B类单边涨日次日胜率仅45%,隔夜=掷硬币;信号不承诺第2天
#
# ■ 交易成本模拟 (基于 stok-mapping SimulatedAccountConfig)
#   佣金: 万分之2.5,最低5元/笔
#   滑点: 0.01% (1跳)
#   印花税: ETF免
#   过户费: ETF免
#   涨跌停/熔断: 未实现 (VIX<19过滤后信号日零触及,实际无影响)
#   T+1: 启用,买入日次日才能卖出
#
# ■ 撮合模拟
#   开盘买入/限价买入: 以目标价全额成交(假设流动性充足)
#   限价单成交: 5分钟线low触及挂单价即认定成交(实际约70%成交率,目前不打折)
#   追踪止损: 5分钟线bar的low触及running_high×0.98即触发,以止损价全额卖出
#   未模拟: 量能约束(512480日均成交10亿+,10万仓位不会冲击价格)
#
# ■ 已验证结果（仅 SH.512480；不能外推至其它 ETF）
#   (2021-05-13→2025-12-31, 严格交易日历, 308 原始信号 / 230 笔完成交易)
#   开盘买入:       +79.9% / 年化+13.6% / 夏普0.78 / 回撤-29.5%
#   限价买入(研究):  +148.2% / 年化+21.7% / 夏普1.15 / 回撤-23.6%
#   对标: 512480 buy&hold +52.5% / 沪深300 -7.3%
#
#   可执行规则本身没有未来函数：开盘挂限价单，盘中触及则成交，未触及则收盘撤单。
#   只有旧研究脚本中的“全天未触及后仍回填当天开盘成交”无法真实执行；该回填分支
#   不进入本策略的 admission、模拟账户或未来实盘订单路径。
#
# ■ 版本历史
#   v1.0.0  2026-08-11  SOX>1%+VIX<22, open→close, 基准建立
#   v1.1.0  2026-08-11  信号优化: SOX>0.5%+VIX<19, 年化+14pp提升
#   v1.2.0  2026-08-11  买入优化: 弱信号限价挂单, 年化再+9.5pp
# ═══════════════════════════════════════════════════════════════════════════════

"""Cross-market semiconductor timing strategy with intraday execution.

Migrated from phase0/research/cross_market/sox_semiconductor_trail.py v1.2.0.
See comment block above for full design rationale and parameter justification.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quant.execution.accounts import (
    SimulatedAccountConfig,
)
from quant.execution.single_etf_intraday import (
    SingleEtfIntradayPolicy,
    run_single_etf_intraday_account_execution,
)
from quant.data_governance.us_market_features import load_common_market_daily_features
from quant.strategies.base import BaseStrategy, StrategyOutput
from quant.strategies.registry import register

ETF_DB_PATH = "data/etf_history.sqlite"
US_DB_PATH = "data/us_market_history.sqlite"
DEFAULT_TARGET_SYMBOL = "SH.512480"
US_SOX_SYMBOL = "^SOX"
US_VIX_SYMBOL = "^VIX"

# 这个策略不是通用 ETF 选股器。允许标的是经过相关性和流动性初筛的 A 股半导体 ETF；
# 每个新增标的仍必须独立完成数据覆盖审计、回测和 admission。
SEMICONDUCTOR_TIMING_ETF_UNIVERSE: dict[str, dict[str, Any]] = {
    "SH.512480": {"ts_code": "512480.SH", "display_name": "国联安半导体ETF", "correlation_to_512480": 1.0000, "average_daily_turnover_cny": 1_350_000_000},
    "SH.512760": {"ts_code": "512760.SH", "display_name": "国联安半导体龙头ETF", "correlation_to_512480": 0.9938, "average_daily_turnover_cny": 420_000_000},
    "SH.516920": {"ts_code": "516920.SH", "display_name": "芯片ETF", "correlation_to_512480": 0.9907, "average_daily_turnover_cny": 210_000_000},
    "SH.516640": {"ts_code": "516640.SH", "display_name": "芯片龙头ETF", "correlation_to_512480": 0.9904, "average_daily_turnover_cny": 610_000_000},
    "SZ.159995": {"ts_code": "159995.SZ", "display_name": "华夏芯片ETF", "correlation_to_512480": 0.9866, "average_daily_turnover_cny": 700_000_000},
    "SZ.159813": {"ts_code": "159813.SZ", "display_name": "芯片ETF", "correlation_to_512480": 0.9854, "average_daily_turnover_cny": 260_000_000},
    "SZ.159801": {"ts_code": "159801.SZ", "display_name": "芯片龙头ETF", "correlation_to_512480": 0.9835, "average_daily_turnover_cny": 890_000_000},
    "SH.588200": {"ts_code": "588200.SH", "display_name": "科创芯片ETF", "correlation_to_512480": 0.9556, "average_daily_turnover_cny": 1_650_000_000},
}


def _opt_float(value: object | None) -> float | None:
    """Parse an optional float; None/empty stays None (engine falls back to position_size)."""
    if value is None or value == "":
        return None
    return float(str(value))


def normalize_semiconductor_timing_target(value: object | None) -> str:
    """Normalize a configured target symbol and reject unapproved ETFs."""
    target = str(value or DEFAULT_TARGET_SYMBOL).strip().upper()
    if target not in SEMICONDUCTOR_TIMING_ETF_UNIVERSE:
        allowed = ", ".join(SEMICONDUCTOR_TIMING_ETF_UNIVERSE)
        raise ValueError(
            f"target_symbol={target!r} is not an allowed semiconductor timing ETF; allowed: {allowed}"
        )
    return target

# ── default intraday parameters ──────────────────────────────────────
STRONG_SIGNAL_THRESHOLD = 0.01   # SOX > 1% → market order at open
LIMIT_ORDER_DISCOUNT = 0.01      # open × 0.99 for weak-signal limit orders
TRAILING_STOP_RATIO = 0.98       # sell when price ≤ running_high × 0.98

# Per-target default tuning (validated by 5-min backtests).
# - SH.512480 (v1.2.0): VIX<19 + 2% trailing stop is optimal; its single-day
#   >3% momentum days are only ~9%, so the trailing stop protects drawdowns.
# - SH.588200 (科创芯片): VIX<20 + pure T+1 scheduled_close is optimal; its
#   single-day >3% momentum days are ~21%, so a trailing stop sells the
#   momentum prematurely. See reports/star_mapping_backtest_588200/回测报告.md.
PER_TARGET_DEFAULTS: dict[str, dict[str, Any]] = {
    "SH.512480": {
        "vix_threshold": 19.0,
        "trailing_stop_ratio": 0.98,
        "exit_mode": "trailing_stop",
    },
    "SH.512760": {
        "vix_threshold": 19.0,
        "trailing_stop_ratio": 0.98,
        "exit_mode": "trailing_stop",
    },
    "SH.588200": {
        "vix_threshold": 20.0,
        "trailing_stop_ratio": 0.98,
        "exit_mode": "scheduled_close",
    },
}


def _target_default(target_symbol: str, key: str) -> Any:
    """Return a per-target default, falling back to the 512480 convention."""
    return PER_TARGET_DEFAULTS.get(target_symbol, PER_TARGET_DEFAULTS["SH.512480"]).get(key)


def map_us_features_to_next_cn_trading_day(
    us_features: pd.DataFrame,
    cn_trading_dates: pd.Series | pd.DatetimeIndex,
) -> pd.DataFrame:
    """Map a US-close feature to the first strictly later A-share session.

    The US session's closing value is only known after the Chinese market has
    closed on the same calendar date. Calendar-day ``+1`` is therefore not a
    trading-calendar rule: it drops Friday and holiday-adjacent signals.
    """
    if us_features.empty:
        return us_features.copy()

    cn_dates = pd.DatetimeIndex(pd.to_datetime(cn_trading_dates)).normalize().unique().sort_values()
    if cn_dates.empty:
        return us_features.iloc[0:0].copy()

    mapped = us_features.copy()
    mapped["date"] = pd.to_datetime(mapped["date"]).dt.normalize()
    mapped = mapped.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    mapped["signal_us_date"] = mapped["date"]
    locations = cn_dates.searchsorted(mapped["date"].to_numpy(), side="right")
    valid = locations < len(cn_dates)
    mapped = mapped.loc[valid].copy()
    mapped["date"] = cn_dates[locations[valid]]
    if mapped["date"].duplicated().any():
        # During an A-share holiday, several completed US sessions can become
        # known before the next CN open.  Treat them as one tradable signal:
        # compound SOX returns across the closed interval and use the latest
        # completed session for point-in-time fields such as VIX.
        compounded_sox = mapped.groupby("date", sort=True)["sox_ret"].apply(
            lambda values: float((1.0 + pd.to_numeric(values, errors="coerce").dropna()).prod() - 1.0)
        )
        mapped = (
            mapped.sort_values("signal_us_date")
            .groupby("date", sort=True, as_index=False)
            .tail(1)
            .set_index("date")
        )
        mapped.loc[compounded_sox.index, "sox_ret"] = compounded_sox
        mapped = mapped.reset_index()
    return mapped.sort_values("date").reset_index(drop=True)


@register
class CrossMarketSemiconductorTimingStrategy(BaseStrategy):
    """SOX + VIX dual-condition semiconductor timing with intraday execution.

    Entry (T day):
      - SOX > strong_signal_threshold (1.0%): market buy at open
      - SOX 0.5-1.0% (weak): limit order at open×0.99; cancel if not filled
    Exit (T+1 day):
      - Trailing stop: running_high × 0.98 triggers market sell
      - Never triggered: sell at last 5-min bar close (≈14:55)
    Position: configurable fraction of capital (default 100% = 全仓).
    """

    name = "cross_market_semiconductor_timing_etf_v1"
    candidate_name = "cross_market_semiconductor_timing_etf_v1"
    display_name = "Cross-Market Semiconductor ETF Timing (SOX+VIX, intraday)"
    category = "cross_market_timing"
    panel_scope = "portfolio"
    strategy_role = "candidate"
    skip_stock_panel = True  # This strategy loads its own ETF + US data via prepare_panel()
    supports_paper_trade = True
    account_execution_model = "single_etf_intraday"

    # ── data loading ──────────────────────────────────────────────────

    @staticmethod
    def _load_etf_daily(
        years: int,
        *,
        symbol: str = DEFAULT_TARGET_SYMBOL,
        as_of_date: date | None = None,
        database_path: Path = ETF_DB_PATH,
    ) -> pd.DataFrame:
        end = as_of_date or date.today()
        start = end - timedelta(days=365 * years + 30)
        with sqlite3.connect(database_path) as conn:
            df = pd.read_sql_query(
                "SELECT date, open, high, low, close, volume, amount "
                "FROM market_etf_daily_bars "
                "WHERE symbol = ? AND date >= ? AND date <= ? "
                "ORDER BY date",
                conn,
                params=[symbol, start.isoformat(), end.isoformat()],
            )
            adj = pd.read_sql_query(
                "SELECT date, adj_factor FROM market_etf_adj_factors "
                "WHERE symbol = ? AND date >= ? AND date <= ? ORDER BY date",
                conn,
                params=[symbol, start.isoformat(), end.isoformat()],
            )
        if df.empty:
            return df
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        for col in ["open", "high", "low", "close", "volume", "amount"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        if not adj.empty:
            adj["date"] = pd.to_datetime(adj["date"]).dt.normalize()
            adj["adj_factor"] = pd.to_numeric(adj["adj_factor"], errors="coerce")
            adj = adj.dropna(subset=["adj_factor"]).drop_duplicates("date", keep="last")
            df = df.merge(adj, on="date", how="left")
        if "adj_factor" not in df.columns:
            df["adj_factor"] = 1.0
        df["adj_factor"] = df["adj_factor"].fillna(1.0)
        df = df.dropna(subset=["open", "close"])
        df["ret"] = df["close"].pct_change()
        df["symbol"] = symbol
        return df.sort_values("date").reset_index(drop=True)

    @staticmethod
    def _load_us_features(
        years: int,
        cn_trading_dates: pd.Series | pd.DatetimeIndex,
        *,
        as_of_date: date | None = None,
        database_path: Path = US_DB_PATH,
    ) -> pd.DataFrame:
        end = as_of_date or date.today()
        start = end - timedelta(days=365 * years + 30)
        features = load_common_market_daily_features(
            Path(database_path),
            "us_daily_bars",
            [US_SOX_SYMBOL, US_VIX_SYMBOL],
            start=start,
            end=end,
        )
        if features.empty:
            return pd.DataFrame(columns=["date", "sox_ret", "vix_close"])
        merged = features.rename(
            columns={f"{US_SOX_SYMBOL}_return": "sox_ret", US_VIX_SYMBOL: "vix_close"}
        )[["date", "sox_ret", "vix_close"]].dropna(subset=["sox_ret", "vix_close"])
        return map_us_features_to_next_cn_trading_day(merged, cn_trading_dates)

    @staticmethod
    def _load_5min_bars(
        date_start: pd.Timestamp,
        date_end: pd.Timestamp,
        symbol: str = DEFAULT_TARGET_SYMBOL,
        database_path: Path = Path(ETF_DB_PATH),
    ) -> pd.DataFrame:
        """Load 5-min bars for the ETF, indexed by time (datetime)."""
        with sqlite3.connect(database_path) as conn:
            df = pd.read_sql_query(
                "SELECT time, open, high, low, close "
                "FROM market_etf_5min_bars "
                "WHERE symbol = ? AND time >= ? AND time <= ? "
                "ORDER BY time",
                conn,
                params=[
                    symbol,
                    date_start.strftime("%Y-%m-%d"),
                    (date_end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                ],
            )
        if df.empty:
            return df
        df["time"] = pd.to_datetime(df["time"])
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["date"] = df["time"].dt.date.astype(str)
        return df.sort_values("time").reset_index(drop=True)

    @staticmethod
    def _account_config(
        *,
        initial_cash: float = 100_000,
        lot_size: int = 100,
        slippage: float = 0.0001,
        commission: float = 0.00025,
        stamp_duty_sell: float = 0.0,
        min_commission: float = 5.0,
        price_tick: float = 0.001,
        intraday_data_path: Path | str | None = None,
    ) -> SimulatedAccountConfig:
        return SimulatedAccountConfig(
            account_id="backtest",
            name="backtest",
            initial_cash=float(initial_cash),
            ledger_path="/dev/null",
            database_path="/dev/null",
            execution_model="single_etf_intraday",
            intraday_data_path=Path(str(intraday_data_path)) if intraday_data_path is not None else Path(ETF_DB_PATH),
            execution_price_mode="next_open",
            price_tick=float(price_tick),
            lot_size=int(lot_size),
            commission=float(commission),
            stamp_duty_sell=float(stamp_duty_sell),
            slippage=float(slippage),
            min_commission=float(min_commission),
            transfer_fee_rate=0.0,
            enable_limit_check=False,
            enable_suspension_check=False,
            enable_t_plus_one=True,
            enable_special_limit_rules=False,
        )

    # ── BaseStrategy interface ────────────────────────────────────────

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return bool(
            strategy_cfg.get("cross_market_semiconductor_timing", {}).get("enabled", True)
        )

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        cfg = strategy_cfg.get("cross_market_semiconductor_timing", {})
        target_symbol = normalize_semiconductor_timing_target(cfg.get("target_symbol"))
        years = int(cfg.get("years", 7))
        as_of = pd.Timestamp(cfg.get("as_of_date", date.today())).date()
        project_root = Path(str(cfg.get("project_root", Path.cwd()))).resolve()
        etf_database_path = Path(str(cfg.get("etf_database_path", project_root / ETF_DB_PATH)))
        us_database_path = Path(str(cfg.get("us_database_path", project_root / US_DB_PATH)))
        if not etf_database_path.is_absolute():
            etf_database_path = project_root / etf_database_path
        if not us_database_path.is_absolute():
            us_database_path = project_root / us_database_path

        etf = self._load_etf_daily(
            years=years,
            symbol=target_symbol,
            as_of_date=as_of,
            database_path=etf_database_path,
        )
        if etf.empty:
            return pd.DataFrame()

        us = self._load_us_features(
            years=years,
            cn_trading_dates=etf["date"],
            as_of_date=as_of,
            database_path=us_database_path,
        )
        merged = etf.merge(us, on="date", how="left")
        first_mapped_date = merged.loc[merged["vix_close"].notna(), "date"].min()
        if pd.isna(first_mapped_date):
            return pd.DataFrame()
        # Preserve every A-share session once US history begins.  A US holiday
        # means there is no new cross-market signal, not that the A-share
        # session disappeared; the row is still required for T+1 exits and NAV.
        merged = merged[merged["date"] >= first_mapped_date].copy()
        merged["sox_ret"] = merged["sox_ret"].fillna(0.0)
        merged["vix_close"] = merged["vix_close"].fillna(999.0)

        merged["timing_ret"] = (merged["close"].shift(-1) / merged["open"] - 1.0).fillna(0.0)
        merged["vol20"] = merged["ret"].rolling(20).std() * np.sqrt(252)
        for w in [3, 5, 10, 20, 60]:
            merged[f"mom{w}"] = merged["close"].pct_change(w)
            merged[f"ma{w}"] = merged["close"].rolling(w).mean()

        return merged.dropna(
            subset=["date", "symbol", "open", "close", "sox_ret", "vix_close"]
        ).reset_index(drop=True)

    def prepare_intraday_account_session(self, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        """Build the current CN session when its daily bar is not yet available.

        This is deliberately a narrow operational path.  It uses only a
        completed US close, the current A-share opening snapshot and current
        5-minute bars; it does not synthesize a daily bar or backfill history.
        """
        cfg = strategy_cfg.get("cross_market_semiconductor_timing", {})
        target_symbol = normalize_semiconductor_timing_target(cfg.get("target_symbol"))
        as_of = pd.Timestamp(cfg.get("as_of_date", date.today())).normalize()
        project_root = Path(str(cfg.get("project_root", Path.cwd()))).resolve()
        etf_database_path = Path(str(cfg.get("etf_database_path", project_root / ETF_DB_PATH)))
        us_database_path = Path(str(cfg.get("us_database_path", project_root / US_DB_PATH)))
        if not etf_database_path.is_absolute():
            etf_database_path = project_root / etf_database_path
        if not us_database_path.is_absolute():
            us_database_path = project_root / us_database_path

        try:
            with sqlite3.connect(etf_database_path) as conn:
                bars = pd.read_sql_query(
                    "SELECT time, open, high, low, close FROM market_etf_5min_bars "
                    "WHERE symbol = ? AND time >= ? AND time < ? ORDER BY time",
                    conn,
                    params=[
                        target_symbol,
                        as_of.strftime("%Y-%m-%d"),
                        (as_of + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                    ],
                )
                opening = pd.read_sql_query(
                    "SELECT open_price FROM market_etf_opening_snapshots "
                    "WHERE symbol = ? AND observed_at >= ? AND observed_at < ? "
                    "AND open_price IS NOT NULL ORDER BY observed_at ASC LIMIT 1",
                    conn,
                    params=[
                        target_symbol,
                        as_of.strftime("%Y-%m-%d"),
                        (as_of + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                    ],
                )
                cn_history = pd.read_sql_query(
                    "SELECT date FROM market_etf_daily_bars WHERE symbol = ? AND date < ? ORDER BY date",
                    conn,
                    params=[target_symbol, as_of.strftime("%Y-%m-%d")],
                )
                adj = pd.read_sql_query(
                    "SELECT adj_factor FROM market_etf_adj_factors "
                    "WHERE symbol = ? AND date <= ? ORDER BY date DESC LIMIT 1",
                    conn,
                    params=[target_symbol, as_of.strftime("%Y-%m-%d")],
                )
        except (sqlite3.Error, pd.errors.DatabaseError):
            return pd.DataFrame()
        if bars.empty or opening.empty:
            return pd.DataFrame()

        bars["time"] = pd.to_datetime(bars["time"], errors="coerce")
        for column in ["open", "high", "low", "close"]:
            bars[column] = pd.to_numeric(bars[column], errors="coerce")
        bars = bars.dropna(subset=["time", "close"])
        opening_price = pd.to_numeric(opening["open_price"], errors="coerce").iloc[0]
        if bars.empty or not np.isfinite(opening_price):
            return pd.DataFrame()

        cn_dates = pd.DatetimeIndex(pd.to_datetime(cn_history["date"], errors="coerce").dropna())
        cn_dates = cn_dates.append(pd.DatetimeIndex([as_of]))
        us = self._load_us_features(
            years=int(cfg.get("years", 7)),
            cn_trading_dates=cn_dates,
            as_of_date=as_of.date(),
            database_path=us_database_path,
        )
        us = us[us["date"] == as_of].copy()
        if us.empty:
            return pd.DataFrame()
        row = us.iloc[-1]
        day_adj_factor = (
            float(pd.to_numeric(adj["adj_factor"], errors="coerce").iloc[0])
            if not adj.empty and pd.notna(pd.to_numeric(adj["adj_factor"], errors="coerce").iloc[0])
            else 1.0
        )
        return pd.DataFrame(
            {
                "date": [as_of],
                "symbol": [target_symbol],
                "open": [float(opening_price)],
                "close": [float(bars.iloc[-1]["close"])],
                "sox_ret": [float(row["sox_ret"])],
                "vix_close": [float(row["vix_close"])],
                "signal_us_date": [row.get("signal_us_date", pd.NaT)],
                "adj_factor": [day_adj_factor],
            }
        )

    def account_execution_params(self, strategy_cfg: dict[str, Any]) -> dict[str, Any]:
        cfg = strategy_cfg.get("cross_market_semiconductor_timing", {})
        target_symbol = normalize_semiconductor_timing_target(cfg.get("target_symbol"))

        def first_value(key: str, default: float) -> float:
            raw = cfg.get(key, [default])
            if isinstance(raw, (list, tuple)):
                return float(raw[0]) if raw else float(default)
            return float(raw)

        return {
            "target_symbol": target_symbol,
            "sox_threshold": first_value("sox_thresholds", 0.005),
            "vix_threshold": first_value("vix_thresholds", _target_default(target_symbol, "vix_threshold")),
            "position_size": first_value("position_sizes", 1.0),
            "strong_position_size": _opt_float(cfg.get("strong_position_size")),
            "weak_position_size": _opt_float(cfg.get("weak_position_size")),
            "strong_signal_threshold": float(cfg.get("strong_signal_threshold", STRONG_SIGNAL_THRESHOLD)),
            "limit_order_discount": float(cfg.get("limit_order_discount", LIMIT_ORDER_DISCOUNT)),
            "trailing_stop_ratio": float(cfg.get("trailing_stop_ratio", _target_default(target_symbol, "trailing_stop_ratio"))),
            "exit_mode": str(cfg.get("exit_mode", _target_default(target_symbol, "exit_mode"))),
            "weak_unfilled_action": str(cfg.get("weak_unfilled_action", "cancel")),
            "fallback_time": str(cfg.get("fallback_time", "14:55")),
        }

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        """Grid-search SOX / VIX thresholds using fast daily-level simulation."""
        cfg = strategy_cfg.get("cross_market_semiconductor_timing", {})
        sox_thresholds = cfg.get("sox_thresholds", [0.005, 0.008, 0.01])
        vix_thresholds = cfg.get("vix_thresholds", [19, 20, 21])
        position_sizes = cfg.get("position_sizes", [1.0])
        min_signals = int(cfg.get("train_min_signals", 5))
        target_symbol = normalize_semiconductor_timing_target(cfg.get("target_symbol"))

        best: dict[str, Any] | None = None
        for sox_t in sox_thresholds:
            for vix_t in vix_thresholds:
                for pos in position_sizes:
                    params = {
                        "target_symbol": target_symbol,
                        "sox_threshold": float(sox_t),
                        "vix_threshold": float(vix_t),
                        "position_size": float(pos),
                        "strong_signal_threshold": float(cfg.get("strong_signal_threshold", STRONG_SIGNAL_THRESHOLD)),
                        "limit_order_discount": float(cfg.get("limit_order_discount", LIMIT_ORDER_DISCOUNT)),
                        "trailing_stop_ratio": float(cfg.get("trailing_stop_ratio", _target_default(target_symbol, "trailing_stop_ratio"))),
                        "exit_mode": str(cfg.get("exit_mode", _target_default(target_symbol, "exit_mode"))),
                        "weak_unfilled_action": str(cfg.get("weak_unfilled_action", "cancel")),
                        "fallback_time": str(cfg.get("fallback_time", "14:55")),
                    }
                    output = self._simulate_daily(
                        train, params,
                        slippage=slippage, commission=commission,
                        stamp_duty_sell=stamp_duty_sell,
                    )
                    from quant.research.metrics import calc_metrics as _cm

                    metric = _cm(output.returns, output.exposure)
                    if metric["trades"] < min_signals:
                        continue
                    candidate = {
                        **params,
                        "train_score": float(metric["sharpe"]),
                        "train_sharpe": float(metric["sharpe"]),
                        "train_trades": int(metric["trades"]),
                        "train_return": float(metric["annualized_return"]),
                        "train_mdd": float(metric["max_drawdown"]),
                    }
                    if best is None or candidate["train_score"] > best["train_score"]:
                        best = candidate

        if best is None:
            best = {
                "target_symbol": target_symbol,
                "sox_threshold": 0.005,
                "vix_threshold": float(cfg.get("vix_thresholds", [_target_default(target_symbol, "vix_threshold")])[0] if cfg.get("vix_thresholds") else _target_default(target_symbol, "vix_threshold")),
                "position_size": 1.0,
                "strong_signal_threshold": float(cfg.get("strong_signal_threshold", STRONG_SIGNAL_THRESHOLD)),
                "limit_order_discount": float(cfg.get("limit_order_discount", LIMIT_ORDER_DISCOUNT)),
                "trailing_stop_ratio": float(cfg.get("trailing_stop_ratio", _target_default(target_symbol, "trailing_stop_ratio"))),
                "exit_mode": str(cfg.get("exit_mode", _target_default(target_symbol, "exit_mode"))),
                "weak_unfilled_action": str(cfg.get("weak_unfilled_action", "cancel")),
                "fallback_time": str(cfg.get("fallback_time", "14:55")),
                "train_score": 0.0,
                "train_sharpe": 0.0,
                "train_trades": 0,
                "train_return": 0.0,
                "train_mdd": 0.0,
            }
        return best

    def apply(
        self,
        panel: pd.DataFrame,
        params: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> StrategyOutput:
        """Full intraday simulation with two-tier entry and trailing stop."""
        cfg_params = {
            "strong_signal_threshold": STRONG_SIGNAL_THRESHOLD,
            "limit_order_discount": LIMIT_ORDER_DISCOUNT,
            "trailing_stop_ratio": TRAILING_STOP_RATIO,
        }
        # Allow config override
        if "strong_signal_threshold" in params:
            cfg_params["strong_signal_threshold"] = float(params["strong_signal_threshold"])
        if "limit_order_discount" in params:
            cfg_params["limit_order_discount"] = float(params["limit_order_discount"])
        if "trailing_stop_ratio" in params:
            cfg_params["trailing_stop_ratio"] = float(params["trailing_stop_ratio"])
        exit_mode = str(params.get("exit_mode", "trailing_stop"))

        return self._simulate_intraday(
            panel, params,
            slippage=slippage, commission=commission,
            stamp_duty_sell=stamp_duty_sell,
            **cfg_params,
        )

    def format_params(self, params: dict[str, Any]) -> str:
        strong_pos = params.get("strong_position_size") or params.get("position_size", 1.0)
        weak_pos = params.get("weak_position_size") or params.get("position_size", 1.0)
        return (
            f"SOX>{params.get('sox_threshold', 0.005):.1%},"
            f"VIX<{params.get('vix_threshold', 19):.0f},"
            f"pos强={float(strong_pos):.0%}/弱={float(weak_pos):.0%},"
            f"exit={params.get('exit_mode', 'trailing_stop')}"
        )

    def build_metadata(self, params: dict[str, Any]) -> dict[str, Any]:
        metadata = super().build_metadata(params)
        metadata["account_execution_policy"] = {
            "target_symbol": normalize_semiconductor_timing_target(params.get("target_symbol")),
            "return_symbol": US_SOX_SYMBOL,
            "volatility_symbol": US_VIX_SYMBOL,
            "return_threshold": float(params.get("sox_threshold", 0.005)),
            "volatility_threshold": float(params.get("vix_threshold", 19.0)),
            "strong_signal_threshold": float(params.get("strong_signal_threshold", STRONG_SIGNAL_THRESHOLD)),
            "weak_limit_discount": float(params.get("limit_order_discount", LIMIT_ORDER_DISCOUNT)),
            "weak_unfilled_action": str(params.get("weak_unfilled_action", "cancel")),
            "holding_sessions": 1,
            "trailing_drawdown": 1.0 - float(params.get("trailing_stop_ratio", TRAILING_STOP_RATIO)),
            "exit_mode": str(params.get("exit_mode", "trailing_stop")),
            "fallback_time": str(params.get("fallback_time", "14:55")),
            "position_size": float(params.get("position_size", 1.0)),
            "strong_position_size": _opt_float(params.get("strong_position_size")),
            "weak_position_size": _opt_float(params.get("weak_position_size")),
        }
        return metadata

    # ── simulation engines ────────────────────────────────────────────

    def _simulate_daily(
        self,
        panel: pd.DataFrame,
        params: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> StrategyOutput:
        """Fast daily-level simulation: open buy → next close sell."""
        sox_t = float(params["sox_threshold"])
        vix_t = float(params["vix_threshold"])
        position_size = float(params["position_size"])

        d = panel.copy()
        d["date"] = pd.to_datetime(d["date"]).dt.normalize()
        d = d.sort_values("date").reset_index(drop=True)

        sox_ret = pd.to_numeric(d["sox_ret"], errors="coerce").fillna(0.0)
        vix_close = pd.to_numeric(d["vix_close"], errors="coerce").fillna(999.0)
        d["signal"] = ((sox_ret > sox_t) & (vix_close < vix_t)).astype(float)
        d["weight"] = d["signal"] * position_size

        timing_ret = pd.to_numeric(d.get("timing_ret", d["ret"]), errors="coerce").fillna(0.0)
        d["position_ret"] = d["weight"] * timing_ret

        turnover = d["weight"].diff().abs().fillna(d["weight"].abs())
        sells = d["weight"].diff().clip(upper=0).abs().fillna(0.0)
        costs = turnover * (slippage + commission) + sells * stamp_duty_sell

        returns = d.groupby("date")["position_ret"].sum().sub(
            pd.Series(costs.values, index=d["date"]), fill_value=0.0
        )
        exposure = d.set_index("date")["weight"].reindex(returns.index, fill_value=0.0)

        signal_frame = d[[
            c for c in ["date", "symbol", "signal", "weight", "sox_ret", "vix_close",
                         "open", "close", "ret", "timing_ret", "position_ret"]
            if c in d.columns
        ]].copy()
        signal_frame["score"] = d["signal"]

        return StrategyOutput(
            returns=returns,
            exposure=exposure,
            signal_frame=signal_frame,
            metadata=self.build_metadata(params),
        )

    def _simulate_intraday(
        self,
        panel: pd.DataFrame,
        params: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
        strong_signal_threshold: float = STRONG_SIGNAL_THRESHOLD,
        limit_order_discount: float = LIMIT_ORDER_DISCOUNT,
        trailing_stop_ratio: float = TRAILING_STOP_RATIO,
    ) -> StrategyOutput:
        """Run the executable 5-minute account model and expose daily metrics."""
        sox_t = float(params["sox_threshold"])
        vix_t = float(params["vix_threshold"])
        position_size = float(params["position_size"])

        d = panel.copy()
        d["date"] = pd.to_datetime(d["date"]).dt.normalize()
        d = d.sort_values("date").reset_index(drop=True)

        sox_ret = pd.to_numeric(d["sox_ret"], errors="coerce").fillna(0.0)
        vix_close = pd.to_numeric(d["vix_close"], errors="coerce").fillna(999.0)
        signal = (sox_ret > sox_t) & (vix_close < vix_t)

        # Load intraday data for the panel's date range
        d0 = d["date"].min()
        d1 = d["date"].max()
        target_symbol = normalize_semiconductor_timing_target(params.get("target_symbol"))
        etf_database_path = params.get("etf_database_path")
        if etf_database_path is None:
            etf_database_path = Path(ETF_DB_PATH)
        elif not Path(str(etf_database_path)).is_absolute():
            etf_database_path = Path.cwd() / Path(str(etf_database_path))
        intraday = self._load_5min_bars(d0, d1, target_symbol, database_path=Path(str(etf_database_path)))
        account = self._account_config(
            initial_cash=100_000,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
            intraday_data_path=etf_database_path,
        )
        policy = SingleEtfIntradayPolicy(
            target_symbol=target_symbol,
            return_symbol=US_SOX_SYMBOL,
            volatility_symbol=US_VIX_SYMBOL,
            return_threshold=sox_t,
            volatility_threshold=vix_t,
            strong_signal_threshold=strong_signal_threshold,
            weak_limit_discount=limit_order_discount,
            weak_unfilled_action=str(params.get("weak_unfilled_action", "cancel")),
            holding_sessions=1,
            trailing_drawdown=1.0 - trailing_stop_ratio,
            fallback_time=str(params.get("fallback_time", "14:55")),
            exit_mode=str(params.get("exit_mode", "trailing_stop")),
            position_size=position_size,
        )
        result = run_single_etf_intraday_account_execution(
            signal_frame=d,
            intraday_bars=intraday,
            account=account,
            policy=policy,
        )
        daily_result = result.daily_assets.copy()
        daily_returns = pd.Series(
            daily_result["daily_return"].to_numpy(dtype=float),
            index=pd.to_datetime(daily_result["date"]),
        )
        exposure_series = pd.Series(
            daily_result["exposure"].to_numpy(dtype=float),
            index=pd.to_datetime(daily_result["date"]),
        )

        # Build signal frame
        signal_frame = d[[
            c for c in ["date", "symbol", "signal_us_date", "sox_ret", "vix_close", "open", "high", "low", "close", "volume", "amount", "ret", "adj_factor"]
            if c in d.columns
        ]].copy()
        signal_frame["signal"] = signal.astype(float)
        signal_frame["score"] = signal_frame["signal"]
        signal_frame["weight_unshifted"] = signal_frame["signal"] * position_size

        return StrategyOutput(
            returns=daily_returns,
            exposure=exposure_series,
            signal_frame=signal_frame,
            metadata={**self.build_metadata(params), "account_execution_metrics": result.metrics},
        )
