from __future__ import annotations

import argparse
import html
import sqlite3
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0.config import load_config
from phase0.external_market_history import configure_us_market_history
from phase0.local_history import configure_local_history
from phase0.strategies import get_strategy
from phase0.walk_forward import (
    _add_cross_market_to_panel,
    _align_symbol_map,
    _calc_metrics,
    _load_symbol_cached,
    _load_symbol_map,
)


def _format_preview_html(df: pd.DataFrame, *, total_rows: int) -> str:
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
  margin-bottom: 16px;
}
.meta h1 {
  margin: 0 0 6px;
  font-size: 22px;
  line-height: 1.2;
}
.meta p {
  margin: 0;
  color: var(--muted);
  font-size: 14px;
}
.bill-preview-wrap {
  overflow-x: auto;
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
            rows.append("<tr>" + "".join(cells) + "</tr>")
        body = (
            style
            + '<div class="page">\n'
            + '<div class="meta">\n'
            + "<h1>Phase 0 Low Turnover Bill Preview</h1>\n"
            + f"<p>Rows: {total_rows} | Preview: first {len(df)} rows</p>\n"
            + "</div>\n"
            + '<div class="bill-preview-wrap">\n'
            + '<table class="bill-preview">\n'
            + f"<thead><tr>{header}</tr></thead>\n"
            + "<tbody>\n"
            + "\n".join(rows)
            + "\n</tbody>\n</table>\n</div>\n</div>\n"
        )

    return "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<title>Phase 0 Low Turnover Bill Preview</title>\n</head>\n<body>\n" + body + "\n</body>\n</html>\n"


def _build_preview_slice(bill_df: pd.DataFrame) -> pd.DataFrame:
    if bill_df.empty:
        return bill_df.copy()

    preview = bill_df.copy()
    preview["交易日期"] = pd.to_datetime(preview["交易日期"])
    first_date = preview["交易日期"].min()
    last_date = preview["交易日期"].max()
    first_cutoff = first_date + pd.DateOffset(years=1)
    last_cutoff = last_date - pd.DateOffset(years=1)

    first_year = preview[preview["交易日期"] < first_cutoff].copy()
    last_year = preview[preview["交易日期"] >= last_cutoff].copy()

    if first_year.empty or last_year.empty:
        merged = preview.copy()
        merged["__row_type__"] = ""
        merged["交易日期"] = merged["交易日期"].dt.strftime("%Y-%m-%d %H:%M:%S")
        return merged

    omitted = {col: "" for col in preview.columns}
    omitted["交易日期"] = "---- 中间数据省略不展示 ----"
    omitted["__row_type__"] = "omitted"

    first_year["__row_type__"] = ""
    last_year["__row_type__"] = ""
    merged = pd.concat([first_year, pd.DataFrame([omitted]), last_year], ignore_index=True)
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


def _parse_symbol_list(config: dict[str, Any], root: Path) -> list[str]:
    if config.get("universe", {}).get("enabled", False):
        path = root / config.get("universe", {}).get("output_dir", "data/universe") / config.get("universe", {}).get(
            "output_file", "local_factor_universe.csv"
        )
        if path.exists():
            df = pd.read_csv(path)
            if "symbol" in df.columns:
                symbols = df["symbol"].dropna().astype(str).tolist()
                limit = int(config.get("universe", {}).get("walk_forward_limit", 0) or 0)
                return symbols[:limit] if limit > 0 else symbols
    return [str(item) for item in config.get("symbols", [])]


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
) -> tuple[pd.DataFrame, pd.DataFrame]:
    sf = signal_frame.copy()
    sf["date"] = pd.to_datetime(sf["date"])
    if "close" not in sf.columns:
        prices = price_frame[["date", "symbol", "close"]].copy()
        prices["date"] = pd.to_datetime(prices["date"])
        prices["symbol"] = prices["symbol"].astype(str)
        sf["symbol"] = sf["symbol"].astype(str)
        sf = sf.merge(prices, on=["date", "symbol"], how="left")
    sf = sf.sort_values(["date", "symbol"]).reset_index(drop=True)
    sf["stock_name"] = sf["symbol"].map(names).fillna("")
    sf["prev_weight"] = sf.groupby("symbol")["weight"].shift(1).fillna(0.0)
    sf["prev_held_days"] = sf.groupby("symbol")["held_days"].shift(1).fillna(0.0)
    sf["delta_weight"] = sf["weight"] - sf["prev_weight"]
    sf["buy_value"] = sf["delta_weight"].clip(lower=0.0) * initial_cash
    sf["sell_value"] = (-sf["delta_weight"].clip(upper=0.0)) * initial_cash
    sf["buy_cost"] = sf["buy_value"] * (slippage + commission)
    sf["sell_cost"] = sf["sell_value"] * (slippage + commission + stamp_duty_sell)
    sf["trade_cash_flow"] = sf["sell_value"] - sf["buy_value"] - sf["buy_cost"] - sf["sell_cost"]
    sf["position_value"] = sf["weight"] * initial_cash
    sf["position_pnl"] = sf["position_ret"] * initial_cash

    daily = (
        sf.groupby("date", as_index=False)
        .agg(
            trade_cash_flow=("trade_cash_flow", "sum"),
            exposure=("weight", "sum"),
            daily_pnl=("position_pnl", "sum"),
            buy_amount=("buy_value", "sum"),
            sell_amount=("sell_value", "sum"),
            buy_cost=("buy_cost", "sum"),
            sell_cost=("sell_cost", "sum"),
        )
        .sort_values("date")
    )
    daily["trade_cost"] = daily["buy_cost"] + daily["sell_cost"]
    daily["net_daily_pnl"] = daily["daily_pnl"] - daily["trade_cost"]
    daily["account_total_assets"] = initial_cash + daily["net_daily_pnl"].cumsum()
    daily["stock_assets"] = daily["account_total_assets"] * daily["exposure"].clip(lower=0.0, upper=1.0)
    daily["cash_assets"] = daily["account_total_assets"] - daily["stock_assets"]
    daily["profit"] = daily["account_total_assets"] - initial_cash
    daily["profit_rate"] = daily["account_total_assets"] / initial_cash - 1.0

    trades = sf[sf["delta_weight"].abs() > 1e-12].copy()
    if trades.empty:
        return trades, daily
    buy_top_n = int(params["buy_top_n"])
    hold_top_n = int(params["hold_top_n"])
    buy_threshold = float(params["buy_threshold"])
    hold_threshold = float(params["hold_threshold"])
    min_hold_days = int(params["min_hold_days"])

    def classify_reason(row: pd.Series) -> str:
        score = row.get("score")
        rank = row.get("rank")
        prev_weight = float(row.get("prev_weight", 0.0) or 0.0)
        curr_weight = float(row.get("weight", 0.0) or 0.0)
        prev_held_days = float(row.get("prev_held_days", 0.0) or 0.0)

        if curr_weight > prev_weight:
            if prev_weight <= 1e-12:
                reasons = []
                if pd.notna(rank) and float(rank) <= buy_top_n:
                    reasons.append("新进前N")
                if pd.notna(score) and float(score) > buy_threshold:
                    reasons.append("满足动量阈值")
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
                    if float(score) <= hold_threshold:
                        reasons.append("跌破持有阈值")
                    if float(rank) > hold_top_n:
                        reasons.append("跌出持有排名")
                if prev_held_days >= min_hold_days:
                    reasons.append("满足最小持有期")
                if not reasons:
                    reasons.append("调仓移出持仓")
                return "调仓卖出-" + "、".join(dict.fromkeys(reasons))
            return "调仓卖出-权重下调"

        return "持仓不变"

    trades["trade_action"] = np.where(trades["delta_weight"] > 0, "买", "卖")
    trades["trade_reason"] = trades.apply(classify_reason, axis=1)
    trades["deal_price"] = trades["close"]
    trades["stock_vol"] = np.floor((trades["delta_weight"].abs() * initial_cash) / trades["deal_price"].replace(0, np.nan) / 100) * 100
    trades["stock_vol"] = trades["stock_vol"].fillna(0).astype(int)
    trades["trade_amount"] = trades["delta_weight"].abs() * initial_cash
    trades["income_type"] = np.where(trades["trade_action"] == "卖", "超时卖/调仓卖", "")
    trades = trades.merge(
        daily[
            [
                "date",
                "account_total_assets",
                "stock_assets",
                "cash_assets",
                "profit",
                "profit_rate",
            ]
        ],
        on="date",
        how="left",
    )
    trades["fold"] = fold
    trades["selected_params"] = params_text
    trades["trade_datetime"] = trades["date"].dt.strftime("%Y-%m-%d 15:00:00")
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
            "profit",
            "profit_rate",
            "income_type",
            "trade_reason",
            "fold",
            "trade_amount",
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
            "profit": "收益额",
            "profit_rate": "收益率",
            "income_type": "收益类型",
            "trade_reason": "交易原因",
            "fold": "折号",
            "trade_amount": "成交金额",
            "score": "动量分数",
            "rank": "当日排名",
            "selected_params": "策略参数",
        }
    )
    return bill, daily


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--output", default="reports/phase0_low_turnover_bill.csv")
    parser.add_argument("--daily-output", default="reports/phase0_low_turnover_daily_assets.csv")
    parser.add_argument("--preview-output", default="reports/phase0_low_turnover_bill_preview.html")
    parser.add_argument("--valid-start", default=None, help="Optional inclusive validation date lower bound, e.g. 2018-08-01")
    parser.add_argument("--valid-end", default=None, help="Optional inclusive validation date upper bound, e.g. 2022-10-31")
    parser.add_argument("--years", type=int, default=None, help="Optional history lookback override for period validation")
    args = parser.parse_args()

    root = Path.cwd()
    config = load_config(root / args.config)
    configure_local_history(config.get("local_history", {}), root)
    configure_us_market_history(config.get("us_market_history", {}), root)
    _load_symbol_cached.cache_clear()

    wcfg = config["walk_forward"]
    strategy_cfg = dict(wcfg.get("strategy_v2", {}))
    symbols = _parse_symbol_list(config, root)
    strategy = get_strategy("legacy_momentum_low_turnover_v1")
    history_years = int(args.years or config["years"])
    panel = _align_symbol_map(_load_symbol_map(symbols, history_years))
    panel = _add_cross_market_to_panel(panel, history_years, strategy_cfg, None)
    names = _load_names(root / config.get("local_history", {}).get("path", ""), panel["symbol"].astype(str).unique().tolist())

    all_bills = []
    all_daily = []
    for fold, train, valid in _fold_windows(
        panel,
        train_years=int(wcfg["train_years"]),
        validate_years=int(wcfg["validate_years"]),
        min_samples=int(wcfg["min_samples"]),
    ):
        params = strategy.select_params(
            train,
            strategy_cfg,
            slippage=float(wcfg["slippage"]),
            commission=float(wcfg["commission"]),
            stamp_duty_sell=float(wcfg["stamp_duty_sell"]),
        )
        output = strategy.apply(
            valid,
            params,
            slippage=float(wcfg["slippage"]),
            commission=float(wcfg["commission"]),
            stamp_duty_sell=float(wcfg["stamp_duty_sell"]),
        )
        params_text = strategy.format_params(params)
        bill, daily = _ledger_for_fold(
            output.signal_frame,
            price_frame=valid,
            params=params,
            fold=fold,
            initial_cash=float(wcfg.get("initial_cash", 1_000_000)),
            names=names,
            slippage=float(wcfg["slippage"]),
            commission=float(wcfg["commission"]),
            stamp_duty_sell=float(wcfg["stamp_duty_sell"]),
            params_text=params_text,
        )
        metric = _calc_metrics(output.returns, output.exposure)
        bill["折年化收益"] = metric["annualized_return"]
        bill["折Sharpe"] = metric["sharpe"]
        daily["fold"] = fold
        daily["selected_params"] = params_text
        all_bills.append(bill)
        all_daily.append(daily)

    bill_df = pd.concat(all_bills, ignore_index=True) if all_bills else pd.DataFrame()
    daily_df = pd.concat(all_daily, ignore_index=True) if all_daily else pd.DataFrame()
    bill_df = _filter_date_window(bill_df, date_col="交易日期", start=args.valid_start, end=args.valid_end)
    daily_df = _filter_date_window(daily_df, date_col="date", start=args.valid_start, end=args.valid_end)
    output_path = root / args.output
    daily_path = root / args.daily_output
    preview_path = root / args.preview_output
    bill_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    daily_df.to_csv(daily_path, index=False, encoding="utf-8-sig")

    # Full preview generation is intentionally kept here for future use.
    # preview = bill_df.copy()
    preview = _build_preview_slice(bill_df)
    for col in ["账户总资产", "股票资产", "现金资产", "成交价", "收益额", "成交金额"]:
        if col in preview.columns:
            preview[col] = preview[col].map(lambda x: f"{float(x):,.2f}" if str(x) not in {"", "nan", "NaT"} else "")
    for col in ["收益率", "折年化收益", "折Sharpe", "动量分数"]:
        if col in preview.columns:
            preview[col] = preview[col].map(lambda x: f"{float(x):.4f}" if str(x) not in {"", "nan", "NaT"} else "")
    preview_path.write_text(
        _format_preview_html(preview, total_rows=len(bill_df)),
        encoding="utf-8",
    )
    print(f"bill={output_path}")
    print(f"daily={daily_path}")
    print(f"preview={preview_path}")
    print(f"rows={len(bill_df)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
