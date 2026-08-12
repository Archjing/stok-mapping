from __future__ import annotations

import pandas as pd

from quant.walk_forward import _date_window_slices, _window_summary_fields


def test_date_window_slices_use_calendar_year_boundaries_not_252_trading_days() -> None:
    dates = pd.bdate_range("2019-04-01", "2022-03-31")

    folds = _date_window_slices(
        dates.tolist(),
        train_years=2,
        validate_years=1,
        min_samples=200,
    )

    assert len(folds) == 1
    _, train_dates, valid_dates = folds[0]

    assert min(train_dates) == pd.Timestamp("2019-04-01")
    assert max(train_dates) == pd.Timestamp("2021-03-31")
    assert min(valid_dates) == pd.Timestamp("2021-04-01")
    assert max(valid_dates) == pd.Timestamp("2022-03-31")
    assert pd.Timestamp("2021-03-19") in train_dates
    assert pd.Timestamp("2021-03-22") in train_dates


def test_date_window_slices_roll_forward_by_validation_years() -> None:
    dates = pd.bdate_range("2019-04-01", "2024-03-31")

    folds = _date_window_slices(
        dates.tolist(),
        train_years=2,
        validate_years=1,
        min_samples=200,
    )

    assert len(folds) == 3
    assert min(folds[0][1]) == pd.Timestamp("2019-04-01")
    assert min(folds[1][1]) == pd.Timestamp("2020-04-01")
    assert min(folds[2][1]) == pd.Timestamp("2021-04-01")
    assert min(folds[2][2]) == pd.Timestamp("2023-04-03")


def test_date_window_slices_honor_explicit_start_and_end_dates() -> None:
    dates = pd.bdate_range("2018-01-01", "2026-06-30")

    folds = _date_window_slices(
        dates.tolist(),
        train_years=2,
        validate_years=1,
        min_samples=200,
        start_date="2019-04-01",
        end_date="2026-03-31",
    )

    assert len(folds) == 5
    assert min(folds[0][1]) == pd.Timestamp("2019-04-01")
    assert max(folds[-1][2]) == pd.Timestamp("2026-03-31")


def test_window_summary_fields_warn_on_expected_fold_mismatch() -> None:
    folds_df = pd.DataFrame({"fold": [1, 1, 2, 2]})

    fields = _window_summary_fields(
        {
            "start_date": pd.Timestamp("2019-04-01").date(),
            "end_date": pd.Timestamp("2026-03-31").date(),
            "expected_folds": 5,
        },
        folds_df,
    )

    assert fields["walk_forward_start_date"] == "2019-04-01"
    assert fields["walk_forward_end_date"] == "2026-03-31"
    assert fields["walk_forward_expected_folds"] == 5
    assert fields["walk_forward_actual_folds"] == 2
    assert fields["walk_forward_fold_generation_warning"] == "expected_folds=5 actual_folds=2"
