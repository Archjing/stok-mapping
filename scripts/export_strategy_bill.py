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
from phase0.local_history import configure_local_history, load_daily_from_local_history
from phase0.reporting.paths import report_config_path
from phase0.strategies import get_strategy
from phase0.walk_forward import (
    _add_cross_market_to_panel,
    _align_symbol_map,
    _calc_metrics,
    _load_symbol_cached,
    _load_symbol_map,
    _resolve_walk_forward_window,
    iter_point_in_time_universe_folds,
)


DEFAULT_BILL_OUTPUT = "phase0_low_turnover_bill.csv"
DEFAULT_DAILY_OUTPUT = "phase0_low_turnover_daily_assets.csv"
DEFAULT_PREVIEW_OUTPUT = "phase0_low_turnover_bill_preview.html"
DEFAULT_PANEL_CACHE = "cache/low_turnover_panel.pkl"
DEFAULT_STRATEGY_ID = "legacy_momentum_low_turnover_v1"
DEFAULT_PREVIEW_HEAD_ROWS = 120
DEFAULT_PREVIEW_TAIL_ROWS = 120
PREVIEW_SCROLL_WIDTH_VW = 96


def _strategy_report_cfg(config: dict[str, Any], strategy_id: str) -> dict[str, Any]:
    reports_cfg = config.get("strategy_reports", {}) or {}
    strategies_cfg = reports_cfg.get("strategies", {}) or {}
    return dict(strategies_cfg.get(strategy_id, {}) or {})


def _default_report_strategy_id(config: dict[str, Any]) -> str:
    reports_cfg = config.get("strategy_reports", {}) or {}
    return str(reports_cfg.get("default_strategy_id") or DEFAULT_STRATEGY_ID)


def _bill_report_cfg(config: dict[str, Any], strategy_id: str) -> dict[str, Any]:
    return dict(_strategy_report_cfg(config, strategy_id).get("bill", {}) or {})


def _format_preview_html(df: pd.DataFrame, *, total_rows: int, title: str = "Phase 0 Strategy Bill Preview") -> str:
    if df.empty:
        body = "<p>No bill rows.</p>\n"
    else:
        visible_columns = [col for col in df.columns if col != "__row_type__"]
        style = """
<style>
:root {
  color-scheme: light;
  --bg: #f3f6fb;
  --surface: #ffffff;
  --border: #d0d7de;
  --header: #eef3f9;
  --text: #1f2937;
  --muted: #6b7280;
}
* {
  box-sizing: border-box;
}
body {
  margin: 0;
  padding: 24px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: var(--text);
  background: linear-gradient(180deg, #f7f9fc 0%, #edf2f8 100%);
}
.page {
  max-width: 100%;
}
.meta {
  display: flex;
  align-items: baseline;
  gap: 14px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.meta h1 {
  margin: 0;
  font-size: 22px;
  line-height: 1.2;
}
.meta p {
  flex-basis: 100%;
  margin: -4px 0 0;
  color: var(--muted);
  font-size: 14px;
}
.generated-at {
  color: #8b95a1;
  font-size: 13px;
}
.bill-preview-wrap {
  overflow: auto;
  max-height: 70vh;
  max-width: 96vw;
  border: 1px solid var(--border);
  background: var(--surface);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}
.bill-preview {
  border-collapse: collapse;
  font-size: 13px;
  line-height: 1.35;
  width: max-content;
  min-width: 100%;
  max-width: none;
}
.bill-preview th,
.bill-preview td {
  border: 1px solid var(--border);
  padding: 6px 8px;
  white-space: nowrap;
  vertical-align: top;
  background: #fff;
}
.bill-preview th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--header);
  font-weight: 600;
}
.bill-preview td.param-cell {
  max-width: 520px;
  min-width: 260px;
  white-space: normal;
  word-break: break-word;
}
.bill-preview tr.omitted-row td {
  background: #fff4cc;
  color: #8a5a00;
  font-weight: 700;
  text-align: center;
  white-space: normal;
}
.bill-preview tr.status-full td {
  background: #ffffff;
}
.bill-preview tr.status-partial td {
  background: #fff7e6;
}
.bill-preview tr.status-unfilled td {
  background: #fff0f0;
}
</style>
"""
        header = "".join(f"<th>{html.escape(str(col))}</th>" for col in visible_columns)
        rows = []
        for _, row in df.iterrows():
            if str(row.get("__row_type__", "")) == "omitted":
                rows.append(
                    '<tr class="omitted-row"><td colspan="{}">{}</td></tr>'.format(
                        len(visible_columns),
                        html.escape(str(row.get("交易日期", "中间数据省略不展示"))),
                    )
                )
                continue
            cells = []
            for col in visible_columns:
                value = "" if pd.isna(row[col]) else str(row[col])
                cls = ' class="param-cell"' if col == "策略参数" else ""
                cells.append(f"<td{cls}>{html.escape(value)}</td>")
            status = str(row.get("交易状态", ""))
            row_cls = ""
            if status == "全部成交":
                row_cls = ' class="status-full"'
            elif status == "部分成交":
                row_cls = ' class="status-partial"'
            elif status == "未成交":
                row_cls = ' class="status-unfilled"'
            rows.append(f"<tr{row_cls}>" + "".join(cells) + "</tr>")
        body = (
            style
            + '<div class="page">\n'
            + '<div class="meta">\n'
            + f"<h1>{html.escape(title)}</h1>\n"
            + f'<span class="generated-at">生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}</span>\n'
            + f"<p>Full CSV rows: {total_rows} | Dashboard rows rendered: {len(df)}</p>\n"
            + "</div>\n"
            + '<div class="bill-preview-wrap">\n'
            + '<table class="bill-preview">\n'
            + f"<thead><tr>{header}</tr></thead>\n"
            + "<tbody>\n"
            + "\n".join(rows)
            + "\n</tbody>\n</table>\n</div>\n</div>\n"
        )

    return f"<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<title>{html.escape(title)}</title>\n</head>\n<body>\n" + body + "\n</body>\n</html>\n"


def _build_preview_slice(
    bill_df: pd.DataFrame,
    *,
    head_rows: int = DEFAULT_PREVIEW_HEAD_ROWS,
    tail_rows: int = DEFAULT_PREVIEW_TAIL_ROWS,
) -> pd.DataFrame:
    if bill_df.empty:
        return bill_df.copy()

    preview = bill_df.copy()
    preview["交易日期"] = pd.to_datetime(preview["交易日期"])
    head_rows = max(0, int(head_rows))
    tail_rows = max(0, int(tail_rows))
    max_direct_rows = head_rows + tail_rows
    if len(preview) <= max_direct_rows or max_direct_rows <= 0:
        merged = preview.copy()
        merged["__row_type__"] = ""
        merged["交易日期"] = merged["交易日期"].dt.strftime("%Y-%m-%d %H:%M:%S")
        return merged

    first_part = preview.head(head_rows).copy()
    last_part = preview.tail(tail_rows).copy()
    omitted_count = max(0, len(preview) - len(first_part) - len(last_part))
    omitted = {col: "" for col in preview.columns}
    omitted["交易日期"] = f"---- 中间 {omitted_count} 行完整交易记录省略不展示，请查看 CSV 全量账单 ----"
    omitted["__row_type__"] = "omitted"

    first_part["__row_type__"] = ""
    last_part["__row_type__"] = ""
    merged = pd.concat([first_part, pd.DataFrame([omitted]), last_part], ignore_index=True)
    merged["交易日期"] = merged["交易日期"].astype(str)
    return merged


def _filter_date_window(
    df: pd.DataFrame,
    *,
    date_col: str,
    start: str | None,
    end: str | None,
) -> pd.DataFrame:
    if df.empty or (not start and not end):
        return df.copy()

    out = df.copy()
    dates = pd.to_datetime(out[date_col])
    mask = pd.Series(True, index=out.index)
    if start:
        mask &= dates >= pd.Timestamp(start)
    if end:
        mask &= dates <= pd.Timestamp(end)
    return out.loc[mask].copy()


def _load_names(db_path: Path, symbols: list[str]) -> dict[str, str]:
    if not db_path.exists() or not symbols:
        return {}
    placeholders = ",".join("?" for _ in symbols)
    query = f"SELECT symbol, name FROM market_stocks WHERE market='CN' AND symbol IN ({placeholders})"
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(query, symbols).fetchall()
    return {str(symbol): str(name or "") for symbol, name in rows}


def _resolve_path(root: Path, value: Any) -> Path:
    path = Path(str(value or ""))
    return path if path.is_absolute() else root / path


def _universe_output_path(config: dict[str, Any], root: Path) -> Path:
    universe_cfg = config.get("universe", {})
    return root / universe_cfg.get("output_dir", "data/universe") / universe_cfg.get("output_file", "local_factor_universe.csv")


def _parse_symbol_list(config: dict[str, Any], root: Path) -> list[str]:
    if config.get("universe", {}).get("enabled", False):
        path = _universe_output_path(config, root)
        if path.exists():
            df = pd.read_csv(path)
            if "symbol" in df.columns:
                symbols = df["symbol"].dropna().astype(str).tolist()
                limit = int(config.get("universe", {}).get("walk_forward_limit", 0) or 0)
                return symbols[:limit] if limit > 0 else symbols
    return [str(item) for item in config.get("symbols", [])]


def _path_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return 0.0


def _path_label(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _panel_cache_key(
    *,
    config_path: Path,
    config: dict[str, Any],
    root: Path,
    symbols: list[str],
    history_years: int,
    strategy_cfg: dict[str, Any],
    as_of_date: str | None = None,
    use_strict_asof: bool = True,
    price_adjustment: str | None = None,
) -> dict[str, Any]:
    source_paths = [
        config_path,
        _resolve_path(root, config.get("local_history", {}).get("path", "")),
    ]
    if config.get("universe", {}).get("enabled", False):
        source_paths.append(_universe_output_path(config, root))
    if bool(strategy_cfg.get("cross_market", {}).get("enabled", False)):
        source_paths.append(_resolve_path(root, config.get("us_market_history", {}).get("path", "")))

    return {
        "symbols": list(symbols),
        "history_years": int(history_years),
        "as_of_date": str(as_of_date or ""),
        "use_strict_asof": bool(use_strict_asof),
        "price_adjustment": str(price_adjustment or ""),
        "source_mtimes": {_path_label(path, root): _path_mtime(path) for path in source_paths},
    }


def _load_or_build_panel(
    *,
    cache_path: Path,
    refresh_cache: bool,
    no_panel_cache: bool,
    cache_key: dict[str, Any],
    symbols: list[str],
    history_years: int,
    strategy_cfg: dict[str, Any],
    as_of_date: str | None = None,
    use_strict_asof: bool = True,
    price_adjustment: str | None = None,
) -> pd.DataFrame:
    if not no_panel_cache and cache_path.exists() and not refresh_cache:
        try:
            payload = pd.read_pickle(cache_path)
            if isinstance(payload, dict) and payload.get("cache_key") == cache_key and isinstance(payload.get("panel"), pd.DataFrame):
                print(f"panel_cache=hit path={cache_path}")
                return payload["panel"].copy()
            print(f"panel_cache=stale path={cache_path}")
        except Exception as exc:  # pragma: no cover - corrupted local cache should not block export.
            print(f"panel_cache=invalid path={cache_path} error={exc}")

    if no_panel_cache:
        print("panel_cache=disabled")
    elif refresh_cache:
        print(f"panel_cache=refresh path={cache_path}")
    else:
        print(f"panel_cache=miss path={cache_path}")

    panel_as_of = as_of_date if use_strict_asof else None
    panel = _align_symbol_map(
        _load_symbol_map(
            symbols,
            history_years,
            as_of_date=panel_as_of,
            price_adjustment=price_adjustment,
        )
    )
    panel = _add_cross_market_to_panel(panel, history_years, strategy_cfg, None)
    if not no_panel_cache:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        pd.to_pickle({"cache_key": cache_key, "panel": panel}, cache_path)
        print(f"panel_cache=saved path={cache_path}")
    return panel


def _fold_windows(panel: pd.DataFrame, train_years: int, validate_years: int, min_samples: int) -> list[tuple[int, pd.DataFrame, pd.DataFrame]]:
    fold_days_train = train_years * 252
    fold_days_valid = validate_years * 252
    folds = []
    start = 0
    fold_idx = 0
    dates = pd.Series(sorted(panel["date"].dropna().unique()))
    while True:
        train_end = start + fold_days_train
        valid_end = train_end + fold_days_valid
        if valid_end > len(dates):
            break
        train_dates = set(dates.iloc[start:train_end])
        valid_dates = set(dates.iloc[train_end:valid_end])
        train = panel[panel["date"].isin(train_dates)].copy()
        valid = panel[panel["date"].isin(valid_dates)].copy()
        if len(train["date"].drop_duplicates()) < min_samples or len(valid["date"].drop_duplicates()) < min_samples // 2:
            break
        fold_idx += 1
        folds.append((fold_idx, train, valid))
        start += fold_days_valid
    return folds


def _load_bfq_execution_price_frame(price_frame: pd.DataFrame) -> pd.DataFrame:
    if price_frame.empty or "date" not in price_frame.columns or "symbol" not in price_frame.columns:
        return price_frame.copy()
    frame = price_frame.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    symbols = sorted(frame["symbol"].dropna().astype(str).unique())
    if not symbols:
        return frame
    start = pd.Timestamp(frame["date"].min()).date()
    end = pd.Timestamp(frame["date"].max()).date()
    rows: list[pd.DataFrame] = []
    for symbol in symbols:
        bfq = load_daily_from_local_history(symbol, start, end, price_adjustment="bfq_raw")
        if bfq.empty:
            continue
        keep = [col for col in ["date", "symbol", "open", "high", "low", "close", "volume", "amount"] if col in bfq.columns]
        one = bfq[keep].copy()
        one["date"] = pd.to_datetime(one["date"]).dt.normalize()
        one["symbol"] = one["symbol"].astype(str)
        rows.append(one)
    if not rows:
        return frame
    bfq_prices = pd.concat(rows, ignore_index=True).drop_duplicates(["date", "symbol"])
    out = frame.drop(columns=[col for col in ["open", "high", "low", "close", "volume", "amount"] if col in frame.columns]).merge(
        bfq_prices,
        on=["date", "symbol"],
        how="left",
    )
    out["execution_adjust_type"] = "bfq_raw"
    return out


def _build_strategy_fold_bill(
    *,
    strategy: Any,
    train: pd.DataFrame,
    valid: pd.DataFrame,
    fold: int,
    strategy_cfg: dict[str, Any],
    wcfg: dict[str, Any],
    names: dict[str, str],
    execution_cfg: dict[str, Any],
    score_label: str = "策略分数",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    params = strategy.select_params(
        train,
        strategy_cfg,
        slippage=float(wcfg["slippage"]),
        commission=float(wcfg["commission"]),
        stamp_duty_sell=float(wcfg["stamp_duty_sell"]),
    )
    strategy_output = strategy.apply(
        valid,
        params,
        slippage=float(wcfg["slippage"]),
        commission=float(wcfg["commission"]),
        stamp_duty_sell=float(wcfg["stamp_duty_sell"]),
    )
    execution_prices = _load_bfq_execution_price_frame(valid)
    params_text = strategy.format_params(params)
    bill, daily = _ledger_for_fold(
        strategy_output.signal_frame,
        price_frame=execution_prices,
        params=params,
        fold=fold,
        initial_cash=float(wcfg.get("initial_cash", 1_000_000)),
        names=names,
        slippage=float(wcfg["slippage"]),
        commission=float(wcfg["commission"]),
        stamp_duty_sell=float(wcfg["stamp_duty_sell"]),
        params_text=params_text,
        execution_cfg=execution_cfg,
        score_label=score_label,
    )
    metric = _calc_metrics(strategy_output.returns, strategy_output.exposure)
    bill["折年化收益"] = metric["annualized_return"]
    bill["折Sharpe"] = metric["sharpe"]
    daily["fold"] = fold
    daily["selected_params"] = params_text
    return bill, daily


def _execution_settings(config: dict[str, Any]) -> dict[str, Any]:
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


def _limit_pct(symbol: str, execution_cfg: dict[str, Any]) -> float:
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


def _lot_floor(quantity: float, lot_size: int) -> int:
    if lot_size <= 1:
        return max(0, int(np.floor(quantity)))
    return max(0, int(np.floor(quantity / lot_size) * lot_size))


def _prepare_execution_frame(signal_frame: pd.DataFrame, price_frame: pd.DataFrame, execution_cfg: dict[str, Any]) -> pd.DataFrame:
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


def _trade_block_reasons(row: pd.Series, action: str, execution_cfg: dict[str, Any]) -> list[str]:
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
        limit_pct = _limit_pct(str(row.get("symbol", "")), execution_cfg)
        limit_up = float(previous_close) * (1.0 + limit_pct)
        limit_down = float(previous_close) * (1.0 - limit_pct)
        tolerance = 0.001
        if action == "买" and open_price >= limit_up * (1.0 - tolerance):
            reasons.append("涨停不可买")
        if action == "卖" and open_price <= limit_down * (1.0 + tolerance):
            reasons.append("跌停不可卖")
    return reasons


def _append_order_record(
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
    classify_reason,
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


def _ledger_for_fold(
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
    sf = _prepare_execution_frame(signal_frame, price_frame, execution_cfg)
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
            return _lot_floor(float(volume) * max_participation_rate, lot_size)

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
                _append_order_record(
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
                target_qty = _lot_floor(value_to_sell / price, lot_size)
            target_qty = max(0, min(held_qty, target_qty))
            block_reasons = _trade_block_reasons(row, "卖", execution_cfg)
            market_qty = max_market_qty(row)
            qty = 0 if block_reasons else min(target_qty, market_qty)
            qty = max(0, min(held_qty, qty))
            if qty <= 0:
                reason = "；".join(block_reasons or ["流动性不足/低于一手"])
                _append_order_record(
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
            _append_order_record(
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
                _append_order_record(
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
            max_affordable_qty = _lot_floor(cash / (price * (1.0 + buy_rate)), lot_size)
            target_qty = _lot_floor(value_to_buy / (price * (1.0 + buy_rate)), lot_size)
            block_reasons = _trade_block_reasons(row, "买", execution_cfg)
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
                _append_order_record(
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
            _append_order_record(
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


def export_strategy_bill(
    *,
    config_path: Path,
    output: str | Path | None = None,
    daily_output: str | Path | None = None,
    preview_output: str | Path | None = None,
    valid_start: str | None = None,
    valid_end: str | None = None,
    years: int | None = None,
    panel_cache: str | Path | None = None,
    refresh_cache: bool = False,
    no_panel_cache: bool = False,
    walk_forward_overrides: dict[str, Any] | None = None,
    execution_overrides: dict[str, Any] | None = None,
    strategy_id: str | None = None,
    preview_title: str | None = None,
    score_label: str | None = None,
) -> dict[str, Any]:
    """Export account-level bill artifacts for any registered portfolio strategy."""
    root = Path.cwd()
    config_path = _resolve_path(root, config_path)
    config = load_config(config_path)
    strategy_id = str(strategy_id or _default_report_strategy_id(config))
    report_cfg = _bill_report_cfg(config, strategy_id)
    explicit_output = output is not None
    explicit_daily_output = daily_output is not None
    explicit_preview_output = preview_output is not None
    explicit_panel_cache = panel_cache is not None
    output = output or report_cfg.get("output", DEFAULT_BILL_OUTPUT)
    daily_output = daily_output or report_cfg.get("daily_output", DEFAULT_DAILY_OUTPUT)
    preview_output = preview_output or report_cfg.get("preview_output", DEFAULT_PREVIEW_OUTPUT)
    panel_cache = panel_cache or report_cfg.get("panel_cache", DEFAULT_PANEL_CACHE)
    preview_title = preview_title or report_cfg.get("preview_title")
    score_label = score_label or str(report_cfg.get("score_label", "策略分数"))
    if walk_forward_overrides:
        config.setdefault("walk_forward", {}).update(walk_forward_overrides)
    if execution_overrides:
        execution_cfg_raw = dict(config.get("execution", {}))
        for key, value in execution_overrides.items():
            if value is not None:
                execution_cfg_raw[key] = value
        config["execution"] = execution_cfg_raw
    configure_local_history(config.get("local_history", {}), root)
    configure_us_market_history(config.get("us_market_history", {}), root)
    _load_symbol_cached.cache_clear()

    wcfg = config["walk_forward"]
    window_cfg = _resolve_walk_forward_window(wcfg)
    train_years = int(window_cfg["train_years"])
    validate_years = int(window_cfg["validate_years"])
    execution_cfg = _execution_settings(config)
    strategy_cfg = dict(wcfg.get("strategy_v2", {}))
    strategy = get_strategy(strategy_id)
    history_years = int(years or config["years"])
    use_point_in_time_universe = bool(
        config.get("universe", {}).get("enabled", False)
        and config.get("universe", {}).get("point_in_time_for_backtest", True)
        and config.get("local_history", {}).get("enabled", True)
    )

    all_bills = []
    all_daily = []
    names: dict[str, str] = {}
    universe_audit = pd.DataFrame()
    if use_point_in_time_universe:
        fold_contexts, universe_audit = iter_point_in_time_universe_folds(
            config,
            years=history_years,
            train_years=train_years,
            validate_years=validate_years,
            min_samples=int(wcfg["min_samples"]),
            strategy_cfg=strategy_cfg,
        )
        all_symbols = sorted({symbol for ctx in fold_contexts for symbol in ctx.get("symbols", [])})
        names = _load_names(_resolve_path(root, config.get("local_history", {}).get("path", "")), all_symbols)
        for ctx in fold_contexts:
            prepared = strategy.prepare_panel(pd.concat([ctx["train"], ctx["valid"]], ignore_index=True), strategy_cfg)
            prepared["date"] = pd.to_datetime(prepared["date"]).dt.normalize()
            train_dates = set(pd.to_datetime(ctx["train"]["date"]).dt.normalize().unique())
            valid_dates = set(pd.to_datetime(ctx["valid"]["date"]).dt.normalize().unique())
            train = prepared[prepared["date"].isin(train_dates)].copy()
            valid = prepared[prepared["date"].isin(valid_dates)].copy()
            bill, daily = _build_strategy_fold_bill(
                strategy=strategy,
                train=train,
                valid=valid,
                fold=int(ctx["fold"]),
                strategy_cfg=strategy_cfg,
                wcfg=wcfg,
                names=names,
                execution_cfg=execution_cfg,
                score_label=score_label,
            )
            if not bill.empty:
                bill["股票池模式"] = "point_in_time"
                bill["股票池时点"] = ctx["audit"].get("universe_as_of_date", "")
                bill["股票池数量"] = ctx["audit"].get("universe_symbol_count", 0)
            if not daily.empty:
                daily["universe_mode"] = "point_in_time"
                daily["universe_as_of_date"] = ctx["audit"].get("universe_as_of_date", "")
                daily["universe_symbol_count"] = ctx["audit"].get("universe_symbol_count", 0)
            all_bills.append(bill)
            all_daily.append(daily)
    else:
        symbols = _parse_symbol_list(config, root)
        cache_path = (
            _resolve_path(root, panel_cache)
            if explicit_panel_cache
            else report_config_path(root=root, config=config, value=panel_cache or DEFAULT_PANEL_CACHE, default_category="runs")
        )
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
        names = _load_names(
            _resolve_path(root, config.get("local_history", {}).get("path", "")),
            panel["symbol"].astype(str).unique().tolist(),
        )
        for fold, train, valid in _fold_windows(
            panel,
            train_years=train_years,
            validate_years=validate_years,
            min_samples=int(wcfg["min_samples"]),
        ):
            bill, daily = _build_strategy_fold_bill(
                strategy=strategy,
                train=train,
                valid=valid,
                fold=fold,
                strategy_cfg=strategy_cfg,
                wcfg=wcfg,
                names=names,
                execution_cfg=execution_cfg,
                score_label=score_label,
            )
            all_bills.append(bill)
            all_daily.append(daily)

    bill_df = pd.concat(all_bills, ignore_index=True) if all_bills else pd.DataFrame()
    daily_df = pd.concat(all_daily, ignore_index=True) if all_daily else pd.DataFrame()
    bill_df = _filter_date_window(bill_df, date_col="交易日期", start=valid_start, end=valid_end)
    daily_df = _filter_date_window(daily_df, date_col="date", start=valid_start, end=valid_end)
    output_path = _resolve_path(root, output) if explicit_output else report_config_path(root=root, config=config, value=output, default_category="phase0")
    daily_path = (
        _resolve_path(root, daily_output)
        if explicit_daily_output
        else report_config_path(root=root, config=config, value=daily_output, default_category="phase0")
    )
    preview_path = (
        _resolve_path(root, preview_output)
        if explicit_preview_output
        else report_config_path(root=root, config=config, value=preview_output, default_category="phase0")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    daily_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    bill_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    daily_df.to_csv(daily_path, index=False, encoding="utf-8-sig")

    # Full preview generation is intentionally kept here for future use.
    # preview = bill_df.copy()
    preview = _build_preview_slice(bill_df)
    for col in ["账户总资产", "股票资产", "现金资产", "成交价", "收益额", "成交金额"]:
        if col in preview.columns:
            preview[col] = preview[col].map(lambda x: f"{float(x):,.2f}" if str(x) not in {"", "nan", "NaT"} else "")
    for col in ["收益率", "折年化收益", "折Sharpe", score_label, "最大成交参与率"]:
        if col in preview.columns:
            preview[col] = preview[col].map(lambda x: f"{float(x):.4f}" if str(x) not in {"", "nan", "NaT"} else "")
    preview_path.write_text(
        _format_preview_html(preview, total_rows=len(bill_df), title=preview_title or f"Phase 0 Strategy Bill Preview - {strategy_id}"),
        encoding="utf-8",
    )
    return {
        "bill": output_path,
        "daily": daily_path,
        "preview": preview_path,
        "rows": len(bill_df),
        "daily_rows": len(daily_df),
        "universe_mode": "point_in_time" if use_point_in_time_universe else "static_current_snapshot",
        "universe_audit_rows": len(universe_audit),
        "strategy_id": strategy_id,
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--output", default=None, help="Output CSV path; defaults to strategy_reports.<strategy>.bill.output")
    parser.add_argument("--daily-output", default=None, help="Daily assets CSV path; defaults to strategy_reports.<strategy>.bill.daily_output")
    parser.add_argument("--preview-output", default=None, help="Preview HTML path; defaults to strategy_reports.<strategy>.bill.preview_output")
    parser.add_argument("--valid-start", default=None, help="Optional inclusive validation date lower bound, e.g. 2018-08-01")
    parser.add_argument("--valid-end", default=None, help="Optional inclusive validation date upper bound, e.g. 2022-10-31")
    parser.add_argument("--years", type=int, default=None, help="Optional history lookback override for period validation")
    parser.add_argument("--strategy-id", default=None, help="Registered strategy ID to export; defaults to strategy_reports.default_strategy_id")
    parser.add_argument("--score-label", default=None, help="Display label for the score column")
    parser.add_argument(
        "--panel-cache",
        default=None,
        help="Cached aligned market panel path; defaults to strategy_reports.<strategy>.bill.panel_cache",
    )
    parser.add_argument("--refresh-cache", action="store_true", help="Rebuild the cached market panel before exporting")
    parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
    args = parser.parse_args()

    result = export_strategy_bill(
        config_path=Path(args.config),
        output=args.output,
        daily_output=args.daily_output,
        preview_output=args.preview_output,
        valid_start=args.valid_start,
        valid_end=args.valid_end,
        years=args.years,
        strategy_id=args.strategy_id,
        score_label=args.score_label,
        panel_cache=args.panel_cache,
        refresh_cache=bool(args.refresh_cache),
        no_panel_cache=bool(args.no_panel_cache),
    )
    output_path = result["bill"]
    daily_path = result["daily"]
    preview_path = result["preview"]
    print(f"bill={output_path}")
    print(f"daily={daily_path}")
    print(f"preview={preview_path}")
    print(f"rows={result['rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
