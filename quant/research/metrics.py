from __future__ import annotations

import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 252.0


def annualized_return(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    cumulative_return = float((1.0 + returns).prod() - 1.0)
    years = max(len(returns) / TRADING_DAYS_PER_YEAR, 1 / TRADING_DAYS_PER_YEAR)
    return float((1.0 + cumulative_return) ** (1.0 / years) - 1.0)


def sharpe(returns: pd.Series) -> float:
    if len(returns) < 2:
        return 0.0
    std = float(returns.std(ddof=1))
    if std == 0:
        return 0.0
    return float((returns.mean() / std) * np.sqrt(TRADING_DAYS_PER_YEAR))


def max_drawdown(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    equity = (1.0 + returns).cumprod()
    peak = equity.cummax()
    drawdown = (equity / peak) - 1.0
    return float(drawdown.min())


def calc_metrics(returns: pd.Series, signals: pd.Series) -> dict[str, float]:
    ann = annualized_return(returns)
    shp = sharpe(returns)
    mdd = max_drawdown(returns)

    realized = returns[signals != 0]
    win_rate = float((realized > 0).mean()) if len(realized) else 0.0
    turnover = float(signals.diff().abs().fillna(0).sum()) * (TRADING_DAYS_PER_YEAR / max(len(signals), 1))
    return {
        "annualized_return": ann,
        "sharpe": shp,
        "max_drawdown": mdd,
        "win_rate": win_rate,
        "turnover_annual": turnover,
        "trades": int((signals.diff().abs() > 0).sum()),
    }
