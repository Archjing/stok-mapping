from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from quant.strategies import available_strategies, get_strategy
from quant.strategies.strong_market_effective_participation import (
    StrongMarketEffectiveParticipationStrategy,
    _attach_benchmark_weights,
)


def _panel(dates: pd.DatetimeIndex | None = None) -> pd.DataFrame:
    rows = []
    if dates is None:
        dates = pd.date_range("2024-01-10", periods=4, freq="D")
    symbols = [
        ("B1", "Bank", 0.050, 0.60, 0.30, 1.8),
        ("B2", "Bank", 0.040, 0.58, 0.28, 1.7),
        ("T1", "Tech", 0.030, 0.56, 0.26, 1.6),
        ("T2", "Tech", 0.020, 0.54, 0.24, 1.5),
        ("A1", "Alpha", 0.000, 0.52, 0.22, 1.4),
        ("A2", "Alpha", 0.000, 0.50, 0.20, 1.3),
    ]
    for idx, date in enumerate(dates):
        for symbol, industry, benchmark_weight, mom60, resid, amount_ratio in symbols:
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "ret": 0.01,
                    "close": 10.0 + idx,
                    "ma60": 9.0,
                    "mom20": 0.10 + resid / 10.0,
                    "mom60": mom60,
                    "vol20": 0.10,
                    "amount_ratio20": amount_ratio,
                    "upper_shadow_pct": 0.5,
                    "breakout20": 1.0,
                    "resid_mom20": resid,
                    "industry_relative_mom20": 0.20 if industry in {"Bank", "Tech"} else 0.10,
                    "industry_relative_mom60": 0.22 if industry in {"Bank", "Tech"} else 0.08,
                    "industry": industry,
                    "benchmark_weight": benchmark_weight,
                    "strong_index_context": True,
                }
            )
    return pd.DataFrame(rows)


def _params(**overrides) -> dict:
    base = {
        "eligible": True,
        "benchmark_symbol": "SH.000300",
        "threshold_status": "pre_registered_i36_first_pass",
        "trend_window": 3,
        "return_short_window": 1,
        "return_long_window": 2,
        "vol_window": 2,
        "vol_quantile": 0.7,
        "vol_threshold_lookback_days": 3,
        "drawdown_min": -0.12,
        "buy_top_n": 5,
        "target_exposure": 0.70,
        "benchmark_core_min_weight": 0.70,
        "benchmark_weight_multiplier": 2.0,
        "max_symbol_weight": 0.25,
        "max_names_per_industry": 2,
        "amount_ratio_min": 1.0,
        "amount_ratio_max": 4.0,
        "upper_shadow_max": 1.3,
        "vol_cross_section_quantile": 0.95,
        "factor_weights": {
            "benchmark_weight": 0.30,
            "mom60": 0.22,
            "mom20": 0.12,
            "resid_mom20": 0.10,
            "industry_relative_mom20": 0.10,
            "industry_relative_mom60": 0.06,
            "amount_ratio20": 0.08,
            "low_vol20": 0.02,
        },
    }
    base.update(overrides)
    return base


def test_strong_market_effective_participation_is_registered_research_only() -> None:
    assert "strong_market_effective_participation_v1" in available_strategies()
    strategy = get_strategy("strong_market_effective_participation_v1")
    assert isinstance(strategy, StrongMarketEffectiveParticipationStrategy)
    assert strategy.supports_brief is False
    assert strategy.supports_paper_trade is False


def test_effective_participation_targets_exposure_and_uses_benchmark_core() -> None:
    strategy = StrongMarketEffectiveParticipationStrategy()

    output = strategy.apply(_panel(), _params(), slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    first_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-10")]
    selected = first_day[first_day["weight_unshifted"] > 0]
    assert selected["weight_unshifted"].sum() == pytest.approx(0.49)
    assert selected["weight_unshifted"].max() <= 0.25
    assert selected.loc[selected["benchmark_weight"] > 0, "weight_unshifted"].sum() == pytest.approx(0.28)
    assert selected["symbol"].nunique() <= 5
    assert selected.loc[selected["industry"] == "Bank", "symbol"].nunique() == 2

    second_day = output.signal_frame[output.signal_frame["date"] == pd.Timestamp("2024-01-11")]
    assert second_day["weight"].sum() == pytest.approx(0.49)


def test_effective_participation_does_not_open_when_context_is_weak() -> None:
    strategy = StrongMarketEffectiveParticipationStrategy()
    panel = _panel()
    panel["strong_index_context"] = False

    output = strategy.apply(panel, _params(), slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    assert output.signal_frame["weight_unshifted"].eq(0.0).all()
    assert output.exposure.eq(0.0).all()


def test_effective_participation_missing_required_field_returns_cash() -> None:
    strategy = StrongMarketEffectiveParticipationStrategy()
    panel = _panel().drop(columns=["ma60"])

    output = strategy.apply(panel, _params(), slippage=0.0, commission=0.0, stamp_duty_sell=0.0)

    assert output.returns.eq(0.0).all()
    assert output.exposure.eq(0.0).all()
    assert output.signal_frame.empty
    assert output.metadata["ineligible_reason"] == "missing_required_fields:ma60"


def test_attach_benchmark_weights_uses_lagged_asof_table(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "history.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE cn_index_weights_asof (
                index_code TEXT,
                trade_date TEXT,
                symbol TEXT,
                weight REAL
            )
            """
        )
        conn.executemany(
            "INSERT INTO cn_index_weights_asof VALUES ('SH.000300', ?, ?, ?)",
            [
                ("2024-01-09", "B1", 50.0),
                ("2024-01-09", "B2", 50.0),
                ("2024-01-10", "B1", 80.0),
                ("2024-01-10", "B2", 20.0),
            ],
        )
    monkeypatch.setattr("quant.strategies.strong_market_effective_participation.local_history_path", lambda: db_path)
    panel = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-10"), pd.Timestamp("2024-01-11")],
            "symbol": ["B1", "B1"],
        }
    )

    out = _attach_benchmark_weights(panel, {"benchmark_symbol": "SH.000300"})

    assert out.loc[out["date"] == pd.Timestamp("2024-01-10"), "benchmark_weight"].iloc[0] == pytest.approx(0.50)
    assert out.loc[out["date"] == pd.Timestamp("2024-01-11"), "benchmark_weight"].iloc[0] == pytest.approx(0.80)
    assert out.loc[out["date"] == pd.Timestamp("2024-01-10"), "benchmark_weight_date"].iloc[0] == "2024-01-09"
