from __future__ import annotations

import argparse
import math
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0.config import load_config
from phase0.local_history import configure_local_history, load_index_daily_from_local_history


def _annualized_return(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    cum = float((1.0 + returns).prod() - 1.0)
    years = max(len(returns) / 252.0, 1.0 / 252.0)
    return float((1.0 + cum) ** (1.0 / years) - 1.0)


def _sharpe(returns: pd.Series) -> float:
    if len(returns) < 2:
        return 0.0
    std = float(returns.std(ddof=1))
    if std == 0.0 or not np.isfinite(std):
        return 0.0
    return float((returns.mean() / std) * np.sqrt(252.0))


def _max_drawdown(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    equity = (1.0 + returns).cumprod()
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    return float(drawdown.min())


def _fmt_money(value: float) -> str:
    return f"{value:,.2f}"


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _fmt_float(value: float, digits: int = 4) -> str:
    return f"{value:.{digits}f}"


def _html_table(df: pd.DataFrame, *, table_class: str = "report-table") -> str:
    if df.empty:
        return "<p class=\"empty-note\">No data.</p>"
    header = "".join(f"<th>{col}</th>" for col in df.columns)
    rows: list[str] = []
    for _, row in df.iterrows():
        cells = "".join(f"<td>{row[col]}</td>" for col in df.columns)
        rows.append(f"<tr>{cells}</tr>")
    return (
        f'<div class="{table_class}-wrap">'
        f'<table class="{table_class}">'
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</div>"
    )


def _load_assets(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["fold", "date"]).reset_index(drop=True)
    return df


def _build_stitched_curve(daily_assets: pd.DataFrame, initial_cash: float) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for fold, fold_df in daily_assets.groupby("fold", sort=True):
        one = fold_df.copy().sort_values("date").reset_index(drop=True)
        prev_assets = one["account_total_assets"].shift(1)
        one["strategy_daily_return"] = one["account_total_assets"].div(prev_assets).sub(1.0)
        one.loc[0, "strategy_daily_return"] = 0.0
        one["strategy_daily_return"] = one["strategy_daily_return"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        one["fold_start_asset"] = float(one["account_total_assets"].iloc[0])
        one["fold_end_asset"] = float(one["account_total_assets"].iloc[-1])
        frames.append(one)

    stitched = pd.concat(frames, ignore_index=True).sort_values("date").reset_index(drop=True)
    stitched["strategy_asset"] = initial_cash * (1.0 + stitched["strategy_daily_return"]).cumprod()
    stitched["strategy_profit_rate_continuous"] = stitched["strategy_asset"] / initial_cash - 1.0
    return stitched


def _load_benchmark_curve(
    benchmark_symbol: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    stitched_dates: pd.Series,
    initial_cash: float,
) -> pd.DataFrame:
    bench = load_index_daily_from_local_history(
        benchmark_symbol,
        (start_date - timedelta(days=5)).date(),
        end_date.date(),
    )
    if bench.empty:
        raise RuntimeError(f"benchmark {benchmark_symbol} not found in local history")
    bench = bench[["date", "close", "name"]].copy().sort_values("date").reset_index(drop=True)
    bench["date"] = pd.to_datetime(bench["date"])
    merged = pd.DataFrame({"date": stitched_dates}).merge(bench, on="date", how="left")
    merged["close"] = pd.to_numeric(merged["close"], errors="coerce")
    if merged["close"].isna().any():
        missing = merged.loc[merged["close"].isna(), "date"].dt.strftime("%Y-%m-%d").tolist()
        raise RuntimeError(f"benchmark missing dates: {missing[:10]}")
    merged["benchmark_daily_return"] = merged["close"].pct_change().fillna(0.0)
    merged["benchmark_asset"] = initial_cash * (1.0 + merged["benchmark_daily_return"]).cumprod()
    merged["benchmark_profit_rate_continuous"] = merged["benchmark_asset"] / initial_cash - 1.0
    merged["benchmark_name"] = str(bench["name"].dropna().iloc[0]) if "name" in bench.columns and bench["name"].notna().any() else benchmark_symbol
    return merged


def _summary_row(label: str, returns: pd.Series, asset_series: pd.Series) -> dict[str, str]:
    total_return = float(asset_series.iloc[-1] / asset_series.iloc[0] - 1.0) if len(asset_series) else 0.0
    return {
        "对象": label,
        "总收益": _fmt_pct(total_return),
        "年化收益": _fmt_pct(_annualized_return(returns)),
        "Sharpe": _fmt_float(_sharpe(returns)),
        "最大回撤": _fmt_pct(_max_drawdown(returns)),
        "期末资产": _fmt_money(float(asset_series.iloc[-1])) if len(asset_series) else _fmt_money(0.0),
    }


def _fold_breakdown(stitched: pd.DataFrame, benchmark: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    merged = stitched.merge(benchmark[["date", "benchmark_daily_return"]], on="date", how="left")
    for fold, fold_df in merged.groupby("fold", sort=True):
        one = fold_df.copy().sort_values("date").reset_index(drop=True)
        strat_start = float(one["account_total_assets"].iloc[0])
        strat_end = float(one["account_total_assets"].iloc[-1])
        strat_total = strat_end / strat_start - 1.0
        bench_total = float((1.0 + one["benchmark_daily_return"]).prod() - 1.0)
        rows.append(
            {
                "fold": int(fold),
                "验证区间": f"{one['date'].iloc[0].date()} -> {one['date'].iloc[-1].date()}",
                "交易日数": int(len(one)),
                "策略折收益": _fmt_pct(strat_total),
                "基准折收益": _fmt_pct(bench_total),
                "超额收益": _fmt_pct(strat_total - bench_total),
                "折Sharpe": _fmt_float(_sharpe(one["strategy_daily_return"])),
                "折最大回撤": _fmt_pct(_max_drawdown(one["strategy_daily_return"])),
                "平均暴露": _fmt_pct(float(one["exposure"].mean())),
            }
        )
    return pd.DataFrame(rows)


def _checkpoint_row(label: str, stitched: pd.DataFrame, benchmark: pd.DataFrame, date_text: str) -> dict[str, str]:
    checkpoint = pd.Timestamp(date_text)
    stitched_cut = stitched[stitched["date"] <= checkpoint].copy()
    benchmark_cut = benchmark[benchmark["date"] <= checkpoint].copy()
    if stitched_cut.empty or benchmark_cut.empty:
        return {}
    return {
        "观察点": date_text,
        "策略连续资产": _fmt_money(float(stitched_cut["strategy_asset"].iloc[-1])),
        "基准连续资产": _fmt_money(float(benchmark_cut["benchmark_asset"].iloc[-1])),
        "策略累计收益": _fmt_pct(float(stitched_cut["strategy_profit_rate_continuous"].iloc[-1])),
        "基准累计收益": _fmt_pct(float(benchmark_cut["benchmark_profit_rate_continuous"].iloc[-1])),
    }


def _build_report_html(
    stitched: pd.DataFrame,
    benchmark: pd.DataFrame,
    benchmark_symbol: str,
    benchmark_name: str,
    fold_breakdown: pd.DataFrame,
    *,
    report_title: str,
    checkpoint_date: str | None,
    checkpoint_note: str,
) -> str:
    merged = stitched.merge(
        benchmark[["date", "benchmark_daily_return", "benchmark_asset", "benchmark_profit_rate_continuous"]],
        on="date",
        how="left",
    )
    merged["excess_daily_return"] = merged["strategy_daily_return"] - merged["benchmark_daily_return"]

    summary = pd.DataFrame(
        [
            _summary_row("策略连续 OOS", merged["strategy_daily_return"], merged["strategy_asset"]),
            _summary_row(f"基准 {benchmark_name}", merged["benchmark_daily_return"], merged["benchmark_asset"]),
        ]
    )

    start_date = merged["date"].iloc[0].date()
    end_date = merged["date"].iloc[-1].date()
    total_days = int(len(merged))
    preview_row = _checkpoint_row("观察点", stitched, benchmark, checkpoint_date) if checkpoint_date else {}
    preview_df = pd.DataFrame([preview_row]) if preview_row else pd.DataFrame()

    curve_tail = merged[["date", "strategy_asset", "benchmark_asset", "strategy_profit_rate_continuous", "benchmark_profit_rate_continuous"]].tail(10).copy()
    curve_tail["date"] = curve_tail["date"].dt.strftime("%Y-%m-%d")
    curve_tail["策略连续资产"] = curve_tail["strategy_asset"].map(_fmt_money)
    curve_tail["基准连续资产"] = curve_tail["benchmark_asset"].map(_fmt_money)
    curve_tail["策略累计收益"] = curve_tail["strategy_profit_rate_continuous"].map(_fmt_pct)
    curve_tail["基准累计收益"] = curve_tail["benchmark_profit_rate_continuous"].map(_fmt_pct)
    curve_tail = curve_tail[["date", "策略连续资产", "基准连续资产", "策略累计收益", "基准累计收益"]]
    curve_tail = curve_tail.rename(columns={"date": "日期"})
    preview_html = ""
    if not preview_df.empty:
        preview_html = (
            "<section>\n"
            f"<h2>截至 {checkpoint_date} 的连续资产观察</h2>\n"
            f"<p class=\"section-note\">{checkpoint_note}</p>\n"
            f"{_html_table(preview_df)}\n"
            "</section>\n"
        )

    style = """
<style>
:root {
  color-scheme: light;
  --bg: #eff4fb;
  --surface: #ffffff;
  --surface-2: #f8fbff;
  --border: #d2d9e3;
  --text: #18212f;
  --muted: #5f6b7a;
  --accent: #0f62fe;
  --accent-soft: #e7f0ff;
  --good: #0f9d58;
  --warn: #b7791f;
}
* {
  box-sizing: border-box;
}
body {
  margin: 0;
  padding: 24px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: var(--text);
  background: linear-gradient(180deg, #f7faff 0%, #edf3fb 100%);
}
.page {
  max-width: 1440px;
  margin: 0 auto;
}
.hero {
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 20px 24px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.06);
}
.hero h1 {
  margin: 0 0 10px;
  font-size: 28px;
  line-height: 1.2;
}
.meta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-top: 18px;
}
.meta-card {
  background: var(--surface-2);
  border: 1px solid var(--border);
  padding: 12px 14px;
}
.meta-label {
  display: block;
  margin-bottom: 6px;
  color: var(--muted);
  font-size: 12px;
}
.meta-value {
  font-size: 18px;
  font-weight: 600;
}
section {
  margin-top: 18px;
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 18px 20px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}
section h2 {
  margin: 0 0 12px;
  font-size: 20px;
  line-height: 1.25;
}
.section-note,
.bullet-notes li,
.empty-note {
  color: var(--muted);
}
.report-table-wrap {
  overflow-x: auto;
}
.report-table {
  width: max-content;
  min-width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  line-height: 1.35;
}
.report-table th,
.report-table td {
  border: 1px solid var(--border);
  padding: 7px 9px;
  white-space: nowrap;
  vertical-align: top;
  background: #fff;
}
.report-table th {
  background: #edf4ff;
  font-weight: 600;
  text-align: left;
}
.report-table td:not(:first-child) {
  text-align: right;
}
.report-table td:nth-child(2),
.report-table td:nth-child(3),
.report-table td:last-child {
  font-variant-numeric: tabular-nums;
}
.bullet-notes {
  margin: 0;
  padding-left: 18px;
}
.bullet-notes li + li {
  margin-top: 6px;
}
</style>
"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{report_title}</title>
  {style}
</head>
<body>
  <div class="page">
    <div class="hero">
      <h1>{report_title}</h1>
      <div class="meta-grid">
        <div class="meta-card"><span class="meta-label">策略</span><span class="meta-value">legacy_momentum_low_turnover_v1</span></div>
        <div class="meta-card"><span class="meta-label">连续样本外区间</span><span class="meta-value">{start_date} 至 {end_date}</span></div>
        <div class="meta-card"><span class="meta-label">样本外交易日</span><span class="meta-value">{total_days}</span></div>
        <div class="meta-card"><span class="meta-label">基准</span><span class="meta-value">{benchmark_symbol} / {benchmark_name}</span></div>
      </div>
    </div>
    <section>
      <h2>结论摘要</h2>
      {_html_table(summary)}
    </section>
    {preview_html}
    <section>
      <h2>Fold 收益分解</h2>
      {_html_table(fold_breakdown)}
    </section>
    <section>
      <h2>连续曲线尾部快照</h2>
      {_html_table(curve_tail)}
    </section>
    <section>
      <h2>解释</h2>
      <ul class="bullet-notes">
        <li>账单预览表中的 1000000 重置点来自 walk-forward 新折开始，不代表策略把前一折收益回吐到 100 万。</li>
        <li>这份报表把四个验证折按真实时间顺序拼成一条连续 OOS 曲线，用于回答“长期到底赚没赚钱”。</li>
        <li>这份报表只解决连续 OOS 与基准对比问题；行情分段验证另列为下一项任务。</li>
      </ul>
    </section>
  </div>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Export continuous OOS report for low-turnover strategy")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--daily-assets", type=Path, default=Path("reports/phase0_low_turnover_daily_assets.csv"))
    parser.add_argument("--report-output", type=Path, default=Path("reports/phase0_low_turnover_oos_report.html"))
    parser.add_argument("--curve-output", type=Path, default=Path("reports/phase0_low_turnover_oos_curve.csv"))
    parser.add_argument("--fold-output", type=Path, default=Path("reports/phase0_low_turnover_oos_fold_compare.csv"))
    parser.add_argument("--title", default="Phase 0 Low Turnover Continuous OOS Report")
    parser.add_argument("--checkpoint-date", default="2025-05-30")
    parser.add_argument(
        "--checkpoint-note",
        default="这一步专门用来纠正账单预览的阅读偏差：这里的观察日期是历史观察点，不是当前日期。预览表按 walk-forward 折展示，中间还有折重置，不等于一条连续复利资金曲线。",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    configure_local_history(config.get("local_history", {}), Path.cwd())

    daily_assets = _load_assets(args.daily_assets)
    if daily_assets.empty:
        raise SystemExit("daily assets csv is empty")

    initial_cash = float(config.get("walk_forward", {}).get("initial_cash", 1_000_000))
    stitched = _build_stitched_curve(daily_assets, initial_cash)
    benchmark_symbol = str(config.get("benchmark_symbol", "SH.000300"))
    benchmark = _load_benchmark_curve(
        benchmark_symbol,
        pd.Timestamp(stitched["date"].min()),
        pd.Timestamp(stitched["date"].max()),
        stitched["date"],
        initial_cash,
    )
    benchmark_name = str(benchmark["benchmark_name"].iloc[0])

    curve_df = stitched.merge(
        benchmark[["date", "benchmark_daily_return", "benchmark_asset", "benchmark_profit_rate_continuous"]],
        on="date",
        how="left",
    )
    curve_df["excess_asset"] = curve_df["strategy_asset"] - curve_df["benchmark_asset"]
    curve_df["excess_profit_rate"] = curve_df["strategy_profit_rate_continuous"] - curve_df["benchmark_profit_rate_continuous"]

    fold_breakdown = _fold_breakdown(stitched, benchmark)
    report = _build_report_html(
        stitched,
        benchmark,
        benchmark_symbol,
        benchmark_name,
        fold_breakdown,
        report_title=args.title,
        checkpoint_date=args.checkpoint_date,
        checkpoint_note=args.checkpoint_note,
    )

    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    curve_df.to_csv(args.curve_output, index=False, encoding="utf-8")
    fold_breakdown.to_csv(args.fold_output, index=False, encoding="utf-8")
    args.report_output.write_text(report, encoding="utf-8")

    print(args.report_output)
    print(args.curve_output)
    print(args.fold_output)


if __name__ == "__main__":
    main()
