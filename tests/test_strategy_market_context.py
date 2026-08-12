from __future__ import annotations

import pandas as pd

import quant.research.diagnostics.market_context as market_context
from quant.research.diagnostics.market_context import run_strategy_market_context


def _config() -> dict:
    return {"benchmark_symbol": "SH.000300"}


def test_strategy_market_context_labels_fold_context_and_writes_artifacts(monkeypatch, tmp_path) -> None:
    fold_path = tmp_path / "strategy_failure_fold_attribution.csv"
    output_dir = tmp_path / "out"
    pd.DataFrame(
        [
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline",
                "fold": 1,
                "valid_start": "2021-01-01",
                "valid_end": "2021-01-31",
                "primary_fold_failure": "absolute_failure_market_weak_but_outperform",
                "fold_severity": "medium",
                "annualized_return": -0.05,
                "benchmark_annualized_return": -0.20,
                "excess_annualized_return": 0.15,
                "sharpe": -1.0,
            },
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline",
                "fold": 2,
                "valid_start": "2021-02-01",
                "valid_end": "2021-02-28",
                "primary_fold_failure": "relative_failure_benchmark_strong",
                "fold_severity": "medium",
                "annualized_return": 0.04,
                "benchmark_annualized_return": 0.18,
                "excess_annualized_return": -0.14,
                "sharpe": 0.5,
            },
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline",
                "fold": 3,
                "valid_start": "2021-03-01",
                "valid_end": "2021-03-31",
                "primary_fold_failure": "clean_positive_fold",
                "fold_severity": "none",
                "annualized_return": 0.08,
                "benchmark_annualized_return": 0.03,
                "excess_annualized_return": 0.05,
                "sharpe": 0.7,
            },
        ]
    ).to_csv(fold_path, index=False)

    dates = pd.date_range("2020-01-01", "2021-03-31", freq="B")
    close = []
    price = 100.0
    for date in dates:
        if date <= pd.Timestamp("2021-01-31"):
            price *= 0.997
        elif date <= pd.Timestamp("2021-02-28"):
            price *= 1.010
        else:
            price *= 1.002
        close.append(price)
    index_df = pd.DataFrame(
        {
            "date": dates,
            "close": close,
            "data_source": "local_history_sqlite",
        }
    )

    monkeypatch.setattr(
        market_context,
        "load_index_daily_from_local_history",
        lambda symbol, start, end: index_df[(index_df["date"] >= pd.Timestamp(start)) & (index_df["date"] <= pd.Timestamp(end))].copy(),
    )

    result = run_strategy_market_context(
        config=_config(),
        root=tmp_path,
        fold_attribution_path=fold_path,
        output_dir=output_dir,
        trend_window=20,
        vol_window=5,
        vol_quantile=0.70,
    )

    assert result.rows == 3
    out = pd.read_csv(result.csv_path)
    labels = out.set_index("fold")["market_context_label"].to_dict()
    assert labels[1] == "absolute_loss_but_benchmark_weak_context"
    assert labels[2] == "relative_lag_in_strong_benchmark_context"
    assert labels[3] == "clean_positive_context"
    summary = pd.read_csv(result.summary_csv_path)
    assert set(summary["primary_fold_failure"]) == {
        "absolute_failure_market_weak_but_outperform",
        "clean_positive_fold",
        "relative_failure_benchmark_strong",
    }
    coverage = pd.read_csv(result.coverage_csv_path)
    assert coverage.loc[0, "coverage_status"] == "available"
    assert bool(coverage.loc[0, "asof_shift_applied"]) is True
    md = result.md_path.read_text(encoding="utf-8")
    assert "does not implement risk scaling" in md
    assert "not admission gates and not trading rules" in md


def test_strategy_market_context_reports_missing_required_columns(tmp_path) -> None:
    fold_path = tmp_path / "bad.csv"
    pd.DataFrame([{"strategy_id": "x"}]).to_csv(fold_path, index=False)

    try:
        run_strategy_market_context(config=_config(), root=tmp_path, fold_attribution_path=fold_path)
    except ValueError as exc:
        assert "valid_start" in str(exc)
    else:
        raise AssertionError("expected missing column validation to fail")


def test_index_context_features_shift_close_derived_context_by_one_day(monkeypatch) -> None:
    index_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2021-01-01", "2021-01-04", "2021-01-05", "2021-01-06"]),
            "close": [100.0, 90.0, 110.0, 120.0],
        }
    )
    monkeypatch.setattr(
        market_context,
        "load_index_daily_from_local_history",
        lambda symbol, start, end: index_df.copy(),
    )

    features = market_context._index_context_features(
        "SH.000300",
        start=pd.Timestamp("2021-01-01").date(),
        end=pd.Timestamp("2021-01-06").date(),
        trend_window=2,
        vol_window=2,
        vol_quantile=0.7,
    )
    by_date = features.set_index("date")

    assert by_date.loc[pd.Timestamp("2021-01-05"), "close"] > by_date.loc[pd.Timestamp("2021-01-05"), "trend_ma"]
    assert bool(by_date.loc[pd.Timestamp("2021-01-05"), "context_above_trend"]) is False
    assert bool(by_date.loc[pd.Timestamp("2021-01-06"), "context_above_trend"]) is True
