from __future__ import annotations

import pandas as pd

from phase0.strategies.base import StrategyOutput
from phase0.strategy_constraints import apply_strategy_constraints
from phase0.walk_forward import _signal_trace_summary


def _sample_output() -> StrategyOutput:
    dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    rows = []
    symbols = [
        ("AAA", "bank", 0.10, 0.90),
        ("BBB", "bank", 0.10, 0.80),
        ("CCC", "bank", 0.10, 0.70),
        ("DDD", "tech", 0.10, 0.60),
        ("EEE", "consumer", 0.10, 0.50),
    ]
    for date in dates:
        for symbol, industry, weight, score in symbols:
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "industry": industry,
                    "score": score,
                    "selected": 1.0,
                    "raw_weight": 1.0,
                    "weight_unshifted": weight,
                    "weight": weight,
                    "ret": 0.01,
                    "position_ret": weight * 0.01,
                }
            )
    signal = pd.DataFrame(rows)
    returns = signal.groupby("date")["position_ret"].sum()
    exposure = signal.groupby("date")["weight"].sum()
    return StrategyOutput(returns=returns, exposure=exposure, signal_frame=signal, metadata={})


def _cfg(mode: str, *, unknown_policy: str = "allow") -> dict:
    return {
        "constraints": {
            "enabled": True,
            "apply_to": ["demo_strategy"],
            "industry": {
                "enabled": True,
                "mode": mode,
                "max_names_per_industry": 2,
                "max_industry_weight": 0.35,
                "unknown_industry_policy": unknown_policy,
            },
        }
    }


def test_audit_does_not_change_returns_or_weights() -> None:
    output = _sample_output()
    result = apply_strategy_constraints(
        output,
        strategy_name="demo_strategy",
        panel_scope="portfolio",
        strategy_cfg=_cfg("audit"),
        panel=pd.DataFrame(),
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
    )

    pd.testing.assert_series_equal(result.output.returns, output.returns)
    pd.testing.assert_series_equal(result.output.exposure, output.exposure)
    assert result.metrics["constraint_status"] == "audited"
    assert result.metrics["industry_constraint_violation_days"] == 3


def test_enforce_limits_names_per_industry() -> None:
    result = apply_strategy_constraints(
        _sample_output(),
        strategy_name="demo_strategy",
        panel_scope="portfolio",
        strategy_cfg=_cfg("enforce"),
        panel=pd.DataFrame(),
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
    )

    signal = result.output.signal_frame
    target = signal[signal["weight_unshifted"] > 0]
    counts = target.groupby(["date", "industry"])["symbol"].nunique()
    assert int(counts.max()) <= 2
    assert result.metrics["constraint_status"] == "enforced"


def test_enforce_limits_industry_weight_share() -> None:
    result = apply_strategy_constraints(
        _sample_output(),
        strategy_name="demo_strategy",
        panel_scope="portfolio",
        strategy_cfg=_cfg("enforce"),
        panel=pd.DataFrame(),
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
    )

    signal = result.output.signal_frame
    target = signal[signal["weight_unshifted"] > 0].copy()
    grouped = target.groupby(["date", "industry"])["weight_unshifted"].sum()
    totals = target.groupby("date")["weight_unshifted"].sum()
    shares = grouped.div(totals, level="date")
    assert float(shares.max()) <= 0.3500001


def test_unknown_industry_reject_sets_weight_to_zero() -> None:
    output = _sample_output()
    signal = output.signal_frame.copy()
    signal.loc[signal["symbol"] == "AAA", "industry"] = ""
    output = StrategyOutput(output.returns, output.exposure, signal, {})

    result = apply_strategy_constraints(
        output,
        strategy_name="demo_strategy",
        panel_scope="portfolio",
        strategy_cfg=_cfg("enforce", unknown_policy="reject"),
        panel=pd.DataFrame(),
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
    )

    constrained = result.output.signal_frame
    assert float(constrained.loc[constrained["symbol"] == "AAA", "weight_unshifted"].abs().sum()) == 0.0


def test_signal_trace_summary_reports_target_and_live_holdings() -> None:
    output = _sample_output()
    summary = _signal_trace_summary(output)
    assert summary["target_days"] == 3
    assert summary["live_days"] == 3
    assert summary["avg_target_holdings"] == 5.0
    assert summary["avg_live_holdings"] == 5.0
    assert summary["first_target_date"] == "2024-01-02"
    assert summary["first_target_symbols"][:3] == ["AAA", "BBB", "CCC"]
