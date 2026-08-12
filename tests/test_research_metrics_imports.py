from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import quant.walk_forward as legacy_walk_forward
from quant.research import metrics
from quant.research.metrics import annualized_return, calc_metrics, max_drawdown, sharpe


def test_research_metrics_match_walk_forward_legacy_helpers() -> None:
    returns = pd.Series([0.01, -0.02, 0.03, 0.00, 0.02])
    signals = pd.Series([0, 1, 1, -1, 0])

    assert annualized_return(returns) == legacy_walk_forward._annualized_return(returns)
    assert sharpe(returns) == legacy_walk_forward._sharpe(returns)
    assert max_drawdown(returns) == legacy_walk_forward._max_drawdown(returns)
    assert calc_metrics(returns, signals) == legacy_walk_forward._calc_metrics(returns, signals)


def test_research_metrics_handle_empty_and_short_returns() -> None:
    empty = pd.Series(dtype=float)
    one = pd.Series([0.01])

    assert annualized_return(empty) == 0.0
    assert sharpe(empty) == 0.0
    assert sharpe(one) == 0.0
    assert max_drawdown(empty) == 0.0
    assert calc_metrics(empty, empty)["turnover_annual"] == 0.0


def test_research_metrics_formula_examples() -> None:
    returns = pd.Series([0.01, -0.02, 0.03])
    expected_cum = float((1.0 + returns).prod() - 1.0)
    expected_years = len(returns) / 252.0
    expected_ann = float((1.0 + expected_cum) ** (1.0 / expected_years) - 1.0)
    expected_sharpe = float((returns.mean() / returns.std(ddof=1)) * np.sqrt(252))
    equity = (1.0 + returns).cumprod()
    expected_mdd = float((equity / equity.cummax() - 1.0).min())

    assert annualized_return(returns) == expected_ann
    assert sharpe(returns) == expected_sharpe
    assert max_drawdown(returns) == expected_mdd


def test_strategy_modules_use_research_metrics_instead_of_walk_forward_private_helper() -> None:
    root = Path(__file__).resolve().parents[1]
    offenders: list[str] = []
    for path in (root / "phase0" / "strategies").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "from quant.walk_forward import _calc_metrics" in text:
            offenders.append(path.name)

    assert offenders == []
