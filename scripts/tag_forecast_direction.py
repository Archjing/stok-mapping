"""Classify and tag earnings-forecast direction for cninfo announcements in the corpus.

Downloads each forecast's PDF, classifies direction (预增/预减/扭亏/...), and
writes it back to the ``topics`` field as a derived ``direction=`` tag.  The
original title/raw fields are left untouched (direction is a derived field).

Usage:
    .venv/bin/python3 scripts/tag_forecast_direction.py [--limit N] [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
import warnings
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quant.ai_corpus.providers.cninfo_direction import (  # noqa: E402
    fetch_and_classify,
)

warnings.filterwarnings("ignore")
DB_PATH = Path("data/ai_corpus/ai_corpus.sqlite")


def _existing_direction(topics: str) -> str | None:
    for part in (topics or "").split("|"):
        if part.startswith("direction="):
            return part.split("=", 1)[1]
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Max docs to process (0=all)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT document_id, symbols, published_at, title, url, topics "
        "FROM ai_corpus_documents WHERE provider='cninfo' AND event_type='earnings_forecast'",
        conn,
    )
    # skip already-tagged
    df["have_dir"] = df["topics"].apply(lambda t: _existing_direction(t) is not None)
    todo = df[~df["have_dir"]]
    if args.limit > 0:
        todo = todo.head(args.limit)
    print(f"总业绩预告 {len(df)} 条, 待标注 {len(todo)} 条")

    counts: dict[str, int] = {}
    t0 = time.time()
    for i, (_, row) in enumerate(todo.iterrows()):
        direction, _ = fetch_and_classify(
            detail_url=row["url"],
            published_at=row["published_at"],
            title=row["title"],
        )
        counts[direction] = counts.get(direction, 0) + 1
        if not args.dry_run and direction != "未知":
            existing = _existing_direction(row["topics"])
            if existing is None:
                new_topics = f"{row['topics']}|direction={direction}" if row["topics"] else f"direction={direction}"
                conn.execute(
                    "UPDATE ai_corpus_documents SET topics=? WHERE document_id=?",
                    (new_topics, row["document_id"]),
                )
        if (i + 1) % 20 == 0:
            conn.commit()
            print(f"  [{i+1}/{len(todo)}] 已处理, 方向分布: {counts}")
    conn.commit()
    conn.close()
    print(f"\n完成 {len(todo)} 条, 耗时 {time.time()-t0:.1f}s")
    print("方向分布:", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
