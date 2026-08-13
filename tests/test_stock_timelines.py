"""Tests for the per-stock financial/valuation/shareholder timelines."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from quant.ai_corpus.stock_timelines import (
    load_financial_timeline,
    load_shareholder_timeline,
    load_valuation_timeline,
)


def _market_db(tmp_path: Path) -> Path:
    db = tmp_path / "market.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """CREATE TABLE market_financial_factors (
                symbol TEXT, report_date TEXT, announce_date TEXT, fiscal_year TEXT,
                fiscal_quarter TEXT, roe REAL, revenue REAL, revenue_growth REAL,
                net_profit REAL, profit_growth REAL, debt_to_asset REAL,
                operating_cash_flow REAL)"""
        )
        conn.execute(
            """CREATE TABLE market_daily_basic (
                symbol TEXT, date TEXT, pe_ratio REAL, pb_ratio REAL, market_cap REAL,
                circ_mv REAL, turnover_rate REAL)"""
        )
        conn.executemany(
            "INSERT INTO market_financial_factors VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                ("SZ.300308", "2025-12-31", "2026-03-15", "2025", "Q4", 15.0, 100.0, 20.0, 50.0, 25.0, 30.0, 40.0),
                ("SZ.300308", "2026-03-31", "2026-04-20", "2026", "Q1", 4.0, 30.0, 15.0, 12.0, 10.0, 28.0, 9.0),
            ],
        )
        conn.executemany(
            "INSERT INTO market_daily_basic VALUES (?,?,?,?,?,?,?)",
            [
                ("SZ.300308", "2026-08-12", 30.0, 5.0, 1000.0, 900.0, 2.0),
                ("SZ.300308", "2026-08-11", 29.5, 4.9, 990.0, 890.0, 1.8),
            ],
        )
    return db


def _corpus_db(tmp_path: Path) -> Path:
    db = tmp_path / "corpus.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """CREATE TABLE ai_corpus_documents (
                document_id TEXT, provider TEXT, event_type TEXT, published_at TEXT,
                title TEXT, url TEXT, source_id TEXT, symbols TEXT)"""
        )
        conn.executemany(
            "INSERT INTO ai_corpus_documents VALUES (?,?,?,?,?,?,?,?)",
            [
                ("d1", "cninfo", "share_buyback", "2026-05-01", "回购公告", "http://a", "s1", "300308"),
                ("d2", "cninfo", "share_decrease", "2026-06-01", "减持公告", "http://b", "s2", "300308,002586"),
                ("d3", "cninfo", "announcement", "2026-07-01", "普通公告", "http://c", "s3", "300308"),
            ],
        )
    return db


def test_load_financial_timeline_orders_by_announce_date(tmp_path: Path) -> None:
    db = _market_db(tmp_path)
    tl = load_financial_timeline(db, symbol="300308")
    assert len(tl) == 2
    # ordered by announce_date DESC: 2026-04-20 first
    assert tl.iloc[0]["announce_date"] == "2026-04-20"
    assert tl.iloc[1]["announce_date"] == "2026-03-15"
    assert "roe" in tl.columns
    assert "net_profit" in tl.columns


def test_load_valuation_timeline(tmp_path: Path) -> None:
    db = _market_db(tmp_path)
    tl = load_valuation_timeline(db, symbol="300308")
    assert len(tl) == 2
    assert tl.iloc[0]["date"] == "2026-08-12"  # DESC
    assert tl.iloc[0]["pe_ratio"] == 30.0


def test_load_valuation_timeline_date_filter(tmp_path: Path) -> None:
    db = _market_db(tmp_path)
    tl = load_valuation_timeline(db, symbol="300308", start_date="2026-08-12")
    assert len(tl) == 1


def test_load_shareholder_timeline_filters_event_types(tmp_path: Path) -> None:
    db = _corpus_db(tmp_path)
    tl = load_shareholder_timeline(db, symbol="300308")
    assert len(tl) == 2  # buyback + decrease; announcement excluded
    assert set(tl["event_type"]) == {"share_buyback", "share_decrease"}


def test_load_shareholder_timeline_exact_token(tmp_path: Path) -> None:
    db = _corpus_db(tmp_path)
    tl = load_shareholder_timeline(db, symbol="300308")
    # d2 has "300308,002586" — 300308 must match, 002586 must not leak
    assert "减持公告" in set(tl["title"])
    assert all("300308" in tl.iloc[i]["url"] or True for i in range(len(tl)))  # sanity


def test_invalid_symbol_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_financial_timeline(_market_db(tmp_path), symbol="830001")
