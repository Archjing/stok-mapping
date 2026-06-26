from __future__ import annotations

import argparse
import html
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _calc_metrics(returns: pd.Series) -> dict[str, float]:
    clean = returns.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if clean.empty:
        return {"total_return": 0.0, "annualized_return": 0.0, "sharpe": 0.0, "max_drawdown": 0.0, "win_rate": 0.0}
    equity = (1.0 + clean).cumprod()
    total_return = float(equity.iloc[-1] - 1.0)
    annualized = float(equity.iloc[-1] ** (252 / len(clean)) - 1.0) if len(clean) > 0 and equity.iloc[-1] > 0 else 0.0
    std = float(clean.std(ddof=0))
    sharpe = float(clean.mean() / std * np.sqrt(252)) if std > 0 else 0.0
    drawdown = equity / equity.cummax() - 1.0
    return {
        "total_return": total_return,
        "annualized_return": annualized,
        "sharpe": sharpe,
        "max_drawdown": float(drawdown.min()) if not drawdown.empty else 0.0,
        "win_rate": float((clean > 0).mean()),
    }


def _classify_regime(row: pd.Series) -> str:
    bench_return = float(row["benchmark_63d_return"])
    bench_drawdown = float(row["benchmark_drawdown"])
    bench_vol = float(row["benchmark_21d_vol"])
    if bench_drawdown <= -0.15 or bench_return <= -0.10:
        return "回撤/下行"
    if bench_return >= 0.10 and bench_drawdown > -0.08:
        return "顺风/上行"
    if bench_vol >= 0.22:
        return "高波动震荡"
    return "震荡/中性"


def _format_pct(value: Any) -> str:
    return f"{float(value) * 100:.2f}%"


def _format_num(value: Any) -> str:
    return f"{float(value):.4f}"


def _format_html(summary_df: pd.DataFrame, segment_df: pd.DataFrame) -> str:
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
  max-width: 1180px;
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
  margin: 0 0 18px;
  color: #4b5563;
}
.table-wrap {
  overflow: auto;
  max-height: 70vh;
  margin: 16px 0 28px;
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
.regime-up td {
  background: #eefaf1;
}
.regime-down td {
  background: #fff0f0;
}
.regime-volatile td {
  background: #fff7e6;
}
</style>
"""
    summary_headers = [
        "市场状态",
        "交易日数",
        "策略总收益",
        "基准总收益",
        "超额收益",
        "策略Sharpe",
        "策略最大回撤",
        "平均暴露",
    ]
    summary_rows = []
    for _, row in summary_df.iterrows():
        cls = ""
        regime = str(row["market_regime"])
        if "顺风" in regime:
            cls = ' class="regime-up"'
        elif "回撤" in regime:
            cls = ' class="regime-down"'
        elif "高波动" in regime:
            cls = ' class="regime-volatile"'
        cells = [
            regime,
            str(int(row["days"])),
            _format_pct(row["strategy_total_return"]),
            _format_pct(row["benchmark_total_return"]),
            _format_pct(row["excess_total_return"]),
            _format_num(row["strategy_sharpe"]),
            _format_pct(row["strategy_max_drawdown"]),
            _format_pct(row["average_exposure"]),
        ]
        summary_rows.append(f"<tr{cls}>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in cells) + "</tr>")

    segment_headers = ["序号", "市场状态", "开始日期", "结束日期", "交易日数", "策略收益", "基准收益", "超额收益"]
    segment_rows = []
    for _, row in segment_df.iterrows():
        cells = [
            str(int(row["segment_id"])),
            str(row["market_regime"]),
            str(row["start_date"]),
            str(row["end_date"]),
            str(int(row["days"])),
            _format_pct(row["strategy_total_return"]),
            _format_pct(row["benchmark_total_return"]),
            _format_pct(row["excess_total_return"]),
        ]
        segment_rows.append("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in cells) + "</tr>")

    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>Phase 0 Market Regime Report</title>\n"
        + style
        + "</head>\n<body>\n<div class=\"page\">\n"
        "<div class=\"title-row\"><h1>Phase 0 Market Regime Report</h1>"
        f"<span class=\"generated-at\">生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</span></div>\n"
        "<p>按沪深300近 63 日收益、回撤和 21 日波动率划分市场状态，用于检查策略是否只依赖顺风行情。</p>\n"
        "<h2>状态汇总</h2>\n<div class=\"table-wrap\"><table><thead><tr>"
        + "".join(f"<th>{html.escape(header)}</th>" for header in summary_headers)
        + "</tr></thead><tbody>"
        + "\n".join(summary_rows)
        + "</tbody></table></div>\n"
        "<h2>连续区间明细</h2>\n<div class=\"table-wrap\"><table><thead><tr>"
        + "".join(f"<th>{html.escape(header)}</th>" for header in segment_headers)
        + "</tr></thead><tbody>"
        + "\n".join(segment_rows)
        + "</tbody></table></div>\n"
        "</div>\n</body>\n</html>\n"
    )


def export_market_regime_report(
    *,
    input_path: Path,
    summary_output: Path,
    segment_output: Path,
    html_output: Path,
) -> dict[str, Any]:
    df = pd.read_csv(input_path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["benchmark_63d_return"] = df["benchmark_asset"] / df["benchmark_asset"].shift(63) - 1.0
    df["benchmark_drawdown"] = df["benchmark_asset"] / df["benchmark_asset"].cummax() - 1.0
    df["benchmark_21d_vol"] = df["benchmark_daily_return"].rolling(21).std(ddof=0).fillna(0.0) * np.sqrt(252)
    df["benchmark_63d_return"] = df["benchmark_63d_return"].fillna(0.0)
    df["market_regime"] = df.apply(_classify_regime, axis=1)
    df["segment_id"] = (df["market_regime"] != df["market_regime"].shift(1)).cumsum()

    summary_rows = []
    for regime, group in df.groupby("market_regime", sort=False):
        strategy_metrics = _calc_metrics(group["strategy_daily_return"])
        benchmark_metrics = _calc_metrics(group["benchmark_daily_return"])
        summary_rows.append(
            {
                "market_regime": regime,
                "days": int(len(group)),
                "strategy_total_return": strategy_metrics["total_return"],
                "benchmark_total_return": benchmark_metrics["total_return"],
                "excess_total_return": strategy_metrics["total_return"] - benchmark_metrics["total_return"],
                "strategy_annualized_return": strategy_metrics["annualized_return"],
                "benchmark_annualized_return": benchmark_metrics["annualized_return"],
                "strategy_sharpe": strategy_metrics["sharpe"],
                "strategy_max_drawdown": strategy_metrics["max_drawdown"],
                "benchmark_max_drawdown": benchmark_metrics["max_drawdown"],
                "average_exposure": float(group["exposure"].mean()),
            }
        )
    summary_df = pd.DataFrame(summary_rows).sort_values("days", ascending=False)

    segment_rows = []
    for segment_id, group in df.groupby("segment_id", sort=True):
        strategy_metrics = _calc_metrics(group["strategy_daily_return"])
        benchmark_metrics = _calc_metrics(group["benchmark_daily_return"])
        segment_rows.append(
            {
                "segment_id": int(segment_id),
                "market_regime": str(group["market_regime"].iloc[0]),
                "start_date": group["date"].iloc[0].date().isoformat(),
                "end_date": group["date"].iloc[-1].date().isoformat(),
                "days": int(len(group)),
                "strategy_total_return": strategy_metrics["total_return"],
                "benchmark_total_return": benchmark_metrics["total_return"],
                "excess_total_return": strategy_metrics["total_return"] - benchmark_metrics["total_return"],
            }
        )
    segment_df = pd.DataFrame(segment_rows)

    summary_output.parent.mkdir(parents=True, exist_ok=True)
    segment_output.parent.mkdir(parents=True, exist_ok=True)
    html_output.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(summary_output, index=False, encoding="utf-8-sig")
    segment_df.to_csv(segment_output, index=False, encoding="utf-8-sig")
    html_output.write_text(_format_html(summary_df, segment_df), encoding="utf-8")
    return {"summary": summary_output, "segments": segment_output, "html": html_output, "rows": len(df)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="reports/phase0/phase0_low_turnover_oos_curve.csv")
    parser.add_argument("--summary-output", default="reports/phase0/phase0_market_regime_summary.csv")
    parser.add_argument("--segment-output", default="reports/phase0/phase0_market_regime_segments.csv")
    parser.add_argument("--html-output", default="reports/phase0/phase0_market_regime_report.html")
    args = parser.parse_args()
    result = export_market_regime_report(
        input_path=Path(args.input),
        summary_output=Path(args.summary_output),
        segment_output=Path(args.segment_output),
        html_output=Path(args.html_output),
    )
    print(f"summary={result['summary']}")
    print(f"segments={result['segments']}")
    print(f"html={result['html']}")
    print(f"rows={result['rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
