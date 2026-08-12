from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

import quant.research.diagnostics.factor_effectiveness as factor_effectiveness
from quant.data_access import local_history
from quant.data_governance import external_market_history
from quant.research.diagnostics.factor_effectiveness import (
    FACTOR_SPECS,
    FactorSpec,
    _add_factor_columns,
    _add_forward_returns,
    run_factor_effectiveness_report,
)


EXISTING_FACTOR_SPECS = [
    FactorSpec("low_vol20", "low_vol20", "-vol20"),
    FactorSpec("low_vol60", "low_vol60", "-vol60"),
    FactorSpec("low_turnover_rate", "low_turnover_rate", "-turnover_rate"),
    FactorSpec("low_amount_ratio20", "low_amount_ratio20", "-amount_ratio20"),
    FactorSpec("mom20", "mom20", "20-day momentum"),
    FactorSpec("mom60", "mom60", "60-day momentum"),
    FactorSpec("reversal_mom3", "reversal_mom3", "-mom3"),
    FactorSpec("reversal_mom5", "reversal_mom5", "-mom5"),
    FactorSpec("roe", "roe", "point-in-time ROE"),
    FactorSpec(
        "cash_flow_quality",
        "cash_flow_quality",
        "point-in-time operating cash flow / net profit",
    ),
    FactorSpec("profit_growth", "profit_growth", "point-in-time profit growth"),
    FactorSpec("revenue_growth", "revenue_growth", "point-in-time revenue growth"),
    FactorSpec("low_debt_to_asset", "low_debt_to_asset", "-debt_to_asset"),
    FactorSpec("ep", "ep", "1 / pe_ttm"),
    FactorSpec("low_pb", "low_pb", "-pb"),
]
SLOW_FACTOR_SPECS = [
    FactorSpec("slow_quality", "slow_quality_score", "PIT quality neutralized by industry and size"),
    FactorSpec(
        "slow_earnings",
        "slow_earnings_score",
        "PIT earnings improvement neutralized by industry and size",
    ),
    FactorSpec(
        "slow_value",
        "slow_value_score",
        "positive E/P and inverse P/B neutralized by industry and size",
    ),
    FactorSpec(
        "slow_low_vol",
        "slow_low_vol_score",
        "60-day low volatility neutralized by industry and size",
    ),
    FactorSpec(
        "slow_residual_momentum",
        "slow_residual_momentum_score",
        "120-to-20-day momentum neutralized by industry and size",
    ),
]


@pytest.fixture(autouse=True)
def _restore_market_history_configuration() -> Iterator[None]:
    original_local = vars(local_history._settings).copy()
    original_us = vars(external_market_history._us_settings).copy()
    original_hk = vars(external_market_history._hk_settings).copy()
    try:
        yield
    finally:
        local_history.configure_local_history(original_local)
        external_market_history.configure_us_market_history(original_us)
        external_market_history.configure_hk_market_history(original_hk)


def _sample_factor_panel() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=125)
    symbols = [
        ("AAA", "Technology", 100.0, 12.0, 1.4, 0.18, 0.0010),
        ("BBB", "Technology", 180.0, 20.0, 2.1, 0.24, 0.0006),
        ("CCC", "Finance", 260.0, 9.0, 0.9, 0.12, 0.0014),
    ]
    rows: list[dict[str, object]] = []
    for symbol_index, (symbol, industry, market_cap, pe_ttm, pb, vol60, daily_growth) in enumerate(symbols):
        for date_index, date in enumerate(dates):
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "walk_forward_preset": "baseline_2y_1y_5fold",
                    "fold": 1,
                    "industry": industry,
                    "close": (20.0 + symbol_index * 5.0) * (1.0 + daily_growth) ** date_index,
                    "ret": daily_growth,
                    "vol20": vol60 * 0.8,
                    "vol60": vol60,
                    "amount_ratio20": 0.9 + symbol_index * 0.2,
                    "turnover_rate": 0.7 + symbol_index * 0.1,
                    "market_cap": market_cap,
                    "pe_ttm": pe_ttm,
                    "pb": pb,
                    "quality_roe_component": 0.8 - symbol_index * 0.2,
                    "quality_cash_flow_component": 0.7 - symbol_index * 0.1,
                    "quality_low_debt_component": 0.6 - symbol_index * 0.15,
                    "quality_profit_growth_component": 0.3 + symbol_index * 0.05,
                    "quality_revenue_growth_component": 0.25 + symbol_index * 0.04,
                }
            )
    return pd.DataFrame(rows).sample(frac=1.0, random_state=23).reset_index(drop=True)


def _raw_pit_factor_panel(*, preset: str, daily_growth_scale: float = 1.0) -> pd.DataFrame:
    dates = pd.bdate_range("2023-01-02", periods=130)
    symbols = [
        ("TEST_A", "Technology", 100.0, 12.0, 1.4, 0.18, 0.0010),
        ("TEST_B", "Technology", 180.0, 20.0, 2.1, 0.24, 0.0006),
        ("TEST_C", "Finance", 260.0, 9.0, 0.9, 0.12, 0.0014),
    ]
    rows: list[dict[str, object]] = []
    for symbol_index, (symbol, industry, market_cap, pe_ttm, pb, vol60, daily_growth) in enumerate(symbols):
        growth = daily_growth * daily_growth_scale
        for date_index, date in enumerate(dates):
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "walk_forward_preset": preset,
                    "industry": industry,
                    "close": (20.0 + symbol_index * 5.0) * (1.0 + growth) ** date_index,
                    "ret": growth,
                    "vol20": vol60 * 0.8,
                    "vol60": vol60,
                    "amount_ratio20": 0.9 + symbol_index * 0.2,
                    "turnover_rate": 0.7 + symbol_index * 0.1,
                    "market_cap": market_cap,
                    "pe_ttm": pe_ttm,
                    "pb": pb,
                    "roe": 18.0 - symbol_index * 2.0,
                    "cash_flow_quality": 1.3 - symbol_index * 0.2,
                    "profit_growth": 22.0 + symbol_index * 3.0,
                    "revenue_growth": 16.0 + symbol_index * 2.0,
                    "debt_to_asset": 35.0 + symbol_index * 5.0,
                }
            )
    return pd.DataFrame(rows)


def _fold_context(panel: pd.DataFrame, *, fold: int) -> dict[str, object]:
    dates = sorted(panel["date"].unique())
    train_dates = set(dates[:125])
    valid_dates = set(dates[125:])
    return {
        "fold": fold,
        "train": panel[panel["date"].isin(train_dates)].copy(),
        "valid": panel[panel["date"].isin(valid_dates)].copy(),
    }


def _run_report_and_capture_pre_label_panel(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    contexts: list[dict[str, object]],
    output_name: str,
) -> pd.DataFrame:
    captured: dict[str, pd.DataFrame] = {}
    audit = pd.DataFrame([{"fold": context["fold"], "warning": ""} for context in contexts])

    monkeypatch.setattr(
        factor_effectiveness,
        "iter_point_in_time_universe_folds",
        lambda *args, **kwargs: (contexts, audit),
    )

    def capture_before_labels(panel: pd.DataFrame, horizon: int) -> pd.DataFrame:
        captured["panel"] = panel.copy()
        return _add_forward_returns(panel, horizon)

    monkeypatch.setattr(factor_effectiveness, "_add_forward_returns", capture_before_labels)
    run_factor_effectiveness_report(
        config={
            "years": 1,
            "local_history": {"path": "absent.sqlite"},
            "walk_forward": {
                "train_years": 1,
                "validate_years": 1,
                "min_samples": 2,
                "strategy_v2": {"local_factor": {"quality_growth": {"enabled": True}}},
            },
        },
        root=tmp_path,
        output_dir=tmp_path / output_name,
        forward_horizon=2,
        min_daily_samples=2,
    )
    return captured["panel"]


def test_factor_specs_append_exactly_five_slow_factors() -> None:
    slow_factor_names = {spec.name for spec in SLOW_FACTOR_SPECS}

    assert slow_factor_names.issubset({spec.name for spec in FACTOR_SPECS})
    assert FACTOR_SPECS[:15] == EXISTING_FACTOR_SPECS
    assert FACTOR_SPECS[15:] == SLOW_FACTOR_SPECS
    assert len(FACTOR_SPECS) == 20


def test_add_factor_columns_produces_slow_factor_scores() -> None:
    result = _add_factor_columns(_sample_factor_panel())
    score_columns = [spec.column for spec in SLOW_FACTOR_SPECS]
    final_date = result["date"].max()

    assert set(score_columns).issubset(result.columns)
    assert result.loc[result["date"] == final_date, score_columns].notna().all().all()
    assert result["walk_forward_preset"].eq("baseline_2y_1y_5fold").all()
    assert result["fold"].eq(1).all()


def test_report_preparation_maps_raw_pit_financial_fields_to_slow_scores(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    raw_panel = _raw_pit_factor_panel(preset="baseline")
    contexts = [_fold_context(raw_panel, fold=1)]

    result = _run_report_and_capture_pre_label_panel(
        monkeypatch,
        tmp_path,
        contexts=contexts,
        output_name="raw-pit",
    )

    assert not any(column.startswith("quality_") and column.endswith("_component") for column in raw_panel.columns)
    assert result["slow_quality_score"].notna().all()
    assert result["slow_earnings_score"].notna().all()


def test_report_preparation_uses_train_history_without_emitting_or_looking_ahead(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    panels = [
        _raw_pit_factor_panel(preset="baseline", daily_growth_scale=1.0),
        _raw_pit_factor_panel(preset="quality", daily_growth_scale=1.7),
    ]
    contexts = [_fold_context(panel, fold=fold) for fold, panel in enumerate(panels, start=1)]

    baseline = _run_report_and_capture_pre_label_panel(
        monkeypatch,
        tmp_path,
        contexts=contexts,
        output_name="baseline-history",
    )
    changed_contexts: list[dict[str, object]] = []
    for context in contexts:
        valid = context["valid"].copy()
        first_valid_date = valid["date"].min()
        valid.loc[valid["date"] > first_valid_date, "close"] *= 10.0
        changed_contexts.append({**context, "train": context["train"].copy(), "valid": valid})
    changed = _run_report_and_capture_pre_label_panel(
        monkeypatch,
        tmp_path,
        contexts=changed_contexts,
        output_name="changed-history",
    )

    validation_dates = set(contexts[0]["valid"]["date"].unique())
    assert set(baseline["date"].unique()) == validation_dates
    assert len(baseline) == sum(len(context["valid"]) for context in contexts)
    assert "forward_ret_2d" not in baseline.columns
    first_day = baseline[baseline["date"] == min(validation_dates)].copy()
    assert first_day["slow_residual_momentum_raw"].notna().all()
    for context in contexts:
        combined = pd.concat([context["train"], context["valid"]]).sort_values(["symbol", "date"])
        expected = combined[combined["symbol"] == "TEST_A"].iloc[105]["close"]
        expected /= combined[combined["symbol"] == "TEST_A"].iloc[5]["close"]
        expected -= 1.0
        actual = first_day.loc[
            (first_day["fold"] == context["fold"]) & (first_day["symbol"] == "TEST_A"),
            "slow_residual_momentum_raw",
        ].item()
        assert actual == pytest.approx(expected)
    comparison_columns = [
        "walk_forward_preset",
        "fold",
        "date",
        "symbol",
        "slow_residual_momentum_raw",
        "slow_residual_momentum_score",
    ]
    pd.testing.assert_frame_equal(
        first_day[comparison_columns].sort_values(comparison_columns[:4]).reset_index(drop=True),
        changed.loc[changed["date"] == min(validation_dates), comparison_columns]
        .sort_values(comparison_columns[:4])
        .reset_index(drop=True),
    )
