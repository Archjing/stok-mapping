"""Event-study orchestration and Markdown reporting.

Ties together the event-study core (Task 1) and the linking layer (Task 2):
load corpus docs → link to securities/indices → load returns → compute CAR →
cross-sectional test → write a Markdown report + CAR detail CSV.

Research + explanation layer only: never feeds a strategy ranker.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from quant.ai_corpus.linking import (
    link_stock_events,
    load_industry_indices,
    link_policy_events,
    normalize_stock_symbol,
)
from quant.research.event_study.abnormal_returns import (
    DEFAULT_WINDOWS,
    compute_ar_car,
    map_event_to_trading_day,
)
from quant.research.event_study.aggregation import aggregate_events, cross_sectional_test
from quant.research.event_study.market_model import estimate_market_model

BENCHMARK_SYMBOL = "SH.000300"


@dataclass(frozen=True)
class EventStudyResult:
    report_md_path: Path
    detail_csv_path: Path
    n_events: int
    n_linked: int
    summary: pd.DataFrame


def _load_docs(
    corpus_db: Path,
    provider: str | None,
    event_type: str | None,
    direction: str | None = None,
    topic_tag: str | None = None,
    topic_value: str | None = None,
) -> pd.DataFrame:
    if not corpus_db.is_file():
        return pd.DataFrame()
    clauses: list[str] = []
    params: list[Any] = []
    if provider:
        clauses.append("provider = ?")
        params.append(provider)
    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    if direction:
        # direction is stored as a derived `direction=...` tag in the topics column
        clauses.append("topics LIKE ?")
        params.append(f"%direction={direction}%")
    if topic_tag and topic_value:
        # generic tag filter, e.g. topic_tag='rating', topic_value='买入'
        clauses.append("topics LIKE ?")
        params.append(f"%{topic_tag}={topic_value}%")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT document_id, provider, event_type, published_at, title, raw_text, symbols, topics
        FROM ai_corpus_documents
        {where}
        ORDER BY published_at
    """
    with sqlite3.connect(corpus_db) as conn:
        try:
            return pd.read_sql_query(sql, conn, params=params)
        except sqlite3.Error:
            return pd.DataFrame()


def _load_industry_symbols(market_db: Path, industries: list[str]) -> set[str]:
    """Return the set of stock symbols (SH./SZ.xxxxxx) in the given industries."""
    if not market_db.is_file() or not industries:
        return set()
    placeholders = ",".join("?" for _ in industries)
    with sqlite3.connect(market_db) as conn:
        try:
            rows = conn.execute(
                f"SELECT symbol FROM market_stocks WHERE industry IN ({placeholders})",
                industries,
            ).fetchall()
        except sqlite3.Error:
            return set()
    return {r[0] for r in rows}


def _load_returns(conn: sqlite3.Connection, symbol: str) -> pd.Series:
    """Return adjusted_close returns for a stock or index symbol, date-ascending.

    Stocks use the forward-adjusted (``qfq``) series so returns are total-return
    consistent across ex-dividend/ex-right dates; indices have no adjust_type.
    """
    try:
        table = "market_index_bars" if "." in symbol and _is_index_symbol(conn, symbol) else "market_daily_bars"
        price_col = "close" if table == "market_index_bars" else "adjusted_close"
        if table == "market_daily_bars":
            df = pd.read_sql_query(
                f"SELECT date, {price_col} AS price FROM {table} "
                "WHERE symbol = ? AND adjust_type = 'qfq' ORDER BY date",
                conn,
                params=(symbol,),
            )
        else:
            df = pd.read_sql_query(
                f"SELECT date, {price_col} AS price FROM {table} WHERE symbol = ? ORDER BY date",
                conn,
                params=(symbol,),
            )
    except sqlite3.Error:
        return pd.Series(dtype=float)
    if df.empty:
        return pd.Series(dtype=float)
    ret = df["price"].astype(float).pct_change()
    ret.index = df["date"].values
    return ret


def _is_index_symbol(conn: sqlite3.Connection, symbol: str) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM market_indices WHERE symbol = ? LIMIT 1", (symbol,)
        ).fetchone()
        return row is not None
    except sqlite3.Error:
        return False


def _load_calendar(conn: sqlite3.Connection) -> pd.DataFrame:
    try:
        return pd.read_sql_query(
            "SELECT DISTINCT date FROM market_daily_bars ORDER BY date", conn
        )
    except sqlite3.Error:
        return pd.DataFrame()


def _load_benchmark(conn: sqlite3.Connection, symbol: str) -> pd.Series:
    return _load_returns(conn, symbol)


def _align_returns(
    asset_ret: pd.Series,
    market_ret: pd.Series,
) -> tuple[pd.Series, pd.Series]:
    """Inner-join asset and market returns on their date index."""
    idx = asset_ret.index.intersection(market_ret.index)
    return asset_ret.loc[idx], market_ret.loc[idx]


def run_event_study(
    *,
    corpus_db: str | Path,
    market_db: str | Path,
    provider: str | None = None,
    event_type: str | None = None,
    direction: str | None = None,
    topic_tag: str | None = None,
    topic_value: str | None = None,
    industries: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    benchmark: str = BENCHMARK_SYMBOL,
    windows: list[tuple[int, int]] | None = None,
    output_dir: Path | None = None,
    embedding_model=None,
) -> EventStudyResult:
    """Run a full event study over corpus documents and write report + CSV.

    ``direction`` optionally filters by the derived ``direction=...`` tag in the
    ``topics`` column (e.g. ``预增`` / ``预减`` / ``扭亏``).
    ``topic_tag``/``topic_value`` filter by a generic tag, e.g. rating=买入.
    ``industries`` optionally restricts to stocks in the given market industries.
    """
    windows = windows or DEFAULT_WINDOWS
    corpus_path = Path(corpus_db)
    market_path = Path(market_db)
    docs = _load_docs(corpus_path, provider, event_type, direction, topic_tag, topic_value)
    if industries:
        industry_symbols = _load_industry_symbols(market_path, industries)
        if industry_symbols:
            # docs carry 6-digit codes in symbols; normalize to SH./SZ. for matching
            docs = docs[docs["symbols"].apply(
                lambda s: normalize_stock_symbol(s) in industry_symbols
            )]
    if start_date:
        docs = docs[docs["published_at"].astype(str) >= start_date]
    if end_date:
        docs = docs[docs["published_at"].astype(str) <= end_date]
    if docs.empty:
        raise ValueError("no corpus documents matched the filters")

    with sqlite3.connect(market_path) as conn:
        calendar = _load_calendar(conn)
        benchmark_ret = _load_benchmark(conn, benchmark)

        # link to securities
        if provider == "gov_policy":
            indices = load_industry_indices(market_path, category="一级行业指数")
            linked = link_policy_events(docs, indices, model=embedding_model)
        else:
            linked = link_stock_events(docs)

        # compute CAR per (event, symbol)
        car_rows: list[dict[str, Any]] = []
        for _, link in linked.iterrows():
            symbol = link["symbol"]
            event_day = map_event_to_trading_day(calendar, str(link["published_at"]))
            if event_day is None:
                continue
            asset_ret = _load_returns(conn, symbol)
            if asset_ret.empty or benchmark_ret.empty:
                continue
            asset_ret, market_ret = _align_returns(asset_ret, benchmark_ret)
            if len(asset_ret) < 150:
                continue
            try:
                event_idx = list(asset_ret.index).index(event_day)
            except ValueError:
                continue
            alpha, beta = estimate_market_model(
                asset_ret, market_ret, event_idx=event_idx
            )
            for start, end in windows:
                ar_car = compute_ar_car(
                    asset_ret, market_ret, alpha, beta, event_idx=event_idx,
                    windows=[(start, end)],
                )
                car_rows.append({
                    "document_id": link.get("document_id"),
                    "provider": link.get("provider"),
                    "published_at": link.get("published_at"),
                    "title": link.get("title"),
                    "symbol": symbol,
                    "event_day": event_day,
                    "window": f"({start:+d}, {end:+d})",
                    "car": ar_car.iloc[0]["car"],
                })

    if not car_rows:
        raise ValueError("no linked events produced CAR rows (check calendar/returns alignment)")

    car_frame = pd.DataFrame(car_rows)
    # per-window cross-sectional summary
    summary = aggregate_events(car_frame, group_col="window")
    summary["mean_car_pct"] = summary["mean_car"] * 100

    # write outputs
    if output_dir is None:
        output_dir = Path("reports/runs") / pd.Timestamp.now().strftime("%Y-%m-%d")
    output_dir.mkdir(parents=True, exist_ok=True)
    prov = provider or "all"
    evt = event_type or "all"
    detail_csv_path = output_dir / f"event_study_{prov}_{evt}_car.csv"
    report_md_path = output_dir / f"event_study_{prov}_{evt}.md"
    car_frame.to_csv(detail_csv_path, index=False)
    report_md_path.write_text(
        _render_report(
            provider=prov, event_type=evt, n_events=len(docs),
            n_linked=len(linked), summary=summary, car_frame=car_frame,
            benchmark=benchmark, windows=windows,
        ),
        encoding="utf-8",
    )
    return EventStudyResult(
        report_md_path=report_md_path,
        detail_csv_path=detail_csv_path,
        n_events=len(docs),
        n_linked=len(linked),
        summary=summary,
    )


def _render_report(
    *,
    provider: str,
    event_type: str,
    n_events: int,
    n_linked: int,
    summary: pd.DataFrame,
    car_frame: pd.DataFrame,
    benchmark: str,
    windows: list[tuple[int, int]],
) -> str:
    lines: list[str] = []
    lines.append(f"# 事件研究报告：{provider}/{event_type}")
    lines.append("")
    lines.append(f"- 事件样本：{n_events}")
    lines.append(f"- 成功关联标的：{n_linked}")
    lines.append(f"- 基准：{benchmark}")
    lines.append(f"- 事件窗口：{', '.join(f'({s:+d}, {e:+d})' for s, e in windows)}")
    lines.append("")
    lines.append("## 板块/个股级 CAR 汇总")
    lines.append("")
    lines.append("| 窗口 | N | 平均 CAR | t 值 | p 值 | 正占比 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for _, row in summary.iterrows():
        lines.append(
            f"| {row['group']} | {row['n']} | {row['mean_car_pct']:.2f}% | "
            f"{row['t_stat']:.2f} | {row['p_value']:.3f} | {row['positive_share']:.1%} |"
        )
    lines.append("")
    lines.append("## Top 冲击事件（按 |CAR| 排序）")
    lines.append("")
    lines.append("| 标的 | 事件日 | CAR | 标题 |")
    lines.append("| --- | --- | ---: | --- |")
    top = car_frame.reindex(car_frame["car"].abs().sort_values(ascending=False).index).head(20)
    for _, row in top.iterrows():
        title = str(row["title"])[:60]
        lines.append(
            f"| {row['symbol']} | {row['event_day']} | {row['car']*100:.2f}% | {title} |"
        )
    lines.append("")
    lines.append("## 样本量局限")
    lines.append("")
    lines.append(
        f"当前事件样本 {n_events} 条，显著性检验效力有限；CAR 结论应保守解读，"
        "仅作为后续事件因子进入 admission 前的假设依据，不作为交易信号。"
    )
    lines.append("")
    return "\n".join(lines)
