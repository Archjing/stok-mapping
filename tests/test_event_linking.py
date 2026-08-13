"""Tests for event→security linking (stock symbol normalization + policy linking)."""
from __future__ import annotations

import pandas as pd
import pytest

from quant.ai_corpus.linking import (
    normalize_stock_symbol,
    link_stock_events,
    link_policy_events,
    load_industry_indices,
)


# ── symbol normalization ───────────────────────────────────────────────

def test_normalize_sh_symbols() -> None:
    assert normalize_stock_symbol("601096") == "SH.601096"
    assert normalize_stock_symbol("688025") == "SH.688025"
    assert normalize_stock_symbol("605001") == "SH.605001"
    assert normalize_stock_symbol("603000") == "SH.603000"


def test_normalize_sz_symbols() -> None:
    assert normalize_stock_symbol("000062") == "SZ.000062"
    assert normalize_stock_symbol("002556") == "SZ.002556"
    assert normalize_stock_symbol("300001") == "SZ.300001"
    assert normalize_stock_symbol("301000") == "SZ.301000"


def test_normalize_already_prefixed() -> None:
    assert normalize_stock_symbol("SH.601096") == "SH.601096"
    assert normalize_stock_symbol("SZ.000062") == "SZ.000062"


def test_normalize_unknown_prefix_returns_none() -> None:
    # 北交所 8/4 开头，本库无数据，无法归一化
    assert normalize_stock_symbol("830001") is None
    assert normalize_stock_symbol("430001") is None


def test_normalize_non_digit() -> None:
    assert normalize_stock_symbol("") is None
    assert normalize_stock_symbol("abc") is None


# ── stock-event linking ────────────────────────────────────────────────

def _docs_with_symbols() -> pd.DataFrame:
    return pd.DataFrame([
        {"document_id": "d1", "provider": "cninfo", "symbols": "601096",
         "published_at": "2026-08-01 20:00:00", "title": "公告1"},
        {"document_id": "d2", "provider": "cninfo", "symbols": "000062,002556",
         "published_at": "2026-08-02 09:00:00", "title": "公告2"},
        {"document_id": "d3", "provider": "gov_policy", "symbols": "",
         "published_at": "2026-08-03 10:00:00", "title": "政策"},
    ])


def test_link_stock_events_normalizes_and_expands() -> None:
    linked = link_stock_events(_docs_with_symbols())
    # d1 -> 1 target, d2 -> 2 targets, d3 (empty symbols) -> dropped
    assert len(linked) == 3
    assert set(linked["symbol"]) == {"SH.601096", "SZ.000062", "SZ.002556"}
    assert "document_id" in linked.columns
    assert "published_at" in linked.columns


def test_link_stock_events_keeps_document_title() -> None:
    linked = link_stock_events(_docs_with_symbols())
    row = linked[linked["symbol"] == "SH.601096"].iloc[0]
    assert row["title"] == "公告1"


# ── industry-index loading ─────────────────────────────────────────────

def test_load_industry_indices(tmp_path) -> None:
    import sqlite3

    db = tmp_path / "market.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE market_indices (symbol TEXT, name TEXT, category TEXT)")
        conn.execute("CREATE TABLE market_index_bars (symbol TEXT, date TEXT)")
        conn.executemany(
            "INSERT INTO market_indices VALUES (?, ?, ?)",
            [("SH.000032", "上证能源", "一级行业指数"),
             ("SH.000033", "上证材料", "一级行业指数"),
             ("SH.000300", "沪深300", "规模指数")],
        )
    indices = load_industry_indices(db, category="一级行业指数")
    assert set(indices["symbol"]) == {"SH.000032", "SH.000033"}


# ── policy linking (deterministic fallback) ────────────────────────────

def test_link_policy_events_keyword_fallback() -> None:
    indices = pd.DataFrame([
        {"symbol": "SH.000032", "name": "上证能源"},
        {"symbol": "SH.000033", "name": "上证材料"},
    ])
    docs = pd.DataFrame([
        {"document_id": "p1", "provider": "gov_policy", "symbols": "",
         "published_at": "2026-08-01", "title": "关于能源行业发展的意见",
         "raw_text": "新能源 能源 光伏"},
    ])
    # no embedding model -> keyword fallback returns indices (top-k by name/title overlap)
    linked = link_policy_events(docs, indices, model=None)
    assert not linked.empty
    assert "SH.000032" in set(linked["symbol"])  # "能源" matches 上证能源
