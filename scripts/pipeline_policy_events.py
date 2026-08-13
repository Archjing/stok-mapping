"""Stage-1 pipeline: fetch finance flashes → recognize macro policy events.

Pipeline:
1. fetch 财联社/新浪/华尔街见闻 flashes via existing providers
2. upsert flashes into ai_corpus_documents (existing schema)
3. rule prefilter + oMLX embedding refine → policy events
4. write recognized policy events into data/macro_policy_events.sqlite

The event table is the structured, point-in-time policy-event source that
replaces the hand-maintained CSV for future events.

Usage:
    .venv/bin/python3 scripts/pipeline_policy_events.py [--skip-embedding]
"""
from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quant.ai_corpus.providers.cn_finance_flash import (
    fetch_cls_telegraph,
    fetch_sina_7x24,
    fetch_wallstcn_lives,
)
from quant.ai_corpus.policy_events import (
    refine_with_embedding,
    rule_direction,
    rule_prefilter,
)
from quant.ai_corpus.storage import upsert_ai_corpus_documents

FLASH_DB = Path("data/ai_corpus/ai_corpus.sqlite")
EVENT_DB = Path("data/macro_policy_events.sqlite")


def ensure_event_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS policy_events (
            event_id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            market TEXT,
            direction TEXT,
            event_type TEXT,
            is_confirmed TEXT,
            magnitude TEXT,
            title TEXT,
            source TEXT,
            confidence REAL,
            fetched_at TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_policy_events_date ON policy_events(date)")


def fetch_flashes(root: Path, limit: int = 100) -> pd.DataFrame:
    frames = []
    for fn in [fetch_cls_telegraph, fetch_sina_7x24, fetch_wallstcn_lives]:
        try:
            df = fn(root=root, limit=limit)
            if not df.empty:
                frames.append(df)
        except Exception as e:
            print(f"  {fn.__name__} ERR: {str(e)[:80]}")
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def extract_policy_events(flashes: pd.DataFrame, linker=None) -> pd.DataFrame:
    """Rule prefilter + embedding refine → policy events with direction."""
    candidates = rule_prefilter(flashes, text_col="title")
    if candidates.empty:
        return pd.DataFrame()
    if linker is not None:
        candidates = refine_with_embedding(candidates, linker, text_col="title")
    else:
        candidates = candidates.assign(is_confirmed="落地", confidence=0.5)

    rows = []
    for _, r in candidates.iterrows():
        market, direction, event_type = rule_direction(str(r["title"]))
        rows.append({
            "date": str(r.get("published_at", ""))[:10],
            "market": market,
            "direction": direction,
            "event_type": event_type,
            "is_confirmed": r.get("is_confirmed", "落地"),
            "magnitude": "unknown",
            "title": str(r["title"]),
            "source": r.get("source", r.get("provider", "")),
            "confidence": float(r.get("confidence", 0.5)),
        })
    out = pd.DataFrame(rows)
    # only keep confirmed (落地) events for the trading-signal table
    out = out[out["is_confirmed"] == "落地"] if "is_confirmed" in out.columns else out
    return out


def upsert_policy_events(db: Path, events: pd.DataFrame) -> int:
    if events.empty:
        return 0
    db.parent.mkdir(parents=True, exist_ok=True)
    now = pd.Timestamp.now().isoformat(timespec="seconds")
    changed = 0
    with sqlite3.connect(db) as conn:
        ensure_event_tables(conn)
        for _, r in events.iterrows():
            event_id = f"{r['date']}_{r['market']}_{r['event_type']}_{r['title'][:20]}"
            conn.execute(
                """INSERT OR IGNORE INTO policy_events
                   (event_id, date, market, direction, event_type, is_confirmed, magnitude, title, source, confidence, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event_id, r["date"], r["market"], r["direction"], r["event_type"],
                 r["is_confirmed"], r["magnitude"], r["title"], r["source"],
                 r["confidence"], now),
            )
            changed += conn.total_changes
    return changed


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    use_embedding = "--skip-embedding" not in sys.argv

    print("=== 抓取实时快讯 ===")
    flashes = fetch_flashes(root, limit=100)
    print(f"  快讯总数: {len(flashes)}")

    if flashes.empty:
        print("  无快讯数据")
        return 0

    print("=== 入库快讯到 ai_corpus ===")
    n = upsert_ai_corpus_documents(FLASH_DB, flashes.to_dict(orient="records"))
    print(f"  入库 {len(flashes)} 条, changes={n}")

    print("=== 提取政策事件 ===")
    linker = None
    if use_embedding:
        from quant.ai_corpus.linking_omlx import OmlxEmbeddingLinker

        linker = OmlxEmbeddingLinker()
        print("  使用 oMLX embedding 精判")
    else:
        print("  跳过 embedding（仅规则）")

    events = extract_policy_events(flashes, linker=linker)
    print(f"  识别出政策事件: {len(events)} 条")
    if not events.empty:
        print(events[["date", "market", "direction", "event_type", "title"]].to_string(index=False))

    print("=== 写入政策事件表 ===")
    n_ev = upsert_policy_events(EVENT_DB, events)
    print(f"  写入 {n_ev} 条 → {EVENT_DB}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
