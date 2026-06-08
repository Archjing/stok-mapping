from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from phase0.accounts import SimulatedAccountConfig, run_signal_account_execution
from phase0.local_history import configure_local_history, load_snapshot_from_local_history_as_of
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
    assert float(grouped.max()) <= 0.3500001


def test_enforce_reuses_constrained_weights_when_original_target_is_unchanged() -> None:
    output = _sample_output()
    signal = output.signal_frame.copy()
    score_by_date_symbol = {
        ("2024-01-02", "AAA"): 0.90,
        ("2024-01-02", "BBB"): 0.80,
        ("2024-01-02", "CCC"): 0.70,
        ("2024-01-03", "AAA"): 0.10,
        ("2024-01-03", "BBB"): 0.20,
        ("2024-01-03", "CCC"): 0.95,
        ("2024-01-04", "AAA"): 0.95,
        ("2024-01-04", "BBB"): 0.10,
        ("2024-01-04", "CCC"): 0.20,
    }
    signal["score"] = [
        score_by_date_symbol.get((str(pd.Timestamp(row["date"]).date()), str(row["symbol"])), row["score"])
        for _, row in signal.iterrows()
    ]
    output = StrategyOutput(output.returns, output.exposure, signal, {})

    result = apply_strategy_constraints(
        output,
        strategy_name="demo_strategy",
        panel_scope="portfolio",
        strategy_cfg=_cfg("enforce"),
        panel=pd.DataFrame(),
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
    )

    constrained = result.output.signal_frame.sort_values(["date", "symbol"])
    weights = constrained.pivot(index="date", columns="symbol", values="weight_unshifted").fillna(0.0)
    assert weights.nunique().max() == 1


def test_constraints_merge_industry_from_panel_when_signal_omits_it() -> None:
    output = _sample_output()
    signal = output.signal_frame.drop(columns=["industry"])
    output = StrategyOutput(output.returns, output.exposure, signal, {})
    panel = _sample_output().signal_frame[["date", "symbol", "industry"]].copy()

    result = apply_strategy_constraints(
        output,
        strategy_name="demo_strategy",
        panel_scope="portfolio",
        strategy_cfg=_cfg("enforce"),
        panel=panel,
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
    )

    assert "industry" in result.output.signal_frame.columns
    assert result.metrics["constraint_status"] == "enforced"
    assert result.metrics["avg_industries"] > 1.0
    assert result.metrics["unknown_industry_weight_avg"] == 0.0


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


def test_point_in_time_snapshot_preserves_static_name_and_industry(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE market_daily_bars (
                market TEXT,
                symbol TEXT,
                date TEXT,
                close REAL,
                amount REAL,
                volume REAL,
                turnover_rate REAL,
                adjust_type TEXT
            );
            CREATE TABLE market_stocks (
                market TEXT,
                symbol TEXT,
                name TEXT,
                industry TEXT,
                list_date TEXT,
                delist_date TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO market_stocks VALUES (?, ?, ?, ?, ?, ?)",
            ("CN", "SH.600519", "贵州茅台", "白酒", "2001-08-27", None),
        )
        rows = [
            ("CN", "SH.600519", f"2024-01-{day:02d}", 100.0 + day, 100000000.0, 1000000.0, 1.0, "qfq")
            for day in range(1, 31)
        ]
        conn.executemany("INSERT INTO market_daily_bars VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)

    configure_local_history(
        {
            "enabled": True,
            "path": str(db_path),
            "market": "CN",
            "adjust_type": "qfq",
            "daily_table": "market_daily_bars",
            "meta_table": "market_stocks",
            "daily_basic_table": "market_daily_basic",
            "financial_table": "market_financial_factors",
            "use_for_universe_fallback": True,
        }
    )

    snapshot = load_snapshot_from_local_history_as_of("2024-01-31", days=30)

    assert snapshot.loc[0, "name"] == "贵州茅台"
    assert snapshot.loc[0, "industry"] == "白酒"
    assert snapshot.attrs["industry_metadata_source"] == "market_stocks_current_static"


def test_signal_account_execution_uses_next_day_target_and_lot_size() -> None:
    signal = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "AAA",
                "name": "Alpha",
                "weight_unshifted": 0.5,
                "open": 10.0,
                "high": 10.2,
                "low": 9.8,
                "close": 10.0,
                "volume": 1000000,
                "amount": 10000000.0,
            },
            {
                "date": "2024-01-03",
                "symbol": "AAA",
                "name": "Alpha",
                "weight_unshifted": 0.5,
                "open": 10.0,
                "high": 11.2,
                "low": 9.9,
                "close": 11.0,
                "volume": 1000000,
                "amount": 11000000.0,
            },
        ]
    )
    account = SimulatedAccountConfig(
        account_id="test",
        name="test",
        initial_cash=100000.0,
        ledger_path=Path("."),
        database_path=Path("."),
        lot_size=100,
        execution_price_mode="next_open",
        max_participation_rate=0.0,
        enable_limit_check=False,
        enable_suspension_check=False,
    )

    result = run_signal_account_execution(signal_frame=signal, account=account)

    assert result.metrics["account_execution_enabled"] is True
    assert result.metrics["account_executed_order_count"] == 1
    assert result.trades.iloc[0]["date"] == "2024-01-03"
    assert result.trades.iloc[0]["shares"] % 100 == 0
    assert result.daily_assets.iloc[0]["stock_asset"] == 0.0
