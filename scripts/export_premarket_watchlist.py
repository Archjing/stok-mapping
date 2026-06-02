from __future__ import annotations

import argparse
import html
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0.config import load_config
from phase0.external_market_history import configure_us_market_history
from phase0.local_history import configure_local_history
from phase0.strategies import get_strategy
from phase0.walk_forward import _calc_metrics
from scripts.export_low_turnover_bill import (
    DEFAULT_PANEL_CACHE,
    _execution_settings,
    _limit_pct,
    _load_names,
    _load_or_build_panel,
    _panel_cache_key,
    _parse_symbol_list,
    _resolve_path,
)


DEFAULT_WATCHLIST_OUTPUT = "reports/phase0_premarket_watchlist.csv"
DEFAULT_REPORT_OUTPUT = "reports/phase0_premarket_report.html"
DEFAULT_SIMULATION_LEDGER = "data/simulated_trading/phase0_daily_brief_ledger.csv"


def _resolve_output_template(root: Path, value: str | Path, summary: dict[str, Any]) -> Path:
    brief_date = str(summary["check_time"])[:10]
    formatted = str(value).format(
        brief_date=brief_date,
        signal_date=str(summary["signal_date"]),
    )
    return _resolve_path(root, formatted)


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
    held_days = row.get("held_days")
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
            parts.append(f"已持有{int(held_days)}个交易日")
    if action == "继续持有":
        parts.append("仍在持有观察区内")
        if pd.notna(held_days):
            parts.append(f"已持有{int(held_days)}个交易日")
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
        limit_pct = _limit_pct(str(row.get("symbol", "")), execution_cfg)
        limit_up = float(previous_close) * (1.0 + limit_pct)
        limit_down = float(previous_close) * (1.0 - limit_pct)
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


def _load_previous_sim_positions(root: Path, brief_date: str, ledger_path: Path) -> tuple[dict[str, float], str]:
    if ledger_path.exists():
        try:
            ledger = pd.read_csv(ledger_path, encoding="utf-8-sig")
        except Exception:
            ledger = pd.DataFrame()
        if not ledger.empty and {"brief_date", "symbol", "target_weight"}.issubset(ledger.columns):
            prior = ledger[ledger["brief_date"].astype(str) < brief_date].copy()
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
            if report_date < brief_date:
                candidates.append((report_date, path))
    for source_date, path in sorted(candidates, reverse=True):
        try:
            previous = pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            continue
        if previous.empty or "股票代码" not in previous.columns:
            continue
        weight_col = "目标权重"
        if "模拟目标权重" in previous.columns:
            weight_col = "模拟目标权重"
        if weight_col not in previous.columns:
            continue
        weights = previous[weight_col].map(_parse_pct)
        return dict(zip(previous["股票代码"].astype(str), weights.astype(float), strict=False)), source_date
    return {}, ""


def _write_simulation_ledger(
    *,
    path: Path,
    brief_date: str,
    signal_date: str,
    watchlist: pd.DataFrame,
) -> None:
    rows = pd.DataFrame(
        {
            "brief_date": brief_date,
            "signal_date": signal_date,
            "symbol": watchlist["股票代码"].astype(str),
            "name": watchlist["股票名称"].astype(str),
            "action": watchlist["交易动作"].astype(str),
            "current_weight": watchlist["当前权重"].map(_parse_pct),
            "target_weight": watchlist["目标权重"].map(_parse_pct),
            "weight_change": watchlist["权重变化"].map(_parse_pct),
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
        existing = existing[existing["brief_date"].astype(str) != brief_date].copy()
    out = pd.concat([existing, rows], ignore_index=True) if not existing.empty else rows
    if not out.empty:
        out = out.sort_values(["brief_date", "symbol"]).reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, encoding="utf-8-sig")


def _format_html(watchlist: pd.DataFrame, summary: dict[str, Any]) -> str:
    style = """
<style>
body {
  margin: 0;
  padding: 24px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #1f2937;
  background: #f5f7fb;
}
.page {
  max-width: 1280px;
  margin: 0 auto;
}
h1 {
  margin: 0 0 8px;
  font-size: 24px;
}
.title-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}
.title-row h1 {
  margin: 0;
}
.generated-at {
  color: #8b95a1;
  font-size: 13px;
}
p {
  margin: 0 0 16px;
  color: #4b5563;
}
.summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 10px;
  margin: 16px 0 18px;
}
.summary div {
  border: 1px solid #d0d7de;
  background: #fff;
  padding: 10px 12px;
}
.summary span {
  display: block;
  color: #6b7280;
  font-size: 12px;
}
.summary strong {
  display: block;
  margin-top: 4px;
  font-size: 16px;
}
.table-wrap {
  overflow: auto;
  max-height: 70vh;
  border: 1px solid #d0d7de;
  background: #fff;
}
table {
  width: max-content;
  min-width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
th,
td {
  border: 1px solid #d0d7de;
  padding: 7px 9px;
  white-space: nowrap;
}
th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #eef3f9;
  text-align: left;
}
.buy td {
  background: #eefaf1;
}
.sell td {
  background: #fff0f0;
}
.hold td {
  background: #f8fafc;
}
</style>
"""
    headers = [
        "信号日期",
        "盘前检查时间",
        "交易动作",
        "策略信号动作",
        "股票代码",
        "股票名称",
        "收盘价",
        "当前权重",
        "目标权重",
        "权重变化",
        "动量分数",
        "当日排名",
        "持有天数",
        "成交价口径",
        "最大成交参与率",
        "执行风险提示",
        "连续模拟说明",
        "观察理由",
    ]
    rows = []
    for _, row in watchlist.iterrows():
        action = str(row["交易动作"])
        cls = ""
        if "买" in action or "加仓" in action:
            cls = ' class="buy"'
        elif "卖" in action or "减仓" in action:
            cls = ' class="sell"'
        elif "持有" in action:
            cls = ' class="hold"'
        cells = [str(row.get(header, "")) for header in headers]
        rows.append(f"<tr{cls}>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in cells) + "</tr>")

    summary_cards = [
        ("信号日期", summary.get("signal_date", "")),
        ("盘前检查时间", summary.get("check_time", "")),
        ("观察股票数", summary.get("watchlist_rows", 0)),
        ("当前总暴露", _format_pct(summary.get("current_exposure", 0.0))),
        ("目标总暴露", _format_pct(summary.get("target_exposure", 0.0))),
        ("买入/加仓", summary.get("buy_or_add_rows", 0)),
        ("卖出/减仓", summary.get("sell_or_reduce_rows", 0)),
        ("训练窗 Sharpe", _format_num(summary.get("train_sharpe", 0.0))),
    ]
    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>Phase 0 Premarket Watchlist</title>\n"
        + style
        + "</head>\n<body>\n<div class=\"page\">\n"
        "<div class=\"title-row\"><h1>Phase 0 盘前观察池</h1>"
        f"<span class=\"generated-at\">生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</span></div>\n"
        "<p>基于最近一个已入库交易日收盘后的低换手动量信号生成，供次日 07:30 盘前检查持仓、候选和调仓关注项。</p>\n"
        "<div class=\"summary\">"
        + "".join(
            f"<div><span>{html.escape(label)}</span><strong>{html.escape(str(value))}</strong></div>"
            for label, value in summary_cards
        )
        + "</div>\n<div class=\"table-wrap\"><table><thead><tr>"
        + "".join(f"<th>{html.escape(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "\n".join(rows)
        + "</tbody></table></div>\n</div>\n</body>\n</html>\n"
    )


def export_premarket_watchlist(
    *,
    config_path: Path,
    output: str | Path = DEFAULT_WATCHLIST_OUTPUT,
    report_output: str | Path = DEFAULT_REPORT_OUTPUT,
    panel_cache: str | Path = DEFAULT_PANEL_CACHE,
    refresh_cache: bool = False,
    no_panel_cache: bool = False,
    top_candidates: int = 20,
    training_days: int | None = None,
    simulation_ledger: str | Path = DEFAULT_SIMULATION_LEDGER,
) -> dict[str, Any]:
    root = Path.cwd()
    config_path = _resolve_path(root, config_path)
    config = load_config(config_path)
    configure_local_history(config.get("local_history", {}), root)
    configure_us_market_history(config.get("us_market_history", {}), root)

    wcfg = config["walk_forward"]
    execution_cfg = _execution_settings(config)
    strategy_cfg = dict(wcfg.get("strategy_v2", {}))
    symbols = _parse_symbol_list(config, root)
    history_years = int(config["years"])
    cache_path = _resolve_path(root, panel_cache)
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
        ),
        symbols=symbols,
        history_years=history_years,
        strategy_cfg=strategy_cfg,
    )
    if panel.empty:
        raise ValueError("market panel is empty; cannot export premarket watchlist")

    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"])
    dates = pd.Series(sorted(panel["date"].dropna().unique()))
    train_len = int(training_days or int(wcfg["train_years"]) * 252)
    min_samples = int(wcfg.get("min_samples", 200))
    if len(dates) < max(min_samples, train_len):
        raise ValueError("not enough market history to select premarket parameters")

    train_dates = set(dates.iloc[-train_len:])
    train = panel[panel["date"].isin(train_dates)].copy()
    strategy = get_strategy("legacy_momentum_low_turnover_v1")
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
    db_path = _resolve_path(root, config.get("local_history", {}).get("path", ""))
    check_time = f"{_next_trade_date(db_path, signal_date)} 07:30"
    brief_date = check_time[:10]
    ledger_path = _resolve_path(root, simulation_ledger)
    previous_positions, previous_source = _load_previous_sim_positions(root, brief_date, ledger_path)

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
        latest["sim_current_weight"] = latest["current_weight"]
    latest["sim_target_weight"] = latest["target_weight"]
    latest["sim_weight_change"] = latest["sim_target_weight"] - latest["sim_current_weight"]
    latest["sim_trade_action"] = latest.apply(
        lambda row: _weight_action(float(row["sim_current_weight"]), float(row["sim_target_weight"])),
        axis=1,
    )
    latest["trade_reason"] = latest.apply(lambda row: _trade_reason(row, params), axis=1)
    latest["execution_risk_note"] = latest.apply(lambda row: _execution_risk_note(row, execution_cfg), axis=1)
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
            "信号日期": candidates["date"].dt.date.astype(str),
            "盘前检查时间": check_time,
            "交易动作": candidates["sim_trade_action"],
            "策略信号动作": candidates["trade_action"],
            "股票代码": candidates["symbol"].astype(str),
            "股票名称": candidates["symbol"].astype(str).map(names).fillna(""),
            "收盘价": candidates["close"].map(_format_price) if "close" in candidates.columns else "",
            "当前权重": candidates["sim_current_weight"].map(_format_pct),
            "目标权重": candidates["sim_target_weight"].map(_format_pct),
            "权重变化": candidates["sim_weight_change"].map(_format_pct),
            "动量分数": candidates["score"].map(lambda value: _format_num(value, 4)),
            "当日排名": candidates["rank"].map(lambda value: "" if pd.isna(value) else str(int(value))),
            "持有天数": candidates["held_days"].map(lambda value: "" if pd.isna(value) else str(int(value))),
            "成交价口径": str(execution_cfg.get("price_mode", "next_open")),
            "最大成交参与率": _format_pct(float(execution_cfg.get("max_participation_rate", 0.0)), 2),
            "执行风险提示": candidates["execution_risk_note"],
            "连续模拟说明": candidates["simulation_note"],
            "观察理由": candidates["trade_reason"],
            "策略参数": strategy.format_params(params),
        }
    )

    summary = {
        "signal_date": signal_date.date().isoformat(),
        "check_time": check_time,
        "brief_date": check_time[:10],
        "watchlist_rows": len(watchlist),
        "current_exposure": float(latest["sim_current_weight"].sum()),
        "target_exposure": float(latest["sim_target_weight"].sum()),
        "buy_or_add_rows": int(watchlist["交易动作"].astype(str).str.contains("买|加仓", regex=True).sum()),
        "sell_or_reduce_rows": int(watchlist["交易动作"].astype(str).str.contains("卖|减仓", regex=True).sum()),
        "previous_position_source": previous_source,
        "train_sharpe": float(metric["sharpe"]),
    }
    output_path = _resolve_output_template(root, output, summary)
    report_path = _resolve_output_template(root, report_output, summary)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    watchlist.to_csv(output_path, index=False, encoding="utf-8-sig")
    report_path.write_text(_format_html(watchlist, summary), encoding="utf-8")
    _write_simulation_ledger(
        path=ledger_path,
        brief_date=brief_date,
        signal_date=signal_date.date().isoformat(),
        watchlist=watchlist,
    )
    return {"watchlist": output_path, "report": report_path, "ledger": ledger_path, "rows": len(watchlist), **summary}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--output", default=DEFAULT_WATCHLIST_OUTPUT)
    parser.add_argument("--report-output", default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--panel-cache", default=DEFAULT_PANEL_CACHE)
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
