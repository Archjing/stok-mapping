"""Backfill + direction-tag earnings forecasts for semiconductor stocks.

Fetch 业绩预告 for stocks not yet in the corpus, then immediately classify the
direction from each announcement PDF and write a ``direction=`` tag.  Idempotent:
stocks already covered are skipped, so it can be re-run to resume after failure.

Usage:
    .venv/bin/python3 scripts/backfill_semiconductor_forecasts.py [--limit N] [--industries 电气设备,汽车配件]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quant.ai_corpus.providers.cninfo import parse_cninfo_announcements  # noqa: E402
from quant.ai_corpus.providers.cninfo_direction import fetch_and_classify  # noqa: E402
from quant.ai_corpus.storage import upsert_ai_corpus_documents  # noqa: E402

warnings.filterwarnings("ignore")
DB_PATH = Path("data/ai_corpus/ai_corpus.sqlite")
MARKET_DB = Path("data/a_share_history.sqlite")
RAW_DIR = Path("data/raw_data/ai_corpus/cninfo/search")
START, END = "20200101", "20260813"

DEFAULT_INDUSTRIES = ["半导体"]


def _connect(path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with a busy timeout so concurrent writers retry."""
    conn = sqlite3.connect(path, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def _industry_codes(industries: list[str]) -> list[str]:
    placeholders = ",".join(f"'{i}'" for i in industries)
    with sqlite3.connect(MARKET_DB) as conn:
        rows = conn.execute(
            f"SELECT symbol FROM market_stocks WHERE industry IN ({placeholders}) AND list_status='上市'"
        ).fetchall()
    return sorted(r[0].split(".")[1] for r in rows)


def _covered_codes() -> set[str]:
    if not DB_PATH.is_file():
        return set()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT DISTINCT symbols FROM ai_corpus_documents "
            "WHERE provider='cninfo' AND event_type='earnings_forecast'"
        ).fetchall()
    return {r[0] for r in rows if r[0]}


def _has_direction(topics: str) -> bool:
    return "direction=" in (topics or "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Max new stocks to process")
    parser.add_argument("--industries", default=",".join(DEFAULT_INDUSTRIES),
                        help="Comma-separated industry names")
    args = parser.parse_args()

    industries = [i.strip() for i in args.industries.split(",") if i.strip()]
    all_codes = _industry_codes(industries)
    covered = _covered_codes()
    todo = [c for c in all_codes if c not in covered]
    if args.limit > 0:
        todo = todo[: args.limit]
    print(f"行业 {industries}: {len(all_codes)} 只, 已覆盖 {len(covered)}, 待补 {len(todo)}")

    import akshare as ak

    fetched_total = tagged_total = 0
    t0 = time.time()
    for i, code in enumerate(todo):
        try:
            frame = ak.stock_zh_a_disclosure_report_cninfo(
                symbol=code, market="沪深京", category="业绩预告",
                start_date=START, end_date=END,
            )
        except Exception as e:
            print(f"[{i+1}/{len(todo)}] {code}: ERR {type(e).__name__}")
            continue
        if frame.empty:
            print(f"[{i+1}/{len(todo)}] {code}: 0 条")
            continue

        # archive + parse
        day = datetime.now().date().isoformat()
        raw_path = RAW_DIR / day.replace("-", "/") / f"cninfo_{code}_earnings_forecast.json"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(
            frame.to_json(orient="records", force_ascii=False, date_format="iso"),
            encoding="utf-8",
        )
        docs = parse_cninfo_announcements(frame, event_type="earnings_forecast", raw_path=raw_path)
        docs = [d for d in docs if d["event_type"] == "earnings_forecast"]
        upsert_ai_corpus_documents(DB_PATH, docs)
        fetched_total += len(docs)

        # direction tag each doc (fetch PDF + classify)
        n_tagged = 0
        for d in docs:
            if _has_direction(d["topics"]):
                continue
            direction, _ = fetch_and_classify(
                detail_url=d["url"], published_at=d["published_at"], title=d["title"],
            )
            if direction != "未知":
                new_topics = f"{d['topics']}|direction={direction}" if d["topics"] else f"direction={direction}"
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute(
                        "UPDATE ai_corpus_documents SET topics=? WHERE document_id=?",
                        (new_topics, d["document_id"]),
                    )
                n_tagged += 1
        tagged_total += n_tagged
        print(f"[{i+1}/{len(todo)}] {code}: {len(docs)} 条, 标注 {n_tagged}")

    print(f"\n完成: 抓取 {fetched_total} 条, 标注 {tagged_total} 条, 耗时 {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
