"""Tests for event-study orchestration + Markdown report generation."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from quant.research.event_study.report import run_event_study


def _build_market_db(path: Path) -> None:
    """Build a synthetic market DB with a benchmark + 3 stocks + calendar."""
    import numpy as np

    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2023-01-01", periods=400).strftime("%Y-%m-%d")
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE market_indices (symbol TEXT, name TEXT, category TEXT)")
        conn.execute("CREATE TABLE market_index_bars (symbol TEXT, date TEXT, close REAL)")
        conn.execute("CREATE TABLE market_daily_bars (symbol TEXT, date TEXT, adjusted_close REAL)")
        conn.execute("CREATE TABLE trading_calendar (exchange TEXT, date TEXT, is_open INTEGER)")
        conn.executemany(
            "INSERT INTO market_indices VALUES (?, ?, ?)",
            [("SH.000300", "沪深300", "规模指数"),
             ("SH.000032", "上证能源", "一级行业指数"),
             ("SH.000033", "上证材料", "一级行业指数")],
        )
        market = pd.Series(rng.normal(0.0, 0.01, len(dates)))
        for i, d in enumerate(dates):
            conn.execute(
                "INSERT INTO market_index_bars VALUES ('SH.000300', ?, ?)",
                (d, float(100 * (1 + market.iloc[: i + 1].sum()))),
            )
        for sym in ["SH.601096", "SZ.000062", "SZ.002556"]:
            price = 10.0
            for i, d in enumerate(dates):
                shock = 0.05 if (d == "2023-06-02" and sym == "SH.601096") else 0.0
                r = rng.normal(0.0005, 0.02) + 1.2 * market.iloc[i] + shock
                price *= 1 + r
                conn.execute(
                    "INSERT INTO market_daily_bars VALUES (?, ?, ?)",
                    (sym, d, float(price)),
                )
        conn.executemany(
            "INSERT INTO trading_calendar VALUES ('SSE', ?, 1)",
            [(d,) for d in dates],
        )
        conn.commit()


def _build_corpus_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """CREATE TABLE ai_corpus_documents (
                document_id TEXT, provider TEXT, event_type TEXT, published_at TEXT,
                title TEXT, raw_text TEXT, symbols TEXT)"""
        )
        conn.execute(
            "INSERT INTO ai_corpus_documents VALUES ('d1', 'cninfo', 'abnormal_trading', "
            "'2023-06-01 20:00:00', '异常波动公告', '', '601096')"
        )
        conn.execute(
            "INSERT INTO ai_corpus_documents VALUES ('d2', 'cninfo', 'abnormal_trading', "
            "'2023-06-01 20:00:00', '异常波动公告2', '', '000062')"
        )
        conn.commit()


def test_run_event_study_produces_report(tmp_path: Path) -> None:
    market_db = tmp_path / "market.sqlite"
    corpus_db = tmp_path / "corpus.sqlite"
    _build_market_db(market_db)
    _build_corpus_db(corpus_db)

    result = run_event_study(
        corpus_db=corpus_db,
        market_db=market_db,
        provider="cninfo",
        event_type="abnormal_trading",
        output_dir=tmp_path / "reports",
    )
    assert result.report_md_path.exists()
    assert result.detail_csv_path.exists()
    assert result.n_events == 2
    assert result.n_linked == 2
    text = result.report_md_path.read_text(encoding="utf-8")
    assert "事件研究报告" in text
    assert "CAR 汇总" in text
    assert "样本量局限" in text
    # summary has one row per window
    assert set(result.summary["group"]) == {"(-1, +1)", "(-5, +10)", "(-5, +20)"}


def test_run_event_study_empty_docs_raises(tmp_path: Path) -> None:
    corpus_db = tmp_path / "empty_corpus.sqlite"
    with sqlite3.connect(corpus_db) as conn:
        conn.execute("CREATE TABLE ai_corpus_documents (document_id TEXT, provider TEXT, event_type TEXT, published_at TEXT, title TEXT, raw_text TEXT, symbols TEXT)")
    market_db = tmp_path / "market.sqlite"
    _build_market_db(market_db)
    with pytest.raises(ValueError):
        run_event_study(corpus_db=corpus_db, market_db=market_db, provider="cninfo")
