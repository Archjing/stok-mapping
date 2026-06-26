from __future__ import annotations

import argparse
import html
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from phase0.config import load_config
from phase0.data_governance.external_market_history import configure_us_market_history
from phase0.data_access.local_history import configure_local_history, load_daily_from_local_history
from phase0.execution.strategy_ledger import (
    append_order_record as _append_order_record,
    execution_settings as _execution_settings,
    ledger_for_fold as _ledger_for_fold,
    limit_pct as _limit_pct,
    lot_floor as _lot_floor,
    prepare_execution_frame as _prepare_execution_frame,
    trade_block_reasons as _trade_block_reasons,
)
from phase0.reporting.paths import report_config_path
from phase0.research.metrics import calc_metrics as _calc_metrics
from phase0.strategies import get_strategy
from phase0.walk_forward import (
    _add_cross_market_to_panel,
    _align_symbol_map,
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
