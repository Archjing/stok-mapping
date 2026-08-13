"""Backfill cninfo announcements for specific stocks into the AI corpus.

抓取指定个股的历史公告（AkShare cninfo 接口），用本地事件分类过滤，upsert 到
``data/ai_corpus/ai_corpus.sqlite``。

Usage:
    .venv/bin/python3 scripts/backfill_cninfo_stock_announcements.py 000651 300308 \
        --start 20220101 --end 20260813 --event-type share_buyback
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import warnings
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quant.ai_corpus.providers.cninfo import (  # noqa: E402
    _classify_event_type,
    _passes_event_filter,
    parse_cninfo_announcements,
)
from quant.ai_corpus.storage import upsert_ai_corpus_documents  # noqa: E402

warnings.filterwarnings("ignore")
DB_PATH = Path("data/ai_corpus/ai_corpus.sqlite")
RAW_ARCHIVE = Path("data/raw_data/ai_corpus/cninfo")


def _fetch_symbol_announcements(symbol: str, start: str, end: str) -> pd.DataFrame:
    import akshare as ak

    return ak.stock_zh_a_disclosure_report_cninfo(
        symbol=symbol, market="沪深京", start_date=start, end_date=end
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("symbols", nargs="+", help="6-digit stock codes")
    parser.add_argument("--start", default="20220101")
    parser.add_argument("--end", default="20260813")
    parser.add_argument("--event-type", default=None,
                        help="Optional event type filter (e.g. share_buyback)")
    parser.add_argument("--limit", type=int, default=0, help="Max rows per symbol (0=all)")
    args = parser.parse_args()

    event_type = args.event_type or ""
    total_upserted = 0
    for code in args.symbols:
        print(f"\n=== 抓取 {code} ===")
        frame = _fetch_symbol_announcements(code, args.start, args.end)
        print(f"原始公告数: {len(frame)}")
        if frame.empty:
            print("  (无数据)")
            continue
        if args.limit > 0:
            frame = frame.head(args.limit)
        # 归档原始抓取结果（schema 要求 raw_path 非空）
        from datetime import datetime

        raw_path = RAW_ARCHIVE / "search" / datetime.now().date().isoformat().replace("-", "/") / f"cninfo_{code}_{args.start}_{args.end}.json"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(frame.to_json(orient="records", force_ascii=False, date_format="iso"), encoding="utf-8")
        # 先分类 + 过滤，再 parse
        if event_type and event_type not in {"", "announcement"}:
            filtered = frame[
                frame["公告标题"].apply(
                    lambda t: _passes_event_filter(str(t), event_type)
                )
            ]
            print(f"过滤后 ({event_type}): {len(filtered)}")
            frame = filtered
        docs = parse_cninfo_announcements(frame, event_type=event_type or "announcement", raw_path=raw_path)
        # parse 后 event_type 已经分类好；如指定事件类型则进一步收敛
        if event_type and event_type not in {"", "announcement"}:
            docs = [d for d in docs if d["event_type"] == event_type]
        print(f"待入库文档: {len(docs)}")
        changed = upsert_ai_corpus_documents(DB_PATH, docs)
        total_upserted += len(docs)
        print(f"upsert 完成 (行数 {len(docs)}, changes {changed})")

    print(f"\n总计入库 {total_upserted} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
