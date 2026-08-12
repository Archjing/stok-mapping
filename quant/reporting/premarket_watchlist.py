from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
import numpy as np
import pandas as pd

from quant.config import load_config
from quant.data_access.local_history import configure_local_history
from quant.data_governance.external_market_history import configure_us_market_history
from quant.execution.accounts import (
    SimulatedAccountConfig,
    build_account_ledger,
    load_simulated_accounts,
    price_mode_label,
)
from quant.execution.strategy_ledger import execution_settings, limit_pct
from quant.reporting.account_bill import export_account_bill_html, load_latest_account_snapshot
from quant.reporting.paths import report_config_path
from quant.research.metrics import calc_metrics as _calc_metrics
from quant.strategies import get_strategy
from quant.walk_forward import _resolve_walk_forward_window
from quant.reporting.strategy_bill import (
    DEFAULT_PANEL_CACHE,
    _load_names,
    _load_or_build_panel,
    _panel_cache_key,
    _parse_symbol_list,
    _resolve_path,
)


DEFAULT_WATCHLIST_OUTPUT = "phase0_premarket_watchlist.csv"
DEFAULT_REPORT_OUTPUT = "phase0_premarket_report.html"
DEFAULT_SIMULATION_LEDGER = "data/simulated_trading/phase0_daily_brief_ledger.csv"
WATCHLIST_TEMPLATE_DIR = Path(__file__).with_name("templates")
WATCHLIST_STATIC_DIR = Path(__file__).with_name("static")
WATCHLIST_TEMPLATE_NAME = "watchlist.html"
WATCHLIST_STATIC_ASSETS = ("style.css",)
WATCHLIST_STYLESHEET_NAME = WATCHLIST_STATIC_ASSETS[0]
STRATEGY_DISPLAY_NAMES = {
    "legacy_momentum_low_turnover_v1": "低换手经典动量",
}
STRATEGY_SHORT_DESCRIPTIONS = {
    "legacy_momentum_low_turnover_v1": (
        "当前采用低换手经典动量策略：仍以动量强弱选股，但买入更严格、持有更宽容，"
        "通过持有区间、周期调仓、最短持有天数和换手惩罚减少来回换股。"
    ),
}
WATCHLIST_RIGHT_ALIGNED_HEADERS = {"收盘价"}
WATCHLIST_CENTER_ALIGNED_NUMERIC_HEADERS = {
    "当前权重",
    "目标权重",
    "权重变化",
    "动量分数",
    "当日排名",
    "持仓天数",
    "信号持有天数",
    "最大成交参与率",
}


def _default_strategy_id(config: dict[str, Any]) -> str:
    reports_cfg = config.get("strategy_reports", {}) or {}
    return str(reports_cfg.get("default_strategy_id") or "legacy_momentum_low_turnover_v1")


def _select_simulated_account(accounts: list[SimulatedAccountConfig], account_id: str | None) -> SimulatedAccountConfig | None:
    if not accounts:
        return None
    if not account_id:
        return accounts[0]
    for account in accounts:
        if account.account_id == account_id:
            return account
    available = ", ".join(account.account_id for account in accounts) or "<none>"
    raise ValueError(f"simulated account {account_id!r} is not configured; available accounts: {available}")


def _account_execution_cfg(account: SimulatedAccountConfig | None, execution_cfg: dict[str, Any]) -> dict[str, Any]:
    if account is None:
        return execution_cfg
    resolved = dict(execution_cfg)
    resolved["price_mode"] = account.execution_price_mode
    resolved["max_participation_rate"] = account.max_participation_rate
    resolved["enable_limit_check"] = account.enable_limit_check
    resolved["enable_suspension_check"] = account.enable_suspension_check
    if account.limit_up_down_pct:
        resolved["limit_up_down_pct"] = dict(account.limit_up_down_pct)
    return resolved


def _resolve_output_template(root: Path, value: str | Path, summary: dict[str, Any]) -> Path:
    brief_date = str(summary["check_time"])[:10]
    formatted = str(value).format(
        brief_date=brief_date,
        signal_date=str(summary["signal_date"]),
    )
    return _resolve_path(root, formatted)


def _resolve_report_output_template(
    root: Path,
    config: dict[str, Any],
    value: str | Path,
    summary: dict[str, Any],
    *,
    default_category: str,
    explicit: bool,
) -> Path:
    brief_date = str(summary["check_time"])[:10]
    formatted = str(value).format(
        brief_date=brief_date,
        signal_date=str(summary["signal_date"]),
    )
    if explicit:
        return _resolve_path(root, formatted)
    return report_config_path(root=root, config=config, value=formatted, default_category=default_category)


def _format_pct(value: Any, digits: int = 2) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value) * 100:.{digits}f}%"


def _format_num(value: Any, digits: int = 4) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.{digits}f}"


def _format_price(value: Any) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.2f}"


def _format_money(value: Any) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):,.2f}"


def _format_volume(value: Any) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):,.0f}"


def _display_cell(header: str, value: Any) -> str:
    text = str(value)
    if header == "成交价口径":
        return price_mode_label(text)
    if header == "执行风险提示":
        summary, _detail = _split_risk_note(text)
        return summary
    if header == "观察理由":
        labels = {
            "动量分数超过买入阈值": "强势达标",
            "动量分数跌破持有阈值": "动量转弱",
        }
        parts = [labels.get(part, part) for part in text.split("；")]
        return "；".join(parts)
    return text


def _cell_title(header: str, value: Any, display_value: str) -> str:
    text = str(value)
    if header == "执行风险提示":
        _summary, detail = _split_risk_note(text)
        return detail
    if header == "观察理由" and text != display_value:
        return text
    return ""


def _split_risk_note(text: str) -> tuple[str, str]:
    raw = str(text)
    for sep in ("，", "；", ",", ";"):
        if sep in raw:
            head, tail = raw.split(sep, 1)
            return head.strip(), tail.strip()
    return raw.strip(), ""


def _watchlist_cell_class(header: str) -> str:
    if header in WATCHLIST_RIGHT_ALIGNED_HEADERS:
        return "num-right"
    if header in WATCHLIST_CENTER_ALIGNED_NUMERIC_HEADERS:
        return "num-center"
    return ""


def _watchlist_template_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(WATCHLIST_TEMPLATE_DIR),
        autoescape=select_autoescape(("html", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _copy_watchlist_assets(html_path: Path) -> None:
    for asset_name in WATCHLIST_STATIC_ASSETS:
        asset = WATCHLIST_STATIC_DIR / asset_name
        if asset.exists():
            shutil.copyfile(asset, html_path.parent / asset_name)


def _parse_pct(value: Any) -> float:
    if pd.isna(value):
        return 0.0
    raw = str(value).strip().replace("%", "")
    if not raw:
        return 0.0
    try:
        return float(raw) / 100.0
    except ValueError:
        return 0.0


def _weight_action(current_weight: float, target_weight: float) -> str:
    if current_weight <= 1e-12 and target_weight > 1e-12:
        return "关注买入"
    if current_weight > 1e-12 and target_weight <= 1e-12:
        return "关注卖出"
    if target_weight > current_weight + 1e-4:
        return "关注加仓"
    if target_weight < current_weight - 1e-4:
        return "关注减仓"
    if current_weight > 1e-12:
        return "继续持有"
    return "候选观察"


def _trade_action(row: pd.Series) -> str:
    current_weight = float(row.get("weight", 0.0) or 0.0)
    target_weight = float(row.get("weight_unshifted", 0.0) or 0.0)
    return _weight_action(current_weight, target_weight)


def _simulation_note(row: pd.Series, previous_source: str) -> str:
    action = str(row.get("sim_trade_action", ""))
    current_weight = float(row.get("sim_current_weight", 0.0) or 0.0)
    target_weight = float(row.get("sim_target_weight", 0.0) or 0.0)
    source = previous_source or "本次策略信号"
    if action in {"关注买入", "关注加仓"}:
        return f"连续模拟从{source}持仓{_format_pct(current_weight)}调整到{_format_pct(target_weight)}"
    if action in {"关注卖出", "关注减仓"}:
        return f"连续模拟从{source}持仓{_format_pct(current_weight)}调整到{_format_pct(target_weight)}"
    if action == "继续持有":
        return f"连续模拟维持{_format_pct(target_weight)}目标仓位"
    return "未进入连续模拟持仓，仅保留观察"


def _trade_reason(row: pd.Series, params: dict[str, Any]) -> str:
    action = str(row.get("sim_trade_action") or _trade_action(row))
    score = row.get("score")
    rank = row.get("rank")
    held_days = row.get("strategy_held_days", row.get("held_days"))
    buy_top_n = int(params.get("buy_top_n", 0) or 0)
    hold_top_n = int(params.get("hold_top_n", 0) or 0)
    buy_threshold = float(params.get("buy_threshold", np.nan))
    hold_threshold = float(params.get("hold_threshold", np.nan))

    parts: list[str] = []
    if action in {"关注买入", "关注加仓", "候选观察"}:
        if pd.notna(rank) and buy_top_n and float(rank) <= buy_top_n:
            parts.append(f"排名进入买入前{buy_top_n}")
        if pd.notna(score) and pd.notna(buy_threshold) and float(score) > buy_threshold:
            parts.append("动量分数超过买入阈值")
    if action in {"关注卖出", "关注减仓"}:
        if pd.isna(score) or pd.isna(rank):
            parts.append("最新交易日无有效信号")
        else:
            if pd.notna(score) and pd.notna(hold_threshold) and float(score) <= hold_threshold:
                parts.append("动量分数跌破持有阈值")
            if hold_top_n and pd.notna(rank) and float(rank) > hold_top_n:
                parts.append(f"排名跌出持有前{hold_top_n}")
        if pd.notna(held_days):
            parts.append(f"策略信号已持有{int(held_days)}个交易日")
    if action == "继续持有":
        parts.append("仍在持有观察区内")
        if pd.notna(held_days):
            parts.append(f"策略信号已持有{int(held_days)}个交易日")
    if not parts:
        parts.append("未触发交易，仅保留观察")
    return "；".join(parts)


def _execution_risk_note(row: pd.Series, execution_cfg: dict[str, Any]) -> str:
    notes: list[str] = []
    close_price = row.get("close")
    previous_close = row.get("previous_close")
    volume = row.get("volume")
    amount = row.get("amount")
    action = str(row.get("sim_trade_action") or _trade_action(row))

    if bool(execution_cfg.get("enable_suspension_check", True)):
        if pd.isna(close_price) or float(close_price) <= 0:
            notes.append("无有效收盘价，次日需人工复核")
        if pd.notna(volume) and float(volume) <= 0:
            notes.append("最近一日成交量为0，可能停牌或流动性异常")
        if pd.notna(amount) and float(amount) <= 0:
            notes.append("最近一日成交额为0，可能停牌或流动性异常")

    if bool(execution_cfg.get("enable_limit_check", True)) and pd.notna(close_price) and pd.notna(previous_close) and float(previous_close) > 0:
        daily_limit_pct = limit_pct(str(row.get("symbol", "")), execution_cfg)
        limit_up = float(previous_close) * (1.0 + daily_limit_pct)
        limit_down = float(previous_close) * (1.0 - daily_limit_pct)
        tolerance = 0.001
        if ("买" in action or "加仓" in action) and float(close_price) >= limit_up * (1.0 - tolerance):
            notes.append("接近/触及涨停，买入可能无法成交")
        if ("卖" in action or "减仓" in action) and float(close_price) <= limit_down * (1.0 + tolerance):
            notes.append("接近/触及跌停，卖出可能无法成交")

    if not notes:
        notes.append("未发现明显执行阻碍，仍需开盘确认价格和成交量")
    return "；".join(dict.fromkeys(notes))


def _next_trade_date(db_path: Path, signal_date: pd.Timestamp) -> str:
    fallback = (signal_date + pd.Timedelta(days=1)).date().isoformat()
    if not db_path.exists():
        return fallback
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT MIN(date) FROM trading_calendar WHERE is_open = 1 AND date > ?",
                (signal_date.date().isoformat(),),
            ).fetchone()
    except sqlite3.Error:
        return fallback
    return str(row[0]) if row and row[0] else fallback


def _latest_trade_date(db_path: Path) -> str:
    if not db_path.exists():
        return ""
    today = pd.Timestamp.today().date().isoformat()
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT MAX(date) FROM trading_calendar WHERE is_open = 1 AND date <= ?",
                (today,),
            ).fetchone()
    except sqlite3.Error:
        return ""
    return str(row[0]) if row and row[0] else ""


def _load_previous_sim_positions(
    root: Path,
    brief_date: str,
    ledger_path: Path,
    *,
    simulation_start_date: str = "",
    account_id: str = "",
    strategy_id: str = "",
) -> tuple[dict[str, float], str]:
    if ledger_path.exists():
        try:
            ledger = pd.read_csv(ledger_path, encoding="utf-8-sig")
        except Exception:
            ledger = pd.DataFrame()
        if not ledger.empty and {"brief_date", "symbol", "target_weight"}.issubset(ledger.columns):
            prior = ledger[ledger["brief_date"].astype(str) < brief_date].copy()
            if simulation_start_date:
                prior = prior[prior["brief_date"].astype(str) >= simulation_start_date].copy()
            if account_id and "account_id" in prior.columns:
                prior = prior[prior["account_id"].astype(str) == account_id].copy()
            elif account_id and account_id != "default":
                prior = prior.iloc[0:0].copy()
            if strategy_id and "strategy_id" in prior.columns:
                prior = prior[prior["strategy_id"].astype(str) == strategy_id].copy()
            if not prior.empty:
                source_date = str(prior["brief_date"].max())
                latest = prior[prior["brief_date"].astype(str) == source_date].copy()
                latest["target_weight"] = pd.to_numeric(latest["target_weight"], errors="coerce").fillna(0.0)
                return dict(zip(latest["symbol"].astype(str), latest["target_weight"].astype(float), strict=False)), source_date

    report_root = root / "reports"
    candidates: list[tuple[str, Path]] = []
    if report_root.exists():
        for path in report_root.glob("????-??-??/phase0_premarket_watchlist*.csv"):
            report_date = path.parent.name
            if simulation_start_date and report_date < simulation_start_date:
                continue
            if report_date < brief_date:
                candidates.append((report_date, path))
    for source_date, path in sorted(candidates, reverse=True):
        try:
            previous = pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            continue
        if previous.empty or "股票代码" not in previous.columns:
            continue
        if account_id and "账户ID" in previous.columns:
            account_values = {str(value) for value in previous["账户ID"].dropna().astype(str).unique()}
            if account_values and account_id not in account_values:
                continue
        elif account_id and account_id != "default":
            continue
        if strategy_id and "策略ID" in previous.columns:
            strategy_values = {str(value) for value in previous["策略ID"].dropna().astype(str).unique()}
            if strategy_values and strategy_id not in strategy_values:
                continue
        weight_col = "目标权重"
        for candidate_col in ("模拟账户目标权重", "模拟目标权重"):
            if candidate_col in previous.columns:
                weight_col = candidate_col
                break
        if weight_col not in previous.columns:
            continue
        weights = previous[weight_col].map(_parse_pct)
        return dict(zip(previous["股票代码"].astype(str), weights.astype(float), strict=False)), source_date
    return {}, ""


def _load_confirmed_account_positions(account: Any, brief_date: str) -> tuple[dict[str, float], str, bool]:
    if not account or not getattr(account, "database_path", Path("")).exists():
        return {}, "", False
    try:
        from quant.execution.accounts import ensure_account_tables

        with sqlite3.connect(account.database_path) as conn:
            ensure_account_tables(conn)
            row = conn.execute(
                """
                SELECT MAX(brief_date)
                FROM account_daily_assets
                WHERE account_id = ?
                  AND brief_date < ?
                """,
                (account.account_id, brief_date),
            ).fetchone()
            source_date = str(row[0]) if row and row[0] else ""
            if not source_date:
                return {}, "", False
            position_rows = conn.execute(
                """
                SELECT symbol, target_weight
                FROM account_positions
                WHERE account_id = ?
                  AND brief_date = ?
                  AND shares > 0
                """,
                (account.account_id, source_date),
            ).fetchall()
    except sqlite3.Error:
        return {}, "", False
    weights = {str(symbol): float(weight or 0.0) for symbol, weight in position_rows}
    return weights, f"确认账单{source_date}", True


def _load_account_holding_days(account: Any, brief_date: str) -> dict[str, int]:
    if not account or not getattr(account, "database_path", Path("")).exists():
        return {}
    try:
        from quant.execution.accounts import ensure_account_tables

        with sqlite3.connect(account.database_path) as conn:
            ensure_account_tables(conn)
            account_dates = [
                str(row[0])
                for row in conn.execute(
                    """
                    SELECT brief_date
                    FROM account_daily_assets
                    WHERE account_id = ?
                      AND brief_date < ?
                    ORDER BY brief_date
                    """,
                    (account.account_id, brief_date),
                ).fetchall()
            ]
            if not account_dates:
                return {}
            position_rows = conn.execute(
                """
                SELECT symbol, brief_date
                FROM account_positions
                WHERE account_id = ?
                  AND brief_date < ?
                  AND shares > 0
                ORDER BY symbol, brief_date
                """,
                (account.account_id, brief_date),
            ).fetchall()
    except sqlite3.Error:
        return {}

    held_dates_by_symbol: dict[str, set[str]] = {}
    for symbol, position_date in position_rows:
        held_dates_by_symbol.setdefault(str(symbol), set()).add(str(position_date))

    holding_days: dict[str, int] = {}
    latest_date = account_dates[-1]
    for symbol, held_dates in held_dates_by_symbol.items():
        if latest_date not in held_dates:
            continue
        days = 0
        for account_date in reversed(account_dates):
            if account_date not in held_dates:
                break
            days += 1
        holding_days[symbol] = days
    return holding_days


def _write_simulation_ledger(
    *,
    path: Path,
    brief_date: str,
    signal_date: str,
    watchlist: pd.DataFrame,
    account_id: str = "",
    strategy_id: str = "",
) -> None:
    current_weight_col = "模拟账户当前权重" if "模拟账户当前权重" in watchlist.columns else "当前权重"
    target_weight_col = "模拟账户目标权重" if "模拟账户目标权重" in watchlist.columns else "目标权重"
    weight_change_col = "模拟账户权重变化" if "模拟账户权重变化" in watchlist.columns else "权重变化"
    action_col = "模拟账户动作" if "模拟账户动作" in watchlist.columns else ("动作" if "动作" in watchlist.columns else "交易动作")
    rows = pd.DataFrame(
        {
            "account_id": account_id,
            "strategy_id": strategy_id,
            "brief_date": brief_date,
            "signal_date": signal_date,
            "symbol": watchlist["股票代码"].astype(str),
            "name": watchlist["股票名称"].astype(str),
            "action": watchlist[action_col].astype(str),
            "current_weight": watchlist[current_weight_col].map(_parse_pct),
            "target_weight": watchlist[target_weight_col].map(_parse_pct),
            "weight_change": watchlist[weight_change_col].map(_parse_pct),
        }
    )
    rows = rows[(rows["current_weight"].abs() > 1e-12) | (rows["target_weight"].abs() > 1e-12)].copy()
    if path.exists():
        try:
            existing = pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            existing = pd.DataFrame()
    else:
        existing = pd.DataFrame()
    if not existing.empty and "brief_date" in existing.columns:
        same_brief_date = existing["brief_date"].astype(str) == brief_date
        if account_id and "account_id" in existing.columns:
            same_account = existing["account_id"].astype(str) == account_id
        else:
            same_account = pd.Series(True, index=existing.index)
        if strategy_id and "strategy_id" in existing.columns:
            same_strategy = existing["strategy_id"].astype(str) == strategy_id
        else:
            same_strategy = pd.Series(True, index=existing.index)
        existing = existing[~(same_brief_date & same_account & same_strategy)].copy()
    out = pd.concat([existing, rows], ignore_index=True) if not existing.empty else rows
    if not out.empty:
        sort_cols = [col for col in ["brief_date", "account_id", "strategy_id", "symbol"] if col in out.columns]
        out = out.sort_values(sort_cols).reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, encoding="utf-8-sig")


def _account_snapshot_context(rows: list[dict[str, Any]], meta: dict[str, Any]) -> dict[str, Any] | None:
    if not rows:
        return None
    headers = ["账单日期", "总资产", "股票资产", "现金资产", "执行价口径", "成交金额", "成交股数", "收益额", "说明"]
    return {
        "headers": headers,
        "rows": [[str(row.get(header, "")) for header in headers] for row in rows],
        "start_date": str(meta.get("start_date", "")),
        "initial_cash": _format_money(meta.get("initial_cash", np.nan)),
    }


def _build_account_snapshot_rows(
    *,
    summary: dict[str, Any],
    account_snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    if not account_snapshot:
        return []
    total_asset = float(account_snapshot.get("total_asset", 0.0) or 0.0)
    stock_asset = float(account_snapshot.get("stock_asset", 0.0) or 0.0)
    cash_asset = float(account_snapshot.get("cash_asset", 0.0) or 0.0)
    daily_pnl = float(account_snapshot.get("daily_pnl", 0.0) or 0.0)
    estimated_trade_amount = float(account_snapshot.get("estimated_trade_amount", 0.0) or 0.0)
    estimated_volume = float(account_snapshot.get("estimated_volume", 0.0) or 0.0)
    price_mode = str(account_snapshot.get("execution_price_mode", ""))
    snapshot_date = str(account_snapshot.get("brief_date", ""))
    current_brief_date = str(summary.get("brief_date", ""))
    note = "最近已确认模拟执行"
    if snapshot_date and current_brief_date and snapshot_date != current_brief_date:
        note = f"当前观察池尚未确认成交，显示最近已确认账单 {snapshot_date}"
    return [
        {
            "账单日期": snapshot_date,
            "总资产": _format_money(total_asset),
            "股票资产": _format_money(stock_asset),
            "现金资产": _format_money(cash_asset),
            "执行价口径": price_mode_label(price_mode or "next_open"),
            "成交金额": _format_money(estimated_trade_amount),
            "成交股数": _format_volume(estimated_volume),
            "收益额": _format_money(daily_pnl),
            "说明": note,
        }
    ]


def _account_summary_cards(account_snapshot: dict[str, Any], *, initial_cash: float | None = None) -> list[tuple[str, str]]:
    if not account_snapshot:
        cash = float(initial_cash) if initial_cash is not None and pd.notna(initial_cash) else np.nan
        return [
            ("总资产（元）", _format_money(cash)),
            ("可用资金（元）", _format_money(cash)),
            ("持仓市值（元）", _format_money(0.0)),
            ("当前仓位（%）", _format_pct(0.0)),
            ("当前收益率（%）", "暂无"),
        ]
    total_asset = float(account_snapshot.get("total_asset", np.nan))
    stock_asset = float(account_snapshot.get("stock_asset", np.nan))
    cash_asset = float(account_snapshot.get("cash_asset", np.nan))
    position_pct = float(account_snapshot.get("target_exposure", np.nan))
    current_return = float(account_snapshot.get("daily_return", np.nan))
    return [
        ("总资产（元）", _format_money(total_asset)),
        ("可用资金（元）", _format_money(cash_asset)),
        ("持仓市值（元）", _format_money(stock_asset)),
        ("当前仓位（%）", _format_pct(position_pct)),
        ("当前收益率（%）", _format_pct(current_return)),
    ]


def _format_html(watchlist: pd.DataFrame, summary: dict[str, Any]) -> str:
    headers = [
        "动作",
        "信号动作",
        "股票代码",
        "股票名称",
        "收盘价",
        "当前权重",
        "目标权重",
        "权重变化",
        "持仓天数",
        "动量分数",
        "当日排名",
        "信号持有天数",
        "成交价口径",
        "最大成交参与率",
        "执行风险提示",
        "账户说明",
        "观察理由",
    ]
    header_tips = {
        "动作": "当前模拟账户口径：根据账户上一确认持仓与本期目标持仓计算今天的计划调仓行为。",
        "信号动作": "策略研究信号口径：表示策略模型根据最新信号给出的目标状态变化，不等同于最终交易指令。",
        "当前权重": "当前模拟账户口径：账户上一确认持仓对应权重；新账户未买入时为 0。",
        "目标权重": "当前模拟账户口径：按本期策略目标生成的计划目标权重。",
        "权重变化": "当前模拟账户口径：目标权重减当前权重。",
        "持仓天数": "当前模拟账户真实持仓口径：按已确认账户持仓记录连续计数；新账户未买入时为 0。",
        "信号持有天数": "策略研究信号口径：策略内部为低换手和最短持有期维护的目标组合持有天数，不等同于账户真实持仓天数。",
        "成交价口径": "执行假设使用的成交价格口径：执行日收盘价、执行日开盘价或执行日开盘保守价。",
        "最大成交参与率": "流动性约束：单只股票交易量最多参与市场成交量的比例。",
        "执行风险提示": "根据价格、成交量、成交额和涨跌停状态提示次日可能的成交障碍。",
        "账户说明": "解释本次动作如何从上一期模拟账户持仓滚动到本期目标持仓。",
        "观察理由": "说明股票进入观察池或触发买入、卖出、持有、候选观察的主要信号原因。",
    }
    rows = []
    for _, row in watchlist.iterrows():
        action = str(row["动作"])
        cls = ""
        if "买" in action or "加仓" in action:
            cls = ' class="buy"'
        elif "卖" in action or "减仓" in action:
            cls = ' class="sell"'
        elif "持有" in action:
            cls = ' class="hold"'
        cells = []
        for header in headers:
            raw_value = row.get(header, "")
            display_value = _display_cell(header, raw_value)
            title = _cell_title(header, raw_value, display_value)
            cell_class = _watchlist_cell_class(header)
            cells.append({"class": cell_class, "title": title, "value": display_value})
        rows.append({"class": cls.removeprefix(' class="').removesuffix('"') if cls else "", "cells": cells})

    summary_cards = [
        {"label": label, "value": str(value), "accent": ""}
        for label, value in [
            ("当前策略", summary.get("strategy_display_name", "")),
            ("信号日期", summary.get("signal_date", "")),
            ("盘前检查时间", summary.get("check_time", "")),
            ("观察股票数", summary.get("watchlist_rows", 0)),
            *summary.get("account_summary_cards", []),
            ("当前总暴露", _format_pct(summary.get("current_exposure", 0.0))),
            ("目标总暴露", _format_pct(summary.get("target_exposure", 0.0))),
            ("买入/加仓", summary.get("buy_or_add_rows", 0)),
            ("卖出/减仓", summary.get("sell_or_reduce_rows", 0)),
            ("训练窗 Sharpe", _format_num(summary.get("train_sharpe", 0.0))),
        ]
    ]
    account_snapshot = _account_snapshot_context(
        summary.get("account_snapshot_rows", []),
        summary.get("account_snapshot_meta", {}),
    )
    template = _watchlist_template_env().get_template(WATCHLIST_TEMPLATE_NAME)
    return template.render(
        stylesheet_href=WATCHLIST_STYLESHEET_NAME,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        strategy_description=str(summary.get("strategy_description", "")),
        summary_cards=summary_cards,
        account_snapshot=account_snapshot,
        headers=headers,
        header_tips=header_tips,
        rows=rows,
    )


def export_premarket_watchlist(
    *,
    config_path: Path,
    output: str | Path | None = None,
    report_output: str | Path | None = None,
    latest_report_output: str | Path | None = None,
    panel_cache: str | Path | None = None,
    refresh_cache: bool = False,
    no_panel_cache: bool = False,
    top_candidates: int = 20,
    training_days: int | None = None,
    simulation_ledger: str | Path = DEFAULT_SIMULATION_LEDGER,
    account_id: str | None = None,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    root = Path.cwd()
    config_path = _resolve_path(root, config_path)
    config = load_config(config_path)
    explicit_output = output is not None
    explicit_report_output = report_output is not None
    explicit_panel_cache = panel_cache is not None
    output = output or DEFAULT_WATCHLIST_OUTPUT
    report_output = report_output or DEFAULT_REPORT_OUTPUT
    panel_cache = panel_cache or DEFAULT_PANEL_CACHE
    configure_local_history(config.get("local_history", {}), root)
    configure_us_market_history(config.get("us_market_history", {}), root)

    wcfg = config["walk_forward"]
    execution_cfg = execution_settings(config)
    strategy_cfg = dict(wcfg.get("strategy_v2", {}))
    accounts = load_simulated_accounts(config, root)
    account = _select_simulated_account(accounts, account_id)
    strategy_id = account.strategy_id if account else _default_strategy_id(config)
    account_execution_cfg = _account_execution_cfg(account, execution_cfg)
    symbols = _parse_symbol_list(config, root)
    history_years = int(config["years"])
    cache_path = (
        _resolve_path(root, panel_cache)
        if explicit_panel_cache
        else report_config_path(root=root, config=config, value=panel_cache, default_category="runs")
    )
    db_path = _resolve_path(root, config.get("local_history", {}).get("path", ""))
    panel_as_of_date = str(as_of_date or _latest_trade_date(db_path))
    use_strict_panel_asof = bool(as_of_date)
    panel = _load_or_build_panel(
        cache_path=cache_path,
        refresh_cache=bool(refresh_cache),
        no_panel_cache=bool(no_panel_cache),
        cache_key=_panel_cache_key(
            config_path=config_path,
            config=config,
            root=root,
            symbols=symbols,
            history_years=history_years,
            strategy_cfg=strategy_cfg,
            as_of_date=panel_as_of_date,
            use_strict_asof=use_strict_panel_asof,
            price_adjustment="qfq_current",
        ),
        symbols=symbols,
        history_years=history_years,
        strategy_cfg=strategy_cfg,
        as_of_date=panel_as_of_date,
        use_strict_asof=use_strict_panel_asof,
        price_adjustment="qfq_current",
    )
    if as_of_date:
        panel = panel.copy()
        panel["date"] = pd.to_datetime(panel["date"])
        panel = panel[panel["date"] <= pd.Timestamp(as_of_date)].copy()
    if panel.empty:
        raise ValueError("market panel is empty; cannot export premarket watchlist")

    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"])
    dates = pd.Series(sorted(panel["date"].dropna().unique()))
    window_cfg = _resolve_walk_forward_window(wcfg)
    train_len = int(training_days or int(window_cfg["train_years"]) * 252)
    min_samples = int(wcfg.get("min_samples", 200))
    if len(dates) < max(min_samples, train_len):
        raise ValueError("not enough market history to select premarket parameters")

    train_dates = set(dates.iloc[-train_len:])
    train = panel[panel["date"].isin(train_dates)].copy()
    strategy = get_strategy(strategy_id)
    params = strategy.select_params(
        train,
        strategy_cfg,
        slippage=float(wcfg["slippage"]),
        commission=float(wcfg["commission"]),
        stamp_duty_sell=float(wcfg["stamp_duty_sell"]),
    )
    output_obj = strategy.apply(
        train,
        params,
        slippage=float(wcfg["slippage"]),
        commission=float(wcfg["commission"]),
        stamp_duty_sell=float(wcfg["stamp_duty_sell"]),
    )
    metric = _calc_metrics(output_obj.returns, output_obj.exposure)
    signal = output_obj.signal_frame.copy()
    signal["date"] = pd.to_datetime(signal["date"])
    signal_date = signal["date"].max()
    latest = signal[signal["date"] == signal_date].copy()
    latest["symbol"] = latest["symbol"].astype(str)
    price_cols = [col for col in ["date", "symbol", "open", "high", "low", "close", "volume", "amount"] if col in train.columns]
    prices = train[price_cols].copy().drop_duplicates(["date", "symbol"])
    prices["date"] = pd.to_datetime(prices["date"])
    prices["symbol"] = prices["symbol"].astype(str)
    if "close" in prices.columns:
        prices = prices.sort_values(["symbol", "date"])
        prices["previous_close"] = prices.groupby("symbol")["close"].shift(1)
    latest = latest.merge(prices, on=["date", "symbol"], how="left")
    check_time = f"{_next_trade_date(db_path, signal_date)} 07:30"
    brief_date = check_time[:10]
    ledger_path = _resolve_path(root, simulation_ledger)
    confirmed_positions, confirmed_source, has_confirmed_positions = _load_confirmed_account_positions(account, brief_date)
    if has_confirmed_positions:
        previous_positions, previous_source = confirmed_positions, confirmed_source
    else:
        previous_positions, previous_source = _load_previous_sim_positions(
            root,
            brief_date,
            ledger_path,
            simulation_start_date=account.simulation_start_date if account else "",
            account_id=account.account_id if account else "",
            strategy_id=strategy_id,
        )
    account_holding_days = _load_account_holding_days(account, brief_date) if account else {}

    missing_previous = sorted(set(previous_positions) - set(latest["symbol"].astype(str)))
    if missing_previous:
        missing_rows = pd.DataFrame({"date": signal_date, "symbol": missing_previous})
        latest = pd.concat([latest, missing_rows], ignore_index=True, sort=False)
    names = _load_names(db_path, sorted(set(latest["symbol"].astype(str)) | set(previous_positions)))

    latest["current_weight"] = latest["weight"].fillna(0.0).astype(float)
    latest["target_weight"] = latest.get("weight_unshifted", latest["current_weight"]).fillna(0.0).astype(float)
    latest["weight_change"] = latest["target_weight"] - latest["current_weight"]
    latest["trade_action"] = latest.apply(_trade_action, axis=1)
    if previous_positions:
        latest["sim_current_weight"] = latest["symbol"].astype(str).map(previous_positions).fillna(0.0).astype(float)
    else:
        latest["sim_current_weight"] = 0.0 if account and account.simulation_start_date else latest["current_weight"]
    latest["sim_target_weight"] = latest["target_weight"]
    latest["sim_weight_change"] = latest["sim_target_weight"] - latest["sim_current_weight"]
    latest["sim_trade_action"] = latest.apply(
        lambda row: _weight_action(float(row["sim_current_weight"]), float(row["sim_target_weight"])),
        axis=1,
    )
    latest["account_holding_days"] = latest["symbol"].astype(str).map(account_holding_days).fillna(0).astype(int)
    latest["strategy_held_days"] = latest["held_days"]
    latest["trade_reason"] = latest.apply(lambda row: _trade_reason(row, params), axis=1)
    latest["execution_risk_note"] = latest.apply(lambda row: _execution_risk_note(row, account_execution_cfg), axis=1)
    latest["simulation_note"] = latest.apply(lambda row: _simulation_note(row, previous_source), axis=1)

    candidates = latest[
        (latest["sim_current_weight"] > 0)
        | (latest["sim_target_weight"] > 0)
        | (latest["rank"].fillna(np.inf).astype(float) <= int(top_candidates))
    ].copy()
    candidates = candidates.sort_values(
        ["sim_target_weight", "sim_current_weight", "rank", "symbol"],
        ascending=[False, False, True, True],
    )

    watchlist = pd.DataFrame(
        {
            "账户ID": account.account_id if account else "",
            "账户名称": account.name if account else "",
            "策略ID": strategy_id,
            "信号日期": candidates["date"].dt.date.astype(str),
            "盘前检查时间": check_time,
            "动作": candidates["sim_trade_action"],
            "信号动作": candidates["trade_action"],
            "股票代码": candidates["symbol"].astype(str),
            "股票名称": candidates["symbol"].astype(str).map(names).fillna(""),
            "收盘价": candidates["close"].map(_format_price) if "close" in candidates.columns else "",
            "当前权重": candidates["sim_current_weight"].map(_format_pct),
            "目标权重": candidates["sim_target_weight"].map(_format_pct),
            "权重变化": candidates["sim_weight_change"].map(_format_pct),
            "持仓天数": candidates["account_holding_days"].map(lambda value: str(int(value))),
            "动量分数": candidates["score"].map(lambda value: _format_num(value, 4)),
            "当日排名": candidates["rank"].map(lambda value: "" if pd.isna(value) else str(int(value))),
            "信号持有天数": candidates["strategy_held_days"].map(lambda value: "" if pd.isna(value) else str(int(value))),
            "成交价口径": str(account_execution_cfg.get("price_mode", "next_open")),
            "最大成交参与率": _format_pct(float(account_execution_cfg.get("max_participation_rate", 0.0)), 2),
            "执行风险提示": candidates["execution_risk_note"],
            "账户说明": candidates["simulation_note"],
            "观察理由": candidates["trade_reason"],
            "策略参数": strategy.format_params(params),
        }
    )

    summary = {
        "account_id": account.account_id if account else "",
        "account_name": account.name if account else "",
        "signal_date": signal_date.date().isoformat(),
        "check_time": check_time,
        "brief_date": check_time[:10],
        "watchlist_rows": len(watchlist),
        "current_exposure": float(latest["sim_current_weight"].sum()),
        "target_exposure": float(latest["sim_target_weight"].sum()),
        "buy_or_add_rows": int(watchlist["动作"].astype(str).str.contains("买|加仓", regex=True).sum()),
        "sell_or_reduce_rows": int(watchlist["动作"].astype(str).str.contains("卖|减仓", regex=True).sum()),
        "previous_position_source": previous_source,
        "train_sharpe": float(metric["sharpe"]),
        "strategy_id": strategy_id,
        "strategy_display_name": STRATEGY_DISPLAY_NAMES.get(strategy_id, getattr(strategy, "display_name", strategy_id) or strategy_id),
        "strategy_description": STRATEGY_SHORT_DESCRIPTIONS.get(strategy_id, ""),
    }
    output_path = _resolve_report_output_template(
        root,
        config,
        output,
        summary,
        default_category="phase0",
        explicit=explicit_output,
    )
    report_path = _resolve_report_output_template(
        root,
        config,
        report_output,
        summary,
        default_category="phase0",
        explicit=explicit_report_output,
    )
    account_ledger_path = account.ledger_path if account else Path("")
    account_bill_path = Path("")
    _, rebuilt_account_snapshot = (
        build_account_ledger(
            root=root,
            current_watchlist=watchlist,
            current_brief_date=str(summary["brief_date"]),
            account=account,
            local_history_cfg=config.get("local_history", {}),
        )
        if account
        else (pd.DataFrame(), {})
    )
    account_snapshot = rebuilt_account_snapshot if rebuilt_account_snapshot else (load_latest_account_snapshot(account) if account else {})
    if account:
        bill_date = str(summary["brief_date"])
        account_bill_path = report_path.with_name("account_bill__report.html")
        account_bill_path.parent.mkdir(parents=True, exist_ok=True)
        export_account_bill_html(
            account=account,
            brief_date=bill_date,
            output_path=account_bill_path,
        )
    summary["account_snapshot_rows"] = _build_account_snapshot_rows(
        summary=summary,
        account_snapshot=account_snapshot,
    )
    summary["account_summary_cards"] = _account_summary_cards(
        account_snapshot,
        initial_cash=account.initial_cash if account else None,
    )
    summary["account_snapshot_meta"] = {
        "start_date": account_snapshot.get("start_date", ""),
        "initial_cash": account.initial_cash if account else np.nan,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    watchlist.to_csv(output_path, index=False, encoding="utf-8-sig")
    report_path.write_text(_format_html(watchlist, summary), encoding="utf-8")
    _copy_watchlist_assets(report_path)
    latest_report_path = Path("")
    if latest_report_output is not None:
        latest_report_path = _resolve_output_template(root, latest_report_output, summary)
        latest_report_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(report_path, latest_report_path)
        _copy_watchlist_assets(latest_report_path)
    _write_simulation_ledger(
        path=ledger_path,
        brief_date=brief_date,
        signal_date=signal_date.date().isoformat(),
        watchlist=watchlist,
        account_id=account.account_id if account else "",
        strategy_id=strategy_id,
    )
    return {
        "watchlist": output_path,
        "report": report_path,
        "latest_report": latest_report_path,
        "ledger": ledger_path,
        "account_ledger": account_ledger_path,
        "account_bill": account_bill_path,
        "account_id": account.account_id if account else "",
        "rows": len(watchlist),
        **summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--output", default=None)
    parser.add_argument("--report-output", default=None)
    parser.add_argument("--panel-cache", default=None)
    parser.add_argument("--account-id", default=None)
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--no-panel-cache", action="store_true")
    parser.add_argument("--top-candidates", type=int, default=20)
    parser.add_argument("--training-days", type=int, default=None)
    args = parser.parse_args()
    result = export_premarket_watchlist(
        config_path=Path(args.config),
        output=args.output,
        report_output=args.report_output,
        panel_cache=args.panel_cache,
        account_id=args.account_id,
        as_of_date=args.as_of_date,
        refresh_cache=bool(args.refresh_cache),
        no_panel_cache=bool(args.no_panel_cache),
        top_candidates=int(args.top_candidates),
        training_days=args.training_days,
    )
    print(f"watchlist={result['watchlist']}")
    print(f"report={result['report']}")
    print(f"rows={result['rows']}")
    print(f"signal_date={result['signal_date']}")
    print(f"check_time={result['check_time']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
