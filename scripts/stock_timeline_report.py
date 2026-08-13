"""One-shot per-stock timeline report: six query lines in Markdown.

Usage:
    python scripts/stock_timeline_report.py 300308 [--days 365]

Environment:
    STOK_MAPPING_ROOT — project root (default: repo root); all DB paths derive
    from it.  Set this (or the individual STOK_*_DB overrides) to point at the
    stok-mapping project from any working directory.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quant.ai_corpus.stock_timeline import load_stock_timeline, normalize_symbol
from quant.ai_corpus.stock_timelines import (
    load_financial_timeline,
    load_shareholder_timeline,
    load_valuation_timeline,
)
from quant.ai_corpus.stock_timelines2 import (
    load_index_membership_changes,
    load_research_coverage_timeline,
)


def _fmt_wan(v: float) -> str:
    """Format large financial numbers in 亿."""
    if pd.isna(v):
        return "—"
    return f"{v / 1e8:.1f}亿"


def render(symbol: str, days: int | None = None) -> str:
    norm = normalize_symbol(symbol)
    if norm is None:
        raise SystemExit(f"无效股票代码: {symbol}")

    start = None
    if days:
        start = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")

    lines: list[str] = []
    lines.append(f"# {norm} 个股时间线")
    lines.append("")

    # 1. 财务时间线
    fin = load_financial_timeline(symbol=norm)
    lines.append("## 财务时间线（按披露日）")
    lines.append("")
    if fin.empty:
        lines.append("（无财务数据）")
    else:
        lines.append("| 披露日 | 报告期 | ROE | 营收 | 净利 | 营收增速 | 净利增速 |")
        lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
        for _, r in fin.head(8).iterrows():
            lines.append(
                f"| {r['announce_date']} | {r['report_date']} | {r['roe']:.1f}% | "
                f"{_fmt_wan(r['revenue'])} | {_fmt_wan(r['net_profit'])} | "
                f"{r['revenue_growth']:.1f}% | {r['profit_growth']:.1f}% |"
            )
    lines.append("")

    # 2. 估值时间线
    val = load_valuation_timeline(symbol=norm)
    lines.append("## 估值时间线")
    lines.append("")
    if val.empty:
        lines.append("（无估值数据）")
    else:
        pe = val["pe_ratio"].dropna()
        pb = val["pb_ratio"].dropna()
        lines.append(f"- 最新 PE: {pe.iloc[0]:.1f}（历史分位 { (pe <= pe.iloc[0]).mean()*100:.0f}%）")
        lines.append(f"- 最新 PB: {pb.iloc[0]:.2f}（历史分位 { (pb <= pb.iloc[0]).mean()*100:.0f}%）")
        lines.append("")
        lines.append("| 日期 | PE | PB | 市值 |")
        lines.append("| --- | ---: | ---: | ---: |")
        for _, r in val.head(5).iterrows():
            lines.append(f"| {r['date']} | {r['pe_ratio']:.1f} | {r['pb_ratio']:.2f} | {_fmt_wan(r['market_cap'])} |")
    lines.append("")

    # 3. 股东行为线
    sh = load_shareholder_timeline(symbol=norm)
    lines.append("## 股东行为线（回购/增持/减持）")
    lines.append("")
    if sh.empty:
        lines.append("（无股东行为记录）")
    else:
        lines.append("| 日期 | 类型 | 事件 |")
        lines.append("| --- | --- | --- |")
        for _, r in sh.head(10).iterrows():
            lines.append(f"| {r['published_at'][:10]} | {r['event_type']} | {r['title'][:40]} |")
    lines.append("")

    # 4. 指数成分线
    idx_ch = load_index_membership_changes(symbol=norm)
    lines.append("## 指数成分变迁线")
    lines.append("")
    if idx_ch.empty:
        lines.append("（无指数成分数据）")
    else:
        lines.append("| 日期 | 指数 | 变动 |")
        lines.append("| --- | --- | --- |")
        for _, r in idx_ch.iterrows():
            lines.append(f"| {r['trade_date']} | {r['index_code']} | {r['change']} |")
    lines.append("")

    # 5. 公告时间线
    tl = load_stock_timeline(symbol=norm, start_date=start)
    lines.append("## 公告时间线")
    lines.append("")
    if tl.empty:
        lines.append("（无公告记录）")
    else:
        lines.append("| 日期 | 类型 | 事件 |")
        lines.append("| --- | --- | --- |")
        for _, r in tl.head(15).iterrows():
            lines.append(f"| {r['published_at'][:10]} | {r['event_type']} | {r['title'][:40]} |")
    lines.append("")

    # 6. 机构关注线
    rc = load_research_coverage_timeline(symbol=norm)
    lines.append("## 机构关注线（研报覆盖）")
    lines.append("")
    if rc.empty:
        lines.append("（无研报数据——research_report provider 尚未回填历史数据）")
    else:
        lines.append("| 日期 | 机构 | 研报 |")
        lines.append("| --- | --- | --- |")
        for _, r in rc.head(10).iterrows():
            lines.append(f"| {r['published_at'][:10]} | {r['org']} | {r['title'][:40]} |")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("symbol", help="6位股票代码或 SH./SZ. 格式")
    parser.add_argument("--days", type=int, default=None, help="公告时间线只回看最近 N 天")
    args = parser.parse_args()
    print(render(args.symbol, args.days))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
