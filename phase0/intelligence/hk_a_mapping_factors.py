from __future__ import annotations

import argparse
import html
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

import pandas as pd

from phase0.config import load_config
from phase0.reporting.paths import report_path
from phase0.data_access.throttle import configure_akshare_throttle, fetch_with_akshare_retries


@dataclass
class FetchResult:
    name: str
    source: str
    ok: bool
    rows: int = 0
    error: str = ""


def _find_col(df: pd.DataFrame, aliases: list[str]) -> str | None:
    lowered = {str(col).lower(): str(col) for col in df.columns}
    for alias in aliases:
        if alias in df.columns:
            return alias
        found = lowered.get(alias.lower())
        if found is not None:
            return found
    return None


def _num(series: pd.Series) -> pd.Series:
    if series.empty:
        return series
    cleaned = (
        series.astype(str)
        .str.replace("%", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace("--", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _safe_fetch(name: str, source: str, fetcher: Callable[[], pd.DataFrame]) -> tuple[pd.DataFrame, FetchResult]:
    try:
        df = fetch_with_akshare_retries(fetcher)
        if df is None:
            df = pd.DataFrame()
        return df, FetchResult(name=name, source=source, ok=not df.empty, rows=int(len(df)))
    except Exception as exc:
        return pd.DataFrame(), FetchResult(name=name, source=source, ok=False, error=f"{type(exc).__name__}: {exc}")


def _clean_company_name(value: object) -> str:
    text = str(value)
    text = text.replace("股份", "").replace("集团", "").replace("有限", "")
    text = text.replace("Ａ", "A").replace("A", "")
    return re.sub(r"[\s（）()·.\-]", "", text)


def _load_latest_a_share_prices(db_path: Path) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame()
    query = """
        WITH latest AS (
          SELECT symbol, MAX(date) AS date
          FROM market_daily_bars
          WHERE market = 'CN' AND adjust_type = 'qfq'
          GROUP BY symbol
        )
        SELECT
          s.symbol AS a_symbol,
          s.raw_symbol AS a_code,
          s.name AS a_name,
          b.date AS a_trade_date,
          b.close AS a_close
        FROM market_stocks s
        JOIN latest l ON s.symbol = l.symbol
        JOIN market_daily_bars b
          ON b.symbol = l.symbol
         AND b.date = l.date
         AND b.market = 'CN'
         AND b.adjust_type = 'qfq'
        WHERE s.market = 'CN'
    """
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn)
    if df.empty:
        return df
    df["match_name"] = df["a_name"].map(_clean_company_name)
    df["a_close"] = pd.to_numeric(df["a_close"], errors="coerce")
    return df


def _normalize_ah_comparison(raw: pd.DataFrame, a_prices: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return raw
    out = pd.DataFrame()
    out["snapshot_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    out["h_code"] = raw[_find_col(raw, ["H股代码", "港股代码", "代码"]) or raw.columns[0]].astype(str)
    out["name"] = raw[_find_col(raw, ["名称", "股票名称", "A股简称"]) or raw.columns[0]].astype(str)

    h_price_col = _find_col(raw, ["H股最新价", "H股价格", "H股价", "最新价"])
    premium_col = _find_col(raw, ["比价", "AH股比价", "A/H股比价", "溢价率", "AH溢价率", "A/H溢价率"])

    out["h_price"] = _num(raw[h_price_col]) if h_price_col else pd.NA
    out["akshare_ah_premium_or_ratio"] = _num(raw[premium_col]) if premium_col else pd.NA
    out["match_name"] = out["name"].map(_clean_company_name)
    if not a_prices.empty:
        out = out.merge(a_prices, on="match_name", how="left")
    else:
        out["a_symbol"] = ""
        out["a_code"] = ""
        out["a_name"] = ""
        out["a_trade_date"] = pd.NA
        out["a_close"] = pd.NA
    out["a_h_price_ratio_without_fx"] = pd.to_numeric(out["a_close"], errors="coerce") / pd.to_numeric(out["h_price"], errors="coerce")
    out["note"] = "H股报价来自 AKShare 腾讯 AH 接口；A股价格来自本地库最新前复权收盘价；未换算 HKD/CNY 汇率"
    out["source_columns"] = ", ".join(map(str, raw.columns))
    return out


def _normalize_hsgt_hist(raw: pd.DataFrame, channel: str) -> pd.DataFrame:
    if raw.empty:
        return raw
    out = pd.DataFrame()
    date_col = _find_col(raw, ["日期", "交易日期", "TRADE_DATE", "date"])
    out["trade_date"] = pd.to_datetime(raw[date_col], errors="coerce").dt.date if date_col else pd.NaT
    out["channel"] = channel
    for target, aliases in {
        "buy_amount": ["买入成交额", "当日买入成交金额", "BUY_AMT"],
        "sell_amount": ["卖出成交额", "当日卖出成交金额", "SELL_AMT"],
        "net_buy_amount": ["历史累计净买额", "当日成交净买额", "净买额", "资金净流入", "净流入"],
        "turnover": ["成交金额", "成交额", "成交总额"],
    }.items():
        col = _find_col(raw, aliases)
        out[target] = _num(raw[col]) if col else pd.NA
    out = out.sort_values("trade_date").reset_index(drop=True)
    out["net_buy_ma5"] = pd.to_numeric(out["net_buy_amount"], errors="coerce").rolling(5, min_periods=1).mean()
    out["net_buy_ma20"] = pd.to_numeric(out["net_buy_amount"], errors="coerce").rolling(20, min_periods=1).mean()
    return out


def _normalize_hsgt_holding(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return raw
    out = pd.DataFrame()
    date_col = _find_col(raw, ["日期", "持股日期", "交易日期", "TRADE_DATE"])
    code_col = _find_col(raw, ["代码", "股票代码", "SECURITY_CODE"])
    name_col = _find_col(raw, ["名称", "股票简称", "SECURITY_NAME_ABBR"])
    market_col = _find_col(raw, ["市场", "MARKET"])
    shares_col = _find_col(raw, ["持股数", "持股数量", "HOLD_SHARES"])
    value_col = _find_col(raw, ["持股市值", "HOLD_MARKET_CAP"])
    ratio_col = _find_col(raw, ["持股占流通股比", "持股占比", "占流通股比例"])

    out["trade_date"] = pd.to_datetime(raw[date_col], errors="coerce").dt.date if date_col else pd.NaT
    out["code"] = raw[code_col].astype(str) if code_col else ""
    out["name"] = raw[name_col].astype(str) if name_col else ""
    out["market"] = raw[market_col].astype(str) if market_col else ""
    out["hold_shares"] = _num(raw[shares_col]) if shares_col else pd.NA
    out["hold_market_value"] = _num(raw[value_col]) if value_col else pd.NA
    out["hold_float_ratio"] = _num(raw[ratio_col]) if ratio_col else pd.NA
    out = out.sort_values(["code", "trade_date"]).reset_index(drop=True)
    out["hold_shares_change"] = out.groupby("code")["hold_shares"].diff()
    out["hold_ratio_change"] = out.groupby("code")["hold_float_ratio"].diff()
    return out


def _normalize_individual_holding(raw: pd.DataFrame, code: str, name: str) -> pd.DataFrame:
    if raw.empty:
        return raw
    out = pd.DataFrame()
    out["trade_date"] = pd.to_datetime(raw[_find_col(raw, ["持股日期", "日期"]) or raw.columns[0]], errors="coerce").dt.date
    out["code"] = code
    out["name"] = name
    out["close"] = _num(raw[_find_col(raw, ["当日收盘价"]) or raw.columns[1]])
    out["change_pct"] = _num(raw[_find_col(raw, ["当日涨跌幅"]) or raw.columns[2]])
    out["hold_shares"] = _num(raw[_find_col(raw, ["持股数量"]) or raw.columns[3]])
    out["hold_market_value"] = _num(raw[_find_col(raw, ["持股市值"]) or raw.columns[4]])
    out["hold_float_ratio"] = _num(raw[_find_col(raw, ["持股数量占A股百分比"]) or raw.columns[5]])
    out["hold_shares_change"] = _num(raw[_find_col(raw, ["今日增持股数"]) or raw.columns[6]])
    out["hold_money_change"] = _num(raw[_find_col(raw, ["今日增持资金"]) or raw.columns[7]])
    out = out.sort_values("trade_date").reset_index(drop=True)
    out["hold_ratio_change"] = out["hold_float_ratio"].diff()
    return out


def _write_html_report(
    path: Path,
    *,
    results: list[FetchResult],
    ah_factor: pd.DataFrame,
    flow_factor: pd.DataFrame,
    hold_factor: pd.DataFrame,
) -> None:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    status_rows = "".join(
        "<tr>"
        f"<td>{html.escape(item.name)}</td>"
        f"<td>{html.escape(item.source)}</td>"
        f"<td>{'OK' if item.ok else 'FAILED'}</td>"
        f"<td>{item.rows}</td>"
        f"<td>{html.escape(item.error)}</td>"
        "</tr>"
        for item in results
    )

    def table(df: pd.DataFrame, max_rows: int = 20) -> str:
        if df.empty:
            return "<p class=\"empty\">无可展示数据。</p>"
        return df.head(max_rows).to_html(index=False, escape=True, classes="report-table")

    document = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>港股映射 A 股因子验证报告</title>
  <style>
    body {{ margin: 24px; color: #1f2937; font: 14px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    h1 {{ margin: 0 0 4px; font-size: 24px; }}
    h2 {{ margin-top: 28px; font-size: 18px; }}
    .meta {{ color: #6b7280; margin-bottom: 20px; }}
    .table-wrap {{ max-width: 95vw; max-height: 70vh; overflow: auto; border: 1px solid #e5e7eb; }}
    .report-table {{ border-collapse: collapse; min-width: 1000px; width: max-content; }}
    .report-table th, .report-table td {{ border: 1px solid #e5e7eb; padding: 7px 10px; white-space: nowrap; text-align: right; }}
    .report-table th {{ background: #f3f4f6; color: #111827; position: sticky; top: 0; }}
    .report-table td:first-child, .report-table th:first-child {{ text-align: left; }}
    .empty {{ color: #9ca3af; }}
    code {{ background: #f3f4f6; padding: 2px 5px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>港股映射 A 股因子验证报告</h1>
  <div class="meta">生成时间：{generated_at}</div>
  <p>本报告只验证 AKShare 数据抓取和因子样表生成，不接入当前 Phase 0 主策略。</p>

  <h2>接口状态</h2>
  <div class="table-wrap">
    <table class="report-table">
      <thead><tr><th>数据</th><th>接口</th><th>状态</th><th>行数</th><th>错误</th></tr></thead>
      <tbody>{status_rows}</tbody>
    </table>
  </div>

  <h2>AH 溢价/比价因子样表</h2>
  <div class="table-wrap">{table(ah_factor)}</div>

  <h2>港股通资金因子样表</h2>
  <div class="table-wrap">{table(flow_factor)}</div>

  <h2>北向持股变化因子样表</h2>
  <div class="table-wrap">{table(hold_factor)}</div>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export HK -> A-share mapping factor samples via AKShare.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--start-date", default=(date.today() - timedelta(days=30)).strftime("%Y%m%d"))
    parser.add_argument("--end-date", default=date.today().strftime("%Y%m%d"))
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--holding-tail", type=int, default=20, help="Rows kept per holding symbol when date range has no rows")
    parser.add_argument(
        "--holding-symbol",
        action="append",
        default=[],
        help="A-share code for single-stock northbound holding history, e.g. 601318:中国平安",
    )
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    cfg = load_config(config_path)
    output_dir = Path(args.output_dir) if args.output_dir else report_path(
        root=config_path.parent,
        config=cfg,
        category="phase0",
        parts=("hk_a_mapping_factors",),
    )

    import akshare as ak

    configure_akshare_throttle(cfg.get("data_sources", {}).get("akshare", {}))
    out_dir = output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[FetchResult] = []

    history_db = Path(cfg.get("data_sources", {}).get("manual_history", {}).get("path", "data/a_share_history.sqlite"))
    a_prices = _load_latest_a_share_prices(history_db)

    ah_raw, result = _safe_fetch("AH 行情", "ak.stock_zh_ah_spot", ak.stock_zh_ah_spot)
    results.append(result)
    ah_factor = _normalize_ah_comparison(ah_raw, a_prices)

    flow_frames = []
    for channel in ["北向资金", "沪股通", "深股通"]:
        raw, result = _safe_fetch(f"{channel}资金历史", f"ak.stock_hsgt_hist_em({channel})", lambda channel=channel: ak.stock_hsgt_hist_em(symbol=channel))
        results.append(result)
        normalized = _normalize_hsgt_hist(raw, channel)
        if not normalized.empty:
            flow_frames.append(normalized)
    flow_factor = pd.concat(flow_frames, ignore_index=True) if flow_frames else pd.DataFrame()

    holding_symbols = args.holding_symbol or [
        "601318:中国平安",
        "600036:招商银行",
        "600519:贵州茅台",
        "000858:五粮液",
        "000333:美的集团",
    ]
    hold_frames = []
    hold_raw_frames = []
    for item in holding_symbols:
        if ":" in item:
            code, name = item.split(":", 1)
        else:
            code, name = item, item
        raw, result = _safe_fetch(f"{name}北向持股", f"ak.stock_hsgt_individual_em({code})", lambda code=code: ak.stock_hsgt_individual_em(symbol=code))
        results.append(result)
        if not raw.empty:
            hold_raw_frames.append(raw.assign(query_code=code, query_name=name))
            normalized = _normalize_individual_holding(raw, code, name)
            filtered = normalized[
                (pd.to_datetime(normalized["trade_date"], errors="coerce") >= pd.to_datetime(args.start_date))
                & (pd.to_datetime(normalized["trade_date"], errors="coerce") <= pd.to_datetime(args.end_date))
            ].copy()
            if filtered.empty and args.holding_tail > 0:
                filtered = normalized.tail(args.holding_tail).copy()
                filtered["note"] = f"请求区间 {args.start_date}-{args.end_date} 无持股数据，回退展示该股票最近 {args.holding_tail} 条历史记录"
            else:
                filtered["note"] = ""
            hold_frames.append(filtered)
    hold_factor = pd.concat(hold_frames, ignore_index=True) if hold_frames else pd.DataFrame()

    ah_raw.to_csv(out_dir / "ah_comparison_raw.csv", index=False)
    ah_factor.to_csv(out_dir / "ah_premium_factor.csv", index=False)
    flow_factor.to_csv(out_dir / "hsgt_moneyflow_factor.csv", index=False)
    hold_factor.to_csv(out_dir / "hk_hold_change_factor.csv", index=False)
    pd.DataFrame([item.__dict__ for item in results]).to_csv(out_dir / "fetch_status.csv", index=False)
    _write_html_report(
        out_dir / "hk_a_mapping_factors_report.html",
        results=results,
        ah_factor=ah_factor,
        flow_factor=flow_factor,
        hold_factor=hold_factor,
    )

    failed = [item for item in results if not item.ok]
    print(f"output_dir={out_dir}")
    print(f"ok={len(results) - len(failed)} failed={len(failed)}")
    for item in failed:
        print(f"FAILED {item.name}: {item.error}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
