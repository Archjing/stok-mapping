from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
import pandas as pd

ACCOUNT_BILL_TEMPLATE_DIR = Path(__file__).with_name("templates")
ACCOUNT_BILL_STATIC_DIR = Path(__file__).with_name("static")
ACCOUNT_BILL_TEMPLATE_NAME = "account_bill.html"
ACCOUNT_BILL_STATIC_ASSETS = ("style.css",)
ACCOUNT_BILL_STYLESHEET_NAME = ACCOUNT_BILL_STATIC_ASSETS[0]


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


def load_latest_account_snapshot(account: Any) -> dict[str, Any]:
    from phase0.execution.accounts import ensure_account_tables

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


def _account_bill_template_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(ACCOUNT_BILL_TEMPLATE_DIR),
        autoescape=select_autoescape(("html", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _copy_account_bill_assets(html_path: Path) -> None:
    for asset_name in ACCOUNT_BILL_STATIC_ASSETS:
        asset = ACCOUNT_BILL_STATIC_DIR / asset_name
        if asset.exists():
            shutil.copyfile(asset, html_path.parent / asset_name)


def _write_account_bill_html(output_path: Path, html_text: str) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_text, encoding="utf-8")
    _copy_account_bill_assets(output_path)
    return output_path


def _table_context(
    df: pd.DataFrame,
    columns: list[tuple[str, str]],
    *,
    right_columns: set[str] | None = None,
    center_columns: set[str] | None = None,
) -> dict[str, Any]:
    right_columns = right_columns or set()
    center_columns = center_columns or set()
    headers = [label for _col, label in columns]
    if df.empty:
        return {"headers": headers, "rows": [], "empty": True}
    rows = []
    for _, row in df.iterrows():
        cells = []
        for col, _label in columns:
            cell_class = ""
            if col in right_columns:
                cell_class = "num-right"
            elif col in center_columns:
                cell_class = "num-center"
            cells.append({"class": cell_class, "value": str(row.get(col, ""))})
        rows.append({"cells": cells})
    return {"headers": headers, "rows": rows, "empty": False}


def _render_account_bill_html(
    *,
    account_name: str,
    brief_date: str,
    tables: list[dict[str, Any]],
    status_message: str = "",
) -> str:
    template = _account_bill_template_env().get_template(ACCOUNT_BILL_TEMPLATE_NAME)
    title_date = brief_date or "暂无确认账单"
    return template.render(
        stylesheet_href=ACCOUNT_BILL_STYLESHEET_NAME,
        title=f"模拟交易账单 {title_date}",
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        account_name=account_name,
        brief_date=title_date,
        status_message=status_message,
        tables=tables,
    )


def export_account_bill_placeholder_html(*, account: Any, output_path: Path) -> Path:
    html_text = _render_account_bill_html(
        account_name=str(account.name),
        brief_date="",
        status_message="暂无确认账单。模拟账户账单只在本地日线库已有对应执行日 OHLCV 后生成；当前页面不推导未确认收益。",
        tables=[],
    )
    return _write_account_bill_html(output_path, html_text)


def export_account_bill_pending_html(
    *,
    account: Any,
    brief_date: str,
    output_path: Path,
    latest_confirmed_date: str = "",
) -> Path:
    from phase0.execution.accounts import price_mode_label

    price_mode = str(getattr(account, "execution_price_mode", "next_open") or "next_open")
    latest_note = f"最近已确认账单日：{latest_confirmed_date}。" if latest_confirmed_date else "暂无更早的确认账单。"
    html_text = _render_account_bill_html(
        account_name=str(account.name),
        brief_date=str(brief_date),
        status_message=(
            f"{brief_date} 模拟交易账单待确认。当前账户使用“{price_mode_label(price_mode)}”口径，"
            "本地日线库尚未具备该账单日所需的执行价 OHLCV，因此不生成未确认收益和成交明细。"
            f"{latest_note}"
        ),
        tables=[],
    )
    return _write_account_bill_html(output_path, html_text)


def export_account_bill_html(*, account: Any, brief_date: str, output_path: Path, status_message: str = "") -> Path:
    from phase0.execution.accounts import ensure_account_tables, price_mode_label

    with sqlite3.connect(account.database_path) as conn:
        ensure_account_tables(conn)
        account_rows = pd.read_sql_query(
            "SELECT account_id, name, initial_cash, execution_price_mode, max_participation_rate, lot_size FROM simulated_accounts WHERE account_id = ?",
            conn,
            params=(account.account_id,),
        )
        position_start_row = conn.execute(
            """
            SELECT MIN(brief_date)
            FROM account_positions
            WHERE account_id = ?
              AND shares > 0
            """,
            (account.account_id,),
        ).fetchone()
        trade_start_row = conn.execute(
            """
            SELECT MIN(brief_date)
            FROM account_trades
            WHERE account_id = ?
              AND side = 'buy'
              AND shares > 0
            """,
            (account.account_id,),
        ).fetchone()
        latest_confirmed_row = conn.execute(
            """
            SELECT MAX(brief_date)
            FROM account_daily_assets
            WHERE account_id = ?
              AND brief_date < ?
            """,
            (account.account_id, brief_date),
        ).fetchone()
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

    if assets.empty:
        latest_confirmed_date = str(latest_confirmed_row[0] or "") if latest_confirmed_row else ""
        return export_account_bill_pending_html(
            account=account,
            brief_date=str(brief_date),
            output_path=output_path,
            latest_confirmed_date=latest_confirmed_date,
        )

    if not account_rows.empty:
        account_rows = account_rows.copy()
        position_start_date = str(position_start_row[0] or trade_start_row[0] or "暂无")
        account_rows["position_start_date"] = position_start_date
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

    money_columns = {"initial_cash", "total_asset", "stock_asset", "cash_asset", "daily_pnl", "estimated_trade_amount", "price", "amount", "cost", "close", "market_value"}
    quantity_columns = {"raw_shares", "shares", "lots", "lot_size", "estimated_volume"}
    pct_columns = {"max_participation_rate", "daily_return", "target_exposure", "weight_before", "weight_after", "weight_change", "target_weight"}
    right_columns = money_columns | quantity_columns | pct_columns
    html_text = _render_account_bill_html(
        account_name=str(account.name),
        brief_date=str(brief_date),
        status_message=status_message,
        tables=[
            {
                "title": "账户总览",
                "data": _table_context(
                    account_rows,
                    [
                        ("account_id", "账户ID"),
                        ("name", "账户名称"),
                        ("initial_cash", "初始资产"),
                        ("position_start_date", "建仓日"),
                        ("execution_price_mode", "成交价口径"),
                        ("max_participation_rate", "最大成交参与率"),
                        ("lot_size", "每手股数"),
                    ],
                    right_columns=right_columns,
                    center_columns={"account_id", "position_start_date", "execution_price_mode"},
                ),
            },
            {
                "title": "每日资产",
                "data": _table_context(
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
                    right_columns=right_columns,
                    center_columns={"brief_date", "start_date"},
                ),
            },
            {
                "title": "交易明细",
                "data": _table_context(
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
                    right_columns=right_columns,
                    center_columns={"symbol", "side", "signal_date", "trade_time", "price_mode", "rounding_rule"},
                ),
            },
            {
                "title": "持仓快照",
                "data": _table_context(
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
                    right_columns=right_columns,
                    center_columns={"symbol"},
                ),
            },
        ],
    )
    return _write_account_bill_html(output_path, html_text)
