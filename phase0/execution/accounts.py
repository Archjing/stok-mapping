from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

import numpy as np
import pandas as pd

from phase0.reporting.account_bill import (
    export_account_bill_html,
    format_money,
    format_num,
    format_pct,
    load_latest_account_snapshot,
)


DEFAULT_ACCOUNT_LEDGER = "data/simulated_trading/phase0_daily_account_ledger.csv"
DEFAULT_BRIEF_LEDGER = "data/simulated_trading/phase0_daily_brief_ledger.csv"


@dataclass(frozen=True)
class SimulatedAccountConfig:
    account_id: str
    name: str
    initial_cash: float
    ledger_path: Path
    database_path: Path
    strategy_id: str = "legacy_momentum_low_turnover_v1"
    simulation_start_date: str = ""
    enabled: bool = True
    execution_price_mode: str = "next_open"
    price_tick: float = 0.01
    max_participation_rate: float = 0.05
    lot_size: int = 100
    commission: float = 0.0
    stamp_duty_sell: float = 0.0
    slippage: float = 0.0
    min_commission: float = 0.0
    transfer_fee_rate: float = 0.0
    min_trade_amount: float = 0.0
    conservative_price_buffer: float = 0.001
    enable_limit_check: bool = True
    enable_suspension_check: bool = True
    enable_t_plus_one: bool = True
    enable_special_limit_rules: bool = True
    limit_up_down_pct: dict[str, float] | None = None
    st_limit_pct: float = 0.05
    new_stock_no_limit_days: int = 5


@dataclass(frozen=True)
class SignalAccountExecutionResult:
    daily_assets: pd.DataFrame
    trades: pd.DataFrame
    positions: pd.DataFrame
    metrics: dict[str, Any]


def load_simulated_accounts(config: dict[str, Any], root: Path) -> list[SimulatedAccountConfig]:
    walk_forward = config.get("walk_forward", {})
    execution = config.get("execution", {})
    limit_cfg = execution.get("limit_up_down_pct", {})
    strategy_reports = config.get("strategy_reports", {}) or {}
    default_strategy_id = str(strategy_reports.get("default_strategy_id") or "legacy_momentum_low_turnover_v1")
    raw_accounts = config.get("accounts", {}).get("simulated", [])
    if not raw_accounts:
        raw_accounts = [
            {
                "account_id": "default",
                "name": "默认模拟账户",
                "initial_cash": walk_forward.get("initial_cash", 1_000_000),
                "ledger_path": DEFAULT_ACCOUNT_LEDGER,
                "enabled": True,
            }
        ]

    accounts: list[SimulatedAccountConfig] = []
    for raw in raw_accounts:
        if not bool(raw.get("enabled", True)):
            continue
        ledger_path = Path(str(raw.get("ledger_path", DEFAULT_ACCOUNT_LEDGER)))
        if not ledger_path.is_absolute():
            ledger_path = root / ledger_path
        database_path = Path(str(raw.get("database_path", "data/simulated_trading/simulated_accounts.sqlite")))
        if not database_path.is_absolute():
            database_path = root / database_path
        accounts.append(
            SimulatedAccountConfig(
                account_id=str(raw.get("account_id", "default")),
                name=str(raw.get("name", raw.get("account_id", "默认模拟账户"))),
                initial_cash=float(raw.get("initial_cash", walk_forward.get("initial_cash", 1_000_000))),
                ledger_path=ledger_path,
                database_path=database_path,
                strategy_id=str(raw.get("strategy_id", default_strategy_id) or default_strategy_id),
                simulation_start_date=str(raw.get("simulation_start_date", raw.get("start_date", "")) or ""),
                enabled=True,
                execution_price_mode=str(raw.get("execution_price_mode", execution.get("price_mode", "next_open"))),
                price_tick=float(raw.get("price_tick", execution.get("price_tick", 0.01))),
                max_participation_rate=float(raw.get("max_participation_rate", execution.get("max_participation_rate", 0.05))),
                lot_size=int(raw.get("lot_size", execution.get("lot_size", 100))),
                commission=float(raw.get("commission", walk_forward.get("commission", 0.0))),
                stamp_duty_sell=float(raw.get("stamp_duty_sell", walk_forward.get("stamp_duty_sell", 0.0))),
                slippage=float(raw.get("slippage", walk_forward.get("slippage", 0.0))),
                min_commission=float(raw.get("min_commission", execution.get("min_commission", 0.0))),
                transfer_fee_rate=float(raw.get("transfer_fee_rate", execution.get("transfer_fee_rate", 0.0))),
                min_trade_amount=float(raw.get("min_trade_amount", execution.get("min_trade_amount", 0.0))),
                conservative_price_buffer=float(raw.get("conservative_price_buffer", execution.get("conservative_price_buffer", 0.001))),
                enable_limit_check=bool(raw.get("enable_limit_check", execution.get("enable_limit_check", True))),
                enable_suspension_check=bool(raw.get("enable_suspension_check", execution.get("enable_suspension_check", True))),
                enable_t_plus_one=bool(raw.get("enable_t_plus_one", execution.get("enable_t_plus_one", True))),
                enable_special_limit_rules=bool(raw.get("enable_special_limit_rules", execution.get("enable_special_limit_rules", True))),
                limit_up_down_pct={
                    "default": float(limit_cfg.get("default", 0.10)),
                    "star": float(limit_cfg.get("star", 0.20)),
                    "chinext": float(limit_cfg.get("chinext", 0.20)),
                    "bj": float(limit_cfg.get("bj", 0.30)),
                },
                st_limit_pct=float(raw.get("st_limit_pct", execution.get("st_limit_pct", 0.05))),
                new_stock_no_limit_days=int(raw.get("new_stock_no_limit_days", execution.get("new_stock_no_limit_days", 5))),
            )
        )
    return accounts


def parse_percent(value: Any) -> float:
    if pd.isna(value):
        return 0.0
    raw = str(value).strip().replace("%", "")
    if not raw:
        return 0.0
    try:
        return float(raw) / 100.0
    except ValueError:
        return 0.0


def round_lot_floor(shares: float, lot_size: int) -> float:
    if lot_size <= 1:
        return max(0.0, float(np.floor(shares)))
    return float(max(0, int(np.floor(float(shares) / lot_size) * lot_size)))


def price_mode_label(price_mode: str) -> str:
    labels = {
        "next_open": "执行日开盘价",
        "close": "执行日收盘价",
        "conservative": "执行日开盘保守价",
    }
    return labels.get(str(price_mode), str(price_mode))


def trade_time_for_price_mode(*, brief_date: str, signal_date: str, price_mode: str) -> str:
    if price_mode == "close":
        return f"{brief_date} 15:00"
    if price_mode == "next_open":
        return f"{brief_date} 09:30"
    if price_mode == "conservative":
        return f"{brief_date} 09:30"
    return f"{brief_date} 09:30"


def _safe_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"unsafe SQL identifier: {value}")
    return value


def _resolve_path(root: Path, value: Any) -> Path:
    path = Path(str(value or ""))
    return path if path.is_absolute() else root / path


def _looks_like_st(name: Any) -> bool:
    text = str(name or "").upper()
    return "ST" in text or "退" in text


def _truthy_market_flag(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        text = value.strip().lower()
        return text in {"1", "true", "t", "yes", "y", "停牌", "暂停交易", "suspended", "limit_up", "limit_down"}
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    return bool(value)


def _is_new_stock_no_limit(price_row: dict[str, Any], account: SimulatedAccountConfig) -> bool:
    if not account.enable_special_limit_rules or account.new_stock_no_limit_days <= 0:
        return False
    limit_days = int(account.new_stock_no_limit_days)
    for key in [
        "listing_trading_days",
        "trade_days_since_listing",
        "trading_days_since_listing",
        "listing_trade_day_index",
        "listing_trade_day_number",
    ]:
        value = pd.to_numeric(price_row.get(key, np.nan), errors="coerce")
        if pd.notna(value):
            age = int(value)
            if key == "listing_trade_day_number":
                return 1 <= age <= limit_days
            return 0 <= age < limit_days
    trade_date = pd.to_datetime(price_row.get("date", ""), errors="coerce")
    list_date = pd.to_datetime(price_row.get("list_date", ""), errors="coerce")
    if pd.isna(trade_date) or pd.isna(list_date):
        return False
    return 0 <= int((trade_date.normalize() - list_date.normalize()).days) < limit_days


def _limit_pct(symbol: str, account: SimulatedAccountConfig, price_row: dict[str, Any] | None = None) -> float:
    if account.enable_special_limit_rules and price_row and _looks_like_st(price_row.get("name", "")):
        return float(account.st_limit_pct)
    limits = account.limit_up_down_pct or {}
    code = str(symbol).split(".")[-1]
    market = str(symbol).split(".")[0]
    if market == "BJ" or code.startswith(("4", "8")):
        return float(limits.get("bj", 0.30))
    if market == "SH" and code.startswith("688"):
        return float(limits.get("star", 0.20))
    if market == "SZ" and code.startswith("300"):
        return float(limits.get("chinext", 0.20))
    return float(limits.get("default", 0.10))


def _trade_cost(trade_amount: float, side: str, account: SimulatedAccountConfig) -> float:
    amount = max(0.0, float(trade_amount))
    if amount <= 0:
        return 0.0
    slippage_cost = amount * float(account.slippage)
    commission_cost = amount * float(account.commission)
    if account.min_commission > 0 and account.commission > 0:
        commission_cost = max(commission_cost, float(account.min_commission))
    transfer_fee = amount * float(account.transfer_fee_rate)
    stamp = amount * float(account.stamp_duty_sell) if side == "sell" else 0.0
    return float(slippage_cost + commission_cost + transfer_fee + stamp)


def _affordable_buy_shares(*, cash_asset: float, price: float, requested_shares: float, account: SimulatedAccountConfig) -> float:
    shares = min(float(requested_shares), round_lot_floor(float(cash_asset) / float(price), account.lot_size))
    step = max(int(account.lot_size), 1)
    while shares > 0:
        amount = shares * float(price)
        if amount + _trade_cost(amount, "buy", account) <= float(cash_asset) + 1e-9:
            return float(shares)
        shares = round_lot_floor(shares - step, account.lot_size)
    return 0.0


def _round_price_to_tick(price: float, side: str, tick: float) -> float:
    if not pd.notna(price) or float(price) <= 0 or float(tick) <= 0:
        return float(price)
    rounding = ROUND_CEILING if side == "buy" else ROUND_FLOOR
    units = (Decimal(str(float(price))) / Decimal(str(float(tick)))).to_integral_value(rounding=rounding)
    rounded = units * Decimal(str(float(tick)))
    return float(rounded)


def _load_execution_prices(
    *,
    root: Path,
    local_history_cfg: dict[str, Any] | None,
    execution_date: str,
    symbols: list[str],
) -> dict[str, dict[str, Any]]:
    if not symbols:
        return {}
    cfg = local_history_cfg or {}
    db_path = _resolve_path(root, cfg.get("path", "data/a_share_history.sqlite"))
    if not db_path.exists():
        return {}
    daily_table = _safe_identifier(str(cfg.get("daily_table", "market_daily_bars")))
    market = str(cfg.get("market", "CN"))
    adjust_type = str(cfg.get("execution_adjust_type", "bfq"))
    meta_table = _safe_identifier(str(cfg.get("meta_table", "market_stocks")))
    try:
        with sqlite3.connect(db_path) as conn:
            daily_cols = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({daily_table})").fetchall()}
            meta_cols = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({meta_table})").fetchall()}
            can_join_meta = {"market", "symbol"}.issubset(meta_cols)
            meta_join = (
                f"""
        LEFT JOIN {meta_table} s
          ON s.market = b.market
         AND s.symbol = b.symbol
                """
                if can_join_meta
                else ""
            )
            name_expr = "s.name" if can_join_meta and "name" in meta_cols else "''"
            list_date_expr = "s.list_date" if can_join_meta and "list_date" in meta_cols else "''"
            optional_cols = [
                "limit_up",
                "limit_down",
                "is_limit_up",
                "is_limit_down",
                "is_suspended",
                "listing_trading_days",
                "trade_days_since_listing",
            ]
            optional_select = ",\n               " + ",\n               ".join(
                f"b.{col} AS {col}" if col in daily_cols else f"NULL AS {col}"
                for col in optional_cols
            )
            placeholders = ",".join("?" for _ in symbols)
            query = f"""
        SELECT b.symbol, b.open, b.high, b.low, b.close, b.volume, b.amount,
               (
                   SELECT p.close
                   FROM {daily_table} p
                   WHERE p.market = b.market
                     AND p.symbol = b.symbol
                     AND p.adjust_type = b.adjust_type
                     AND p.date < b.date
                   ORDER BY p.date DESC
                   LIMIT 1
               ) AS previous_close,
               {name_expr} AS name,
               {list_date_expr} AS list_date
               {optional_select}
        FROM {daily_table} b
        {meta_join}
        WHERE b.market = ?
          AND b.adjust_type = ?
          AND b.date = ?
          AND b.symbol IN ({placeholders})
    """
            rows = conn.execute(query, (market, adjust_type, execution_date, *symbols)).fetchall()
    except (sqlite3.Error, ValueError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        symbol, open_, high, low, close, volume, amount, previous_close, name, list_date, *optional_values = row
        item: dict[str, Any] = {
            "symbol": str(symbol),
            "date": str(execution_date),
            "open": float(open_) if open_ is not None else np.nan,
            "high": float(high) if high is not None else np.nan,
            "low": float(low) if low is not None else np.nan,
            "close": float(close) if close is not None else np.nan,
            "volume": float(volume) if volume is not None else np.nan,
            "amount": float(amount) if amount is not None else np.nan,
            "previous_close": float(previous_close) if previous_close is not None else np.nan,
            "name": str(name or ""),
            "list_date": str(list_date or ""),
        }
        for key, value in zip(optional_cols, optional_values):
            item[key] = value
        out[str(symbol)] = item
    return out


def _execution_price(price_row: dict[str, float], side: str, account: SimulatedAccountConfig) -> float:
    mode = account.execution_price_mode
    if mode == "close":
        return _round_price_to_tick(float(price_row.get("close", np.nan)), side, account.price_tick)
    base = float(price_row.get("open", np.nan))
    if not pd.notna(base) or base <= 0:
        base = float(price_row.get("close", np.nan))
    if mode == "conservative":
        if side == "buy":
            return _round_price_to_tick(base * (1.0 + account.conservative_price_buffer), side, account.price_tick)
        return _round_price_to_tick(base * (1.0 - account.conservative_price_buffer), side, account.price_tick)
    return _round_price_to_tick(base, side, account.price_tick)


def _trade_block_reasons(price_row: dict[str, float], side: str, account: SimulatedAccountConfig) -> list[str]:
    reasons: list[str] = []
    open_price = float(price_row.get("open", np.nan))
    close_price = float(price_row.get("close", np.nan))
    volume = float(price_row.get("volume", np.nan))
    amount = float(price_row.get("amount", np.nan))
    if account.enable_suspension_check:
        if _truthy_market_flag(price_row.get("is_suspended")) or _truthy_market_flag(price_row.get("suspended")):
            reasons.append("停牌/显式状态")
        if not pd.notna(open_price) or open_price <= 0 or not pd.notna(close_price) or close_price <= 0:
            reasons.append("停牌/无有效价格")
        if pd.notna(volume) and volume <= 0:
            reasons.append("停牌/成交量为0")
        if pd.notna(amount) and amount <= 0:
            reasons.append("停牌/成交额为0")
    previous_close = float(price_row.get("previous_close", np.nan))
    check_price = close_price if account.execution_price_mode == "close" else open_price
    if (
        account.enable_limit_check
        and not _is_new_stock_no_limit(price_row, account)
        and pd.notna(check_price)
    ):
        tolerance = 0.001
        explicit_limit_up = pd.to_numeric(price_row.get("limit_up", np.nan), errors="coerce")
        explicit_limit_down = pd.to_numeric(price_row.get("limit_down", np.nan), errors="coerce")
        if side == "buy" and _truthy_market_flag(price_row.get("is_limit_up")):
            reasons.append("涨停不可买")
        if side == "sell" and _truthy_market_flag(price_row.get("is_limit_down")):
            reasons.append("跌停不可卖")
        if side == "buy" and pd.notna(explicit_limit_up) and check_price >= float(explicit_limit_up) * (1.0 - tolerance):
            reasons.append("涨停不可买")
        if side == "sell" and pd.notna(explicit_limit_down) and check_price <= float(explicit_limit_down) * (1.0 + tolerance):
            reasons.append("跌停不可卖")
        if not (pd.notna(previous_close) and previous_close > 0):
            return list(dict.fromkeys(reasons))
        limit_pct = _limit_pct(str(price_row.get("symbol", "")), account, price_row)
        limit_up = previous_close * (1.0 + limit_pct)
        limit_down = previous_close * (1.0 - limit_pct)
        if side == "buy" and check_price >= limit_up * (1.0 - tolerance):
            reasons.append("涨停不可买")
        if side == "sell" and check_price <= limit_down * (1.0 + tolerance):
            reasons.append("跌停不可卖")
    return list(dict.fromkeys(reasons))


def _order_block_reason_counts(reasons: list[str]) -> str:
    counts: dict[str, int] = {}
    for reason in reasons:
        key = str(reason or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return json.dumps(counts, ensure_ascii=False, sort_keys=True)


def _order_event_row(
    *,
    account: SimulatedAccountConfig,
    brief_date: str,
    signal_date: str,
    symbol: str,
    name: str,
    side: str,
    trade_time: str,
    price: float,
    target_weight: float,
    weight_before: float,
    weight_change: float,
    requested_shares: float,
    filled_shares: float,
    amount: float,
    reasons: list[str],
    event_type: str,
    trade_status: str,
) -> dict[str, Any]:
    return {
        "account_id": account.account_id,
        "brief_date": brief_date,
        "signal_date": signal_date,
        "symbol": symbol,
        "name": name,
        "side": side,
        "trade_time": trade_time,
        "price_mode": account.execution_price_mode,
        "price": float(price) if pd.notna(price) else np.nan,
        "target_weight": float(target_weight),
        "weight_before": float(weight_before),
        "weight_change": float(weight_change),
        "requested_shares": float(requested_shares),
        "filled_shares": float(filled_shares),
        "shares": float(filled_shares),
        "lots": float(filled_shares) / float(account.lot_size) if account.lot_size else np.nan,
        "amount": float(amount),
        "trade_status": trade_status,
        "block_reasons": "；".join(str(reason) for reason in reasons if str(reason).strip()),
        "event_type": event_type,
        "is_estimated": 1,
    }


def watchlist_to_account_frame(watchlist: pd.DataFrame, brief_date: str) -> pd.DataFrame:
    if watchlist.empty:
        return pd.DataFrame(columns=["brief_date", "signal_date", "symbol", "name", "signal_close", "target_weight", "weight_change"])
    target_weight_col = "模拟账户目标权重" if "模拟账户目标权重" in watchlist.columns else "目标权重"
    weight_change_col = "模拟账户权重变化" if "模拟账户权重变化" in watchlist.columns else "权重变化"
    required = {"股票代码", "股票名称", "收盘价", target_weight_col, weight_change_col}
    if not required.issubset(watchlist.columns):
        return pd.DataFrame(columns=["brief_date", "signal_date", "symbol", "name", "signal_close", "target_weight", "weight_change"])
    if "信号日期" in watchlist.columns:
        signal_dates = watchlist["信号日期"].astype(str)
    else:
        signal_dates = pd.Series([brief_date] * len(watchlist), index=watchlist.index)
    return pd.DataFrame(
        {
            "brief_date": brief_date,
            "signal_date": signal_dates,
            "symbol": watchlist["股票代码"].astype(str),
            "name": watchlist["股票名称"].astype(str),
            "signal_close": pd.to_numeric(watchlist["收盘价"], errors="coerce"),
            "target_weight": watchlist[target_weight_col].map(parse_percent),
            "weight_change": watchlist[weight_change_col].map(parse_percent),
        }
    )


def _has_account_weight_columns(df: pd.DataFrame) -> bool:
    target_col = "模拟账户目标权重" if "模拟账户目标权重" in df.columns else "目标权重"
    change_col = "模拟账户权重变化" if "模拟账户权重变化" in df.columns else "权重变化"
    return {"股票代码", "股票名称", "收盘价", target_col, change_col}.issubset(df.columns)


def _brief_date_from_watchlist(df: pd.DataFrame, fallback: str) -> str:
    if "盘前检查时间" not in df.columns or df.empty:
        return fallback
    values = df["盘前检查时间"].dropna().astype(str)
    for value in values:
        if re.match(r"^\d{4}-\d{2}-\d{2}", value):
            return value[:10]
    return fallback


def _is_blank_scope_value(value: Any) -> bool:
    text = str(value or "").strip()
    return not text or text.lower() == "nan"


def _brief_ledger_to_account_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"brief_date", "symbol", "name", "target_weight", "weight_change"}
    if frame.empty or not required.issubset(frame.columns):
        return pd.DataFrame(columns=["brief_date", "signal_date", "symbol", "name", "signal_close", "target_weight", "weight_change"])
    signal_dates = frame["signal_date"].astype(str) if "signal_date" in frame.columns else frame["brief_date"].astype(str)
    return pd.DataFrame(
        {
            "brief_date": frame["brief_date"].astype(str),
            "signal_date": signal_dates,
            "symbol": frame["symbol"].astype(str),
            "name": frame["name"].astype(str),
            "signal_close": pd.Series([np.nan] * len(frame), index=frame.index),
            "target_weight": pd.to_numeric(frame["target_weight"], errors="coerce").fillna(0.0),
            "weight_change": pd.to_numeric(frame["weight_change"], errors="coerce").fillna(0.0),
        }
    )


def _load_brief_ledger_frames(
    *,
    root: Path,
    current_brief_date: str,
    simulation_start_date: str,
    account_id: str,
    strategy_id: str,
) -> dict[str, pd.DataFrame]:
    path = root / DEFAULT_BRIEF_LEDGER
    if not path.exists():
        return {}
    try:
        raw = pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        return {}
    required = {"brief_date", "symbol", "name", "target_weight", "weight_change"}
    if raw.empty or not required.issubset(raw.columns):
        return {}

    frame = raw.copy()
    frame["brief_date"] = frame["brief_date"].astype(str)
    if simulation_start_date:
        frame = frame[frame["brief_date"] >= simulation_start_date].copy()
    frame = frame[frame["brief_date"] <= current_brief_date].copy()
    if frame.empty:
        return {}

    if account_id and "account_id" in frame.columns:
        account_values = frame["account_id"].astype(str)
        if account_id == "default":
            frame = frame[(account_values == account_id) | account_values.map(_is_blank_scope_value)].copy()
        else:
            frame = frame[account_values == account_id].copy()
    elif account_id and account_id != "default":
        return {}

    if strategy_id and "strategy_id" in frame.columns:
        strategy_values = frame["strategy_id"].astype(str)
        frame = frame[(strategy_values == strategy_id) | strategy_values.map(_is_blank_scope_value)].copy()
    if frame.empty:
        return {}

    frames: dict[str, pd.DataFrame] = {}
    for brief_date, day in frame.groupby("brief_date", sort=True):
        frames[str(brief_date)] = _brief_ledger_to_account_frame(day)
    return frames


def collect_watchlist_frames(
    root: Path,
    current_watchlist: pd.DataFrame,
    current_brief_date: str,
    *,
    simulation_start_date: str = "",
    account_id: str = "",
    strategy_id: str = "",
) -> dict[str, pd.DataFrame]:
    def matches_account_scope(df: pd.DataFrame) -> bool:
        if account_id and "账户ID" in df.columns:
            values = {str(value) for value in df["账户ID"].dropna().astype(str).unique()}
            if values and account_id not in values:
                return False
        elif account_id and account_id != "default":
            return False
        if strategy_id and "策略ID" in df.columns:
            values = {str(value) for value in df["策略ID"].dropna().astype(str).unique()}
            if values and strategy_id not in values:
                return False
        return True

    frames: dict[str, pd.DataFrame] = {}
    frames.update(
        _load_brief_ledger_frames(
            root=root,
            current_brief_date=current_brief_date,
            simulation_start_date=simulation_start_date,
            account_id=account_id,
            strategy_id=strategy_id,
        )
    )
    report_root = root / "reports"
    watchlist_paths: list[tuple[str, Path]] = []
    if report_root.exists():
        watchlist_paths.extend((path.parent.name, path) for path in report_root.glob("????-??-??/phase0_premarket_watchlist*.csv"))
        watchlist_paths.extend(
            (path.parents[2].name, path)
            for path in report_root.glob("runs/????-??-??/*/premarket__watchlist.csv")
        )
        for fallback_date, path in sorted(watchlist_paths):
            try:
                df = pd.read_csv(path, encoding="utf-8-sig")
            except Exception:
                continue
            brief_date = _brief_date_from_watchlist(df, fallback_date)
            if simulation_start_date and brief_date < simulation_start_date:
                continue
            if brief_date > current_brief_date:
                continue
            if not matches_account_scope(df):
                continue
            if _has_account_weight_columns(df):
                frames[brief_date] = watchlist_to_account_frame(df, brief_date)
    frames[current_brief_date] = watchlist_to_account_frame(current_watchlist, current_brief_date)
    return dict(sorted(frames.items()))


def build_account_ledger(
    *,
    root: Path,
    current_watchlist: pd.DataFrame,
    current_brief_date: str,
    account: SimulatedAccountConfig,
    local_history_cfg: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    frames = collect_watchlist_frames(
        root,
        current_watchlist,
        current_brief_date,
        simulation_start_date=account.simulation_start_date,
        account_id=account.account_id,
        strategy_id=account.strategy_id,
    )
    if not frames:
        return pd.DataFrame(), {}

    previous_positions: dict[str, tuple[float, float, str]] = {}
    previous_total_asset = float(account.initial_cash)
    previous_cash_asset = float(account.initial_cash)
    rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    order_event_rows: list[dict[str, Any]] = []
    position_rows: list[dict[str, Any]] = []
    start_date = str(account.simulation_start_date or next(iter(frames.keys())))
    available_shares: dict[str, float] = {}

    for brief_date, frame in frames.items():
        required_symbols = set(previous_positions) | set(frame["symbol"].astype(str))
        symbols = sorted(required_symbols)
        execution_prices = _load_execution_prices(
            root=root,
            local_history_cfg=local_history_cfg,
            execution_date=brief_date,
            symbols=symbols,
        )
        if required_symbols - set(execution_prices):
            continue
        for symbol, price_row in execution_prices.items():
            price_row["symbol"] = symbol

        close_prices = {
            symbol: values["close"]
            for symbol, values in execution_prices.items()
            if pd.notna(values.get("close")) and float(values["close"]) > 0
        }
        current_names = dict(zip(frame["symbol"], frame["name"], strict=False))
        target_weights = dict(zip(frame["symbol"], frame["target_weight"], strict=False))
        signal_dates = frame.get("signal_date", pd.Series(dtype=str)).dropna().astype(str)
        signal_date = ""
        for value in signal_dates:
            if value and value.lower() != "nan":
                signal_date = value
                break
        trade_time = trade_time_for_price_mode(
            brief_date=brief_date,
            signal_date=signal_date,
            price_mode=account.execution_price_mode,
        )

        pre_trade_positions: dict[str, tuple[float, float, str]] = {}
        stock_asset_before_trade = 0.0
        for symbol, (prev_shares, prev_close, name) in previous_positions.items():
            current_close = close_prices.get(symbol, np.nan)
            if pd.notna(prev_close) and float(prev_close) > 0 and pd.notna(current_close):
                shares = float(prev_shares)
                close = float(current_close)
                pre_trade_positions[symbol] = (shares, close, name)
                stock_asset_before_trade += shares * close
        total_asset_before_trade = previous_cash_asset + stock_asset_before_trade
        pnl = total_asset_before_trade - previous_total_asset
        post_trade_positions = dict(pre_trade_positions)
        cash_asset = previous_cash_asset
        estimated_trade_amount = 0.0
        estimated_volume = 0.0
        day_unfilled_orders = 0
        day_partial_fill_orders = 0
        day_block_reasons: list[str] = []

        def planned_side(symbol: str) -> str:
            shares = float(post_trade_positions.get(symbol, (0.0, np.nan, ""))[0])
            close = close_prices.get(symbol, np.nan)
            current_value = shares * float(close) if pd.notna(close) else 0.0
            target_value = float(target_weights.get(symbol, 0.0) or 0.0) * total_asset_before_trade
            return "buy" if target_value > current_value else "sell"

        symbols = sorted(
            set(pre_trade_positions) | set(target_weights),
            key=lambda symbol: (0 if planned_side(str(symbol)) == "sell" else 1, str(symbol)),
        )
        for symbol in symbols:
            current_shares = float(post_trade_positions.get(symbol, (0.0, np.nan, ""))[0])
            close_price = close_prices.get(symbol, np.nan)
            current_weight = (
                current_shares * float(close_price) / total_asset_before_trade
                if total_asset_before_trade and pd.notna(close_price)
                else 0.0
            )
            target_weight = float(target_weights.get(symbol, 0.0) or 0.0)
            weight_change = target_weight - current_weight
            price_row = execution_prices.get(symbol, {})
            side = "buy" if target_weight * total_asset_before_trade > current_shares * float(close_price) else "sell"
            price = _execution_price(price_row, side, account)
            if abs(weight_change) > 1e-12 and pd.notna(price) and float(price) > 0:
                target_value = target_weight * total_asset_before_trade
                current_value = current_shares * float(close_price)
                target_trade_amount = abs(target_value - current_value)
                raw_shares = target_trade_amount / float(price)
                requested_shares = round_lot_floor(raw_shares, account.lot_size)
                shares = requested_shares
                if shares <= 0:
                    continue
                trade_amount = shares * float(price)
                block_reasons = _trade_block_reasons(price_row, side, account)
                if account.min_trade_amount > 0 and trade_amount < account.min_trade_amount:
                    block_reasons.append("低于最小成交金额")
                if side == "sell" and account.enable_t_plus_one:
                    sellable = float(available_shares.get(symbol, 0.0))
                    shares = min(shares, sellable)
                    trade_amount = shares * float(price)
                    if sellable <= 0:
                        block_reasons.append("T+1可卖库存不足")
                volume = float(price_row.get("volume", np.nan))
                if pd.notna(volume) and account.max_participation_rate > 0:
                    market_shares = round_lot_floor(volume * account.max_participation_rate, account.lot_size)
                    shares = min(shares, market_shares)
                    trade_amount = shares * float(price)
                if block_reasons or shares <= 0:
                    reasons = block_reasons or ["成交股数为0"]
                    order_event_rows.append(
                        _order_event_row(
                            account=account,
                            brief_date=brief_date,
                            signal_date=signal_date,
                            symbol=symbol,
                            name=str(current_names.get(symbol, previous_positions.get(symbol, (0.0, np.nan, ""))[2]) or ""),
                            side=side,
                            trade_time=trade_time,
                            price=float(price),
                            target_weight=target_weight,
                            weight_before=current_weight,
                            weight_change=weight_change,
                            requested_shares=requested_shares,
                            filled_shares=0.0,
                            amount=0.0,
                            reasons=reasons,
                            event_type="unfilled",
                            trade_status="未成交",
                        )
                    )
                    day_unfilled_orders += 1
                    day_block_reasons.extend(reasons)
                    continue
                if side == "buy":
                    shares = _affordable_buy_shares(
                        cash_asset=cash_asset,
                        price=float(price),
                        requested_shares=shares,
                        account=account,
                    )
                    trade_amount = shares * float(price)
                    if shares <= 0:
                        order_event_rows.append(
                            _order_event_row(
                                account=account,
                                brief_date=brief_date,
                                signal_date=signal_date,
                                symbol=symbol,
                                name=str(current_names.get(symbol, previous_positions.get(symbol, (0.0, np.nan, ""))[2]) or ""),
                                side=side,
                                trade_time=trade_time,
                                price=float(price),
                                target_weight=target_weight,
                                weight_before=current_weight,
                                weight_change=weight_change,
                                requested_shares=requested_shares,
                                filled_shares=0.0,
                                amount=0.0,
                                reasons=["现金不足"],
                                event_type="unfilled",
                                trade_status="未成交",
                            )
                        )
                        day_unfilled_orders += 1
                        day_block_reasons.append("现金不足")
                        continue
                if side == "sell":
                    shares = min(shares, current_shares)
                    trade_amount = shares * float(price)
                    if shares <= 0:
                        order_event_rows.append(
                            _order_event_row(
                                account=account,
                                brief_date=brief_date,
                                signal_date=signal_date,
                                symbol=symbol,
                                name=str(current_names.get(symbol, previous_positions.get(symbol, (0.0, np.nan, ""))[2]) or ""),
                                side=side,
                                trade_time=trade_time,
                                price=float(price),
                                target_weight=target_weight,
                                weight_before=current_weight,
                                weight_change=weight_change,
                                requested_shares=requested_shares,
                                filled_shares=0.0,
                                amount=0.0,
                                reasons=["可卖持仓不足"],
                                event_type="unfilled",
                                trade_status="未成交",
                            )
                        )
                        day_unfilled_orders += 1
                        day_block_reasons.append("可卖持仓不足")
                        continue
                if shares < requested_shares - 1e-12:
                    day_partial_fill_orders += 1
                lots = shares / float(account.lot_size) if account.lot_size else np.nan
                trade_cost = _trade_cost(trade_amount, side, account)
                if side == "buy":
                    cash_asset -= trade_amount + trade_cost
                    new_shares = current_shares + shares
                else:
                    cash_asset += trade_amount - trade_cost
                    new_shares = current_shares - shares
                    available_shares[symbol] = max(0.0, float(available_shares.get(symbol, 0.0)) - float(shares))
                if new_shares > 1e-12:
                    post_trade_positions[symbol] = (
                        new_shares,
                        float(close_price),
                        str(current_names.get(symbol, previous_positions.get(symbol, (0.0, np.nan, ""))[2]) or ""),
                    )
                else:
                    post_trade_positions.pop(symbol, None)
                estimated_trade_amount += trade_amount
                estimated_volume += shares
                if shares < requested_shares - 1e-12:
                    order_event_rows.append(
                        _order_event_row(
                            account=account,
                            brief_date=brief_date,
                            signal_date=signal_date,
                            symbol=symbol,
                            name=str(current_names.get(symbol, previous_positions.get(symbol, (0.0, np.nan, ""))[2]) or ""),
                            side=side,
                            trade_time=trade_time,
                            price=float(price),
                            target_weight=target_weight,
                            weight_before=current_weight,
                            weight_change=weight_change,
                            requested_shares=requested_shares,
                            filled_shares=shares,
                            amount=trade_amount,
                            reasons=["成交量/参与率/现金/持仓约束导致部分成交"],
                            event_type="partial_fill",
                            trade_status="部分成交",
                        )
                    )
                trade_rows.append(
                    {
                        "account_id": account.account_id,
                        "brief_date": brief_date,
                        "signal_date": signal_date,
                        "symbol": symbol,
                        "name": str(current_names.get(symbol, previous_positions.get(symbol, (0.0, np.nan, ""))[2]) or ""),
                        "side": side,
                        "trade_time": trade_time,
                        "price_mode": account.execution_price_mode,
                        "price": float(price),
                        "amount": trade_amount,
                        "cost": trade_cost,
                        "shares": shares,
                        "lots": lots,
                        "lot_size": account.lot_size,
                        "raw_shares": raw_shares,
                        "rounding_rule": "floor_to_lot_size",
                        "trade_status": "部分成交" if shares < requested_shares - 1e-12 else "全部成交",
                        "block_reasons": "",
                        "weight_before": current_weight,
                        "weight_after": target_weight,
                        "weight_change": weight_change,
                        "is_estimated": 1,
                    }
                )

        stock_asset = sum(shares * close for shares, close, _name in post_trade_positions.values())
        total_asset = cash_asset + stock_asset
        pnl = total_asset - previous_total_asset
        actual_exposure = stock_asset / total_asset if total_asset else 0.0
        rows.append(
            {
                "account_id": account.account_id,
                "account_name": account.name,
                "brief_date": brief_date,
                "start_date": start_date,
                "total_asset": total_asset,
                "stock_asset": stock_asset,
                "cash_asset": cash_asset,
                "daily_pnl": pnl,
                "daily_return": pnl / previous_total_asset if previous_total_asset else 0.0,
                "target_exposure": actual_exposure,
                "estimated_trade_amount": estimated_trade_amount,
                "estimated_volume": estimated_volume,
                "execution_price_mode": account.execution_price_mode,
                "max_participation_rate": account.max_participation_rate,
                "unfilled_orders": int(day_unfilled_orders),
                "partial_fill_orders": int(day_partial_fill_orders),
                "block_reason_counts": _order_block_reason_counts(day_block_reasons),
                "confirmed": 1,
            }
        )

        for symbol, (position_shares, close, name) in sorted(post_trade_positions.items()):
            if position_shares > 1e-12:
                position_rows.append(
                    {
                        "account_id": account.account_id,
                        "brief_date": brief_date,
                        "symbol": symbol,
                        "name": str(name),
                        "close": float(close),
                        "target_weight": position_shares * float(close) / total_asset if total_asset else 0.0,
                        "market_value": position_shares * float(close),
                        "shares": position_shares,
                        "lots": position_shares / float(account.lot_size) if account.lot_size else np.nan,
                        "lot_size": account.lot_size,
                    }
                )

        previous_total_asset = total_asset
        previous_cash_asset = cash_asset
        previous_positions = post_trade_positions
        available_shares = {symbol: float(shares) for symbol, (shares, _close, _name) in post_trade_positions.items()}

    ledger = pd.DataFrame(rows)
    if ledger.empty:
        return ledger, {}
    account.ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(account.ledger_path, index=False, encoding="utf-8-sig")
    write_account_database(
        account=account,
        daily_assets=ledger,
        trades=pd.DataFrame(trade_rows),
        positions=pd.DataFrame(position_rows),
        order_events=pd.DataFrame(order_event_rows),
    )
    latest = ledger.iloc[-1].to_dict() if not ledger.empty else {}
    return ledger, latest


def run_signal_account_execution(
    *,
    signal_frame: pd.DataFrame,
    account: SimulatedAccountConfig,
) -> SignalAccountExecutionResult:
    """Simulate account execution from strategy target weights without writing ledgers."""
    signal = _prepare_signal_execution_frame(signal_frame)
    if signal.empty:
        return SignalAccountExecutionResult(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), _empty_signal_execution_metrics())

    previous_positions: dict[str, tuple[float, float, str]] = {}
    previous_total_asset = float(account.initial_cash)
    previous_cash_asset = float(account.initial_cash)
    daily_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    position_rows: list[dict[str, Any]] = []
    unfilled_orders_total = 0
    partial_fill_orders_total = 0
    block_reasons_total: list[str] = []
    available_shares: dict[str, float] = {}

    for date_value, frame in signal.groupby("date", sort=True):
        trade_date = str(pd.Timestamp(date_value).date())
        symbols = sorted(set(previous_positions) | set(frame["symbol"].astype(str)))
        price_map = _price_rows_from_signal_day(frame)
        for symbol in set(previous_positions) - set(price_map):
            prev_shares, prev_close, name = previous_positions[symbol]
            if pd.notna(prev_close) and prev_close > 0:
                price_map[symbol] = {
                    "symbol": symbol,
                    "open": float(prev_close),
                    "high": float(prev_close),
                    "low": float(prev_close),
                    "close": float(prev_close),
                    "volume": np.nan,
                    "amount": np.nan,
                    "previous_close": float(prev_close),
                    "name": name,
                }

        target_weights = {
            str(row["symbol"]): float(row["execution_target_weight"])
            for _, row in frame.iterrows()
            if abs(float(row["execution_target_weight"])) > 1e-12
        }
        names = {
            str(row["symbol"]): str(row.get("name", ""))
            for _, row in frame.iterrows()
        }

        pre_trade_positions: dict[str, tuple[float, float, str]] = {}
        stock_asset_before_trade = 0.0
        stale_valuation_positions = 0
        for symbol, (prev_shares, prev_close, name) in previous_positions.items():
            close = float(price_map.get(symbol, {}).get("close", np.nan))
            if pd.notna(close) and close > 0:
                pre_trade_positions[symbol] = (float(prev_shares), close, name)
                stock_asset_before_trade += float(prev_shares) * close
            else:
                stale_valuation_positions += 1
        total_asset_before_trade = previous_cash_asset + stock_asset_before_trade
        post_trade_positions = dict(pre_trade_positions)
        cash_asset = previous_cash_asset
        estimated_trade_amount = 0.0
        estimated_volume = 0.0
        day_unfilled_orders = 0
        day_partial_fill_orders = 0
        day_block_reasons: list[str] = []

        def planned_side(symbol: str) -> str:
            current_shares = float(post_trade_positions.get(symbol, (0.0, np.nan, ""))[0])
            close = float(price_map.get(symbol, {}).get("close", np.nan))
            current_value = current_shares * close if pd.notna(close) else 0.0
            target_value = float(target_weights.get(symbol, 0.0) or 0.0) * total_asset_before_trade
            return "buy" if target_value > current_value else "sell"

        ordered_symbols = sorted(
            symbols,
            key=lambda symbol: (0 if planned_side(str(symbol)) == "sell" else 1, str(symbol)),
        )
        for symbol in ordered_symbols:
            price_row = price_map.get(symbol, {})
            close_price = float(price_row.get("close", np.nan))
            if not pd.notna(close_price) or close_price <= 0 or total_asset_before_trade <= 0:
                continue
            current_shares = float(post_trade_positions.get(symbol, (0.0, np.nan, ""))[0])
            current_value = current_shares * close_price
            current_weight = current_value / total_asset_before_trade
            target_weight = float(target_weights.get(symbol, 0.0) or 0.0)
            target_value = target_weight * total_asset_before_trade
            weight_change = target_weight - current_weight
            if abs(weight_change) <= 1e-12:
                continue
            side = "buy" if target_value > current_value else "sell"
            price = _execution_price(price_row, side, account)
            if not pd.notna(price) or float(price) <= 0:
                continue

            target_trade_amount = abs(target_value - current_value)
            raw_shares = target_trade_amount / float(price)
            requested_shares = round_lot_floor(raw_shares, account.lot_size)
            shares = requested_shares
            if shares <= 0:
                continue
            trade_amount = shares * float(price)
            block_reasons = _trade_block_reasons(price_row, side, account)
            if account.min_trade_amount > 0 and trade_amount < account.min_trade_amount:
                block_reasons.append("低于最小成交金额")
            if side == "sell" and account.enable_t_plus_one:
                sellable = float(available_shares.get(symbol, 0.0))
                shares = min(shares, sellable)
                trade_amount = shares * float(price)
                if sellable <= 0:
                    block_reasons.append("T+1可卖库存不足")
            volume = float(price_row.get("volume", np.nan))
            if pd.notna(volume) and account.max_participation_rate > 0:
                market_shares = round_lot_floor(volume * account.max_participation_rate, account.lot_size)
                shares = min(shares, market_shares)
                trade_amount = shares * float(price)
            if block_reasons or shares <= 0:
                day_unfilled_orders += 1
                unfilled_orders_total += 1
                day_block_reasons.extend(block_reasons or ["成交股数为0"])
                block_reasons_total.extend(block_reasons or ["成交股数为0"])
                continue
            if side == "buy":
                shares = _affordable_buy_shares(
                    cash_asset=cash_asset,
                    price=float(price),
                    requested_shares=shares,
                    account=account,
                )
                trade_amount = shares * float(price)
                if shares <= 0:
                    day_unfilled_orders += 1
                    unfilled_orders_total += 1
                    day_block_reasons.append("现金不足")
                    block_reasons_total.append("现金不足")
                    continue
            else:
                shares = min(shares, current_shares)
                trade_amount = shares * float(price)
                if shares <= 0:
                    day_unfilled_orders += 1
                    unfilled_orders_total += 1
                    day_block_reasons.append("可卖持仓不足")
                    block_reasons_total.append("可卖持仓不足")
                    continue
            if shares < requested_shares - 1e-12:
                day_partial_fill_orders += 1
                partial_fill_orders_total += 1

            lots = shares / float(account.lot_size) if account.lot_size else np.nan
            trade_cost = _trade_cost(trade_amount, side, account)
            if side == "buy":
                cash_asset -= trade_amount + trade_cost
                new_shares = current_shares + shares
            else:
                cash_asset += trade_amount - trade_cost
                new_shares = current_shares - shares
                available_shares[symbol] = max(0.0, float(available_shares.get(symbol, 0.0)) - float(shares))
            if new_shares > 1e-12:
                post_trade_positions[symbol] = (new_shares, close_price, names.get(symbol, ""))
            else:
                post_trade_positions.pop(symbol, None)
            estimated_trade_amount += trade_amount
            estimated_volume += shares
            trade_rows.append(
                {
                    "date": trade_date,
                    "symbol": symbol,
                    "name": names.get(symbol, ""),
                    "side": side,
                    "price": float(price),
                    "amount": float(trade_amount),
                    "cost": float(trade_cost),
                    "shares": float(shares),
                    "lots": float(lots) if pd.notna(lots) else np.nan,
                    "lot_size": int(account.lot_size),
                    "raw_shares": float(raw_shares),
                    "requested_shares": float(requested_shares),
                    "is_partial": bool(shares < requested_shares - 1e-12),
                    "trade_status": "部分成交" if shares < requested_shares - 1e-12 else "全部成交",
                    "block_reasons": "",
                    "weight_before": float(current_weight),
                    "weight_after": float(target_weight),
                    "weight_change": float(weight_change),
                }
            )

        stock_asset = 0.0
        for symbol, (shares, _prev_close, name) in list(post_trade_positions.items()):
            close = float(price_map.get(symbol, {}).get("close", _prev_close))
            if pd.notna(close) and close > 0:
                post_trade_positions[symbol] = (shares, close, name)
                stock_asset += shares * close
        total_asset = cash_asset + stock_asset
        daily_return = (total_asset / previous_total_asset - 1.0) if previous_total_asset else 0.0
        exposure = stock_asset / total_asset if total_asset else 0.0
        daily_rows.append(
            {
                "date": trade_date,
                "total_asset": float(total_asset),
                "stock_asset": float(stock_asset),
                "cash_asset": float(cash_asset),
                "daily_return": float(daily_return),
                "exposure": float(exposure),
                "estimated_trade_amount": float(estimated_trade_amount),
                "estimated_volume": float(estimated_volume),
                "unfilled_orders": int(day_unfilled_orders),
                "partial_fill_orders": int(day_partial_fill_orders),
                "block_reason_counts": _order_block_reason_counts(day_block_reasons),
                "stale_valuation_positions": int(stale_valuation_positions),
            }
        )
        for symbol, (shares, close, name) in sorted(post_trade_positions.items()):
            if shares > 1e-12:
                position_rows.append(
                    {
                        "date": trade_date,
                        "symbol": symbol,
                        "name": name,
                        "close": float(close),
                        "market_value": float(shares * close),
                        "shares": float(shares),
                        "lots": float(shares / float(account.lot_size)) if account.lot_size else np.nan,
                        "target_weight": float(shares * close / total_asset) if total_asset else 0.0,
                    }
                )
        previous_total_asset = total_asset
        previous_cash_asset = cash_asset
        previous_positions = post_trade_positions
        available_shares = {symbol: float(shares) for symbol, (shares, _close, _name) in post_trade_positions.items()}

    daily = pd.DataFrame(daily_rows)
    trades = pd.DataFrame(trade_rows)
    positions = pd.DataFrame(position_rows)
    metrics = _signal_execution_metrics(daily, trades, unfilled_orders_total, partial_fill_orders_total)
    metrics["account_block_reason_counts"] = _order_block_reason_counts(block_reasons_total)
    return SignalAccountExecutionResult(daily, trades, positions, metrics)


def _prepare_signal_execution_frame(signal_frame: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "symbol", "weight_unshifted"}
    if signal_frame is None or signal_frame.empty or not required.issubset(signal_frame.columns):
        return pd.DataFrame()
    signal = signal_frame.copy()
    signal["date"] = pd.to_datetime(signal["date"], errors="coerce").dt.normalize()
    signal["symbol"] = signal["symbol"].astype(str)
    numeric_cols = [
        "weight_unshifted",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "previous_close",
        "limit_up",
        "limit_down",
        "listing_trading_days",
        "trade_days_since_listing",
        "trading_days_since_listing",
        "listing_trade_day_index",
        "listing_trade_day_number",
    ]
    for col in numeric_cols:
        if col not in signal.columns:
            signal[col] = np.nan
        signal[col] = pd.to_numeric(signal[col], errors="coerce")
    for col in ["is_suspended", "suspended", "is_limit_up", "is_limit_down"]:
        if col not in signal.columns:
            signal[col] = False
    if "name" not in signal.columns:
        signal["name"] = ""
    signal = signal.dropna(subset=["date", "symbol"]).sort_values(["symbol", "date"]).reset_index(drop=True)
    computed_previous_close = signal.groupby("symbol")["close"].shift(1)
    signal["previous_close"] = signal["previous_close"].where(signal["previous_close"].notna(), computed_previous_close)
    # Strategy targets are formed after the signal date; account execution uses the next trading row.
    signal["execution_target_weight"] = signal.groupby("symbol")["weight_unshifted"].shift(1).fillna(0.0)
    return signal.sort_values(["date", "symbol"]).reset_index(drop=True)


def _price_rows_from_signal_day(frame: pd.DataFrame) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for _, row in frame.iterrows():
        symbol = str(row["symbol"])
        close = float(row.get("close", np.nan))
        open_price = float(row.get("open", np.nan))
        if not pd.notna(open_price) or open_price <= 0:
            open_price = close
        out[symbol] = {
            "symbol": symbol,
            "date": str(row.get("date", "")),
            "open": open_price,
            "high": float(row.get("high", np.nan)),
            "low": float(row.get("low", np.nan)),
            "close": close,
            "volume": float(row.get("volume", np.nan)),
            "amount": float(row.get("amount", np.nan)),
            "previous_close": float(row.get("previous_close", np.nan)),
            "name": str(row.get("name", "")),
            "list_date": str(row.get("list_date", "")),
            "limit_up": float(row.get("limit_up", np.nan)),
            "limit_down": float(row.get("limit_down", np.nan)),
            "is_limit_up": row.get("is_limit_up", False),
            "is_limit_down": row.get("is_limit_down", False),
            "is_suspended": row.get("is_suspended", False),
            "suspended": row.get("suspended", False),
            "listing_trading_days": float(row.get("listing_trading_days", np.nan)),
            "trade_days_since_listing": float(row.get("trade_days_since_listing", np.nan)),
            "trading_days_since_listing": float(row.get("trading_days_since_listing", np.nan)),
            "listing_trade_day_index": float(row.get("listing_trade_day_index", np.nan)),
            "listing_trade_day_number": float(row.get("listing_trade_day_number", np.nan)),
        }
    return out


def _signal_execution_metrics(
    daily: pd.DataFrame,
    trades: pd.DataFrame,
    unfilled_orders_total: int,
    partial_fill_orders_total: int,
) -> dict[str, Any]:
    if daily.empty:
        return _empty_signal_execution_metrics()
    returns = pd.Series(pd.to_numeric(daily["daily_return"], errors="coerce").fillna(0.0).values, index=pd.to_datetime(daily["date"]))
    exposure = pd.Series(pd.to_numeric(daily["exposure"], errors="coerce").fillna(0.0).values, index=pd.to_datetime(daily["date"]))
    total_asset = pd.to_numeric(daily["total_asset"], errors="coerce").dropna()
    ann = _annualized_return_from_returns(returns)
    sharpe = _sharpe_from_returns(returns)
    max_drawdown = _max_drawdown_from_returns(returns)
    executed_order_count = int(len(trades))
    total_orders = executed_order_count + int(unfilled_orders_total)
    return {
        "account_execution_enabled": True,
        "account_annualized_return": ann,
        "account_sharpe": sharpe,
        "account_max_drawdown": max_drawdown,
        "account_final_assets": float(total_asset.iloc[-1]) if len(total_asset) else 0.0,
        "account_min_cash_assets": float(pd.to_numeric(daily["cash_asset"], errors="coerce").min()),
        "account_exposure_mean": float(exposure.mean()) if len(exposure) else 0.0,
        "account_executed_order_count": executed_order_count,
        "account_unfilled_order_count": int(unfilled_orders_total),
        "account_partial_fill_order_count": int(partial_fill_orders_total),
        "account_unfilled_or_partial_order_ratio": float((unfilled_orders_total + partial_fill_orders_total) / total_orders) if total_orders else 0.0,
        "account_partial_fill_order_ratio": float(partial_fill_orders_total / total_orders) if total_orders else 0.0,
        "account_stale_valuation_positions_total": int(pd.to_numeric(daily.get("stale_valuation_positions", 0), errors="coerce").fillna(0).sum()),
        "account_lot_size": int(trades["lot_size"].dropna().iloc[0]) if not trades.empty and "lot_size" in trades.columns else 0,
    }


def _annualized_return_from_returns(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    cumulative = float((1.0 + returns.fillna(0.0)).prod())
    if cumulative <= 0:
        return -1.0
    return float(cumulative ** (252.0 / len(returns)) - 1.0)


def _sharpe_from_returns(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    std = float(returns.std())
    if std == 0 or np.isnan(std):
        return 0.0
    return float(returns.mean() / std * np.sqrt(252))


def _max_drawdown_from_returns(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    equity = (1.0 + returns.fillna(0.0)).cumprod()
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    return float(drawdown.min())


def _empty_signal_execution_metrics() -> dict[str, Any]:
    return {
        "account_execution_enabled": False,
        "account_annualized_return": 0.0,
        "account_sharpe": 0.0,
        "account_max_drawdown": 0.0,
        "account_final_assets": 0.0,
        "account_min_cash_assets": 0.0,
        "account_exposure_mean": 0.0,
        "account_executed_order_count": 0,
        "account_unfilled_order_count": 0,
        "account_partial_fill_order_count": 0,
        "account_unfilled_or_partial_order_ratio": 0.0,
        "account_partial_fill_order_ratio": 0.0,
        "account_block_reason_counts": "{}",
        "account_stale_valuation_positions_total": 0,
        "account_lot_size": 0,
    }


def ensure_account_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS simulated_accounts (
            account_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            initial_cash REAL NOT NULL,
            strategy_id TEXT,
            simulation_start_date TEXT,
            enabled INTEGER NOT NULL,
            execution_price_mode TEXT NOT NULL,
            max_participation_rate REAL NOT NULL,
            lot_size INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS account_daily_assets (
            account_id TEXT NOT NULL,
            brief_date TEXT NOT NULL,
            start_date TEXT NOT NULL,
            total_asset REAL NOT NULL,
            stock_asset REAL NOT NULL,
            cash_asset REAL NOT NULL,
            daily_pnl REAL NOT NULL,
            daily_return REAL NOT NULL,
            target_exposure REAL NOT NULL,
            estimated_trade_amount REAL NOT NULL,
            estimated_volume REAL,
            execution_price_mode TEXT NOT NULL,
            max_participation_rate REAL NOT NULL,
            unfilled_orders INTEGER NOT NULL DEFAULT 0,
            partial_fill_orders INTEGER NOT NULL DEFAULT 0,
            block_reason_counts TEXT,
            PRIMARY KEY (account_id, brief_date)
        );

        CREATE TABLE IF NOT EXISTS account_trades (
            account_id TEXT NOT NULL,
            brief_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT,
            side TEXT NOT NULL,
            signal_date TEXT,
            trade_time TEXT NOT NULL,
            price_mode TEXT NOT NULL,
            price REAL NOT NULL,
            amount REAL NOT NULL,
            cost REAL DEFAULT 0,
            shares REAL NOT NULL,
            lots REAL NOT NULL,
            lot_size INTEGER NOT NULL,
            raw_shares REAL,
            rounding_rule TEXT,
            trade_status TEXT,
            block_reasons TEXT,
            weight_before REAL NOT NULL,
            weight_after REAL NOT NULL,
            weight_change REAL NOT NULL,
            is_estimated INTEGER NOT NULL,
            PRIMARY KEY (account_id, brief_date, symbol, side)
        );

        CREATE TABLE IF NOT EXISTS account_positions (
            account_id TEXT NOT NULL,
            brief_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT,
            close REAL NOT NULL,
            target_weight REAL NOT NULL,
            market_value REAL NOT NULL,
            shares REAL NOT NULL,
            lots REAL NOT NULL,
            lot_size INTEGER NOT NULL,
            PRIMARY KEY (account_id, brief_date, symbol)
        );

        CREATE TABLE IF NOT EXISTS account_order_events (
            account_id TEXT NOT NULL,
            brief_date TEXT NOT NULL,
            signal_date TEXT,
            symbol TEXT NOT NULL,
            name TEXT,
            side TEXT NOT NULL,
            trade_time TEXT NOT NULL,
            price_mode TEXT NOT NULL,
            price REAL,
            target_weight REAL NOT NULL,
            weight_before REAL NOT NULL,
            weight_change REAL NOT NULL,
            requested_shares REAL NOT NULL,
            filled_shares REAL NOT NULL,
            shares REAL NOT NULL,
            lots REAL,
            amount REAL NOT NULL,
            trade_status TEXT NOT NULL,
            block_reasons TEXT,
            event_type TEXT NOT NULL,
            is_estimated INTEGER NOT NULL,
            PRIMARY KEY (account_id, brief_date, symbol, side, event_type)
        );
        """
    )
    existing_trade_cols = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info(account_trades)").fetchall()
    }
    existing_daily_cols = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info(account_daily_assets)").fetchall()
    }
    existing_account_cols = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info(simulated_accounts)").fetchall()
    }
    if "simulation_start_date" not in existing_account_cols:
        conn.execute("ALTER TABLE simulated_accounts ADD COLUMN simulation_start_date TEXT")
    if "strategy_id" not in existing_account_cols:
        conn.execute("ALTER TABLE simulated_accounts ADD COLUMN strategy_id TEXT")
    if "raw_shares" not in existing_trade_cols:
        conn.execute("ALTER TABLE account_trades ADD COLUMN raw_shares REAL")
    if "rounding_rule" not in existing_trade_cols:
        conn.execute("ALTER TABLE account_trades ADD COLUMN rounding_rule TEXT")
    if "trade_time" not in existing_trade_cols:
        conn.execute("ALTER TABLE account_trades ADD COLUMN trade_time TEXT")
    if "signal_date" not in existing_trade_cols:
        conn.execute("ALTER TABLE account_trades ADD COLUMN signal_date TEXT")
    if "cost" not in existing_trade_cols:
        conn.execute("ALTER TABLE account_trades ADD COLUMN cost REAL DEFAULT 0")
    if "trade_status" not in existing_trade_cols:
        conn.execute("ALTER TABLE account_trades ADD COLUMN trade_status TEXT")
    if "block_reasons" not in existing_trade_cols:
        conn.execute("ALTER TABLE account_trades ADD COLUMN block_reasons TEXT")
    if "unfilled_orders" not in existing_daily_cols:
        conn.execute("ALTER TABLE account_daily_assets ADD COLUMN unfilled_orders INTEGER NOT NULL DEFAULT 0")
    if "partial_fill_orders" not in existing_daily_cols:
        conn.execute("ALTER TABLE account_daily_assets ADD COLUMN partial_fill_orders INTEGER NOT NULL DEFAULT 0")
    if "block_reason_counts" not in existing_daily_cols:
        conn.execute("ALTER TABLE account_daily_assets ADD COLUMN block_reason_counts TEXT")


def write_account_database(
    *,
    account: SimulatedAccountConfig,
    daily_assets: pd.DataFrame,
    trades: pd.DataFrame,
    positions: pd.DataFrame,
    order_events: pd.DataFrame | None = None,
) -> None:
    account.database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(account.database_path) as conn:
        ensure_account_tables(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO simulated_accounts
            (account_id, name, initial_cash, strategy_id, simulation_start_date, enabled, execution_price_mode, max_participation_rate, lot_size, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                account.account_id,
                account.name,
                account.initial_cash,
                account.strategy_id,
                account.simulation_start_date,
                1 if account.enabled else 0,
                account.execution_price_mode,
                account.max_participation_rate,
                account.lot_size,
            ),
        )
        conn.execute("DELETE FROM account_daily_assets WHERE account_id = ?", (account.account_id,))
        conn.execute("DELETE FROM account_trades WHERE account_id = ?", (account.account_id,))
        conn.execute("DELETE FROM account_positions WHERE account_id = ?", (account.account_id,))
        conn.execute("DELETE FROM account_order_events WHERE account_id = ?", (account.account_id,))
        if not daily_assets.empty:
            conn.executemany(
                """
                INSERT OR REPLACE INTO account_daily_assets
                (account_id, brief_date, start_date, total_asset, stock_asset, cash_asset, daily_pnl, daily_return,
                 target_exposure, estimated_trade_amount, estimated_volume, execution_price_mode, max_participation_rate,
                 unfilled_orders, partial_fill_orders, block_reason_counts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                daily_assets[
                    [
                        "account_id",
                        "brief_date",
                        "start_date",
                        "total_asset",
                        "stock_asset",
                        "cash_asset",
                        "daily_pnl",
                        "daily_return",
                        "target_exposure",
                        "estimated_trade_amount",
                        "estimated_volume",
                        "execution_price_mode",
                        "max_participation_rate",
                        "unfilled_orders",
                        "partial_fill_orders",
                        "block_reason_counts",
                    ]
                ].itertuples(index=False, name=None),
            )
        if order_events is not None and not order_events.empty:
            conn.executemany(
                """
                INSERT OR REPLACE INTO account_order_events
                (account_id, brief_date, signal_date, symbol, name, side, trade_time, price_mode, price,
                 target_weight, weight_before, weight_change, requested_shares, filled_shares, shares, lots,
                 amount, trade_status, block_reasons, event_type, is_estimated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                order_events[
                    [
                        "account_id",
                        "brief_date",
                        "signal_date",
                        "symbol",
                        "name",
                        "side",
                        "trade_time",
                        "price_mode",
                        "price",
                        "target_weight",
                        "weight_before",
                        "weight_change",
                        "requested_shares",
                        "filled_shares",
                        "shares",
                        "lots",
                        "amount",
                        "trade_status",
                        "block_reasons",
                        "event_type",
                        "is_estimated",
                    ]
                ].itertuples(index=False, name=None),
            )
        if not trades.empty:
            conn.executemany(
                """
                INSERT OR REPLACE INTO account_trades
                (account_id, brief_date, signal_date, symbol, name, side, trade_time, price_mode, price, amount, cost, shares,
                 lots, lot_size, raw_shares, rounding_rule, trade_status, block_reasons, weight_before, weight_after, weight_change, is_estimated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                trades[
                    [
                        "account_id",
                        "brief_date",
                        "signal_date",
                        "symbol",
                        "name",
                        "side",
                        "trade_time",
                        "price_mode",
                        "price",
                        "amount",
                        "cost",
                        "shares",
                        "lots",
                        "lot_size",
                        "raw_shares",
                        "rounding_rule",
                        "trade_status",
                        "block_reasons",
                        "weight_before",
                        "weight_after",
                        "weight_change",
                        "is_estimated",
                    ]
                ].itertuples(index=False, name=None),
            )
        if not positions.empty:
            conn.executemany(
                """
                INSERT OR REPLACE INTO account_positions
                (account_id, brief_date, symbol, name, close, target_weight, market_value, shares, lots, lot_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                positions[
                    [
                        "account_id",
                        "brief_date",
                        "symbol",
                        "name",
                        "close",
                        "target_weight",
                        "market_value",
                        "shares",
                        "lots",
                        "lot_size",
                    ]
                ].itertuples(index=False, name=None),
            )
