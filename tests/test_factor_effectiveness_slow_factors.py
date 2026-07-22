from __future__ import annotations

import pandas as pd

from phase0.research.diagnostics.factor_effectiveness import FACTOR_SPECS, FactorSpec, _add_factor_columns


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
