from __future__ import annotations

import argparse
import html
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0.config import load_config
from scripts.export_strategy_bill import DEFAULT_STRATEGY_ID, _default_report_strategy_id, _strategy_report_cfg


DEFAULT_COMPARE_TITLE = "策略 OOS：早期区间与当前区间对比"
DEFAULT_COMPARE_NOTE = "两段应沿用相同 walk-forward 与执行口径；该表用于观察策略是否只适配某一段市场环境。"


def _period_compare_cfg(config: dict[str, Any], strategy_id: str) -> dict[str, Any]:
    return dict(_strategy_report_cfg(config, strategy_id).get("period_compare", {}) or {})


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
    drawdown = equity / equity.cummax() - 1.0
    return float(drawdown.min())


def _fmt_money(value: float) -> str:
    return f"{value:,.2f}"


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _fmt_float(value: float) -> str:
    return f"{value:.4f}"


def _load_curve(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def _summarize(label: str, path: Path) -> dict[str, str]:
    df = _load_curve(path)
    strategy_returns = df["strategy_daily_return"].fillna(0.0)
    strategy_total = float(df["strategy_asset"].iloc[-1] / df["strategy_asset"].iloc[0] - 1.0)
    benchmark_total = float(df["benchmark_asset"].iloc[-1] / df["benchmark_asset"].iloc[0] - 1.0)
    return {
        "区间": label,
        "起始日期": str(df["date"].iloc[0].date()),
        "结束日期": str(df["date"].iloc[-1].date()),
        "策略总收益": _fmt_pct(strategy_total),
        "基准总收益": _fmt_pct(benchmark_total),
        "超额收益": _fmt_pct(strategy_total - benchmark_total),
        "策略年化": _fmt_pct(_annualized_return(strategy_returns)),
        "策略Sharpe": _fmt_float(_sharpe(strategy_returns)),
        "策略最大回撤": _fmt_pct(_max_drawdown(strategy_returns)),
        "平均暴露": _fmt_pct(float(df["exposure"].mean())),
        "交易日数": str(len(df)),
    }


def _html_table(df: pd.DataFrame) -> str:
    header = "".join(f"<th>{html.escape(str(col))}</th>" for col in df.columns)
    rows = []
    for _, row in df.iterrows():
        cells = "".join(f"<td>{html.escape(str(row[col]))}</td>" for col in df.columns)
        rows.append(f"<tr>{cells}</tr>")
    return (
        '<div class="table-wrap"><table>'
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table></div>"
    )


def _parse_pct(text: str) -> float:
    return float(str(text).rstrip("%")) / 100.0


def _conclusion(summary: pd.DataFrame, *, early_label: str, current_label: str) -> tuple[str, list[dict[str, str]]]:
    early = summary[summary["区间"] == early_label].iloc[0]
    current = summary[summary["区间"] == current_label].iloc[0]
    early_excess = _parse_pct(early["超额收益"])
    current_excess = _parse_pct(current["超额收益"])
    early_sharpe = float(early["策略Sharpe"])
    current_sharpe = float(current["策略Sharpe"])

    if early_excess > 0 and current_excess > 0:
        text = f"结论：{early_label}和{current_label}都取得正超额收益，暂未看到该策略只依赖单一区间的明显证据。"
    else:
        text = "结论：不同区间表现存在明显分化，需要继续拆解市场状态和因子暴露。"

    cards = [
        {"指标": f"{early_label}超额收益", "数值": early["超额收益"]},
        {"指标": f"{current_label}超额收益", "数值": current["超额收益"]},
        {"指标": "Sharpe 差异", "数值": _fmt_float(early_sharpe - current_sharpe)},
    ]
    return text, cards


def _build_html(summary: pd.DataFrame, *, title: str, note: str) -> str:
    early_label = str(summary["区间"].iloc[0])
    current_label = str(summary["区间"].iloc[1])
    conclusion, cards = _conclusion(summary, early_label=early_label, current_label=current_label)
    cards_html = "".join(
        f'<div class="card"><span>{html.escape(item["指标"])}</span><strong>{html.escape(item["数值"])}</strong></div>'
        for item in cards
    )
    style = """
<style>
:root {
  color-scheme: light;
  --bg: #f3f6fb;
  --surface: #ffffff;
  --border: #d6dee8;
  --text: #172033;
  --muted: #607085;
  --accent: #116466;
}
* {
  box-sizing: border-box;
}
body {
  margin: 0;
  padding: 28px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: var(--text);
  background: var(--bg);
}
.page {
  max-width: 1280px;
  margin: 0 auto;
}
.hero {
  margin-bottom: 18px;
}
h1 {
  margin: 0 0 8px;
  font-size: 26px;
  letter-spacing: 0;
}
.note {
  margin: 0;
  color: var(--muted);
  line-height: 1.6;
}
.decision {
  margin: 16px 0;
  padding: 14px 16px;
  border-left: 4px solid var(--accent);
  background: #ffffff;
  font-size: 16px;
  line-height: 1.6;
  font-weight: 700;
}
.cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: 16px 0 18px;
}
.card {
  padding: 12px 14px;
  border: 1px solid var(--border);
  background: var(--surface);
}
.card span {
  display: block;
  color: var(--muted);
  font-size: 13px;
  margin-bottom: 6px;
}
.card strong {
  display: block;
  font-size: 22px;
  font-variant-numeric: tabular-nums;
}
.table-wrap {
  overflow: auto;
  max-height: 70vh;
  border: 1px solid var(--border);
  background: var(--surface);
}
table {
  width: max-content;
  min-width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
th,
td {
  border: 1px solid var(--border);
  padding: 8px 10px;
  white-space: nowrap;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
th:first-child,
td:first-child,
th:nth-child(2),
td:nth-child(2),
th:nth-child(3),
td:nth-child(3) {
  text-align: left;
}
th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #eaf1f8;
  font-weight: 700;
}
.explain {
  margin-top: 18px;
  padding: 14px 16px;
  border-left: 4px solid var(--accent);
  background: #ffffff;
  color: var(--muted);
  line-height: 1.7;
}
@media (max-width: 760px) {
  .cards {
    grid-template-columns: 1fr;
  }
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
</style>
"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  {style}
</head>
<body>
  <main class="page">
    <div class="hero">
      <div class="title-row">
        <h1>{html.escape(title)}</h1>
        <span class="generated-at">生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}</span>
      </div>
      <p class="note">{html.escape(note)}</p>
    </div>
    <div class="decision">{html.escape(conclusion)}</div>
    <div class="cards">{cards_html}</div>
    {_html_table(summary)}
    <div class="explain">
      重点看策略总收益、基准总收益、超额收益、Sharpe、最大回撤和平均暴露。若后续市场状态分段显示某类行情贡献过高，再结合行业分布、动量有效性、成交量环境和基本面因子暴露解释原因。
    </div>
  </main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare strategy OOS periods")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--strategy-id", default=None)
    parser.add_argument("--early-curve", type=Path, default=Path("reports/phase0_low_turnover_oos_curve_201808_202210.csv"))
    parser.add_argument("--current-curve", type=Path, default=Path("reports/phase0_low_turnover_oos_curve.csv"))
    parser.add_argument("--output", type=Path, default=Path("reports/phase0_low_turnover_period_compare.html"))
    parser.add_argument("--early-label", default="早期区间")
    parser.add_argument("--current-label", default="当前区间")
    parser.add_argument("--title", default=None)
    parser.add_argument("--note", default=None)
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else Path.cwd() / args.config
    config = load_config(config_path)
    strategy_id = str(args.strategy_id or _default_report_strategy_id(config) or DEFAULT_STRATEGY_ID)
    report_cfg = _period_compare_cfg(config, strategy_id)
    title = args.title or str(report_cfg.get("title") or DEFAULT_COMPARE_TITLE)
    note = args.note or str(report_cfg.get("note") or DEFAULT_COMPARE_NOTE)

    summary = pd.DataFrame(
        [
            _summarize(args.early_label, args.early_curve),
            _summarize(args.current_label, args.current_curve),
        ]
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(_build_html(summary, title=title, note=note), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
