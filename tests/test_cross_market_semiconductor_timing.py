from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from quant.execution.accounts import SimulatedAccountConfig
from quant.strategies.base import StrategyOutput
from quant.strategies.cross_market_semiconductor_timing import (
    CrossMarketSemiconductorTimingStrategy,
    map_us_features_to_next_cn_trading_day,
)
from quant import walk_forward


def _load_backtest_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "backtest_sox_512480.py"
    spec = importlib.util.spec_from_file_location("backtest_sox_512480_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_us_close_maps_to_first_strictly_later_cn_trading_day() -> None:
    us = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-06-07", "2024-06-10"]),  # Friday, Monday
            "sox_ret": [0.011, 0.012],
            "vix_close": [18.0, 18.0],
        }
    )
    cn_sessions = pd.to_datetime(["2024-06-10", "2024-06-11"])

    actual = map_us_features_to_next_cn_trading_day(us, cn_sessions)

    assert actual["date"].tolist() == [pd.Timestamp("2024-06-10"), pd.Timestamp("2024-06-11")]
    assert actual["sox_ret"].tolist() == [0.011, 0.012]


def test_account_execution_params_accepts_a_whitelisted_target_etf() -> None:
    params = CrossMarketSemiconductorTimingStrategy().account_execution_params(
        {
            "cross_market_semiconductor_timing": {
                "target_symbol": "SH.512760",
            }
        }
    )

    assert params["target_symbol"] == "SH.512760"
    assert CrossMarketSemiconductorTimingStrategy().build_metadata(params)[
        "account_execution_policy"
    ]["target_symbol"] == "SH.512760"


def test_account_execution_params_rejects_etf_outside_semiconductor_universe() -> None:
    with pytest.raises(ValueError, match="not an allowed semiconductor timing ETF"):
        CrossMarketSemiconductorTimingStrategy().account_execution_params(
            {
                "cross_market_semiconductor_timing": {
                    "target_symbol": "SH.510300",
                }
            }
        )


def test_holiday_us_returns_are_compounded_into_one_cn_signal() -> None:
    us = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-10-01", "2024-10-02", "2024-10-03"]),
            "sox_ret": [0.01, -0.02, 0.03],
            "vix_close": [18.0, 18.5, 17.5],
        }
    )
    cn_sessions = pd.to_datetime(["2024-09-30", "2024-10-08"])

    actual = map_us_features_to_next_cn_trading_day(us, cn_sessions)

    assert len(actual) == 1
    assert actual.iloc[0]["date"] == pd.Timestamp("2024-10-08")
    assert actual.iloc[0]["signal_us_date"] == pd.Timestamp("2024-10-03")
    assert actual.iloc[0]["sox_ret"] == pytest.approx((1.01 * 0.98 * 1.03) - 1.0)
    assert actual.iloc[0]["vix_close"] == 17.5


def test_prepare_panel_does_not_drop_executable_rows_for_unused_lookbacks(monkeypatch) -> None:
    etf = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-06-10", "2024-06-11", "2024-06-12"]),
            "symbol": ["SH.512480"] * 3,
            "open": [1.0, 1.0, 1.0],
            "high": [1.0, 1.0, 1.0],
            "low": [1.0, 1.0, 1.0],
            "close": [1.0, 1.0, 1.0],
            "volume": [1.0, 1.0, 1.0],
            "amount": [1.0, 1.0, 1.0],
            "ret": [float("nan"), 0.0, 0.0],
        }
    )
    us = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-06-10", "2024-06-11", "2024-06-12"]),
            "signal_us_date": pd.to_datetime(["2024-06-07", "2024-06-10", "2024-06-11"]),
            "sox_ret": [0.02, 0.0, 0.0],
            "vix_close": [18.0, 25.0, 25.0],
        }
    )
    monkeypatch.setattr(CrossMarketSemiconductorTimingStrategy, "_load_etf_daily", staticmethod(lambda **_kwargs: etf))
    monkeypatch.setattr(CrossMarketSemiconductorTimingStrategy, "_load_us_features", staticmethod(lambda **_kwargs: us))

    panel = CrossMarketSemiconductorTimingStrategy().prepare_panel(
        pd.DataFrame(),
        {"cross_market_semiconductor_timing": {"as_of_date": "2024-06-12"}},
    )

    assert panel["date"].tolist() == list(etf["date"])


def test_prepare_panel_keeps_cn_session_without_new_us_signal(monkeypatch) -> None:
    etf = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-06-10", "2024-06-11", "2024-06-12"]),
            "symbol": ["SH.512480"] * 3,
            "open": [1.0, 1.0, 1.0],
            "high": [1.0, 1.0, 1.0],
            "low": [1.0, 1.0, 1.0],
            "close": [1.0, 1.0, 1.0],
            "volume": [1.0, 1.0, 1.0],
            "amount": [1.0, 1.0, 1.0],
            "ret": [float("nan"), 0.0, 0.0],
        }
    )
    us = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-06-10", "2024-06-12"]),
            "signal_us_date": pd.to_datetime(["2024-06-07", "2024-06-11"]),
            "sox_ret": [0.02, 0.01],
            "vix_close": [18.0, 18.0],
        }
    )
    monkeypatch.setattr(CrossMarketSemiconductorTimingStrategy, "_load_etf_daily", staticmethod(lambda **_kwargs: etf))
    monkeypatch.setattr(CrossMarketSemiconductorTimingStrategy, "_load_us_features", staticmethod(lambda **_kwargs: us))

    panel = CrossMarketSemiconductorTimingStrategy().prepare_panel(
        pd.DataFrame(),
        {"cross_market_semiconductor_timing": {"as_of_date": "2024-06-12"}},
    )

    assert panel["date"].tolist() == list(etf["date"])
    missing_us_session = panel.loc[panel["date"] == pd.Timestamp("2024-06-11")].iloc[0]
    assert missing_us_session["sox_ret"] == 0.0
    assert missing_us_session["vix_close"] == 999.0


def test_backtest_exits_on_fixed_next_cn_session_and_does_not_reenter_at_exit_open(monkeypatch) -> None:
    module = _load_backtest_module()
    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(["2021-05-13", "2021-05-14", "2021-05-17"]),
            "open": [1.0, 1.0, 1.0],
            "high": [1.1, 1.1, 1.1],
            "low": [0.9, 0.9, 0.9],
            "close": [1.0, 1.0, 1.0],
        }
    )
    us = pd.DataFrame(
        {
            "date": pd.to_datetime(["2021-05-13", "2021-05-14", "2021-05-17"]),
            "sox_ret": [0.02, 0.02, 0.0],
            "vix": [18.0, 18.0, 25.0],
        }
    )
    empty_intraday = pd.DataFrame(columns=["date", "open", "high", "low", "close"])
    monkeypatch.setattr(module, "load_etf_daily", lambda: daily)
    monkeypatch.setattr(module, "load_us", lambda _dates: us)
    monkeypatch.setattr(module, "load_etf_5min", lambda *_args: empty_intraday)

    result = module.run(use_limit=False)

    assert result["signals"] == 2
    assert result["trades"] == 1
    assert result["trade_log"][0]["entry_date"] == "2021-05-13"
    assert result["trade_log"][0]["exit_date"] == "2021-05-14"


def test_intraday_output_counts_the_t_plus_one_exit_day_as_exposed(monkeypatch) -> None:
    panel = pd.DataFrame(
        {
            "date": pd.to_datetime(["2021-05-13", "2021-05-14", "2021-05-17"]),
            "symbol": ["SH.512480"] * 3,
            "open": [1.0, 1.0, 1.0],
            "high": [1.1, 1.1, 1.1],
            "low": [0.9, 0.9, 0.9],
            "close": [1.0, 1.0, 1.0],
            "sox_ret": [0.02, 0.0, 0.0],
            "vix_close": [18.0, 25.0, 25.0],
            "ret": [0.0, 0.0, 0.0],
        }
    )
    intraday = pd.DataFrame(
        {
            "time": pd.to_datetime(["2021-05-13 14:55", "2021-05-14 14:55", "2021-05-17 14:55"]),
            "open": [1.0, 1.0, 1.0],
            "high": [1.0, 1.0, 1.0],
            "low": [1.0, 1.0, 1.0],
            "close": [1.0, 1.0, 1.0],
        }
    )
    monkeypatch.setattr(
        CrossMarketSemiconductorTimingStrategy,
        "_load_5min_bars",
        staticmethod(lambda *args, **kwargs: intraday),
    )

    output = CrossMarketSemiconductorTimingStrategy()._simulate_intraday(
        panel,
        {"sox_threshold": 0.005, "vix_threshold": 19.0, "position_size": 1.0},
        slippage=0.0001,
        commission=0.00025,
        stamp_duty_sell=0.0,
    )

    assert output.exposure.loc[pd.Timestamp("2021-05-13")] == 1.0
    assert output.exposure.loc[pd.Timestamp("2021-05-14")] == 1.0
    assert output.exposure.loc[pd.Timestamp("2021-05-17")] == 0.0


def test_admission_intraday_path_cancels_unfilled_weak_limit_without_open_fill(monkeypatch) -> None:
    panel = pd.DataFrame(
        {
            "date": pd.to_datetime(["2021-05-13", "2021-05-14"]),
            "symbol": ["SH.512480"] * 2,
            "open": [1.0, 1.0],
            "high": [1.02, 1.02],
            "low": [0.995, 0.995],
            "close": [1.0, 1.0],
            "sox_ret": [0.007, 0.0],
            "vix_close": [18.0, 25.0],
            "ret": [0.0, 0.0],
        }
    )
    intraday = pd.DataFrame(
        {
            "time": pd.to_datetime(["2021-05-13 09:35", "2021-05-13 14:55", "2021-05-14 14:55"]),
            "open": [1.0, 1.0, 1.0],
            "high": [1.01, 1.01, 1.01],
            "low": [0.995, 0.995, 0.995],
            "close": [1.0, 1.0, 1.0],
        }
    )
    monkeypatch.setattr(
        CrossMarketSemiconductorTimingStrategy,
        "_load_5min_bars",
        staticmethod(lambda *args, **kwargs: intraday),
    )

    output = CrossMarketSemiconductorTimingStrategy().apply(
        panel,
        {
            "sox_threshold": 0.005,
            "vix_threshold": 19.0,
            "position_size": 1.0,
            "strong_signal_threshold": 0.01,
            "limit_order_discount": 0.01,
            "trailing_stop_ratio": 0.98,
            "weak_unfilled_action": "cancel",
            "fallback_time": "14:55",
        },
        slippage=0.0001,
        commission=0.00025,
        stamp_duty_sell=0.0,
    )

    metrics = output.metadata["account_execution_metrics"]
    assert metrics["account_entry_count"] == 0
    assert metrics["account_unfilled_order_count"] == 1
    assert output.exposure.eq(0.0).all()
    assert output.returns.eq(0.0).all()


def test_intraday_strategy_is_routed_to_single_etf_account_execution(monkeypatch) -> None:
    account = SimulatedAccountConfig(
        account_id="test",
        name="test",
        initial_cash=100_000,
        ledger_path=Path("/dev/null"),
        database_path=Path("/dev/null"),
    )
    output = StrategyOutput(
        returns=pd.Series(dtype=float),
        exposure=pd.Series(dtype=float),
        signal_frame=pd.DataFrame(),
        metadata={"strategy_id": CrossMarketSemiconductorTimingStrategy.name},
    )
    monkeypatch.setattr(walk_forward, "run_signal_account_execution", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not call generic account execution")))
    monkeypatch.setattr(
        walk_forward,
        "run_single_etf_intraday_account_execution",
        lambda **_kwargs: type(
            "Result",
            (),
            {"metrics": {"account_execution_enabled": True, "account_execution_complete": True}},
        )(),
    )

    actual = walk_forward._account_execution_metrics(output, account, "portfolio")

    assert actual == {
        "account_execution_status": "enabled",
        "account_execution_enabled": True,
        "account_execution_complete": True,
    }
