"""Tests for index-membership and research-coverage timelines (second tier)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from quant.ai_corpus.stock_timelines2 import (
    load_index_membership_changes,
    load_index_membership_timeline,
    load_research_coverage_timeline,
)


def _market_db(tmp_path: Path) -> Path:
    db = tmp_path / "market.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """CREATE TABLE cn_index_constituents_asof (
                index_code TEXT, trade_date TEXT, symbol TEXT, effective_date TEXT,
                source TEXT, vendor_index_code TEXT, vendor_symbol TEXT, ingested_at TEXT)"""
        )
        # 300308 in 000300: 2024-01 → 2024-06 (continuous), then gap, then 2025-01 → 2025-03
        rows = [
            ("SH.000300", "2024-01-31", "SZ.300308", "2024-01-31", "s", "", "", ""),
            ("SH.000300", "2024-02-29", "SZ.300308", "2024-02-29", "s", "", "", ""),
            ("SH.000300", "2024-06-30", "SZ.300308", "2024-06-30", "s", "", "", ""),
            ("SH.000300", "2025-01-31", "SZ.300308", "2025-01-31", "s", "", "", ""),
            ("SH.000300", "2025-03-31", "SZ.300308", "2025-03-31", "s", "", "", ""),
            ("SH.000905", "2024-01-31", "SZ.300308", "2024-01-31", "s", "", "", ""),
        ]
        conn.executemany(
            "INSERT INTO cn_index_constituents_asof VALUES (?,?,?,?,?,?,?,?)", rows
        )
    return db


def test_load_index_membership_timeline(tmp_path: Path) -> None:
    db = _market_db(tmp_path)
    tl = load_index_membership_timeline(db, symbol="300308")
    assert len(tl) == 6
    # ordered by index_code then effective_date
    assert tl.iloc[0]["index_code"] == "SH.000300"


def test_load_index_membership_timeline_filter(tmp_path: Path) -> None:
    db = _market_db(tmp_path)
    tl = load_index_membership_timeline(db, symbol="300308", index_code="SH.000905")
    assert len(tl) == 1


def test_load_index_membership_changes_detects_gap(tmp_path: Path) -> None:
    db = _market_db(tmp_path)
    changes = load_index_membership_changes(db, symbol="300308")
    # 300308 has two runs in 000300 (2024-01~06, then 2025-01~03)
    # should detect: enter 2024-01, enter 2025-01 (gap between runs)
    assert not changes.empty
    enters = changes[changes["change"] == "enter"]
    assert any("2024-01" in d for d in enters["effective_date"])
    assert any("2025-01" in d for d in enters["effective_date"])


def test_load_research_coverage_empty_when_no_data(tmp_path: Path) -> None:
    db = tmp_path / "corpus.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """CREATE TABLE ai_corpus_documents (
                document_id TEXT, provider TEXT, published_at TEXT, title TEXT,
                org TEXT, topics TEXT, url TEXT, source_id TEXT, symbols TEXT)"""
        )
    tl = load_research_coverage_timeline(db, symbol="300308")
    assert tl.empty


def test_load_research_coverage_matches_symbol(tmp_path: Path) -> None:
    db = tmp_path / "corpus.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """CREATE TABLE ai_corpus_documents (
                document_id TEXT, provider TEXT, published_at TEXT, title TEXT,
                org TEXT, topics TEXT, url TEXT, source_id TEXT, symbols TEXT)"""
        )
        conn.executemany(
            "INSERT INTO ai_corpus_documents VALUES (?,?,?,?,?,?,?,?,?)",
            [
                ("r1", "research_report", "2026-01-01", "买入评级", "中金", "rating=买入", "http://x", "s1", "300308"),
                ("r2", "research_report", "2026-02-01", "中性评级", "中信", "rating=中性", "http://y", "s2", "600519"),
            ],
        )
    tl = load_research_coverage_timeline(db, symbol="300308")
    assert len(tl) == 1
    assert tl.iloc[0]["title"] == "买入评级"


def test_invalid_symbol_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_index_membership_timeline(_market_db(tmp_path), symbol="830001")
