from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd


def execution_settings(config: dict[str, Any]) -> dict[str, Any]:
    cfg = config.get("execution", {})
    limit_cfg = cfg.get("limit_up_down_pct", {})
    return {
        "price_mode": str(cfg.get("price_mode", "next_open")),
        "conservative_price_buffer": float(cfg.get("conservative_price_buffer", 0.001)),
        "lot_size": int(cfg.get("lot_size", 100)),
        "max_participation_rate": float(cfg.get("max_participation_rate", 0.05)),
        "enable_limit_check": bool(cfg.get("enable_limit_check", True)),
        "enable_suspension_check": bool(cfg.get("enable_suspension_check", True)),
        "limit_up_down_pct": {
            "default": float(limit_cfg.get("default", 0.10)),
            "star": float(limit_cfg.get("star", 0.20)),
            "chinext": float(limit_cfg.get("chinext", 0.20)),
            "bj": float(limit_cfg.get("bj", 0.30)),
        },
    }


def limit_pct(symbol: str, execution_cfg: dict[str, Any]) -> float:
    limits = execution_cfg.get("limit_up_down_pct", {})
    code = str(symbol).split(".")[-1]
    market = str(symbol).split(".")[0]
    if market == "BJ" or code.startswith(("4", "8")):
        return float(limits.get("bj", 0.30))
    if market == "SH" and code.startswith("688"):
        return float(limits.get("star", 0.20))
    if market == "SZ" and code.startswith("300"):
        return float(limits.get("chinext", 0.20))
    return float(limits.get("default", 0.10))


def lot_floor(quantity: float, lot_size: int) -> int:
    if lot_size <= 1:
        return max(0, int(np.floor(quantity)))
    return max(0, int(np.floor(quantity / lot_size) * lot_size))


def prepare_execution_frame(signal_frame: pd.DataFrame, price_frame: pd.DataFrame, execution_cfg: dict[str, Any]) -> pd.DataFrame:
    sf = signal_frame.copy()
    sf["date"] = pd.to_datetime(sf["date"])
    sf["symbol"] = sf["symbol"].astype(str)

    cols = [col for col in ["date", "symbol", "open", "high", "low", "close", "volume", "amount", "execution_adjust_type"] if col in price_frame.columns]
    prices = price_frame[cols].copy()
    prices["date"] = pd.to_datetime(prices["date"])
    prices["symbol"] = prices["symbol"].astype(str)
    if "execution_adjust_type" not in prices.columns:
        prices["execution_adjust_type"] = "unknown"
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        if col not in prices.columns:
            prices[col] = np.nan
        prices[col] = pd.to_numeric(prices[col], errors="coerce")

    # Signal rows are dated by the day whose signal is applied. Execution uses
    # a configurable execution price, while account valuation still uses close.
    sf = sf.merge(prices, on=["date", "symbol"], how="left")
    price_mode = str(execution_cfg.get("price_mode", "next_open"))
    buffer = float(execution_cfg.get("conservative_price_buffer", 0.001))
    if price_mode == "close":
        sf["execution_price_buy"] = sf["close"]
        sf["execution_price_sell"] = sf["close"]
    elif price_mode == "conservative":
        base = sf["open"].where(sf["open"].notna() & (sf["open"] > 0), sf["close"])
        sf["execution_price_buy"] = base * (1.0 + buffer)
        sf["execution_price_sell"] = base * (1.0 - buffer)
    else:
        sf["execution_price_buy"] = sf["open"].where(sf["open"].notna() & (sf["open"] > 0), sf["close"])
        sf["execution_price_sell"] = sf["open"].where(sf["open"].notna() & (sf["open"] > 0), sf["close"])
        price_mode = "next_open"

    sf["valuation_price"] = sf["close"]
    sf = sf.sort_values(["symbol", "date"]).reset_index(drop=True)
    sf["previous_close"] = sf.groupby("symbol")["close"].shift(1)
    sf["price_mode"] = sf["execution_adjust_type"].astype(str).fillna("unknown") + ":" + price_mode
    return sf.sort_values(["date", "symbol"]).reset_index(drop=True)


def trade_block_reasons(row: pd.Series, action: str, execution_cfg: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    open_price = float(row.get("open", np.nan) or np.nan)
    close_price = float(row.get("close", np.nan) or np.nan)
    volume = float(row.get("volume", np.nan) or np.nan)
    amount = float(row.get("amount", np.nan) or np.nan)
    if bool(execution_cfg.get("enable_suspension_check", True)):
        if pd.isna(open_price) or open_price <= 0 or pd.isna(close_price) or close_price <= 0:
            reasons.append("停牌/无有效价格")
        if pd.notna(volume) and volume <= 0:
            reasons.append("停牌/成交量为0")
        if pd.notna(amount) and amount <= 0:
            reasons.append("停牌/成交额为0")
    previous_close = row.get("previous_close")
    if bool(execution_cfg.get("enable_limit_check", True)) and pd.notna(previous_close) and float(previous_close) > 0 and pd.notna(open_price):
        limit = limit_pct(str(row.get("symbol", "")), execution_cfg)
        limit_up = float(previous_close) * (1.0 + limit)
        limit_down = float(previous_close) * (1.0 - limit)
        tolerance = 0.001
        if action == "买" and open_price >= limit_up * (1.0 - tolerance):
            reasons.append("涨停不可买")
        if action == "卖" and open_price <= limit_down * (1.0 + tolerance):
            reasons.append("跌停不可卖")
    return reasons


def append_order_record(
    records_for_date: list[dict[str, Any]],
    *,
    row: pd.Series,
    date: pd.Timestamp,
    symbol: str,
    action: str,
    deal_price: float,
    target_qty: int,
    actual_qty: int,
    trade_amount: float,
    trade_cost: float,
    trade_status: str,
    unfilled_reason: str,
    target_weight: float,
    trade_constraint: str,
    execution_cfg: dict[str, Any],
    classify_reason: Callable[[pd.Series], str],
    income_type: str,
) -> None:
    record = row.to_dict()
    record.update(
        {
            "date": date,
            "symbol": symbol,
            "trade_action": action,
            "deal_price": deal_price,
            "stock_vol": actual_qty,
            "target_stock_vol": target_qty,
            "unfilled_stock_vol": max(0, target_qty - actual_qty),
            "trade_amount": trade_amount,
            "trade_cost": trade_cost,
            "target_weight": target_weight,
            "actual_weight_after_trade": 0.0,
            "trade_constraint": trade_constraint,
            "trade_status": trade_status,
            "unfilled_reason": unfilled_reason,
            "price_mode": str(execution_cfg.get("price_mode", "next_open")),
            "max_participation_rate": float(execution_cfg.get("max_participation_rate", 0.0)),
        }
    )
    record["trade_reason"] = classify_reason(pd.Series(record))
    record["income_type"] = income_type
    records_for_date.append(record)


def ledger_for_fold(
    signal_frame: pd.DataFrame,
    *,
    price_frame: pd.DataFrame,
    params: dict[str, Any],
    fold: int,
    initial_cash: float,
    names: dict[str, str],
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
    params_text: str,
    execution_cfg: dict[str, Any],
    score_label: str = "策略分数",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    required_signal_cols = {"date", "symbol", "weight"}
    if signal_frame.empty or not required_signal_cols <= set(signal_frame.columns):
        return pd.DataFrame(), pd.DataFrame()
    sf = prepare_execution_frame(signal_frame, price_frame, execution_cfg)
    sf = sf.sort_values(["date", "symbol"]).reset_index(drop=True)
    sf["stock_name"] = sf["symbol"].map(names).fillna("")
    for col in ["score", "rank"]:
        if col not in sf.columns:
            sf[col] = np.nan
    sf["prev_weight"] = sf.groupby("symbol")["weight"].shift(1).fillna(0.0)
    if "held_days" not in sf.columns:
        sf["held_days"] = 0
    sf["prev_held_days"] = sf.groupby("symbol")["held_days"].shift(1).fillna(0.0)
    sf["delta_weight"] = sf["weight"] - sf["prev_weight"]
    buy_top_n = int(params.get("buy_top_n", params.get("top_n", 0)) or 0)
    hold_top_n = int(params.get("hold_top_n", buy_top_n) or buy_top_n)
    buy_threshold = params.get("buy_threshold")
    hold_threshold = params.get("hold_threshold", buy_threshold)
    min_hold_days = int(params.get("min_hold_days", 0) or 0)

    def classify_reason(row: pd.Series) -> str:
        score = row.get("score")
        rank = row.get("rank")
        prev_weight = float(row.get("prev_weight", 0.0) or 0.0)
        curr_weight = float(row.get("weight", 0.0) or 0.0)
        prev_held_days = float(row.get("prev_held_days", 0.0) or 0.0)

        if curr_weight > prev_weight:
            if prev_weight <= 1e-12:
                reasons = []
                if buy_top_n > 0 and pd.notna(rank) and float(rank) <= buy_top_n:
                    reasons.append("新进前N")
                if buy_threshold is not None and pd.notna(score) and float(score) > float(buy_threshold):
                    reasons.append("满足买入阈值")
                if not reasons:
                    reasons.append("调仓纳入持仓")
                return "调仓买入-" + "、".join(reasons)
            return "调仓买入-权重上调"

        if curr_weight < prev_weight:
            if curr_weight <= 1e-12:
                reasons = []
                if pd.isna(score) or pd.isna(rank):
                    reasons.append("当日无有效信号")
                else:
                    if hold_threshold is not None and float(score) <= float(hold_threshold):
                        reasons.append("跌破持有阈值")
                    if hold_top_n > 0 and float(rank) > hold_top_n:
                        reasons.append("跌出持有排名")
                if prev_held_days >= min_hold_days:
                    reasons.append("满足最小持有期")
                if not reasons:
                    reasons.append("调仓移出持仓")
                return "调仓卖出-" + "、".join(dict.fromkeys(reasons))
            return "调仓卖出-权重下调"

        return "持仓不变"

    cash = float(initial_cash)
    positions: dict[str, int] = {}
    previous_total_assets = float(initial_cash)
    daily_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    lot_size = int(execution_cfg.get("lot_size", 100))
    max_participation_rate = max(0.0, float(execution_cfg.get("max_participation_rate", 0.0)))
    last_valuation_prices: dict[str, float] = {}

    for date, day in sf.groupby("date", sort=True):
        day = day.copy()
        day["symbol"] = day["symbol"].astype(str)
        day_by_symbol = day.set_index("symbol", drop=False)
        valuation_by_symbol = day_by_symbol["valuation_price"].astype(float).to_dict()
        buy_price_by_symbol = day_by_symbol["execution_price_buy"].astype(float).to_dict()
        sell_price_by_symbol = day_by_symbol["execution_price_sell"].astype(float).to_dict()

        def valuation_price_for(symbol: str) -> float:
            value = valuation_by_symbol.get(symbol, np.nan)
            if pd.notna(value) and float(value) > 0:
                return float(value)
            fallback = last_valuation_prices.get(symbol, np.nan)
            return float(fallback) if pd.notna(fallback) and float(fallback) > 0 else np.nan

        def is_stale_valuation(symbol: str) -> bool:
            value = valuation_by_symbol.get(symbol, np.nan)
            return not (pd.notna(value) and float(value) > 0) and symbol in last_valuation_prices

        def trade_price_for(symbol: str, action: str) -> float:
            source = buy_price_by_symbol if action == "买" else sell_price_by_symbol
            value = source.get(symbol, np.nan)
            return float(value) if pd.notna(value) and float(value) > 0 else np.nan

        def max_market_qty(row: pd.Series) -> int:
            volume = row.get("volume")
            if max_participation_rate <= 0 or pd.isna(volume):
                return 10**12
            return lot_floor(float(volume) * max_participation_rate, lot_size)

        stock_assets_before_trade = 0.0
        for symbol, qty in positions.items():
            price = valuation_price_for(symbol)
            if pd.notna(price):
                stock_assets_before_trade += qty * price
        total_before_trade = cash + stock_assets_before_trade

        buy_amount = 0.0
        sell_amount = 0.0
        buy_cost = 0.0
        sell_cost = 0.0
        trade_cash_flow = 0.0
        records_for_date: list[dict[str, Any]] = []

        target_values = {
            str(row.symbol): max(0.0, float(row.weight or 0.0)) * total_before_trade
            for row in day.itertuples()
        }

        sell_orders: list[tuple[str, float, pd.Series]] = []
        for symbol, qty in list(positions.items()):
            price = valuation_price_for(symbol)
            if pd.isna(price) or qty <= 0:
                continue
            current_value = qty * price
            target_value = target_values.get(symbol, 0.0)
            value_to_sell = max(0.0, current_value - target_value)
            if value_to_sell <= 0:
                continue
            row = day_by_symbol.loc[symbol] if symbol in day_by_symbol.index else pd.Series({"symbol": symbol, "close": price})
            sell_orders.append((symbol, value_to_sell, row))

        for symbol, value_to_sell, row in sell_orders:
            price = trade_price_for(symbol, "卖")
            if pd.isna(price):
                append_order_record(
                    records_for_date,
                    row=row,
                    date=date,
                    symbol=symbol,
                    action="卖",
                    deal_price=np.nan,
                    target_qty=int(positions.get(symbol, 0)),
                    actual_qty=0,
                    trade_amount=0.0,
                    trade_cost=0.0,
                    trade_status="未成交",
                    unfilled_reason="无有效执行价",
                    target_weight=float(row.get("weight", 0.0) or 0.0),
                    trade_constraint="账户级撮合-v2",
                    execution_cfg=execution_cfg,
                    classify_reason=classify_reason,
                    income_type="超时卖/调仓卖",
                )
                continue
            held_qty = int(positions.get(symbol, 0))
            target_value = target_values.get(symbol, 0.0)
            if target_value <= 0:
                target_qty = held_qty
            else:
                target_qty = lot_floor(value_to_sell / price, lot_size)
            target_qty = max(0, min(held_qty, target_qty))
            block_reasons = trade_block_reasons(row, "卖", execution_cfg)
            market_qty = max_market_qty(row)
            qty = 0 if block_reasons else min(target_qty, market_qty)
            qty = max(0, min(held_qty, qty))
            if qty <= 0:
                reason = "；".join(block_reasons or ["流动性不足/低于一手"])
                append_order_record(
                    records_for_date,
                    row=row,
                    date=date,
                    symbol=symbol,
                    action="卖",
                    deal_price=price,
                    target_qty=target_qty,
                    actual_qty=0,
                    trade_amount=0.0,
                    trade_cost=0.0,
                    trade_status="未成交",
                    unfilled_reason=reason,
                    target_weight=float(row.get("weight", 0.0) or 0.0),
                    trade_constraint="账户级撮合-v2",
                    execution_cfg=execution_cfg,
                    classify_reason=classify_reason,
                    income_type="超时卖/调仓卖",
                )
                continue
            gross = qty * price
            cost = gross * (slippage + commission + stamp_duty_sell)
            cash += gross - cost
            positions[symbol] = held_qty - qty
            if positions[symbol] <= 0:
                positions.pop(symbol, None)
            sell_amount += gross
            sell_cost += cost
            trade_cash_flow += gross - cost
            status = "全部成交" if qty >= target_qty else "部分成交"
            reason = "" if status == "全部成交" else "流动性限制导致部分成交"
            append_order_record(
                records_for_date,
                row=row,
                date=date,
                symbol=symbol,
                action="卖",
                deal_price=price,
                target_qty=target_qty,
                actual_qty=qty,
                trade_amount=gross,
                trade_cost=cost,
                trade_status=status,
                unfilled_reason=reason,
                target_weight=float(row.get("weight", 0.0) or 0.0),
                trade_constraint="账户级撮合-v2-卖出回款/涨跌停停牌流动性约束",
                execution_cfg=execution_cfg,
                classify_reason=classify_reason,
                income_type="超时卖/调仓卖",
            )

        buy_orders: list[tuple[str, float, pd.Series]] = []
        for symbol, row in day_by_symbol.iterrows():
            price = trade_price_for(str(symbol), "买")
            if pd.isna(price):
                continue
            valuation_price = valuation_price_for(str(symbol))
            current_value = positions.get(str(symbol), 0) * valuation_price if pd.notna(valuation_price) else 0.0
            target_value = target_values.get(str(symbol), 0.0)
            value_to_buy = max(0.0, target_value - current_value)
            if value_to_buy > 0:
                buy_orders.append((str(symbol), value_to_buy, row))
        buy_orders.sort(key=lambda item: (float(item[2].get("rank", np.inf)) if pd.notna(item[2].get("rank", np.inf)) else np.inf, item[0]))

        for symbol, value_to_buy, row in buy_orders:
            price = trade_price_for(symbol, "买")
            if pd.isna(price):
                append_order_record(
                    records_for_date,
                    row=row,
                    date=date,
                    symbol=symbol,
                    action="买",
                    deal_price=np.nan,
                    target_qty=0,
                    actual_qty=0,
                    trade_amount=0.0,
                    trade_cost=0.0,
                    trade_status="未成交",
                    unfilled_reason="无有效执行价",
                    target_weight=float(row.get("weight", 0.0) or 0.0),
                    trade_constraint="账户级撮合-v2",
                    execution_cfg=execution_cfg,
                    classify_reason=classify_reason,
                    income_type="",
                )
                continue
            buy_rate = slippage + commission
            max_affordable_qty = lot_floor(cash / (price * (1.0 + buy_rate)), lot_size)
            target_qty = lot_floor(value_to_buy / (price * (1.0 + buy_rate)), lot_size)
            block_reasons = trade_block_reasons(row, "买", execution_cfg)
            market_qty = max_market_qty(row)
            qty = 0 if block_reasons else min(max_affordable_qty, target_qty, market_qty)
            qty = max(0, qty)
            if qty <= 0:
                reasons = list(block_reasons)
                if target_qty <= 0:
                    reasons.append("目标金额低于一手")
                if max_affordable_qty <= 0:
                    reasons.append("现金不足一手")
                if market_qty <= 0:
                    reasons.append("流动性不足/低于一手")
                append_order_record(
                    records_for_date,
                    row=row,
                    date=date,
                    symbol=symbol,
                    action="买",
                    deal_price=price,
                    target_qty=target_qty,
                    actual_qty=0,
                    trade_amount=0.0,
                    trade_cost=0.0,
                    trade_status="未成交",
                    unfilled_reason="；".join(dict.fromkeys(reasons or ["约束后无可成交数量"])),
                    target_weight=float(row.get("weight", 0.0) or 0.0),
                    trade_constraint="账户级撮合-v2",
                    execution_cfg=execution_cfg,
                    classify_reason=classify_reason,
                    income_type="",
                )
                continue
            gross = qty * price
            cost = gross * buy_rate
            cash -= gross + cost
            positions[symbol] = int(positions.get(symbol, 0)) + qty
            buy_amount += gross
            buy_cost += cost
            trade_cash_flow -= gross + cost
            status = "全部成交" if qty >= target_qty else "部分成交"
            reason = "" if status == "全部成交" else "现金/流动性限制导致部分成交"
            append_order_record(
                records_for_date,
                row=row,
                date=date,
                symbol=symbol,
                action="买",
                deal_price=price,
                target_qty=target_qty,
                actual_qty=qty,
                trade_amount=gross,
                trade_cost=cost,
                trade_status=status,
                unfilled_reason=reason,
                target_weight=float(row.get("weight", 0.0) or 0.0),
                trade_constraint="账户级撮合-v2-100股整手/现金/涨跌停停牌流动性约束",
                execution_cfg=execution_cfg,
                classify_reason=classify_reason,
                income_type="",
            )

        stock_assets = 0.0
        stale_valuation_positions = 0
        for symbol, qty in positions.items():
            price = valuation_price_for(symbol)
            if pd.notna(price):
                stock_assets += qty * price
                if is_stale_valuation(symbol):
                    stale_valuation_positions += 1
        account_total_assets = cash + stock_assets
        exposure = stock_assets / account_total_assets if account_total_assets > 0 else 0.0
        trade_cost = buy_cost + sell_cost
        daily_pnl = total_before_trade - previous_total_assets
        net_daily_pnl = account_total_assets - previous_total_assets
        profit = account_total_assets - initial_cash
        profit_rate = account_total_assets / initial_cash - 1.0

        for record in records_for_date:
            qty_after = positions.get(str(record["symbol"]), 0)
            price = valuation_price_for(str(record["symbol"]))
            record["actual_weight_after_trade"] = (qty_after * price / account_total_assets) if account_total_assets > 0 and pd.notna(price) else 0.0
            trade_rows.append(record)

        unfilled_orders = sum(1 for record in records_for_date if str(record.get("trade_status", "")) in {"未成交", "部分成交"})
        daily_rows.append(
            {
                "date": date,
                "trade_cash_flow": trade_cash_flow,
                "exposure": exposure,
                "daily_pnl": daily_pnl,
                "buy_amount": buy_amount,
                "sell_amount": sell_amount,
                "buy_cost": buy_cost,
                "sell_cost": sell_cost,
                "trade_cost": trade_cost,
                "net_daily_pnl": net_daily_pnl,
                "account_total_assets": account_total_assets,
                "stock_assets": stock_assets,
                "cash_assets": cash,
                "profit": profit,
                "profit_rate": profit_rate,
                "unfilled_orders": unfilled_orders,
                "stale_valuation_positions": stale_valuation_positions,
            }
        )
        for symbol, price in valuation_by_symbol.items():
            if pd.notna(price) and float(price) > 0:
                last_valuation_prices[str(symbol)] = float(price)
        previous_total_assets = account_total_assets

    daily = pd.DataFrame(daily_rows).sort_values("date") if daily_rows else pd.DataFrame()
    trades = pd.DataFrame(trade_rows)
    if trades.empty:
        return trades, daily

    trades = trades.merge(
        daily[["date", "account_total_assets", "stock_assets", "cash_assets", "profit", "profit_rate"]],
        on="date",
        how="left",
    )
    trades["fold"] = fold
    trades["selected_params"] = params_text
    trades["trade_datetime"] = pd.to_datetime(trades["date"]).dt.strftime("%Y-%m-%d 15:00:00")
    trades["profit_rate"] = trades["profit_rate"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    bill = trades[
        [
            "trade_datetime",
            "account_total_assets",
            "stock_assets",
            "cash_assets",
            "trade_action",
            "symbol",
            "stock_name",
            "deal_price",
            "stock_vol",
            "target_stock_vol",
            "unfilled_stock_vol",
            "profit",
            "profit_rate",
            "income_type",
            "trade_reason",
            "trade_constraint",
            "trade_status",
            "unfilled_reason",
            "price_mode",
            "max_participation_rate",
            "fold",
            "trade_amount",
            "trade_cost",
            "target_weight",
            "actual_weight_after_trade",
            "score",
            "rank",
            "selected_params",
        ]
    ].copy()
    bill = bill.rename(
        columns={
            "trade_datetime": "交易日期",
            "account_total_assets": "账户总资产",
            "stock_assets": "股票资产",
            "cash_assets": "现金资产",
            "trade_action": "交易动作",
            "symbol": "股票代码",
            "stock_name": "股票名称",
            "deal_price": "成交价",
            "stock_vol": "成交量",
            "target_stock_vol": "目标成交量",
            "unfilled_stock_vol": "未成交量",
            "profit": "收益额",
            "profit_rate": "收益率",
            "income_type": "收益类型",
            "trade_reason": "交易原因",
            "trade_constraint": "成交约束",
            "trade_status": "交易状态",
            "unfilled_reason": "未成交原因",
            "price_mode": "成交价口径",
            "max_participation_rate": "最大成交参与率",
            "fold": "折号",
            "trade_amount": "成交金额",
            "trade_cost": "交易成本",
            "target_weight": "目标权重",
            "actual_weight_after_trade": "实际权重",
            "score": score_label,
            "rank": "当日排名",
            "selected_params": "策略参数",
        }
    )
    return bill, daily
