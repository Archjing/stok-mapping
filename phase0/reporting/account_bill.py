from __future__ import annotations

import html
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd


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


def export_account_bill_html(*, account: Any, brief_date: str, output_path: Path) -> Path:
    from phase0.execution.accounts import ensure_account_tables, price_mode_label

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
