from __future__ import annotations

from dataclasses import dataclass
import html
from pathlib import Path
import re
import sqlite3
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_ACCOUNT_LEDGER = "data/simulated_trading/phase0_daily_account_ledger.csv"


@dataclass(frozen=True)
class SimulatedAccountConfig:
    account_id: str
    name: str
    initial_cash: float
    ledger_path: Path
    database_path: Path
    enabled: bool = True
    execution_price_mode: str = "next_open"
    max_participation_rate: float = 0.05
    lot_size: int = 100
    commission: float = 0.0
    stamp_duty_sell: float = 0.0
    slippage: float = 0.0
    conservative_price_buffer: float = 0.001
    enable_limit_check: bool = True
    enable_suspension_check: bool = True
    limit_up_down_pct: dict[str, float] | None = None


def load_simulated_accounts(config: dict[str, Any], root: Path) -> list[SimulatedAccountConfig]:
    walk_forward = config.get("walk_forward", {})
    execution = config.get("execution", {})
    limit_cfg = execution.get("limit_up_down_pct", {})
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
                enabled=True,
                execution_price_mode=str(raw.get("execution_price_mode", execution.get("price_mode", "next_open"))),
                max_participation_rate=float(raw.get("max_participation_rate", execution.get("max_participation_rate", 0.05))),
                lot_size=int(raw.get("lot_size", execution.get("lot_size", 100))),
                commission=float(raw.get("commission", walk_forward.get("commission", 0.0))),
                stamp_duty_sell=float(raw.get("stamp_duty_sell", walk_forward.get("stamp_duty_sell", 0.0))),
                slippage=float(raw.get("slippage", walk_forward.get("slippage", 0.0))),
                conservative_price_buffer=float(raw.get("conservative_price_buffer", execution.get("conservative_price_buffer", 0.001))),
                enable_limit_check=bool(raw.get("enable_limit_check", execution.get("enable_limit_check", True))),
                enable_suspension_check=bool(raw.get("enable_suspension_check", execution.get("enable_suspension_check", True))),
                limit_up_down_pct={
                    "default": float(limit_cfg.get("default", 0.10)),
                    "star": float(limit_cfg.get("star", 0.20)),
                    "chinext": float(limit_cfg.get("chinext", 0.20)),
                    "bj": float(limit_cfg.get("bj", 0.30)),
                },
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


def _limit_pct(symbol: str, account: SimulatedAccountConfig) -> float:
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


def _load_execution_prices(
    *,
    root: Path,
    local_history_cfg: dict[str, Any] | None,
    execution_date: str,
    symbols: list[str],
) -> dict[str, dict[str, float]]:
    if not symbols:
        return {}
    cfg = local_history_cfg or {}
    db_path = _resolve_path(root, cfg.get("path", "data/manual_history/a_share_history.sqlite"))
    if not db_path.exists():
        return {}
    daily_table = _safe_identifier(str(cfg.get("daily_table", "market_daily_bars")))
    market = str(cfg.get("market", "CN"))
    adjust_type = str(cfg.get("execution_adjust_type", "bfq"))
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
               ) AS previous_close
        FROM {daily_table} b
        WHERE b.market = ?
          AND b.adjust_type = ?
          AND b.date = ?
          AND b.symbol IN ({placeholders})
    """
    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(query, (market, adjust_type, execution_date, *symbols)).fetchall()
    except (sqlite3.Error, ValueError):
        return {}
    out: dict[str, dict[str, float]] = {}
    for symbol, open_, high, low, close, volume, amount, previous_close in rows:
        out[str(symbol)] = {
            "open": float(open_) if open_ is not None else np.nan,
            "high": float(high) if high is not None else np.nan,
            "low": float(low) if low is not None else np.nan,
            "close": float(close) if close is not None else np.nan,
            "volume": float(volume) if volume is not None else np.nan,
            "amount": float(amount) if amount is not None else np.nan,
            "previous_close": float(previous_close) if previous_close is not None else np.nan,
        }
    return out


def _execution_price(price_row: dict[str, float], side: str, account: SimulatedAccountConfig) -> float:
    mode = account.execution_price_mode
    if mode == "close":
        return float(price_row.get("close", np.nan))
    base = float(price_row.get("open", np.nan))
    if not pd.notna(base) or base <= 0:
        base = float(price_row.get("close", np.nan))
    if mode == "conservative":
        if side == "buy":
            return base * (1.0 + account.conservative_price_buffer)
        return base * (1.0 - account.conservative_price_buffer)
    return base


def _trade_block_reasons(price_row: dict[str, float], side: str, account: SimulatedAccountConfig) -> list[str]:
    reasons: list[str] = []
    open_price = float(price_row.get("open", np.nan))
    close_price = float(price_row.get("close", np.nan))
    volume = float(price_row.get("volume", np.nan))
    amount = float(price_row.get("amount", np.nan))
    if account.enable_suspension_check:
        if not pd.notna(open_price) or open_price <= 0 or not pd.notna(close_price) or close_price <= 0:
            reasons.append("停牌/无有效价格")
        if pd.notna(volume) and volume <= 0:
            reasons.append("停牌/成交量为0")
        if pd.notna(amount) and amount <= 0:
            reasons.append("停牌/成交额为0")
    previous_close = float(price_row.get("previous_close", np.nan))
    check_price = close_price if account.execution_price_mode == "close" else open_price
    if account.enable_limit_check and pd.notna(previous_close) and previous_close > 0 and pd.notna(check_price):
        limit_pct = _limit_pct(str(price_row.get("symbol", "")), account)
        limit_up = previous_close * (1.0 + limit_pct)
        limit_down = previous_close * (1.0 - limit_pct)
        tolerance = 0.001
        if side == "buy" and check_price >= limit_up * (1.0 - tolerance):
            reasons.append("涨停不可买")
        if side == "sell" and check_price <= limit_down * (1.0 + tolerance):
            reasons.append("跌停不可卖")
    return reasons


def format_money(value: Any) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):,.2f}"


def format_pct(value: Any) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value) * 100:.2f}%"


def format_num(value: Any, digits: int = 2) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):,.{digits}f}"


def watchlist_to_account_frame(watchlist: pd.DataFrame, brief_date: str) -> pd.DataFrame:
    if watchlist.empty:
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
            "target_weight": watchlist["目标权重"].map(parse_percent),
            "weight_change": watchlist["权重变化"].map(parse_percent),
        }
    )


def collect_watchlist_frames(root: Path, current_watchlist: pd.DataFrame, current_brief_date: str) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    report_root = root / "reports"
    if report_root.exists():
        for path in sorted(report_root.glob("????-??-??/phase0_premarket_watchlist*.csv")):
            brief_date = path.parent.name
            if brief_date > current_brief_date or brief_date in frames:
                continue
            try:
                df = pd.read_csv(path, encoding="utf-8-sig")
            except Exception:
                continue
            required = {"股票代码", "股票名称", "收盘价", "目标权重", "权重变化"}
            if required.issubset(df.columns):
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
    frames = collect_watchlist_frames(root, current_watchlist, current_brief_date)
    if not frames:
        return pd.DataFrame(), {}

    previous_positions: dict[str, tuple[float, float, str]] = {}
    previous_total_asset = float(account.initial_cash)
    previous_cash_asset = float(account.initial_cash)
    rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    position_rows: list[dict[str, Any]] = []
    start_date = next(iter(frames.keys()))

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
                shares = round_lot_floor(raw_shares, account.lot_size)
                if shares <= 0:
                    continue
                trade_amount = shares * float(price)
                block_reasons = _trade_block_reasons(price_row, side, account)
                volume = float(price_row.get("volume", np.nan))
                if pd.notna(volume) and account.max_participation_rate > 0:
                    market_shares = round_lot_floor(volume * account.max_participation_rate, account.lot_size)
                    shares = min(shares, market_shares)
                    trade_amount = shares * float(price)
                if block_reasons or shares <= 0:
                    continue
                if side == "buy":
                    buy_rate = account.slippage + account.commission
                    affordable_shares = round_lot_floor(cash_asset / (float(price) * (1.0 + buy_rate)), account.lot_size)
                    shares = min(shares, affordable_shares)
                    trade_amount = shares * float(price)
                    if affordable_shares <= 0:
                        continue
                if side == "sell":
                    shares = min(shares, current_shares)
                    trade_amount = shares * float(price)
                    if shares <= 0:
                        continue
                lots = shares / float(account.lot_size) if account.lot_size else np.nan
                if side == "buy":
                    trade_cost = trade_amount * (account.slippage + account.commission)
                    cash_asset -= trade_amount + trade_cost
                    new_shares = current_shares + shares
                else:
                    trade_cost = trade_amount * (account.slippage + account.commission + account.stamp_duty_sell)
                    cash_asset += trade_amount - trade_cost
                    new_shares = current_shares - shares
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

    ledger = pd.DataFrame(rows)
    account.ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(account.ledger_path, index=False, encoding="utf-8-sig")
    write_account_database(
        account=account,
        daily_assets=ledger,
        trades=pd.DataFrame(trade_rows),
        positions=pd.DataFrame(position_rows),
    )
    latest = ledger.iloc[-1].to_dict() if not ledger.empty else {}
    return ledger, latest


def ensure_account_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS simulated_accounts (
            account_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            initial_cash REAL NOT NULL,
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
        """
    )
    existing_trade_cols = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info(account_trades)").fetchall()
    }
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


def write_account_database(
    *,
    account: SimulatedAccountConfig,
    daily_assets: pd.DataFrame,
    trades: pd.DataFrame,
    positions: pd.DataFrame,
) -> None:
    account.database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(account.database_path) as conn:
        ensure_account_tables(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO simulated_accounts
            (account_id, name, initial_cash, enabled, execution_price_mode, max_participation_rate, lot_size, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                account.account_id,
                account.name,
                account.initial_cash,
                1 if account.enabled else 0,
                account.execution_price_mode,
                account.max_participation_rate,
                account.lot_size,
            ),
        )
        conn.execute("DELETE FROM account_daily_assets WHERE account_id = ?", (account.account_id,))
        conn.execute("DELETE FROM account_trades WHERE account_id = ?", (account.account_id,))
        conn.execute("DELETE FROM account_positions WHERE account_id = ?", (account.account_id,))
        if not daily_assets.empty:
            conn.executemany(
                """
                INSERT OR REPLACE INTO account_daily_assets
                (account_id, brief_date, start_date, total_asset, stock_asset, cash_asset, daily_pnl, daily_return,
                 target_exposure, estimated_trade_amount, estimated_volume, execution_price_mode, max_participation_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    ]
                ].itertuples(index=False, name=None),
            )
        if not trades.empty:
            conn.executemany(
                """
                INSERT OR REPLACE INTO account_trades
                (account_id, brief_date, signal_date, symbol, name, side, trade_time, price_mode, price, amount, cost, shares,
                 lots, lot_size, raw_shares, rounding_rule, weight_before, weight_after, weight_change, is_estimated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def load_latest_account_snapshot(account: SimulatedAccountConfig) -> dict[str, Any]:
    if not account.database_path.exists():
        return {}
    try:
        with sqlite3.connect(account.database_path) as conn:
            ensure_account_tables(conn)
            row = conn.execute(
                """
                SELECT account_id, brief_date, start_date, total_asset, stock_asset, cash_asset,
                       daily_pnl, daily_return, target_exposure, estimated_trade_amount,
                       estimated_volume, execution_price_mode, max_participation_rate
                FROM account_daily_assets
                WHERE account_id = ?
                ORDER BY brief_date DESC
                LIMIT 1
                """,
                (account.account_id,),
            ).fetchone()
    except sqlite3.Error:
        return {}
    if not row:
        return {}
    keys = [
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
    ]
    return dict(zip(keys, row, strict=False))


def _html_table(df: pd.DataFrame, columns: list[tuple[str, str]]) -> str:
    if df.empty:
        return "<p class=\"empty\">暂无记录</p>"
    head = "".join(f"<th>{html.escape(label)}</th>" for _col, label in columns)
    body_rows = []
    for _, row in df.iterrows():
        cells = "".join(f"<td>{html.escape(str(row.get(col, '')))}</td>" for col, _label in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    return (
        "<div class=\"table-wrap\"><table><thead><tr>"
        + head
        + "</tr></thead><tbody>"
        + "\n".join(body_rows)
        + "</tbody></table></div>"
    )


def export_account_bill_html(*, account: SimulatedAccountConfig, brief_date: str, output_path: Path) -> Path:
    with sqlite3.connect(account.database_path) as conn:
        ensure_account_tables(conn)
        account_rows = pd.read_sql_query(
            "SELECT account_id, name, initial_cash, execution_price_mode, max_participation_rate, lot_size FROM simulated_accounts WHERE account_id = ?",
            conn,
            params=(account.account_id,),
        )
        assets = pd.read_sql_query(
            "SELECT * FROM account_daily_assets WHERE account_id = ? AND brief_date = ?",
            conn,
            params=(account.account_id, brief_date),
        )
        trades = pd.read_sql_query(
            "SELECT * FROM account_trades WHERE account_id = ? AND brief_date = ? ORDER BY side, symbol",
            conn,
            params=(account.account_id, brief_date),
        )
        positions = pd.read_sql_query(
            "SELECT * FROM account_positions WHERE account_id = ? AND brief_date = ? ORDER BY symbol",
            conn,
            params=(account.account_id, brief_date),
        )

    if not account_rows.empty:
        account_rows = account_rows.copy()
        account_rows["initial_cash"] = account_rows["initial_cash"].map(format_money)
        account_rows["max_participation_rate"] = account_rows["max_participation_rate"].map(format_pct)
        account_rows["execution_price_mode"] = account_rows["execution_price_mode"].map(price_mode_label)

    if not assets.empty:
        assets = assets.copy()
        for col in ["total_asset", "stock_asset", "cash_asset", "daily_pnl", "estimated_trade_amount"]:
            assets[col] = assets[col].map(format_money)
        assets["daily_return"] = assets["daily_return"].map(format_pct)
        assets["target_exposure"] = assets["target_exposure"].map(format_pct)
        assets["estimated_volume"] = assets["estimated_volume"].map(lambda value: format_num(value, 0))

    if not trades.empty:
        trades = trades.copy()
        trades["side"] = trades["side"].map({"buy": "买入", "sell": "卖出"}).fillna(trades["side"])
        trades["price_mode"] = trades["price_mode"].map(price_mode_label)
        for col in ["price", "amount", "cost"]:
            trades[col] = trades[col].map(format_money)
        for col in ["raw_shares", "shares", "lots"]:
            trades[col] = trades[col].map(lambda value: format_num(value, 2))
        for col in ["weight_before", "weight_after", "weight_change"]:
            trades[col] = trades[col].map(format_pct)

    if not positions.empty:
        positions = positions.copy()
        positions["close"] = positions["close"].map(format_money)
        positions["target_weight"] = positions["target_weight"].map(format_pct)
        positions["market_value"] = positions["market_value"].map(format_money)
        for col in ["shares", "lots"]:
            positions[col] = positions[col].map(lambda value: format_num(value, 2))

    style = """
<style>
body { margin: 0; padding: 24px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1f2937; background: #f5f7fb; }
.page { max-width: 1280px; margin: 0 auto; }
h1 { margin: 0 0 6px; font-size: 24px; }
h2 { margin: 22px 0 8px; font-size: 17px; }
p { margin: 0 0 12px; color: #6b7280; }
.table-wrap { overflow: auto; border: 1px solid #d0d7de; background: #fff; }
table { width: max-content; min-width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { border: 1px solid #d0d7de; padding: 7px 9px; white-space: nowrap; }
th { background: #eef3f9; text-align: left; }
.empty { padding: 10px 0; }
.notice { margin-top: 16px; font-size: 12px; color: #6b7280; line-height: 1.6; }
</style>
"""
    html_text = (
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>模拟交易账单 {html.escape(brief_date)}</title>"
        + style
        + "</head><body><div class=\"page\">"
        f"<h1>模拟交易账单</h1><p>账户：{html.escape(account.name)} ｜ 日期：{html.escape(brief_date)}</p>"
        "<h2>账户配置</h2>"
        + _html_table(
            account_rows,
            [
                ("account_id", "账户ID"),
                ("name", "账户名称"),
                ("initial_cash", "初始资产"),
                ("execution_price_mode", "成交价口径"),
                ("max_participation_rate", "最大成交参与率"),
                ("lot_size", "每手股数"),
            ],
        )
        + "<h2>每日资产</h2>"
        + _html_table(
            assets,
            [
                ("brief_date", "账户日期"),
                ("start_date", "起始日期"),
                ("total_asset", "总资产"),
                ("stock_asset", "股票资产"),
                ("cash_asset", "现金资产"),
                ("daily_pnl", "收益额"),
                ("daily_return", "收益率"),
                ("target_exposure", "实际股票暴露"),
                ("estimated_trade_amount", "成交金额"),
                ("estimated_volume", "成交股数"),
            ],
        )
        + "<h2>交易明细</h2>"
        + _html_table(
            trades,
            [
                ("symbol", "股票代码"),
                ("name", "股票名称"),
                ("side", "方向"),
                ("signal_date", "信号日期"),
                ("trade_time", "交易时间"),
                ("price_mode", "成交价口径"),
                ("price", "价格"),
                ("amount", "金额"),
                ("cost", "交易成本"),
                ("raw_shares", "理论股数"),
                ("shares", "实际股数"),
                ("lots", "手数"),
                ("lot_size", "每手股数"),
                ("weight_before", "交易前权重"),
                ("weight_after", "目标权重"),
                ("weight_change", "权重变化"),
                ("rounding_rule", "取整规则"),
            ],
        )
        + "<h2>持仓快照</h2>"
        + _html_table(
            positions,
            [
                ("symbol", "股票代码"),
                ("name", "股票名称"),
                ("close", "价格"),
                ("target_weight", "实际权重"),
                ("market_value", "市值"),
                ("shares", "股数"),
                ("lots", "手数"),
                ("lot_size", "每手股数"),
            ],
        )
        + "<p class=\"notice\">本账单为模拟账户估算记录，不代表实盘成交；交易股数已按每手股数向下取整。</p>"
        "</div></body></html>"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_text, encoding="utf-8")
    return output_path
