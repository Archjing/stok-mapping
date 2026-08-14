"""Additional edge-case tests for the event-study engine.

Covers paths not exercised by the original suite:
- run_single_event (one-call wrapper)
- aggregate_events (grouped aggregation, unknown group, missing column)
- compute_ar_car window-out-of-range handling
- report._load_returns qfq filter + _is_index_symbol
- report._load_industry_symbols
- report._render_report Top-event sort
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quant.research.event_study.abnormal_returns import compute_ar_car, run_single_event
from quant.research.event_study.aggregation import aggregate_events, cross_sectional_test
from quant.research.event_study.market_model import estimate_market_model


# ── helpers ────────────────────────────────────────────────────────────

def _series(n: int = 300, seed: int = 0) -> tuple[pd.Series, pd.Series]:
    rng = np.random.default_rng(seed)
    market = pd.Series(rng.normal(0, 0.01, n))
    asset = 1.5 * market + rng.normal(0, 0.008, n)
    return asset, market


# ── run_single_event ───────────────────────────────────────────────────

def test_run_single_event_wraps_estimate_and_car() -> None:
    asset, market = _series()
    asset.iloc[200] += 0.05  # shock at event day
    out = run_single_event(asset, market, event_idx=200, windows=[(-1, 1)])
    assert len(out) == 1
    assert out.iloc[0]["car"] == pytest.approx(0.05, abs=0.02)


def test_run_single_event_returns_nan_when_insufficient_history() -> None:
    asset, market = _series(n=50)
    out = run_single_event(asset, market, event_idx=40, windows=[(-1, 1)])
    assert np.isnan(out.iloc[0]["car"])


# ── compute_ar_car out-of-range windows ────────────────────────────────

def test_compute_ar_car_window_out_of_range() -> None:
    asset, market = _series(n=50)
    alpha, beta = estimate_market_model(asset, market, event_idx=40)
    out = compute_ar_car(asset, market, alpha, beta, event_idx=40, windows=[(-100, 100)])
    # window extends past the series -> n_days == 0, nan car
    assert out.iloc[0]["n_days"] == 0
    assert np.isnan(out.iloc[0]["car"])


# ── aggregate_events ───────────────────────────────────────────────────

def test_aggregate_events_grouped() -> None:
    frame = pd.DataFrame({
        "car": [0.01, 0.02, -0.01, 0.03],
        "group": ["a", "a", "b", "b"],
    })
    out = aggregate_events(frame, group_col="group")
    assert set(out["group"]) == {"a", "b"}
    a = out[out["group"] == "a"].iloc[0]
    assert a["mean_car"] == pytest.approx(0.015)


def test_aggregate_events_no_group() -> None:
    frame = pd.DataFrame({"car": [0.01, 0.02, 0.03]})
    out = aggregate_events(frame)
    assert len(out) == 1
    assert out.iloc[0]["group"] == "all"
    assert out.iloc[0]["n"] == 3


def test_aggregate_events_missing_car_raises() -> None:
    with pytest.raises(ValueError):
        aggregate_events(pd.DataFrame({"x": [1, 2]}))


def test_aggregate_events_with_nan_car() -> None:
    frame = pd.DataFrame({"car": [0.01, np.nan, 0.02], "group": ["a", "a", "a"]})
    out = aggregate_events(frame, group_col="group")
    assert out.iloc[0]["n"] == 2  # NaN dropped


# ── report layer helpers ───────────────────────────────────────────────

def _market_db(tmp_path: Path) -> Path:
    db = tmp_path / "market.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE market_daily_bars (symbol TEXT, date TEXT, adjusted_close REAL, adjust_type TEXT)")
        conn.execute("CREATE TABLE market_index_bars (symbol TEXT, date TEXT, close REAL)")
        conn.execute("CREATE TABLE market_indices (symbol TEXT, name TEXT, category TEXT)")
        conn.execute("CREATE TABLE market_stocks (symbol TEXT, industry TEXT)")
        conn.executemany(
            "INSERT INTO market_daily_bars VALUES (?,?,?,?)",
            [
                ("SZ.000651", "2026-01-05", 40.0, "bfq"),
                ("SZ.000651", "2026-01-06", 40.5, "bfq"),
                ("SZ.000651", "2026-01-07", 41.0, "bfq"),
                ("SZ.000651", "2026-01-05", 10.0, "qfq"),
                ("SZ.000651", "2026-01-06", 10.1, "qfq"),
                ("SZ.000651", "2026-01-07", 10.2, "qfq"),
            ],
        )
        conn.executemany(
            "INSERT INTO market_index_bars VALUES (?,?,?)",
            [("SH.000300", "2026-01-05", 4000.0),
             ("SH.000300", "2026-01-06", 4020.0),
             ("SH.000300", "2026-01-07", 4050.0)],
        )
        conn.executemany(
            "INSERT INTO market_indices VALUES (?,?,?)",
            [("SH.000300", "沪深300", "规模指数"),
             ("SH.000032", "上证能源", "一级行业指数")],
        )
        conn.executemany(
            "INSERT INTO market_stocks VALUES (?,?)",
            [("SZ.000651", "家用电器"), ("SH.601857", "石油石化")],
        )
    return db


def test_load_returns_uses_qfq_only(tmp_path: Path) -> None:
    from quant.research.event_study.report import _load_returns

    db = _market_db(tmp_path)
    conn = sqlite3.connect(db)
    ret = _load_returns(conn, "SZ.000651")
    conn.close()
    # qfq prices 10.0->10.1->10.2 -> returns ~0.01 each, NOT bfq's 40->40.5
    assert not ret.empty
    assert ret.iloc[1] == pytest.approx(10.1 / 10.0 - 1)


def test_is_index_symbol_detects_index(tmp_path: Path) -> None:
    from quant.research.event_study.report import _is_index_symbol

    db = _market_db(tmp_path)
    conn = sqlite3.connect(db)
    assert _is_index_symbol(conn, "SH.000300") is True
    assert _is_index_symbol(conn, "SZ.000651") is False
    conn.close()


def test_load_industry_symbols_filters(tmp_path: Path) -> None:
    from quant.research.event_study.report import _load_industry_symbols

    db = _market_db(tmp_path)
    symbols = _load_industry_symbols(db, ["家用电器"])
    assert symbols == {"SZ.000651"}
    symbols2 = _load_industry_symbols(db, ["石油石化"])
    assert symbols2 == {"SH.601857"}


# ── report Top-event sort ──────────────────────────────────────────────

def test_render_report_tops_by_abs_car() -> None:
    from quant.research.event_study.report import _render_report

    summary = pd.DataFrame({
        "group": ["(-1, +1)"], "n": [3], "mean_car": [0.01], "mean_car_pct": [1.0],
        "t_stat": [1.5], "p_value": [0.1], "positive_share": [0.5],
    })
    car_frame = pd.DataFrame({
        "symbol": ["A", "B", "C"],
        "event_day": ["2026-01-05", "2026-01-06", "2026-01-07"],
        "car": [-0.05, 0.02, 0.08],  # abs: C(0.08) > A(0.05) > B(0.02)
        "title": ["事件A", "事件B", "事件C"],
    })
    md = _render_report(
        provider="cninfo", event_type="announcement", n_events=3, n_linked=3,
        summary=summary, car_frame=car_frame, benchmark="SH.000300",
        windows=[(-1, 1)],
    )
    # Top 表第一行应是最 |CAR| 的事件 C
    lines = md.splitlines()
    top_section = [i for i, l in enumerate(lines) if "Top 冲击事件" in l][0]
    first_data_row = lines[top_section + 4]  # blank + header + separator
    assert "C" in first_data_row
    assert "8.00%" in first_data_row


def test_render_report_head_limits_to_20() -> None:
    from quant.research.event_study.report import _render_report

    summary = pd.DataFrame({
        "group": ["(-1, +1)"], "n": [25], "mean_car": [0.0], "mean_car_pct": [0.0],
        "t_stat": [0.0], "p_value": [0.5], "positive_share": [0.5],
    })
    car_frame = pd.DataFrame({
        "symbol": [f"S{i}" for i in range(25)],
        "event_day": ["2026-01-05"] * 25,
        "car": [(i - 12) / 100 for i in range(25)],
        "title": [f"事件{i}" for i in range(25)],
    })
    md = _render_report(
        provider="cninfo", event_type="announcement", n_events=25, n_linked=25,
        summary=summary, car_frame=car_frame, benchmark="SH.000300",
        windows=[(-1, 1)],
    )
    top_section = [i for i, l in enumerate(md.splitlines()) if "Top 冲击事件" in l][0]
    # 表头 + 分隔线后最多 20 行数据
    data_rows = 0
    for l in md.splitlines()[top_section + 3 :]:
        if l.startswith("| S"):
            data_rows += 1
    assert data_rows <= 20
