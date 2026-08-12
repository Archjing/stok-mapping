from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from quant.research.attribution.csi300 import run_strategy_csi300_attribution


def _create_history_db(path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE cn_index_weights_asof (
                index_code TEXT,
                trade_date TEXT,
                symbol TEXT,
                weight REAL,
                effective_date TEXT,
                asof_time TEXT,
                source TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE market_stocks (
                market TEXT,
                symbol TEXT,
                name TEXT,
                industry TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE market_index_bars (
                symbol TEXT,
                date TEXT,
                close REAL,
                frequency TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO market_stocks VALUES ('CN', ?, ?, ?)",
            [
                ("SH.600000", "浦发银行", "银行"),
                ("SH.600519", "贵州茅台", "白酒"),
                ("SZ.000001", "平安银行", "银行"),
                ("SZ.000333", "美的集团", "家用电器"),
            ],
        )
        conn.executemany(
            "INSERT INTO cn_index_weights_asof VALUES ('SH.000300', ?, ?, ?, ?, ?, 'unit')",
            [
                ("2024-03-29", "SH.600000", 40.0, "2024-03-29", "2024-03-29T18:00:00"),
                ("2024-03-29", "SH.600519", 30.0, "2024-03-29", "2024-03-29T18:00:00"),
                ("2024-03-29", "SZ.000001", 20.0, "2024-03-29", "2024-03-29T18:00:00"),
                ("2024-03-29", "SZ.000333", 10.0, "2024-03-29", "2024-03-29T18:00:00"),
                ("2024-04-30", "SH.600000", 10.0, "2024-04-30", "2024-04-30T18:00:00"),
                ("2024-04-30", "SH.600519", 60.0, "2024-04-30", "2024-04-30T18:00:00"),
                ("2024-04-30", "SZ.000001", 20.0, "2024-04-30", "2024-04-30T18:00:00"),
                ("2024-04-30", "SZ.000333", 10.0, "2024-04-30", "2024-04-30T18:00:00"),
            ],
        )
        conn.executemany(
            "INSERT INTO market_index_bars VALUES ('SH.000300', ?, ?, 'daily')",
            [
                ("2024-03-29", 100.0),
                ("2024-04-01", 110.0),
                ("2024-04-02", 121.0),
                ("2024-04-30", 133.1),
            ],
        )


def test_csi300_attribution_uses_latest_prior_weight_date_and_missed_top_weights(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite"
    _create_history_db(db_path)
    holdings_path = tmp_path / "strategy_daily_holdings.csv"
    daily_path = tmp_path / "strategy_daily_exposure.csv"
    pd.DataFrame(
        [
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 4,
                "valid_start": "2024-04-01",
                "valid_end": "2025-03-31",
                "market_context_label": "relative_lag_in_strong_benchmark_context",
                "date": "2024-04-02",
                "symbol": "SH.600000",
                "name": "浦发银行",
                "industry": "银行",
                "live_weight": 0.20,
                "position_ret": 0.002,
            },
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 4,
                "valid_start": "2024-04-01",
                "valid_end": "2025-03-31",
                "market_context_label": "relative_lag_in_strong_benchmark_context",
                "date": "2024-04-02",
                "symbol": "SZ.000333",
                "name": "美的集团",
                "industry": "家用电器",
                "live_weight": 0.10,
                "position_ret": 0.001,
            },
        ]
    ).to_csv(holdings_path, index=False)
    pd.DataFrame(
        [
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 4,
                "date": "2024-04-02",
                "market_context_label": "relative_lag_in_strong_benchmark_context",
                "live_exposure": 0.30,
                "live_holding_count": 2,
                "benchmark_daily_return": 0.01,
            }
        ]
    ).to_csv(daily_path, index=False)

    result = run_strategy_csi300_attribution(
        config={
            "benchmark_symbol": "SH.000300",
            "local_history": {"path": str(db_path)},
        },
        root=tmp_path,
        holdings_path=holdings_path,
        daily_exposure_path=daily_path,
        output_dir=tmp_path / "out",
        top_n=2,
    )

    assert result.status == "ok"
    daily = pd.read_csv(result.daily_csv_path)
    row = daily.iloc[0]
    assert row["benchmark_weight_date"] == "2024-03-29"
    assert row["strategy_live_exposure"] == 0.30
    assert row["strategy_weight_in_benchmark"] == 0.30
    assert row["benchmark_weight_held_by_strategy"] == 0.50
    assert row["benchmark_top_n_weight_missed"] == pytest.approx(0.30)
    assert row["benchmark_top_n_coverage_ratio"] == pytest.approx(0.40 / 0.70)

    missed = pd.read_csv(result.missed_top_csv_path)
    assert set(missed["symbol"]) == {"SH.600519"}
    assert missed.iloc[0]["avg_benchmark_weight"] == 0.30

    fold = pd.read_csv(result.fold_csv_path)
    assert fold.iloc[0]["primary_driver"] == "low_participation"
    assert "仓位参与不足" in fold.iloc[0]["plain_language_summary"]
    report = result.report_md_path.read_text(encoding="utf-8")
    assert report.startswith("# 沪深300权重归因报告")
    assert "I34 沪深300权重归因报告" not in report


def test_csi300_attribution_defaults_to_lagged_weight_date(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite"
    _create_history_db(db_path)
    holdings_path = tmp_path / "strategy_daily_holdings.csv"
    pd.DataFrame(
        [
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 4,
                "valid_start": "2024-04-01",
                "valid_end": "2025-03-31",
                "market_context_label": "relative_lag_in_strong_benchmark_context",
                "date": "2024-04-30",
                "symbol": "SH.600519",
                "name": "贵州茅台",
                "industry": "白酒",
                "live_weight": 0.20,
                "position_ret": 0.002,
            }
        ]
    ).to_csv(holdings_path, index=False)

    default_result = run_strategy_csi300_attribution(
        config={
            "benchmark_symbol": "SH.000300",
            "local_history": {"path": str(db_path)},
        },
        root=tmp_path,
        holdings_path=holdings_path,
        output_dir=tmp_path / "default_lag",
        top_n=2,
    )
    same_day_result = run_strategy_csi300_attribution(
        config={
            "benchmark_symbol": "SH.000300",
            "local_history": {"path": str(db_path)},
        },
        root=tmp_path,
        holdings_path=holdings_path,
        output_dir=tmp_path / "same_day",
        top_n=2,
        weight_date_lag_days=0,
    )

    default_daily = pd.read_csv(default_result.daily_csv_path)
    same_day_daily = pd.read_csv(same_day_result.daily_csv_path)
    assert default_daily.iloc[0]["benchmark_weight_date"] == "2024-03-29"
    assert same_day_daily.iloc[0]["benchmark_weight_date"] == "2024-04-30"
    assert default_daily.iloc[0]["benchmark_weight_held_by_strategy"] == 0.30
    assert same_day_daily.iloc[0]["benchmark_weight_held_by_strategy"] == 0.60


def test_csi300_attribution_can_use_candidate_folds_without_daily_exposure(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite"
    _create_history_db(db_path)
    candidate_folds_path = tmp_path / "strategy_admission_candidate_folds.csv"
    market_context_path = tmp_path / "strategy_market_context_diagnostic.csv"
    pd.DataFrame(
        [
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 4,
                "valid_start": "2024-04-01",
                "valid_end": "2024-04-02",
            }
        ]
    ).to_csv(candidate_folds_path, index=False)
    pd.DataFrame(
        [
            {
                "strategy_id": "price_volume_low_turnover_v1",
                "walk_forward_preset": "baseline_2y_1y_5fold",
                "fold": 4,
                "market_context_label": "relative_lag_in_strong_benchmark_context",
            }
        ]
    ).to_csv(market_context_path, index=False)

    result = run_strategy_csi300_attribution(
        config={
            "benchmark_symbol": "SH.000300",
            "local_history": {"path": str(db_path)},
        },
        root=tmp_path,
        candidate_folds_path=candidate_folds_path,
        market_context_path=market_context_path,
        output_dir=tmp_path / "fold_scaffold",
        top_n=2,
    )

    assert result.status == "ok"
    daily = pd.read_csv(result.daily_csv_path)
    fold = pd.read_csv(result.fold_csv_path)
    assert len(daily) == 2
    assert set(daily["benchmark_daily_return"].round(6)) == {0.1}
    assert daily["strategy_live_exposure"].sum() == 0
    assert fold.iloc[0]["benchmark_total_return"] == pytest.approx(0.21)
    assert fold.iloc[0]["primary_driver"] == "low_participation"


def test_csi300_attribution_blocks_when_weight_table_is_missing(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE market_stocks (market TEXT, symbol TEXT, name TEXT, industry TEXT)")
    holdings_path = tmp_path / "strategy_daily_holdings.csv"
    pd.DataFrame(
        [
            {
                "strategy_id": "x",
                "walk_forward_preset": "p",
                "fold": 1,
                "valid_start": "2024-04-01",
                "valid_end": "2025-03-31",
                "market_context_label": "relative_lag_in_strong_benchmark_context",
                "date": "2024-04-02",
                "symbol": "SH.600000",
                "industry": "银行",
                "live_weight": 0.2,
                "position_ret": 0.001,
            }
        ]
    ).to_csv(holdings_path, index=False)

    result = run_strategy_csi300_attribution(
        config={"local_history": {"path": str(db_path)}},
        root=tmp_path,
        holdings_path=holdings_path,
        output_dir=tmp_path / "out",
    )

    assert result.status == "blocked_missing_asof_tables"
    assert "缺少必要 as-of 数据" in result.report_md_path.read_text(encoding="utf-8")
