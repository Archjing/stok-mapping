from __future__ import annotations

import pandas as pd
import pytest

from quant.research.core_coverage.core_reachability import (
    _asof_weight_date_map,
    _diagnose_fold,
    _fold_summary,
    _seed_benchmark_panel,
)


def test_core_reachability_uses_complete_benchmark_top_n_and_lagged_weights() -> None:
    panel = pd.DataFrame(
        [
            {
                "date": "2024-01-10",
                "symbol": "A",
                "close": 10.0,
                "amount": 1000.0,
                "amount_ratio20": 1.2,
                "industry": "Bank",
            },
            {
                "date": "2024-01-10",
                "symbol": "B",
                "close": 11.0,
                "amount": 1000.0,
                "amount_ratio20": 1.2,
                "industry": "Tech",
            },
            {
                "date": "2024-01-10",
                "symbol": "C",
                "close": 12.0,
                "amount": 1000.0,
                "amount_ratio20": 1.2,
                "industry": "Tech",
            },
        ]
    )
    benchmark_weights = pd.DataFrame(
        [
            {"trade_date_dt": pd.Timestamp("2024-01-09"), "symbol": "A", "benchmark_weight": 0.40},
            {"trade_date_dt": pd.Timestamp("2024-01-09"), "symbol": "B", "benchmark_weight": 0.30},
            {"trade_date_dt": pd.Timestamp("2024-01-09"), "symbol": "X", "benchmark_weight": 0.20},
            {"trade_date_dt": pd.Timestamp("2024-01-09"), "symbol": "C", "benchmark_weight": 0.10},
            {"trade_date_dt": pd.Timestamp("2024-01-10"), "symbol": "A", "benchmark_weight": 0.10},
            {"trade_date_dt": pd.Timestamp("2024-01-10"), "symbol": "B", "benchmark_weight": 0.10},
            {"trade_date_dt": pd.Timestamp("2024-01-10"), "symbol": "X", "benchmark_weight": 0.80},
        ]
    )
    benchmark_weights["benchmark_rank"] = benchmark_weights.groupby("trade_date_dt")["benchmark_weight"].rank(
        method="first",
        ascending=False,
    )
    candidate = pd.Series(
        {
            "strategy_id": "candidate",
            "walk_forward_preset": "baseline",
            "fold": 1,
            "valid_start": "2024-01-10",
            "valid_end": "2024-01-10",
        }
    )

    daily, reasons = _diagnose_fold(
        panel=panel,
        candidate_row=candidate,
        benchmark_weights=benchmark_weights,
        benchmark_symbol="SH.000300",
        top_n=2,
        core_top_n=3,
        core_cumulative_weight=0.60,
        min_amount=0.0,
        min_amount_ratio20=0.0,
        weight_date_lag_days=1,
    )
    row = daily.iloc[0]

    assert row["benchmark_weight_date"] == "2024-01-09"
    assert row["core_weight_sum"] == pytest.approx(0.90)
    assert row["reachable_core_weight_sum"] == pytest.approx(0.70)
    assert row["top_n_weight_sum"] == pytest.approx(0.70)
    assert row["reachable_top_n_weight_sum"] == pytest.approx(0.70)
    assert set(reasons["symbol"]) == {"X"}
    assert reasons.iloc[0]["failure_reason"] == "missing_from_pit_panel"


def test_core_reachability_reports_filter_reasons_and_fold_status() -> None:
    panel = pd.DataFrame(
        [
            {"date": "2024-01-10", "symbol": "A", "close": 10.0, "amount": 1000.0, "amount_ratio20": 1.2, "industry": "Bank"},
            {"date": "2024-01-10", "symbol": "B", "close": 0.0, "amount": 1000.0, "amount_ratio20": 1.2, "industry": "Tech"},
            {"date": "2024-01-10", "symbol": "C", "close": 10.0, "amount": 10.0, "amount_ratio20": 1.2, "industry": "Tech"},
            {"date": "2024-01-10", "symbol": "D", "close": 10.0, "amount": 1000.0, "amount_ratio20": 0.1, "industry": "Tech"},
            {"date": "2024-01-10", "symbol": "E", "close": 10.0, "amount": 1000.0, "amount_ratio20": 1.2, "industry": ""},
        ]
    )
    benchmark_weights = pd.DataFrame(
        [
            {"trade_date_dt": pd.Timestamp("2024-01-09"), "symbol": symbol, "benchmark_weight": weight, "benchmark_rank": idx}
            for idx, (symbol, weight) in enumerate(
                [("A", 0.30), ("B", 0.25), ("C", 0.20), ("D", 0.15), ("E", 0.10)],
                start=1,
            )
        ]
    )
    candidate = pd.Series(
        {
            "strategy_id": "candidate",
            "walk_forward_preset": "baseline",
            "fold": 1,
            "valid_start": "2024-01-10",
            "valid_end": "2024-01-10",
        }
    )

    daily, reasons = _diagnose_fold(
        panel=panel,
        candidate_row=candidate,
        benchmark_weights=benchmark_weights,
        benchmark_symbol="SH.000300",
        top_n=3,
        core_top_n=5,
        core_cumulative_weight=1.0,
        min_amount=100.0,
        min_amount_ratio20=1.0,
        weight_date_lag_days=1,
    )

    reason_by_symbol = dict(zip(reasons["symbol"], reasons["failure_reason"], strict=True))
    assert reason_by_symbol == {
        "B": "invalid_price",
        "C": "amount_below_min",
        "D": "amount_ratio20_below_min",
        "E": "missing_industry",
    }
    assert daily.iloc[0]["reachable_core_weight_sum"] == pytest.approx(0.30)
    summary = _fold_summary(daily)
    assert summary.iloc[0]["main_status"] == "core_reachability_below_threshold"


def test_fold_status_uses_top_n_coverage_not_absolute_top_n_weight() -> None:
    panel = pd.DataFrame(
        [
            {
                "date": "2024-01-10",
                "symbol": f"S{idx}",
                "close": 10.0,
                "amount": 1000.0,
                "amount_ratio20": 1.2,
                "industry": "Core",
            }
            for idx in range(1, 7)
        ]
    )
    benchmark_weights = pd.DataFrame(
        [
            {
                "trade_date_dt": pd.Timestamp("2024-01-09"),
                "symbol": f"S{idx}",
                "benchmark_weight": weight,
                "benchmark_rank": idx,
            }
            for idx, weight in enumerate([0.18, 0.14, 0.10, 0.08, 0.05, 0.05], start=1)
        ]
    )
    candidate = pd.Series(
        {
            "strategy_id": "candidate",
            "walk_forward_preset": "baseline",
            "fold": 1,
            "valid_start": "2024-01-10",
            "valid_end": "2024-01-10",
        }
    )

    daily, _reasons = _diagnose_fold(
        panel=panel,
        candidate_row=candidate,
        benchmark_weights=benchmark_weights,
        benchmark_symbol="SH.000300",
        top_n=2,
        core_top_n=6,
        core_cumulative_weight=0.60,
        min_amount=0.0,
        min_amount_ratio20=0.0,
        weight_date_lag_days=1,
    )

    summary = _fold_summary(daily)

    assert summary.iloc[0]["avg_reachable_top_n_weight_sum"] == pytest.approx(0.32)
    assert summary.iloc[0]["avg_reachable_top_n_weight_ratio"] == pytest.approx(1.0)
    assert summary.iloc[0]["main_status"] == "pass"


def test_asof_weight_date_map_normalizes_datetime_precision() -> None:
    dates = pd.Series(pd.to_datetime(["2024-01-10", "2024-01-11"]).astype("datetime64[ns]"))
    weight_dates = pd.Series(pd.to_datetime(["2024-01-09", "2024-01-10"]).astype("datetime64[us]"))

    mapped = _asof_weight_date_map(dates, weight_dates, lag_days=1)

    assert mapped[pd.Timestamp("2024-01-10")] == pd.Timestamp("2024-01-09")
    assert mapped[pd.Timestamp("2024-01-11")] == pd.Timestamp("2024-01-10")


def test_seed_benchmark_panel_adds_missing_core_members(monkeypatch: pytest.MonkeyPatch) -> None:
    panel = pd.DataFrame(
        [
            {
                "date": "2024-01-10",
                "symbol": "A",
                "close": 10.0,
                "amount": 1000.0,
                "amount_ratio20": 1.2,
                "industry": "Bank",
            }
        ]
    )
    benchmark_weights = pd.DataFrame(
        [
            {"trade_date_dt": pd.Timestamp("2024-01-09"), "symbol": "A", "benchmark_weight": 0.40, "benchmark_rank": 1},
            {"trade_date_dt": pd.Timestamp("2024-01-09"), "symbol": "B", "benchmark_weight": 0.35, "benchmark_rank": 2},
        ]
    )
    candidate = pd.Series({"valid_start": "2024-01-10", "valid_end": "2024-01-10"})

    def fake_load_daily(symbol, start, end, price_adjustment=None, as_of_date=None):
        assert symbol == "B"
        return pd.DataFrame(
            [
                {
                    "date": "2024-01-10",
                    "open": 20.0,
                    "high": 21.0,
                    "low": 19.0,
                    "close": 20.5,
                    "volume": 100.0,
                    "amount": 2000.0,
                    "amount_ratio20": 1.1,
                }
            ]
        )

    monkeypatch.setattr("quant.research.core_coverage.core_reachability.load_daily_from_local_history", fake_load_daily)
    monkeypatch.setattr("quant.research.core_coverage.core_reachability._lookup_stock_industry", lambda symbol: "Tech")

    seeded = _seed_benchmark_panel(
        panel=panel,
        candidate_row=candidate,
        benchmark_weights=benchmark_weights,
        years=1,
        strategy_cfg={"price_adjustment": "qfq_asof"},
        seed_benchmark_core=True,
        seed_top_n=2,
        seed_core_top_n=2,
        seed_core_cumulative_weight=1.0,
        weight_date_lag_days=1,
    )

    assert set(seeded["symbol"]) == {"A", "B"}
    added = seeded[seeded["symbol"].eq("B")].iloc[0]
    assert bool(added["benchmark_seeded"]) is True
    assert added["industry"] == "Tech"
