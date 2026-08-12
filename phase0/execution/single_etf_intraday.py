from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any

import numpy as np
import pandas as pd

from phase0.execution.accounts import (
    SignalAccountExecutionResult,
    SimulatedAccountConfig,
    affordable_buy_shares,
    build_signal_execution_metrics,
    calculate_trade_cost,
    round_price_to_tick,
)


@dataclass(frozen=True)
class SingleEtfIntradayPolicy:
    """Executable rules for mapping a completed US signal to one A-share ETF.

    The input signal frame is already aligned to the first A-share trading
    session strictly after the US session.  This class defines only execution;
    it does not fetch or forward-fill market signals.
    """

    target_symbol: str
    return_symbol: str
    volatility_symbol: str
    return_threshold: float
    volatility_threshold: float
    strong_signal_threshold: float
    weak_limit_discount: float = 0.01
    weak_unfilled_action: str = "cancel"
    holding_sessions: int = 1
    trailing_drawdown: float = 0.02
    fallback_time: str = "14:55"
    position_size: float = 1.0
    strong_position_size: float | None = None
    weak_position_size: float | None = None

    def __post_init__(self) -> None:
        if not self.target_symbol:
            raise ValueError("target_symbol is required")
        if self.weak_unfilled_action != "cancel":
            raise ValueError("executable mode only supports weak_unfilled_action='cancel'")
        if self.holding_sessions < 1:
            raise ValueError("holding_sessions must be at least 1")
        if not 0.0 < self.trailing_drawdown < 1.0:
            raise ValueError("trailing_drawdown must be between 0 and 1")
        if not 0.0 <= self.weak_limit_discount < 1.0:
            raise ValueError("weak_limit_discount must be in [0, 1)")
        if not 0.0 < self.position_size <= 1.0:
            raise ValueError("position_size must be in (0, 1]")
        for name, value in (
            ("strong_position_size", self.strong_position_size),
            ("weak_position_size", self.weak_position_size),
        ):
            if value is not None and not 0.0 < float(value) <= 1.0:
                raise ValueError(f"{name} must be in (0, 1]")
        try:
            pd.Timestamp(f"2000-01-01 {self.fallback_time}")
        except ValueError as exc:
            raise ValueError("fallback_time must be HH:MM") from exc

    @classmethod
    def from_metadata(cls, metadata: dict[str, Any]) -> "SingleEtfIntradayPolicy":
        raw = metadata.get("account_execution_policy", metadata)
        return cls(
            target_symbol=str(raw["target_symbol"]),
            return_symbol=str(raw.get("return_symbol", "")),
            volatility_symbol=str(raw.get("volatility_symbol", "")),
            return_threshold=float(raw["return_threshold"]),
            volatility_threshold=float(raw["volatility_threshold"]),
            strong_signal_threshold=float(raw["strong_signal_threshold"]),
            weak_limit_discount=float(raw.get("weak_limit_discount", 0.01)),
            weak_unfilled_action=str(raw.get("weak_unfilled_action", "cancel")),
            holding_sessions=int(raw.get("holding_sessions", 1)),
            trailing_drawdown=float(raw.get("trailing_drawdown", 0.02)),
            fallback_time=str(raw.get("fallback_time", "14:55")),
            position_size=float(raw.get("position_size", 1.0)),
            strong_position_size=(
                float(raw["strong_position_size"])
                if raw.get("strong_position_size") is not None
                else None
            ),
            weak_position_size=(
                float(raw["weak_position_size"])
                if raw.get("weak_position_size") is not None
                else None
            ),
        )

    def position_size_for(self, signal_return: float) -> float:
        """Return the configured capital fraction for this signal tier."""
        if float(signal_return) > self.strong_signal_threshold:
            return float(self.strong_position_size or self.position_size)
        return float(self.weak_position_size or self.position_size)


@dataclass(frozen=True)
class EntryDecision:
    status: str
    order_type: str
    price: float | None
    time: pd.Timestamp | None
    reason: str
    limit_price: float | None = None


@dataclass(frozen=True)
class ExitDecision:
    status: str
    price: float | None
    time: pd.Timestamp | None
    reason: str
    running_high: float


def _normalize_intraday_bars(bars: pd.DataFrame) -> pd.DataFrame:
    required = {"time", "open", "high", "low", "close"}
    if bars is None or bars.empty or not required.issubset(bars.columns):
        return pd.DataFrame(columns=sorted(required))
    out = bars.copy()
    out["time"] = pd.to_datetime(out["time"], errors="coerce")
    for col in ["open", "high", "low", "close"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["time", "open", "high", "low", "close"])
    out = out[(out[["open", "high", "low", "close"]] > 0).all(axis=1)]
    return out.sort_values("time").drop_duplicates("time", keep="last").reset_index(drop=True)


def _bars_for_date(bars: pd.DataFrame, session_date: pd.Timestamp) -> pd.DataFrame:
    if bars.empty:
        return bars.copy()
    normalized = pd.Timestamp(session_date).normalize()
    return bars[bars["time"].dt.normalize() == normalized].copy()


def evaluate_entry(
    *,
    session_open: float,
    session_bars: pd.DataFrame,
    signal_return: float,
    policy: SingleEtfIntradayPolicy,
    price_tick: float,
) -> EntryDecision:
    """Evaluate one entry without using information from a later session."""
    open_price = float(session_open)
    if not np.isfinite(open_price) or open_price <= 0:
        return EntryDecision("data_missing", "none", None, None, "missing_session_open")

    bars = _normalize_intraday_bars(session_bars)
    if float(signal_return) > policy.strong_signal_threshold:
        price = round_price_to_tick(open_price, "buy", price_tick)
        trade_time = bars.iloc[0]["time"] if not bars.empty else None
        return EntryDecision("filled", "market_open", price, trade_time, "strong_signal")

    # A buy limit is a maximum acceptable price, so an off-tick target must
    # be rounded down.  Rounding it up would weaken the configured discount.
    limit_price = round_price_to_tick(
        open_price * (1.0 - policy.weak_limit_discount),
        "sell",
        price_tick,
    )
    if bars.empty:
        return EntryDecision(
            "data_missing",
            "limit",
            None,
            None,
            "missing_entry_intraday_bars",
            limit_price,
        )
    touched = bars[pd.to_numeric(bars["low"], errors="coerce") <= limit_price]
    if touched.empty:
        return EntryDecision("cancelled", "limit", None, None, "limit_not_touched", limit_price)
    bar = touched.iloc[0]
    # A buy limit receives the opening price when the bar gaps below the limit;
    # otherwise it is conservatively filled at the limit itself.
    base_price = min(float(bar["open"]), limit_price)
    fill_price = round_price_to_tick(base_price, "buy", price_tick)
    return EntryDecision("filled", "limit", fill_price, pd.Timestamp(bar["time"]), "limit_touched", limit_price)


def evaluate_trailing_exit(
    *,
    bars: pd.DataFrame,
    entry_price: float,
    running_high: float,
    policy: SingleEtfIntradayPolicy,
    price_tick: float,
    slippage: float = 0.0,
) -> ExitDecision:
    """Evaluate the T+1 exit using a conservative completed-bar rule.

    A bar may trigger a stop derived from highs observed before that bar.  Its
    own high is added to ``running_high`` only after its low has been checked,
    so OHLC data never assumes that the high occurred before the low.
    Slippage is accounted for by the account cost model rather than changing
    the reported market fill price.
    """
    _ = slippage
    day_bars = _normalize_intraday_bars(bars)
    high_watermark = max(float(entry_price), float(running_high))
    if day_bars.empty:
        return ExitDecision("data_missing", None, None, "missing_exit_intraday_bars", high_watermark)

    fallback = policy.fallback_time
    for _, bar in day_bars.iterrows():
        bar_time = pd.Timestamp(bar["time"])
        stop_price = round_price_to_tick(
            high_watermark * (1.0 - policy.trailing_drawdown),
            "sell",
            price_tick,
        )
        if float(bar["open"]) <= stop_price:
            fill_price = round_price_to_tick(float(bar["open"]), "sell", price_tick)
            return ExitDecision("filled", fill_price, bar_time, "trailing_stop_gap", high_watermark)
        if float(bar["low"]) <= stop_price:
            return ExitDecision("filled", stop_price, bar_time, "trailing_stop", high_watermark)

        high_watermark = max(high_watermark, float(bar["high"]))
        if bar_time.strftime("%H:%M") == fallback:
            fill_price = round_price_to_tick(float(bar["close"]), "sell", price_tick)
            return ExitDecision("filled", fill_price, bar_time, "scheduled_exit", high_watermark)

    return ExitDecision("data_missing", None, None, "missing_fallback_bar", high_watermark)


def load_single_etf_intraday_bars(
    *,
    database_path: Path,
    symbol: str,
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
) -> pd.DataFrame:
    start = pd.Timestamp(start_date).normalize()
    end_exclusive = pd.Timestamp(end_date).normalize() + pd.Timedelta(days=1)
    if not Path(database_path).exists():
        return pd.DataFrame(columns=["time", "open", "high", "low", "close"])
    with sqlite3.connect(database_path) as conn:
        frame = pd.read_sql_query(
            "SELECT time, open, high, low, close, volume, amount "
            "FROM market_etf_5min_bars "
            "WHERE symbol = ? AND time >= ? AND time < ? ORDER BY time",
            conn,
            params=[symbol, start.strftime("%Y-%m-%d"), end_exclusive.strftime("%Y-%m-%d")],
        )
    return _normalize_intraday_bars(frame)


def _trade_row(
    *,
    trade_date: pd.Timestamp,
    signal_date: pd.Timestamp,
    symbol: str,
    side: str,
    price: float,
    shares: float,
    cost: float,
    account: SimulatedAccountConfig,
    trade_time: pd.Timestamp | None,
    order_type: str,
    reason: str,
) -> dict[str, Any]:
    amount = float(price) * float(shares)
    return {
        "date": pd.Timestamp(trade_date).date().isoformat(),
        "signal_date": pd.Timestamp(signal_date).date().isoformat(),
        "symbol": symbol,
        "name": symbol,
        "side": side,
        "trade_time": trade_time.isoformat(sep=" ") if trade_time is not None else f"{pd.Timestamp(trade_date).date()} 09:30:00",
        "order_type": order_type,
        "reason": reason,
        "price": float(price),
        "amount": amount,
        "cost": float(cost),
        "shares": float(shares),
        "lots": float(shares / account.lot_size) if account.lot_size else np.nan,
        "lot_size": int(account.lot_size),
        "raw_shares": float(shares),
        "requested_shares": float(shares),
        "is_partial": False,
        "trade_status": "全部成交",
        "block_reasons": "",
        "weight_before": 0.0 if side == "buy" else 1.0,
        "weight_after": 1.0 if side == "buy" else 0.0,
        "weight_change": 1.0 if side == "buy" else -1.0,
    }


def run_single_etf_intraday_account_execution(
    *,
    signal_frame: pd.DataFrame,
    account: SimulatedAccountConfig,
    policy: SingleEtfIntradayPolicy,
    intraday_bars: pd.DataFrame | None = None,
    live_session: bool = False,
    session_complete: bool = True,
) -> SignalAccountExecutionResult:
    """Replay an executable single-ETF strategy without mutating account state."""
    required = {"date", "symbol", "open", "close", "sox_ret", "vix_close"}
    if signal_frame is None or signal_frame.empty or not required.issubset(signal_frame.columns):
        metrics = build_signal_execution_metrics(pd.DataFrame(), pd.DataFrame(), 0, 0)
        metrics.update({"account_execution_complete": False, "account_execution_error": "missing_signal_columns"})
        return SignalAccountExecutionResult(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), metrics)

    daily = signal_frame.copy()
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    daily = daily[daily["symbol"].astype(str) == policy.target_symbol].copy()
    for col in ["open", "close", "sox_ret", "vix_close"]:
        daily[col] = pd.to_numeric(daily[col], errors="coerce")
    daily = daily.dropna(subset=["date", "open", "close"]).sort_values("date")
    daily = daily.drop_duplicates("date", keep="last").reset_index(drop=True)
    if daily.empty:
        metrics = build_signal_execution_metrics(pd.DataFrame(), pd.DataFrame(), 0, 0)
        metrics.update({"account_execution_complete": False, "account_execution_error": "empty_target_history"})
        return SignalAccountExecutionResult(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), metrics)

    bars = _normalize_intraday_bars(intraday_bars) if intraday_bars is not None else load_single_etf_intraday_bars(
        database_path=account.intraday_data_path or Path("data/etf_history.sqlite"),
        symbol=policy.target_symbol,
        start_date=daily["date"].min(),
        end_date=daily["date"].max(),
    )

    cash = float(account.initial_cash)
    shares = 0.0
    entry_price = 0.0
    running_high = 0.0
    signal_date = pd.NaT
    planned_exit_date = pd.NaT
    active_position_size = 0.0
    blocked_by_missing_exit = False
    previous_total_asset = float(account.initial_cash)
    trade_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    position_rows: list[dict[str, Any]] = []
    order_event_rows: list[dict[str, Any]] = []
    unfilled_orders = 0
    missing_days: set[str] = set()
    pending_exit_count = 0
    dates = daily["date"].tolist()
    raw_signal_mask = (
        pd.to_numeric(daily["sox_ret"], errors="coerce") > policy.return_threshold
    ) & (
        pd.to_numeric(daily["vix_close"], errors="coerce") < policy.volatility_threshold
    )
    raw_signal_count = int(raw_signal_mask.fillna(False).sum())

    for index, row in daily.iterrows():
        session_date = pd.Timestamp(row["date"])
        day_bars = _bars_for_date(bars, session_date)
        held_at_open = shares > 0
        held_position_size = active_position_size if held_at_open else 0.0
        exited_today = False
        exit_time: pd.Timestamp | None = None
        day_trade_amount = 0.0
        day_trade_volume = 0.0

        if shares > 0 and not blocked_by_missing_exit and pd.notna(planned_exit_date) and session_date >= planned_exit_date:
            exit_decision = evaluate_trailing_exit(
                bars=day_bars,
                entry_price=entry_price,
                running_high=running_high,
                policy=policy,
                price_tick=account.price_tick,
                slippage=account.slippage,
            )
            running_high = exit_decision.running_high
            if exit_decision.status == "filled" and exit_decision.price is not None:
                amount = shares * exit_decision.price
                cost = calculate_trade_cost(amount, "sell", account)
                cash += amount - cost
                trade_rows.append(
                    _trade_row(
                        trade_date=session_date,
                        signal_date=pd.Timestamp(signal_date),
                        symbol=policy.target_symbol,
                        side="sell",
                        price=exit_decision.price,
                        shares=shares,
                        cost=cost,
                        account=account,
                        trade_time=exit_decision.time,
                        order_type="trailing_stop" if exit_decision.reason.startswith("trailing_stop") else "scheduled_exit",
                        reason=exit_decision.reason,
                    )
                )
                day_trade_amount += amount
                day_trade_volume += shares
                shares = 0.0
                entry_price = 0.0
                running_high = 0.0
                active_position_size = 0.0
                planned_exit_date = pd.NaT
                exited_today = True
                exit_time = pd.Timestamp(exit_decision.time) if exit_decision.time is not None else None
            else:
                missing_days.add(session_date.date().isoformat())
                blocked_by_missing_exit = True
                pending_exit_count = 1

        signal_return = float(row["sox_ret"]) if pd.notna(row["sox_ret"]) else np.nan
        volatility = float(row["vix_close"]) if pd.notna(row["vix_close"]) else np.nan
        has_signal = (
            np.isfinite(signal_return)
            and np.isfinite(volatility)
            and signal_return > policy.return_threshold
            and volatility < policy.volatility_threshold
        )
        if shares <= 0 and not blocked_by_missing_exit and has_signal:
            exit_index = index + policy.holding_sessions
            next_exit_date = pd.Timestamp(dates[exit_index]) if exit_index < len(dates) else pd.NaT
            entry_bars = day_bars
            entry_open = float(row["open"])
            if exited_today:
                entry_bars = _normalize_intraday_bars(day_bars)
                if exit_time is not None:
                    entry_bars = entry_bars[entry_bars["time"] > exit_time].copy()
                if entry_bars.empty:
                    order_type = "market" if signal_return > policy.strong_signal_threshold else "limit"
                    entry = EntryDecision(
                        "cancelled",
                        order_type,
                        None,
                        None,
                        "no_post_exit_bar",
                    )
                else:
                    if signal_return > policy.strong_signal_threshold:
                        entry_open = float(entry_bars.iloc[0]["open"])
                    entry = evaluate_entry(
                        session_open=entry_open,
                        session_bars=entry_bars,
                        signal_return=signal_return,
                        policy=policy,
                        price_tick=account.price_tick,
                    )
            else:
                entry = evaluate_entry(
                    session_open=entry_open,
                    session_bars=entry_bars,
                    signal_return=signal_return,
                    policy=policy,
                    price_tick=account.price_tick,
                )
            is_current_live_session = live_session and session_date == pd.Timestamp(daily["date"].max())
            if entry.status == "cancelled" and is_current_live_session and not session_complete:
                entry = EntryDecision(
                    "pending",
                    entry.order_type,
                    None,
                    None,
                    "limit_waiting_for_session_close",
                    entry.limit_price,
                )

            entry_position_size = policy.position_size_for(signal_return)
            entry_budget = cash * entry_position_size
            if exited_today:
                entry_budget = min(cash, previous_total_asset * entry_position_size)
            requested_price = entry.limit_price if entry.order_type == "limit" else entry_open
            requested_shares = (
                affordable_buy_shares(
                    cash_asset=entry_budget,
                    price=float(requested_price),
                    requested_shares=1e18,
                    account=account,
                )
                if requested_price is not None and float(requested_price) > 0
                else 0.0
            )
            if entry.status == "filled" and entry.price is not None:
                bought_shares = affordable_buy_shares(
                    cash_asset=entry_budget,
                    price=entry.price,
                    requested_shares=1e18,
                    account=account,
                )
                if bought_shares > 0:
                    amount = bought_shares * entry.price
                    cost = calculate_trade_cost(amount, "buy", account)
                    cash -= amount + cost
                    shares = bought_shares
                    entry_price = entry.price
                    running_high = entry.price
                    active_position_size = entry_position_size
                    signal_date = pd.Timestamp(row.get("signal_us_date", session_date))
                    planned_exit_date = next_exit_date
                    if pd.isna(planned_exit_date):
                        pending_exit_count = 1
                    trade_rows.append(
                        _trade_row(
                            trade_date=session_date,
                            signal_date=pd.Timestamp(signal_date),
                            symbol=policy.target_symbol,
                            side="buy",
                            price=entry.price,
                            shares=shares,
                            cost=cost,
                            account=account,
                            trade_time=entry.time,
                            order_type=entry.order_type,
                            reason=entry.reason,
                        )
                    )
                    day_trade_amount += amount
                    day_trade_volume += shares
                    order_event_rows.append(
                        {
                            "date": session_date.date().isoformat(),
                            "signal_date": pd.Timestamp(signal_date).date().isoformat(),
                            "symbol": policy.target_symbol,
                            "side": "buy",
                            "order_type": entry.order_type,
                            "status": "filled",
                            "trade_time": entry.time.isoformat(sep=" ") if entry.time is not None else "",
                            "reference_open_price": float(entry_open),
                            "limit_price": entry.limit_price,
                            "requested_shares": float(requested_shares),
                            "filled_shares": float(bought_shares),
                            "price": float(entry.price),
                            "reason": entry.reason,
                        }
                    )
                else:
                    unfilled_orders += 1
                    order_event_rows.append(
                        {
                            "date": session_date.date().isoformat(),
                            "signal_date": pd.Timestamp(row.get("signal_us_date", session_date)).date().isoformat(),
                            "symbol": policy.target_symbol,
                            "side": "buy",
                            "order_type": entry.order_type,
                            "status": "cancelled",
                            "trade_time": "",
                            "reference_open_price": float(entry_open),
                            "limit_price": entry.limit_price,
                            "requested_shares": float(requested_shares),
                            "filled_shares": 0.0,
                            "price": None,
                            "reason": "insufficient_cash_after_cost",
                        }
                    )
            elif entry.status in {"cancelled", "pending"}:
                event_status = "pending" if entry.status == "pending" else "cancelled"
                if event_status == "cancelled":
                    unfilled_orders += 1
                order_event_rows.append(
                    {
                        "date": session_date.date().isoformat(),
                        "signal_date": pd.Timestamp(row.get("signal_us_date", session_date)).date().isoformat(),
                        "symbol": policy.target_symbol,
                        "side": "buy",
                        "order_type": entry.order_type,
                        "status": event_status,
                        "trade_time": "",
                        "reference_open_price": float(entry_open),
                        "limit_price": entry.limit_price,
                        "requested_shares": float(requested_shares),
                        "filled_shares": 0.0,
                        "price": None,
                        "reason": entry.reason,
                    }
                )
            elif entry.status == "cancelled":
                unfilled_orders += 1
            else:
                missing_days.add(session_date.date().isoformat())

        close_price = float(row["close"])
        stock_asset = shares * close_price
        total_asset = cash + stock_asset
        daily_return = total_asset / previous_total_asset - 1.0 if previous_total_asset else 0.0
        closing_position_size = active_position_size if shares > 0 else 0.0
        exposure = max(held_position_size, closing_position_size)
        daily_rows.append(
            {
                "date": session_date.date().isoformat(),
                "total_asset": float(total_asset),
                "stock_asset": float(stock_asset),
                "cash_asset": float(cash),
                "daily_return": float(daily_return),
                "exposure": float(exposure),
                "estimated_trade_amount": float(day_trade_amount),
                "estimated_volume": float(day_trade_volume),
                "unfilled_orders": 1 if any(
                    event["date"] == session_date.date().isoformat() and event["status"] == "cancelled"
                    for event in order_event_rows
                ) else 0,
                "partial_fill_orders": 0,
                "block_reason_counts": "{}",
                "stale_valuation_positions": 0,
            }
        )
        if shares > 0:
            position_rows.append(
                {
                    "date": session_date.date().isoformat(),
                    "symbol": policy.target_symbol,
                    "name": policy.target_symbol,
                    "close": close_price,
                    "market_value": stock_asset,
                    "shares": shares,
                    "lots": shares / account.lot_size if account.lot_size else np.nan,
                    "target_weight": stock_asset / total_asset if total_asset else 0.0,
                    "planned_exit_date": pd.Timestamp(planned_exit_date).date().isoformat() if pd.notna(planned_exit_date) else "",
                    "running_high": running_high,
                    "entry_price": entry_price,
                }
            )
        previous_total_asset = total_asset

    daily_result = pd.DataFrame(daily_rows)
    trades_result = pd.DataFrame(trade_rows)
    positions_result = pd.DataFrame(position_rows)
    order_events_result = pd.DataFrame(order_event_rows)
    metrics = build_signal_execution_metrics(daily_result, trades_result, unfilled_orders, 0)
    side_counts = trades_result["side"].value_counts().to_dict() if not trades_result.empty else {}
    reason_counts = trades_result["reason"].value_counts().to_dict() if not trades_result.empty else {}
    if blocked_by_missing_exit:
        state_status = "blocked_missing_exit_data"
    elif shares > 0:
        state_status = "open_position_pending_exit"
    else:
        state_status = "complete_flat"
    metrics.update(
        {
            "account_execution_model": "single_etf_intraday",
            "account_execution_complete": not missing_days and not blocked_by_missing_exit,
            "account_state_status": state_status,
            "account_raw_signal_count": raw_signal_count,
            "account_entry_count": int(side_counts.get("buy", 0)),
            "account_exit_count": int(side_counts.get("sell", 0)),
            "account_completed_round_trip_count": int(side_counts.get("sell", 0)),
            "account_trade_reason_counts": {str(key): int(value) for key, value in reason_counts.items()},
            "account_intraday_data_missing_days": len(missing_days),
            "account_intraday_data_missing_dates": sorted(missing_days),
            "account_pending_exit_count": int(pending_exit_count),
            "account_open_position_shares": float(shares),
            "account_open_position_symbol": policy.target_symbol if shares > 0 else "",
            "account_planned_exit_date": pd.Timestamp(planned_exit_date).date().isoformat() if pd.notna(planned_exit_date) else "",
        }
    )
    return SignalAccountExecutionResult(daily_result, trades_result, positions_result, metrics, order_events_result)


def ensure_single_etf_intraday_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS single_etf_intraday_accounts (
            account_id TEXT PRIMARY KEY,
            strategy_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            policy_json TEXT NOT NULL,
            execution_complete INTEGER NOT NULL,
            open_position_shares REAL NOT NULL,
            planned_exit_date TEXT,
            as_of_date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS single_etf_intraday_daily_assets (
            account_id TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            total_asset REAL NOT NULL,
            stock_asset REAL NOT NULL,
            cash_asset REAL NOT NULL,
            daily_return REAL NOT NULL,
            exposure REAL NOT NULL,
            PRIMARY KEY (account_id, trade_date)
        );

        CREATE TABLE IF NOT EXISTS single_etf_intraday_trades (
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
            cost REAL NOT NULL,
            PRIMARY KEY (account_id, trade_date, symbol, side, signal_date)
        );

        CREATE TABLE IF NOT EXISTS single_etf_intraday_order_events (
            account_id TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            signal_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            order_type TEXT NOT NULL,
            status TEXT NOT NULL,
            trade_time TEXT NOT NULL DEFAULT '',
            reference_open_price REAL,
            limit_price REAL,
            requested_shares REAL NOT NULL,
            filled_shares REAL NOT NULL,
            price REAL,
            reason TEXT NOT NULL,
            PRIMARY KEY (account_id, trade_date, symbol, side, signal_date, order_type)
        );
        """
    )


def write_single_etf_intraday_account_state(
    *,
    account: SimulatedAccountConfig,
    policy: SingleEtfIntradayPolicy,
    result: SignalAccountExecutionResult,
) -> None:
    """Replace one account's deterministic replay snapshot in one transaction."""
    account.database_path.parent.mkdir(parents=True, exist_ok=True)
    as_of_date = str(result.daily_assets["date"].max()) if not result.daily_assets.empty else ""
    with sqlite3.connect(account.database_path) as conn:
        ensure_single_etf_intraday_tables(conn)
        conn.execute("DELETE FROM single_etf_intraday_daily_assets WHERE account_id = ?", (account.account_id,))
        conn.execute("DELETE FROM single_etf_intraday_trades WHERE account_id = ?", (account.account_id,))
        conn.execute("DELETE FROM single_etf_intraday_order_events WHERE account_id = ?", (account.account_id,))
        conn.execute(
            """
            INSERT OR REPLACE INTO single_etf_intraday_accounts
            (account_id, strategy_id, symbol, policy_json, execution_complete,
             open_position_shares, planned_exit_date, as_of_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account.account_id,
                account.strategy_id,
                policy.target_symbol,
                json.dumps(asdict(policy), ensure_ascii=False, sort_keys=True),
                int(bool(result.metrics.get("account_execution_complete", False))),
                float(result.metrics.get("account_open_position_shares", 0.0)),
                str(result.metrics.get("account_planned_exit_date", "")),
                as_of_date,
            ),
        )
        if not result.daily_assets.empty:
            conn.executemany(
                """
                INSERT INTO single_etf_intraday_daily_assets
                (account_id, trade_date, total_asset, stock_asset, cash_asset, daily_return, exposure)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        account.account_id,
                        str(row.date),
                        float(row.total_asset),
                        float(row.stock_asset),
                        float(row.cash_asset),
                        float(row.daily_return),
                        float(row.exposure),
                    )
                    for row in result.daily_assets.itertuples(index=False)
                ],
            )
        if not result.trades.empty:
            conn.executemany(
                """
                INSERT INTO single_etf_intraday_trades
                (account_id, trade_date, signal_date, symbol, side, trade_time,
                 order_type, reason, price, shares, amount, cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        account.account_id,
                        str(row.date),
                        str(row.signal_date),
                        str(row.symbol),
                        str(row.side),
                        str(row.trade_time),
                        str(row.order_type),
                        str(row.reason),
                        float(row.price),
                        float(row.shares),
                        float(row.amount),
                        float(row.cost),
                    )
                    for row in result.trades.itertuples(index=False)
                ],
            )
        if not result.order_events.empty:
            conn.executemany(
                """
                INSERT INTO single_etf_intraday_order_events
                (account_id, trade_date, signal_date, symbol, side, order_type, status,
                 trade_time, reference_open_price, limit_price, requested_shares,
                 filled_shares, price, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        account.account_id,
                        str(row.date),
                        str(row.signal_date),
                        str(row.symbol),
                        str(row.side),
                        str(row.order_type),
                        str(row.status),
                        str(row.trade_time or ""),
                        None if pd.isna(row.reference_open_price) else float(row.reference_open_price),
                        None if pd.isna(row.limit_price) else float(row.limit_price),
                        float(row.requested_shares),
                        float(row.filled_shares),
                        None if pd.isna(row.price) else float(row.price),
                        str(row.reason),
                    )
                    for row in result.order_events.itertuples(index=False)
                ],
            )


def load_single_etf_intraday_state(database_path: Path, account_id: str) -> dict[str, Any]:
    if not Path(database_path).exists():
        return {"account": {}, "daily_assets": [], "trades": [], "order_events": []}
    with sqlite3.connect(database_path) as conn:
        ensure_single_etf_intraday_tables(conn)
        conn.row_factory = sqlite3.Row
        account_row = conn.execute(
            "SELECT * FROM single_etf_intraday_accounts WHERE account_id = ?",
            (account_id,),
        ).fetchone()
        daily_rows = conn.execute(
            "SELECT * FROM single_etf_intraday_daily_assets WHERE account_id = ? ORDER BY trade_date",
            (account_id,),
        ).fetchall()
        trade_rows = conn.execute(
            "SELECT * FROM single_etf_intraday_trades WHERE account_id = ? ORDER BY trade_time, side",
            (account_id,),
        ).fetchall()
        order_event_rows = conn.execute(
            "SELECT * FROM single_etf_intraday_order_events WHERE account_id = ? "
            "ORDER BY trade_date, trade_time, side, symbol",
            (account_id,),
        ).fetchall()
    return {
        "account": dict(account_row) if account_row is not None else {},
        "daily_assets": [dict(row) for row in daily_rows],
        "trades": [dict(row) for row in trade_rows],
        "order_events": [dict(row) for row in order_event_rows],
    }
