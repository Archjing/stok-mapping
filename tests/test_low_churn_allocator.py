from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant.strategies.low_churn_allocator import allocate_low_churn


SIGNAL_COLUMNS = [
    "date",
    "symbol",
    "industry",
    "final_score",
    "score",
    "rank",
    "selected",
    "raw_weight",
    "weight_unshifted",
    "weight",
    "held_days",
    "review_reason",
    "ret",
    "position_ret",
]


def _state_machine_panel() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=4)
    daily_scores = [
        {"AAA": 0.9, "BBB": 0.8, "CCC": 0.7},
        {"AAA": 0.6, "BBB": 0.9, "CCC": 0.7},
        {"AAA": 0.5, "BBB": 0.9, "CCC": 0.8},
        {"AAA": 0.5, "BBB": 0.9, "CCC": 0.8},
    ]
    industries = {"AAA": "A", "BBB": "A", "CCC": "B"}
    rows = []
    for date, scores in zip(dates, daily_scores, strict=True):
        for symbol in ["AAA", "BBB", "CCC"]:
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "industry": industries[symbol],
                    "final_score": scores[symbol],
                    "score": scores[symbol],
                    "risk_overlay_scale": 1.0,
                    "ret": 0.0,
                }
            )
    return pd.DataFrame(rows)


def _params() -> dict[str, object]:
    return {
        "buy_top_n": 1,
        "hold_top_n": 1,
        "rebalance_days": 2,
        "min_hold_days": 2,
        "max_symbol_weight": 0.5,
        "max_names_per_industry": 1,
    }


def test_allocate_low_churn_runs_the_existing_state_machine() -> None:
    metadata = {"source": "allocator-unit-test"}

    output = allocate_low_churn(
        _state_machine_panel(),
        params=_params(),
        slippage=0.001,
        commission=0.00025,
        stamp_duty_sell=0.0005,
        signal_columns=SIGNAL_COLUMNS,
        metadata=metadata,
    )
    signal = output.signal_frame.set_index(["date", "symbol"])
    dates = list(pd.bdate_range("2024-01-02", periods=4))

    assert signal.loc[(dates[0], "AAA"), "weight_unshifted"] == 0.5
    assert signal.loc[(dates[1], "AAA"), "weight_unshifted"] == 0.5
    assert signal.loc[(dates[2], "AAA"), "weight_unshifted"] == 0.0
    assert signal.loc[(dates[2], "BBB"), "weight_unshifted"] == 0.5
    assert signal.loc[(dates[2], "AAA"), "weight"] == 0.5
    assert signal.loc[(dates[3], "BBB"), "weight"] == 0.5
    assert signal.loc[(dates[2], "AAA"), "held_days"] == 0
    assert signal.loc[(dates[2], "BBB"), "held_days"] == 0
    assert signal.loc[(dates[2], "BBB"), "review_reason"] == "fixed_rebalance"
    assert output.returns.loc[dates[1]] == pytest.approx(-0.000625)
    assert list(output.signal_frame.columns) == SIGNAL_COLUMNS
    assert output.metadata == metadata


def test_allocate_low_churn_degrades_when_required_columns_are_missing() -> None:
    date = pd.Timestamp("2024-01-02")
    metadata = {"source": "allocator-unit-test"}

    output = allocate_low_churn(
        pd.DataFrame([{"date": date, "final_score": 0.9}]),
        params=_params(),
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
        signal_columns=SIGNAL_COLUMNS,
        metadata=metadata,
    )

    pd.testing.assert_series_equal(output.returns, pd.Series([0.0], index=pd.Index([date])))
    pd.testing.assert_series_equal(output.exposure, pd.Series([0.0], index=pd.Index([date])))
    assert output.signal_frame.empty
    assert output.metadata == metadata


def test_allocate_low_churn_preserves_none_and_unknown_as_distinct_industries() -> None:
    dates = list(pd.bdate_range("2024-01-02", periods=2))
    panel = pd.DataFrame(
        [
            {
                "date": dates[0],
                "symbol": "AAA",
                "industry": None,
                "final_score": 0.9,
                "score": 0.9,
                "risk_overlay_scale": 1.0,
                "ret": 0.0,
            },
            {
                "date": dates[0],
                "symbol": "BBB",
                "industry": "UNKNOWN",
                "final_score": float("nan"),
                "score": float("nan"),
                "risk_overlay_scale": 1.0,
                "ret": 0.0,
            },
            {
                "date": dates[1],
                "symbol": "AAA",
                "industry": None,
                "final_score": 0.9,
                "score": 0.9,
                "risk_overlay_scale": 1.0,
                "ret": 0.0,
            },
            {
                "date": dates[1],
                "symbol": "BBB",
                "industry": "UNKNOWN",
                "final_score": 0.8,
                "score": 0.8,
                "risk_overlay_scale": 1.0,
                "ret": 0.0,
            },
        ]
    )
    panel["industry"] = pd.Series([None, "UNKNOWN", None, "UNKNOWN"], dtype=object)

    output = allocate_low_churn(
        panel,
        params={
            "buy_top_n": 2,
            "hold_top_n": 2,
            "rebalance_days": 1,
            "min_hold_days": 0,
            "max_symbol_weight": 0.5,
            "max_names_per_industry": 1,
        },
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
        signal_columns=SIGNAL_COLUMNS,
        metadata={},
    )

    second_day = output.signal_frame[output.signal_frame["date"] == dates[1]]
    assert set(second_day.loc[second_day["selected"] > 0, "symbol"]) == {"AAA", "BBB"}


@pytest.mark.parametrize(
    ("risk_overlay_scale", "expected_weight"),
    [(-0.2, 0.0), (1.5, 0.5), (np.inf, 0.5), (-np.inf, 0.5), (np.nan, 0.5)],
)
def test_allocate_low_churn_normalizes_risk_overlay_scale(
    risk_overlay_scale: float,
    expected_weight: float,
) -> None:
    dates = list(pd.bdate_range("2024-01-02", periods=2))
    panel = pd.DataFrame(
        [
            {
                "date": date,
                "symbol": "AAA",
                "final_score": 0.9,
                "score": 0.9,
                "risk_overlay_scale": risk_overlay_scale,
                "ret": 0.01,
            }
            for date in dates
        ]
    )

    output = allocate_low_churn(
        panel,
        params={
            "buy_top_n": 1,
            "hold_top_n": 1,
            "rebalance_days": 1,
            "min_hold_days": 0,
            "max_symbol_weight": 0.5,
            "max_names_per_industry": None,
        },
        slippage=0.001,
        commission=0.0,
        stamp_duty_sell=0.0,
        signal_columns=SIGNAL_COLUMNS,
        metadata={},
    )
    signal = output.signal_frame.sort_values("date").reset_index(drop=True)

    assert signal.loc[0, "weight_unshifted"] == expected_weight
    assert signal.loc[1, "weight"] == expected_weight
    assert signal["weight_unshifted"].between(0.0, 0.5).all()
    assert signal["selected"].equals((signal["weight_unshifted"] > 0).astype(float))
    assert np.isfinite(output.returns).all()
    assert np.isfinite(output.exposure).all()


def test_allocate_low_churn_rejects_duplicate_normalized_date_symbol_keys() -> None:
    date = pd.Timestamp("2024-01-02")
    panel = pd.DataFrame(
        [
            {
                "date": date,
                "symbol": 1,
                "final_score": 0.9,
                "score": 0.9,
                "risk_overlay_scale": 1.0,
                "ret": 0.0,
            },
            {
                "date": date,
                "symbol": "1",
                "final_score": 0.8,
                "score": 0.8,
                "risk_overlay_scale": 1.0,
                "ret": 0.0,
            },
        ]
    )

    with pytest.raises(ValueError) as exc_info:
        allocate_low_churn(
            panel,
            params=_params(),
            slippage=0.0,
            commission=0.0,
            stamp_duty_sell=0.0,
            signal_columns=SIGNAL_COLUMNS,
            metadata={},
        )

    message = str(exc_info.value)
    assert "unique (date, symbol) rows" in message
    assert "duplicate key samples" in message
    assert "2024-01-02" in message
    assert "'1'" in message


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), ("", None), ("invalid", None), (0, None), (-1, None), ("3", 3)],
)
def test_optional_positive_int(value: object, expected: int | None) -> None:
    from quant.strategies.low_churn_allocator import optional_positive_int

    assert optional_positive_int(value) == expected
