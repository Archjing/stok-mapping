from __future__ import annotations

import pandas as pd

from quant.research.participation.path_audit import run_strategy_participation_path_audit


def test_participation_path_audit_buckets_target_and_live_exposure(tmp_path) -> None:
    daily = pd.DataFrame(
        [
            {
                "strategy_id": "strategy_a",
                "walk_forward_preset": "baseline",
                "fold": 4,
                "valid_start": "2024-04-01",
                "valid_end": "2025-03-31",
                "market_context_label": "relative_lag_in_strong_benchmark_context",
                "date": "2024-04-01",
                "target_exposure": 0.15,
                "live_exposure": 0.00,
            },
            {
                "strategy_id": "strategy_a",
                "walk_forward_preset": "baseline",
                "fold": 4,
                "valid_start": "2024-04-01",
                "valid_end": "2025-03-31",
                "market_context_label": "relative_lag_in_strong_benchmark_context",
                "date": "2024-04-02",
                "target_exposure": 0.85,
                "live_exposure": 0.15,
            },
            {
                "strategy_id": "strategy_a",
                "walk_forward_preset": "baseline",
                "fold": 4,
                "valid_start": "2024-04-01",
                "valid_end": "2025-03-31",
                "market_context_label": "relative_lag_in_strong_benchmark_context",
                "date": "2024-04-03",
                "target_exposure": 0.85,
                "live_exposure": 0.83,
            },
            {
                "strategy_id": "strategy_a",
                "walk_forward_preset": "baseline",
                "fold": 5,
                "valid_start": "2025-04-01",
                "valid_end": "2026-03-31",
                "market_context_label": "risk_context_pressure",
                "date": "2025-04-01",
                "target_exposure": 0.15,
                "live_exposure": 0.15,
            },
        ]
    )
    path = tmp_path / "daily.csv"
    daily.to_csv(path, index=False)

    result = run_strategy_participation_path_audit(
        daily_exposure_path=path,
        output_dir=tmp_path / "out",
        target_high_threshold=0.80,
        live_low_threshold=0.50,
    )

    summary = pd.read_csv(result.summary_csv_path)
    daily_audit = pd.read_csv(result.daily_csv_path)
    rel = summary[summary["market_context_label"] == "relative_lag_in_strong_benchmark_context"].iloc[0]

    assert result.summary_rows == 2
    assert int(rel["days"]) == 3
    assert int(rel["high_target_days"]) == 2
    assert int(rel["low_live_after_high_target_days"]) == 1
    assert float(rel["avg_target_exposure"]) == 0.616667
    assert float(rel["avg_abs_live_minus_target_exposure"]) == 0.29
    assert float(rel["avg_abs_live_minus_previous_target_exposure"]) == 0.01
    assert rel["avg_abs_live_minus_previous_target_exposure"] < rel["avg_abs_live_minus_target_exposure"]
    assert set(daily_audit["target_exposure_bucket"]) == {"risk_or_low", "strong_high"}
    assert "previous_target_exposure" in daily_audit.columns
    assert result.report_md_path.exists()
