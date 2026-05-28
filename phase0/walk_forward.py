from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from phase0.env import prepare_imports

prepare_imports()

from backend.markets.cn import CNMarketSource  # noqa: E402
from backend.markets.hk import HKMarketSource  # noqa: E402


@dataclass
class FoldResult:
    fold: int
    train_start: str
    train_end: str
    valid_start: str
    valid_end: str
    annualized_return: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    turnover_annual: float
    trades: int
    passed_min_samples: bool
    selected_params: str = ""


def _annualized_return(r: pd.Series) -> float:
    if r.empty:
        return 0.0
    cum = float((1.0 + r).prod() - 1.0)
    yrs = max(len(r) / 252.0, 1 / 252.0)
    return float((1 + cum) ** (1 / yrs) - 1)


def _sharpe(r: pd.Series) -> float:
    if len(r) < 2:
        return 0.0
    std = float(r.std(ddof=1))
    if std == 0:
        return 0.0
    return float((r.mean() / std) * np.sqrt(252))


def _max_drawdown(r: pd.Series) -> float:
    if r.empty:
        return 0.0
    eq = (1 + r).cumprod()
    peak = eq.cummax()
    dd = (eq / peak) - 1
    return float(dd.min())


def _calc_metrics(returns: pd.Series, signals: pd.Series) -> dict[str, float]:
    ann = _annualized_return(returns)
    shp = _sharpe(returns)
    mdd = _max_drawdown(returns)

    realized = returns[signals != 0]
    win_rate = float((realized > 0).mean()) if len(realized) else 0.0
    turnover = float(signals.diff().abs().fillna(0).sum()) * (252.0 / max(len(signals), 1))
    return {
        "annualized_return": ann,
        "sharpe": shp,
        "max_drawdown": mdd,
        "win_rate": win_rate,
        "turnover_annual": turnover,
        "trades": int((signals.diff().abs() > 0).sum()),
    }


def _load_cn_daily(symbol: str, years: int) -> pd.DataFrame:
    src = CNMarketSource()
    end = date.today()
    start = end - timedelta(days=365 * years + 30)
    df = src.get_daily_data(symbol, start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), adjust="qfq")
    return df


def _load_hk_daily(symbol: str, years: int) -> pd.DataFrame:
    src = HKMarketSource()
    end = date.today()
    start = end - timedelta(days=365 * years + 30)
    df = src.get_daily_data(symbol, start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), adjust="qfq")
    return df


def _load_symbol(symbol: str, years: int) -> pd.DataFrame:
    if symbol.startswith("HK."):
        df = _load_hk_daily(symbol, years)
    else:
        df = _load_cn_daily(symbol, years)
    if df.empty:
        return df
    out = df[["date", "close"]].copy()
    out["date"] = pd.to_datetime(out["date"])
    out["ret"] = out["close"].pct_change().fillna(0.0)
    for window in [3, 5, 10, 20, 60]:
        out[f"mom{window}"] = out["close"].pct_change(window)
        out[f"ma{window}"] = out["close"].rolling(window).mean()
    out["vol20"] = out["ret"].rolling(20).std() * np.sqrt(252)
    out = out.dropna().reset_index(drop=True)
    return out


def _apply_strategy_v2(
    df: pd.DataFrame,
    *,
    mom_window: int,
    mom_threshold: float,
    trend_window: int,
    vol_threshold: float,
    target_vol: float,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
) -> tuple[pd.Series, pd.Series]:
    mom_col = f"mom{mom_window}"
    trend_col = f"ma{trend_window}"
    raw_signal = (
        (df[mom_col] > mom_threshold)
        & (df["close"] > df[trend_col])
        & (df["vol20"] <= vol_threshold)
    ).astype(float)

    exposure = np.minimum(1.0, target_vol / df["vol20"].replace(0, np.nan)).fillna(0.0)
    signal = (raw_signal * exposure).shift(1).fillna(0.0)
    trade_size = signal.diff().abs().fillna(signal.abs())
    costs = trade_size * (slippage + commission)
    sell_size = (signal.shift(1).fillna(0.0) - signal).clip(lower=0)
    costs += sell_size * stamp_duty_sell
    returns = signal * df["ret"] - costs
    return returns, signal


def _select_params(
    train: pd.DataFrame,
    strategy_cfg: dict[str, Any],
    *,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
) -> dict[str, Any]:
    best: dict[str, Any] | None = None
    min_trades = int(strategy_cfg.get("train_min_trades", 5))
    target_vol = float(strategy_cfg.get("target_vol", 0.18))
    vol_window = int(strategy_cfg.get("vol_window", 20))
    vol_col = f"vol{vol_window}"
    if vol_col not in train.columns:
        vol_col = "vol20"

    for mom_window in strategy_cfg.get("mom_windows", [5]):
        mom_col = f"mom{mom_window}"
        if mom_col not in train.columns:
            continue
        for mom_q in strategy_cfg.get("mom_quantiles", [0.5]):
            mom_threshold = float(train[mom_col].quantile(float(mom_q)))
            for trend_window in strategy_cfg.get("trend_windows", [20]):
                trend_col = f"ma{trend_window}"
                if trend_col not in train.columns:
                    continue
                for vol_q in strategy_cfg.get("vol_quantiles", [0.75]):
                    vol_threshold = float(train[vol_col].quantile(float(vol_q)))
                    returns, signal = _apply_strategy_v2(
                        train,
                        mom_window=int(mom_window),
                        mom_threshold=mom_threshold,
                        trend_window=int(trend_window),
                        vol_threshold=vol_threshold,
                        target_vol=target_vol,
                        slippage=slippage,
                        commission=commission,
                        stamp_duty_sell=stamp_duty_sell,
                    )
                    metric = _calc_metrics(returns, signal)
                    if metric["trades"] < min_trades:
                        continue
                    score = metric["sharpe"] + max(metric["max_drawdown"], -1.0) * 0.5
                    candidate = {
                        "mom_window": int(mom_window),
                        "mom_quantile": float(mom_q),
                        "mom_threshold": mom_threshold,
                        "trend_window": int(trend_window),
                        "vol_quantile": float(vol_q),
                        "vol_threshold": vol_threshold,
                        "target_vol": target_vol,
                        "train_score": float(score),
                        "train_sharpe": float(metric["sharpe"]),
                        "train_trades": int(metric["trades"]),
                    }
                    if best is None or candidate["train_score"] > best["train_score"]:
                        best = candidate

    if best is None:
        best = {
            "mom_window": 5,
            "mom_quantile": 0.5,
            "mom_threshold": float(train["mom5"].median()),
            "trend_window": 20,
            "vol_quantile": 0.75,
            "vol_threshold": float(train["vol20"].quantile(0.75)),
            "target_vol": target_vol,
            "train_score": 0.0,
            "train_sharpe": 0.0,
            "train_trades": 0,
        }
    return best


def _format_params(params: dict[str, Any]) -> str:
    return (
        f"mom{params['mom_window']}@q{params['mom_quantile']},"
        f"ma{params['trend_window']},"
        f"vol@q{params['vol_quantile']},"
        f"target_vol={params['target_vol']}"
    )


def _load_symbol_map(symbols: list[str], years: int) -> dict[str, pd.DataFrame]:
    data: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        df = _load_symbol(sym, years=years)
        if not df.empty:
            data[sym] = df
    return data


def _align_symbol_map(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = []
    for sym, df in data.items():
        d = df.copy()
        d["symbol"] = sym
        frames.append(d)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)


def _apply_portfolio_strategy(
    panel: pd.DataFrame,
    *,
    mom_window: int,
    mom_threshold: float,
    trend_window: int,
    vol_threshold: float,
    target_vol: float,
    top_n: int,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
) -> tuple[pd.Series, pd.Series]:
    if panel.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)

    d = panel.copy()
    mom_col = f"mom{mom_window}"
    trend_col = f"ma{trend_window}"
    eligible = (
        (d[mom_col] > mom_threshold)
        & (d["close"] > d[trend_col])
        & (d["vol20"] <= vol_threshold)
    )
    d["rank_score"] = d[mom_col].where(eligible, np.nan)
    d["rank"] = d.groupby("date")["rank_score"].rank(method="first", ascending=False)
    d["selected"] = ((d["rank"] <= top_n) & d["rank_score"].notna()).astype(float)
    daily_count = d.groupby("date")["selected"].transform("sum").replace(0, np.nan)
    d["raw_weight"] = (d["selected"] / daily_count).fillna(0.0)
    vol_scale = np.minimum(1.0, target_vol / d["vol20"].replace(0, np.nan)).fillna(0.0)
    d["weight"] = d["raw_weight"] * vol_scale
    d["weight"] = d.groupby("symbol")["weight"].shift(1).fillna(0.0)
    d["position_ret"] = d["weight"] * d["ret"]

    weights = d.pivot(index="date", columns="symbol", values="weight").fillna(0.0)
    turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
    sells = weights.diff().clip(upper=0).abs().sum(axis=1).fillna(0.0)
    gross = d.groupby("date")["position_ret"].sum()
    costs = turnover * (slippage + commission) + sells * stamp_duty_sell
    returns = gross.sub(costs, fill_value=0.0)
    exposure = weights.sum(axis=1)
    return returns, exposure


def _select_portfolio_params(
    train: pd.DataFrame,
    strategy_cfg: dict[str, Any],
    *,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
) -> dict[str, Any]:
    best: dict[str, Any] | None = None
    min_trades = int(strategy_cfg.get("train_min_trades", 5))
    target_vol = float(strategy_cfg.get("target_vol", 0.18))
    top_n = int(strategy_cfg.get("top_n", 2))

    for mom_window in strategy_cfg.get("mom_windows", [5]):
        mom_col = f"mom{mom_window}"
        if mom_col not in train.columns:
            continue
        for mom_q in strategy_cfg.get("mom_quantiles", [0.5]):
            mom_threshold = float(train[mom_col].quantile(float(mom_q)))
            for trend_window in strategy_cfg.get("trend_windows", [20]):
                trend_col = f"ma{trend_window}"
                if trend_col not in train.columns:
                    continue
                for vol_q in strategy_cfg.get("vol_quantiles", [0.75]):
                    vol_threshold = float(train["vol20"].quantile(float(vol_q)))
                    returns, exposure = _apply_portfolio_strategy(
                        train,
                        mom_window=int(mom_window),
                        mom_threshold=mom_threshold,
                        trend_window=int(trend_window),
                        vol_threshold=vol_threshold,
                        target_vol=target_vol,
                        top_n=top_n,
                        slippage=slippage,
                        commission=commission,
                        stamp_duty_sell=stamp_duty_sell,
                    )
                    metric = _calc_metrics(returns, exposure)
                    if metric["trades"] < min_trades:
                        continue
                    score = metric["sharpe"] + max(metric["max_drawdown"], -1.0) * 0.5
                    candidate = {
                        "mom_window": int(mom_window),
                        "mom_quantile": float(mom_q),
                        "mom_threshold": mom_threshold,
                        "trend_window": int(trend_window),
                        "vol_quantile": float(vol_q),
                        "vol_threshold": vol_threshold,
                        "target_vol": target_vol,
                        "top_n": top_n,
                        "train_score": float(score),
                        "train_sharpe": float(metric["sharpe"]),
                        "train_trades": int(metric["trades"]),
                    }
                    if best is None or candidate["train_score"] > best["train_score"]:
                        best = candidate

    if best is None:
        best = {
            "mom_window": 5,
            "mom_quantile": 0.5,
            "mom_threshold": float(train["mom5"].median()),
            "trend_window": 20,
            "vol_quantile": 0.75,
            "vol_threshold": float(train["vol20"].quantile(0.75)),
            "target_vol": target_vol,
            "top_n": top_n,
            "train_score": 0.0,
            "train_sharpe": 0.0,
            "train_trades": 0,
        }
    return best


def _format_portfolio_params(params: dict[str, Any]) -> str:
    return _format_params(params) + f",top_n={params.get('top_n', '')}"


def _run_legacy_momentum(
    symbol: str,
    years: int,
    train_years: int,
    validate_years: int,
    min_samples: int,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
) -> list[dict[str, Any]]:
    df = _load_symbol(symbol, years=years)
    if df.empty or len(df) < min_samples:
        return []

    fold_days_train = train_years * 252
    fold_days_valid = validate_years * 252
    rows: list[dict[str, Any]] = []
    fold_idx = 0
    start = 0
    while True:
        train_end = start + fold_days_train
        valid_end = train_end + fold_days_valid
        if valid_end > len(df):
            break
        train = df.iloc[start:train_end].copy()
        valid = df.iloc[train_end:valid_end].copy()
        if len(train) < min_samples or len(valid) < min_samples // 2:
            break

        threshold = float(train["mom5"].median())
        valid["signal"] = (valid["mom5"] > threshold).astype(float).shift(1).fillna(0.0)
        trade_size = valid["signal"].diff().abs().fillna(valid["signal"].abs())
        costs = trade_size * (slippage + commission)
        sell_size = (valid["signal"].shift(1).fillna(0.0) - valid["signal"]).clip(lower=0)
        costs += sell_size * stamp_duty_sell
        returns = valid["signal"] * valid["ret"] - costs
        metric = _calc_metrics(returns, valid["signal"])
        fold_idx += 1
        rows.append(
            {
                "symbol": symbol,
                "fold": fold_idx,
                "train_start": str(train["date"].iloc[0].date()),
                "train_end": str(train["date"].iloc[-1].date()),
                "valid_start": str(valid["date"].iloc[0].date()),
                "valid_end": str(valid["date"].iloc[-1].date()),
                "annualized_return": metric["annualized_return"],
                "sharpe": metric["sharpe"],
                "max_drawdown": metric["max_drawdown"],
                "win_rate": metric["win_rate"],
                "turnover_annual": metric["turnover_annual"],
                "trades": metric["trades"],
                "passed_min_samples": True,
                "selected_params": "legacy_mom5_median",
                "candidate": "legacy_momentum",
            }
        )
        start += fold_days_valid
    return rows


def _run_portfolio(
    symbols: list[str],
    years: int,
    train_years: int,
    validate_years: int,
    min_samples: int,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
    strategy_cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    panel = _align_symbol_map(_load_symbol_map(symbols, years=years))
    if panel.empty:
        return []

    dates = sorted(panel["date"].dropna().unique())
    fold_days_train = train_years * 252
    fold_days_valid = validate_years * 252
    rows: list[dict[str, Any]] = []
    start = 0
    fold_idx = 0
    while True:
        train_end = start + fold_days_train
        valid_end = train_end + fold_days_valid
        if valid_end > len(dates):
            break
        train_dates = set(dates[start:train_end])
        valid_dates = set(dates[train_end:valid_end])
        train = panel[panel["date"].isin(train_dates)].copy()
        valid = panel[panel["date"].isin(valid_dates)].copy()
        if train["date"].nunique() < min_samples or valid["date"].nunique() < min_samples // 2:
            break

        params = _select_portfolio_params(
            train,
            strategy_cfg,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
        )
        returns, exposure = _apply_portfolio_strategy(
            valid,
            mom_window=int(params["mom_window"]),
            mom_threshold=float(params["mom_threshold"]),
            trend_window=int(params["trend_window"]),
            vol_threshold=float(params["vol_threshold"]),
            target_vol=float(params["target_vol"]),
            top_n=int(params.get("top_n", strategy_cfg.get("top_n", 2))),
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
        )
        metric = _calc_metrics(returns, exposure)
        fold_idx += 1
        rows.append(
            {
                "symbol": "PORTFOLIO",
                "fold": fold_idx,
                "train_start": str(pd.Timestamp(min(train_dates)).date()),
                "train_end": str(pd.Timestamp(max(train_dates)).date()),
                "valid_start": str(pd.Timestamp(min(valid_dates)).date()),
                "valid_end": str(pd.Timestamp(max(valid_dates)).date()),
                "annualized_return": metric["annualized_return"],
                "sharpe": metric["sharpe"],
                "max_drawdown": metric["max_drawdown"],
                "win_rate": metric["win_rate"],
                "turnover_annual": metric["turnover_annual"],
                "trades": metric["trades"],
                "passed_min_samples": True,
                "selected_params": _format_portfolio_params(params),
                "candidate": "portfolio_v2",
            }
        )
        start += fold_days_valid
    return rows


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, float]:
    df = pd.DataFrame(rows)
    if df.empty:
        return {"fold_count": 0, "annualized_return_mean": 0.0, "sharpe_mean": 0.0, "max_drawdown_mean": 0.0}
    return {
        "fold_count": int(len(df)),
        "annualized_return_mean": float(df["annualized_return"].mean()),
        "sharpe_mean": float(df["sharpe"].mean()),
        "max_drawdown_mean": float(df["max_drawdown"].mean()),
        "win_rate_mean": float(df["win_rate"].mean()),
        "turnover_annual_mean": float(df["turnover_annual"].mean()),
    }


def _candidate_score(summary: dict[str, float]) -> float:
    return (
        float(summary.get("sharpe_mean", 0.0))
        + float(summary.get("annualized_return_mean", 0.0)) * 0.5
        + max(float(summary.get("max_drawdown_mean", 0.0)), -1.0) * 0.5
    )


def _run_compare(
    symbols: list[str],
    years: int,
    train_years: int,
    validate_years: int,
    min_samples: int,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
    strategy_cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: dict[str, list[dict[str, Any]]] = {}

    legacy_rows: list[dict[str, Any]] = []
    filtered_rows: list[dict[str, Any]] = []
    for sym in symbols:
        legacy_rows.extend(
            _run_legacy_momentum(
                symbol=sym,
                years=years,
                train_years=train_years,
                validate_years=validate_years,
                min_samples=min_samples,
                slippage=slippage,
                commission=commission,
                stamp_duty_sell=stamp_duty_sell,
            )
        )
        for f in _run_single_symbol(
            symbol=sym,
            years=years,
            train_years=train_years,
            validate_years=validate_years,
            min_samples=min_samples,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
            strategy_cfg=strategy_cfg,
        ):
            filtered_rows.append(
                {
                    "symbol": sym,
                    "fold": f.fold,
                    "train_start": f.train_start,
                    "train_end": f.train_end,
                    "valid_start": f.valid_start,
                    "valid_end": f.valid_end,
                    "annualized_return": f.annualized_return,
                    "sharpe": f.sharpe,
                    "max_drawdown": f.max_drawdown,
                    "win_rate": f.win_rate,
                    "turnover_annual": f.turnover_annual,
                    "trades": f.trades,
                    "passed_min_samples": f.passed_min_samples,
                    "selected_params": f.selected_params,
                    "candidate": "filtered_single_v2",
                }
            )

    candidates["legacy_momentum"] = legacy_rows
    candidates["filtered_single_v2"] = filtered_rows
    candidates["portfolio_v2"] = _run_portfolio(
        symbols=symbols,
        years=years,
        train_years=train_years,
        validate_years=validate_years,
        min_samples=min_samples,
        slippage=slippage,
        commission=commission,
        stamp_duty_sell=stamp_duty_sell,
        strategy_cfg={**strategy_cfg, "mode": "portfolio"},
    )

    summaries = {name: _summarize_rows(rows) for name, rows in candidates.items()}
    best_name = max(candidates, key=lambda name: _candidate_score(summaries[name]))
    comparison = "; ".join(
        (
            f"{name}: score={_candidate_score(summary):.4f}, "
            f"ann={summary.get('annualized_return_mean', 0.0):.4f}, "
            f"sharpe={summary.get('sharpe_mean', 0.0):.4f}, "
            f"mdd={summary.get('max_drawdown_mean', 0.0):.4f}"
        )
        for name, summary in summaries.items()
    )
    selected = candidates[best_name]
    for row in selected:
        row["candidate_summary"] = comparison
    return selected


def _run_single_symbol(
    symbol: str,
    years: int,
    train_years: int,
    validate_years: int,
    min_samples: int,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
    strategy_cfg: dict[str, Any],
) -> list[FoldResult]:
    df = _load_symbol(symbol, years=years)
    if df.empty or len(df) < min_samples:
        return []

    fold_days_train = train_years * 252
    fold_days_valid = validate_years * 252
    folds: list[FoldResult] = []
    fold_idx = 0
    start = 0
    while True:
        train_end = start + fold_days_train
        valid_end = train_end + fold_days_valid
        if valid_end > len(df):
            break

        train = df.iloc[start:train_end].copy()
        valid = df.iloc[train_end:valid_end].copy()
        passed = len(train) >= min_samples and len(valid) >= min_samples // 2
        if not passed:
            break

        params = _select_params(
            train,
            strategy_cfg,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
        )
        valid["strategy_ret"], valid["signal"] = _apply_strategy_v2(
            valid,
            mom_window=int(params["mom_window"]),
            mom_threshold=float(params["mom_threshold"]),
            trend_window=int(params["trend_window"]),
            vol_threshold=float(params["vol_threshold"]),
            target_vol=float(params["target_vol"]),
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
        )

        metric = _calc_metrics(valid["strategy_ret"], valid["signal"])
        fold_idx += 1
        folds.append(
            FoldResult(
                fold=fold_idx,
                train_start=str(train["date"].iloc[0].date()),
                train_end=str(train["date"].iloc[-1].date()),
                valid_start=str(valid["date"].iloc[0].date()),
                valid_end=str(valid["date"].iloc[-1].date()),
                annualized_return=metric["annualized_return"],
                sharpe=metric["sharpe"],
                max_drawdown=metric["max_drawdown"],
                win_rate=metric["win_rate"],
                turnover_annual=metric["turnover_annual"],
                trades=metric["trades"],
                passed_min_samples=passed,
                selected_params=_format_params(params),
            )
        )

        start += fold_days_valid
    return folds


def run_walk_forward(config: dict[str, Any]) -> dict[str, Any]:
    years = int(config["years"])
    wcfg = config["walk_forward"]
    symbols = config["symbols"]
    strategy_cfg = wcfg.get("strategy_v2", {})

    if strategy_cfg.get("mode") == "compare":
        all_rows = _run_compare(
            symbols=symbols,
            years=years,
            train_years=int(wcfg["train_years"]),
            validate_years=int(wcfg["validate_years"]),
            min_samples=int(wcfg["min_samples"]),
            slippage=float(wcfg["slippage"]),
            commission=float(wcfg["commission"]),
            stamp_duty_sell=float(wcfg["stamp_duty_sell"]),
            strategy_cfg=strategy_cfg,
        )
    elif strategy_cfg.get("mode") == "portfolio":
        all_rows = _run_portfolio(
            symbols=symbols,
            years=years,
            train_years=int(wcfg["train_years"]),
            validate_years=int(wcfg["validate_years"]),
            min_samples=int(wcfg["min_samples"]),
            slippage=float(wcfg["slippage"]),
            commission=float(wcfg["commission"]),
            stamp_duty_sell=float(wcfg["stamp_duty_sell"]),
            strategy_cfg=strategy_cfg,
        )
    else:
        all_rows: list[dict[str, Any]] = []
        for sym in symbols:
            folds = _run_single_symbol(
                symbol=sym,
                years=years,
                train_years=int(wcfg["train_years"]),
                validate_years=int(wcfg["validate_years"]),
                min_samples=int(wcfg["min_samples"]),
                slippage=float(wcfg["slippage"]),
                commission=float(wcfg["commission"]),
                stamp_duty_sell=float(wcfg["stamp_duty_sell"]),
                strategy_cfg=strategy_cfg,
            )
            for f in folds:
                all_rows.append(
                    {
                        "symbol": sym,
                        "fold": f.fold,
                        "train_start": f.train_start,
                        "train_end": f.train_end,
                        "valid_start": f.valid_start,
                        "valid_end": f.valid_end,
                        "annualized_return": f.annualized_return,
                        "sharpe": f.sharpe,
                        "max_drawdown": f.max_drawdown,
                        "win_rate": f.win_rate,
                        "turnover_annual": f.turnover_annual,
                        "trades": f.trades,
                        "passed_min_samples": f.passed_min_samples,
                        "selected_params": f.selected_params,
                        "candidate": "filtered_single_v2",
                    }
                )

    folds_df = pd.DataFrame(all_rows)
    if folds_df.empty:
        return {"folds": folds_df, "summary": {"status": "failed", "reason": "no valid folds"}}

    summary = {
        "status": "ok",
        "fold_count": int(len(folds_df)),
        "symbol_count": int(folds_df["symbol"].nunique()),
        "annualized_return_mean": float(folds_df["annualized_return"].mean()),
        "sharpe_mean": float(folds_df["sharpe"].mean()),
        "max_drawdown_mean": float(folds_df["max_drawdown"].mean()),
        "win_rate_mean": float(folds_df["win_rate"].mean()),
        "turnover_annual_mean": float(folds_df["turnover_annual"].mean()),
    }
    if "candidate" in folds_df.columns:
        summary["selected_candidate"] = str(folds_df["candidate"].iloc[0])
    if "candidate_summary" in folds_df.columns:
        summary["candidate_comparison"] = str(folds_df["candidate_summary"].iloc[0])

    # Out-of-sample proxy: last 20% folds as recent hold-out segment
    cutoff = max(1, int(len(folds_df) * 0.2))
    oos = folds_df.sort_values(["valid_end"]).tail(cutoff)
    train_like = folds_df.sort_values(["valid_end"]).head(len(folds_df) - cutoff)
    summary["oos_fold_count"] = int(len(oos))
    summary["oos_annualized_return_mean"] = float(oos["annualized_return"].mean())
    summary["oos_sharpe_mean"] = float(oos["sharpe"].mean())
    if len(train_like) > 0 and np.isfinite(train_like["annualized_return"].mean()):
        base = float(train_like["annualized_return"].mean())
        oosv = float(oos["annualized_return"].mean())
        if base != 0:
            summary["oos_return_decay_ratio"] = float((base - oosv) / abs(base))
        else:
            summary["oos_return_decay_ratio"] = 0.0
    else:
        summary["oos_return_decay_ratio"] = 0.0

    return {"folds": folds_df, "summary": summary}


def save_walk_forward_csv(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8")
