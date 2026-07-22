from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from phase0.research.factors import DEFAULT_WEIGHTS, add_slow_multifactor_features


SLOW_FACTOR_PREFIXES = [
    "slow_quality",
    "slow_earnings",
    "slow_value",
    "slow_low_vol",
    "slow_residual_momentum",
]
SLOW_FACTOR_OUTPUT_COLUMNS = [
    *[f"{prefix}_raw" for prefix in SLOW_FACTOR_PREFIXES],
    *[
        column
        for prefix in SLOW_FACTOR_PREFIXES
        for column in [f"{prefix}_neutral", f"{prefix}_score"]
    ],
    "slow_factor_available_count",
    "slow_composite_score",
]


def _sample_panel() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=140)
    specifications = [
        ("QUALITY", "Tech", 80.0, 16.0, 2.0, 0.25, (0.90, 0.80, 0.85), (0.30, 0.35), 0.0010),
        ("WEAK", "Tech", 110.0, 18.0, 2.2, 0.28, (-0.50, -0.40, -0.30), (-0.20, -0.10), 0.0006),
        ("VALUE", "Tech", 150.0, 5.0, 0.7, 0.20, (0.20, 0.10, 0.20), (0.10, 0.15), 0.0012),
        ("EXPENSIVE", "Tech", 230.0, 45.0, 6.0, 0.22, (0.10, 0.10, 0.10), (0.10, 0.10), 0.0008),
        ("LOWVOL", "Finance", 90.0, 12.0, 1.2, 0.08, (0.30, 0.20, 0.10), (0.20, 0.10), 0.0005),
        ("HIGHVOL", "Finance", 130.0, 14.0, 1.4, 0.75, (0.25, 0.15, 0.05), (0.15, 0.12), 0.0015),
        ("BALANCED_A", "Finance", 190.0, 9.0, 1.0, 0.30, (0.40, 0.10, 0.20), (0.05, 0.20), 0.0010),
        ("BALANCED_B", "Finance", 310.0, 30.0, 4.0, 0.40, (-0.10, 0.20, 0.00), (0.30, -0.10), 0.0007),
    ]
    rows: list[dict[str, object]] = []
    for symbol_index, (
        symbol,
        industry,
        market_cap,
        pe_ttm,
        pb,
        vol60,
        quality,
        growth,
        daily_growth,
    ) in enumerate(specifications):
        base_close = 40.0 + 5.0 * symbol_index
        for date_index, date in enumerate(dates):
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "industry": industry,
                    "close": base_close * (1.0 + daily_growth) ** date_index,
                    "market_cap": market_cap,
                    "pe_ttm": pe_ttm,
                    "pb": pb,
                    "vol60": vol60,
                    "quality_roe_component": quality[0],
                    "quality_cash_flow_component": quality[1],
                    "quality_low_debt_component": quality[2],
                    "quality_profit_growth_component": growth[0],
                    "quality_revenue_growth_component": growth[1],
                }
            )
    return pd.DataFrame(rows).sample(frac=1.0, random_state=37).reset_index(drop=True)


def _final_rows(result: pd.DataFrame) -> pd.DataFrame:
    return result[result["date"] == result["date"].max()].set_index("symbol")


def _walk_forward_comparison_columns() -> list[str]:
    return [
        "slow_residual_momentum_raw",
        *[
            column
            for prefix in SLOW_FACTOR_PREFIXES
            for column in [f"{prefix}_neutral", f"{prefix}_score"]
        ],
        "slow_factor_available_count",
        "slow_composite_score",
    ]


def _sorted_walk_forward_result(frame: pd.DataFrame) -> pd.DataFrame:
    keys = ["walk_forward_preset", "fold", "symbol", "date"]
    return frame[keys + _walk_forward_comparison_columns()].sort_values(keys).reset_index(drop=True)


def test_default_weights_match_slow_multifactor_contract() -> None:
    assert DEFAULT_WEIGHTS == {
        "slow_quality_score": 0.30,
        "slow_value_score": 0.20,
        "slow_low_vol_score": 0.20,
        "slow_earnings_score": 0.15,
        "slow_residual_momentum_score": 0.15,
    }


def test_slow_multifactor_raw_directions_and_availability() -> None:
    result = add_slow_multifactor_features(_sample_panel())
    final = _final_rows(result)

    assert final.loc["QUALITY", "slow_quality_raw"] > final.loc["WEAK", "slow_quality_raw"]
    assert final.loc["VALUE", "slow_value_raw"] > final.loc["EXPENSIVE", "slow_value_raw"]
    assert final.loc["LOWVOL", "slow_low_vol_raw"] > final.loc["HIGHVOL", "slow_low_vol_raw"]
    assert final["slow_factor_available_count"].min() >= 4
    assert final["slow_composite_score"].notna().all()
    assert list(result[["symbol", "date"]].itertuples(index=False, name=None)) == sorted(
        result[["symbol", "date"]].itertuples(index=False, name=None)
    )


def test_slow_multifactor_does_not_look_ahead() -> None:
    panel = _sample_panel()
    dates = sorted(panel["date"].unique())
    cutoff = dates[-21]
    changed = panel.copy()
    changed.loc[changed["date"] > cutoff, "close"] *= 10.0

    baseline = add_slow_multifactor_features(panel)
    perturbed = add_slow_multifactor_features(changed)
    columns = ["date", "symbol", "slow_residual_momentum_raw", "slow_composite_score"]

    pd.testing.assert_frame_equal(
        baseline.loc[baseline["date"] <= cutoff, columns].reset_index(drop=True),
        perturbed.loc[perturbed["date"] <= cutoff, columns].reset_index(drop=True),
    )


def test_walk_forward_partitions_match_independent_computation() -> None:
    panel = _sample_panel()
    partitions = [
        panel.assign(walk_forward_preset=preset, fold=fold)
        for preset in ["baseline", "quality"]
        for fold in [1, 2]
    ]
    concatenated = pd.concat(partitions, ignore_index=True).sample(frac=1.0, random_state=19)

    actual = add_slow_multifactor_features(concatenated)
    expected = pd.concat(
        [add_slow_multifactor_features(partition) for partition in partitions],
        ignore_index=True,
    )

    pd.testing.assert_frame_equal(
        _sorted_walk_forward_result(actual),
        _sorted_walk_forward_result(expected),
    )


def test_short_folds_do_not_borrow_momentum_history() -> None:
    panel = _sample_panel()
    first_80_dates = sorted(panel["date"].unique())[:80]
    short = panel[panel["date"].isin(first_80_dates)]
    concatenated = pd.concat(
        [
            short.assign(walk_forward_preset="baseline", fold=1),
            short.assign(walk_forward_preset="baseline", fold=2),
        ],
        ignore_index=True,
    )

    result = add_slow_multifactor_features(concatenated)

    assert result["slow_residual_momentum_raw"].isna().all()
    assert result["slow_residual_momentum_neutral"].isna().all()
    assert result["slow_residual_momentum_score"].isna().all()


def test_slow_value_is_industry_and_size_neutral() -> None:
    final = _final_rows(add_slow_multifactor_features(_sample_panel()))
    valid = final[final["slow_value_score"].notna()].copy()

    industry_means = valid.groupby("industry")["slow_value_neutral"].mean()
    size_correlation = valid["slow_value_neutral"].corr(np.log(valid["market_cap"]))

    assert industry_means.abs().max() < 1e-10
    assert abs(size_correlation) < 1e-10


def test_missing_inputs_degrade_to_missing_scores_without_mutating_input() -> None:
    panel = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-02"],
            "symbol": ["B", "A"],
            "market_cap": [100.0, 200.0],
            "quality_roe_component": ["not-numeric", None],
        }
    )
    original = panel.copy(deep=True)

    result = add_slow_multifactor_features(panel)

    pd.testing.assert_frame_equal(panel, original)
    assert result["industry"].eq("").all()
    assert result["slow_factor_available_count"].eq(0).all()
    assert result["slow_composite_score"].isna().all()
    assert result["slow_value_raw"].isna().all()
    assert result["slow_residual_momentum_raw"].isna().all()


def test_composite_requires_quality_earnings_and_minimum_available_factors() -> None:
    snapshot = _sample_panel()
    snapshot = snapshot[snapshot["date"] == snapshot["date"].max()].copy()
    snapshot.loc[snapshot["symbol"] == "WEAK", "quality_profit_growth_component"] = np.nan
    snapshot.loc[snapshot["symbol"] == "WEAK", "quality_revenue_growth_component"] = np.nan

    result = add_slow_multifactor_features(snapshot)
    rows = result.set_index("symbol")

    assert rows.loc["QUALITY", "slow_factor_available_count"] == 4
    assert pd.notna(rows.loc["QUALITY", "slow_composite_score"])
    assert rows.loc["WEAK", "slow_factor_available_count"] == 3
    assert pd.isna(rows.loc["WEAK", "slow_composite_score"])


def test_custom_weights_clamp_negative_values_and_renormalize_available_scores() -> None:
    snapshot = _sample_panel()
    snapshot = snapshot[snapshot["date"] == snapshot["date"].max()].copy()

    result = add_slow_multifactor_features(
        snapshot,
        weights={
            "slow_quality_score": 2.0,
            "slow_earnings_score": 1.0,
            "slow_value_score": -10.0,
        },
        min_available_factors=2,
    )
    expected = (2.0 * result["slow_quality_score"] + result["slow_earnings_score"]) / 3.0

    pd.testing.assert_series_equal(result["slow_composite_score"], expected, check_names=False)


@pytest.mark.parametrize(
    "weights",
    [
        {"slow_quality_score": 0.0},
        {"slow_quality_score": -1.0, "slow_value_score": -2.0},
    ],
)
def test_nonpositive_weight_total_is_rejected(weights: dict[str, float]) -> None:
    with pytest.raises(ValueError, match="positive"):
        add_slow_multifactor_features(_sample_panel().head(8), weights=weights)


def test_empty_panel_has_stable_output_schema_without_mutating_input() -> None:
    panel = pd.DataFrame(columns=["symbol", "date"])
    original = panel.copy(deep=True)

    result = add_slow_multifactor_features(panel)

    pd.testing.assert_frame_equal(panel, original)
    assert list(result.columns) == ["symbol", "date", *SLOW_FACTOR_OUTPUT_COLUMNS]
    assert result.empty
    for column in SLOW_FACTOR_OUTPUT_COLUMNS:
        assert pd.api.types.is_numeric_dtype(result[column])
