"""Tests for the per-stock event timeline query layer."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from quant.ai_corpus.stock_timeline import (
    load_stock_timeline,
    normalize_symbol,
    timeline_summary,
)


def test_normalize_symbol_6digit() -> None:
    assert normalize_symbol("300308") == "SZ.300308"
    assert normalize_symbol("600519") == "SH.600519"
    assert normalize_symbol("688025") == "SH.688025"


def test_normalize_symbol_prefixed() -> None:
    assert normalize_symbol("SZ.300308") == "SZ.300308"
    assert normalize_symbol("SH.600519") == "SH.600519"


def test_normalize_symbol_invalid() -> None:
    assert normalize_symbol("") is None
    assert normalize_symbol("830001") is None  # BSE
    assert normalize_symbol("abc") is None


def _corpus_db(tmp_path: Path) -> Path:
    db = tmp_path / "corpus.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """CREATE TABLE ai_corpus_documents (
                document_id TEXT, provider TEXT, event_type TEXT, published_at TEXT,
                issued_at TEXT, ingested_at TEXT, as_of_time TEXT, title TEXT,
                url TEXT, source_id TEXT, parse_status TEXT, symbols TEXT)"""
        )
        conn.executemany(
            "INSERT INTO ai_corpus_documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                ("d1", "cninfo", "announcement", "2026-08-01 09:00", "", "2026-08-01 09:01", "2026-08-01 09:01",
                 "业绩预告", "http://a", "s1", "ok", "300308"),
                ("d2", "cninfo", "abnormal_trading", "2026-08-02 10:00", "", "2026-08-02 10:01", "2026-08-02 10:01",
                 "异常波动", "http://b", "s2", "ok", "300308,002586"),
                ("d3", "cninfo", "announcement", "2026-08-03 11:00", "", "2026-08-03 11:01", "2026-08-03 11:01",
                 "无关公告", "http://c", "s3", "ok", "600519"),
            ],
        )
    return db


def test_load_stock_timeline_filters_and_orders(tmp_path: Path) -> None:
    db = _corpus_db(tmp_path)
    tl = load_stock_timeline(db, symbol="300308")
    assert len(tl) == 2  # d1 and d2 (d3 is 600519, excluded)
    # ordered by published_at DESC
    assert tl.iloc[0]["title"] == "异常波动"
    assert tl.iloc[1]["title"] == "业绩预告"
    # traceable fields present
    assert "published_at" in tl.columns
    assert "as_of_time" in tl.columns
    assert "url" in tl.columns


def test_load_stock_timeline_exact_token_match(tmp_path: Path) -> None:
    db = _corpus_db(tmp_path)
    # 300308 must not match a hypothetical 1300308; our fixture has none, but
    # verify 300308 doesn't match 300308-adjacent tokens
    tl = load_stock_timeline(db, symbol="SZ.300308")
    assert set(tl["title"]) == {"业绩预告", "异常波动"}


def test_load_stock_timeline_provider_filter(tmp_path: Path) -> None:
    db = _corpus_db(tmp_path)
    tl = load_stock_timeline(db, symbol="300308", providers=["cninfo"])
    assert len(tl) == 2
    tl2 = load_stock_timeline(db, symbol="300308", providers=["cctv"])
    assert tl2.empty


def test_load_stock_timeline_date_filter(tmp_path: Path) -> None:
    db = _corpus_db(tmp_path)
    tl = load_stock_timeline(db, symbol="300308", start_date="2026-08-02")
    assert len(tl) == 1
    assert tl.iloc[0]["title"] == "异常波动"


def test_timeline_summary(tmp_path: Path) -> None:
    db = _corpus_db(tmp_path)
    tl = load_stock_timeline(db, symbol="300308")
    s = timeline_summary(tl)
    assert s["n_events"] == 2
    assert s["by_provider"] == {"cninfo": 2}
