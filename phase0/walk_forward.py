from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from phase0.data_sources import fetch_yf_daily
from phase0.env import prepare_imports
from phase0.local_history import configure_local_history, load_daily_from_local_history
from phase0.throttle import configure_akshare_throttle, fetch_with_akshare_retries
from phase0.universe import load_universe_symbols

prepare_imports()

from backend.markets.cn import CNMarketSource  # noqa: E402
from backend.markets.hk import HKMarketSource  # noqa: E402


MARKET_TICKERS = ["^NDX", "^SOX", "NVDA", "KWEB", "^VIX", "CNY=X"]


def _xmarket_enabled(strategy_cfg: dict[str, Any]) -> bool:
    return bool(strategy_cfg.get("cross_market", {}).get("enabled", False))


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
    df = fetch_with_akshare_retries(
        lambda: src.get_daily_data(symbol, start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), adjust="qfq")
    )
    if not df.empty:
        return df
    return load_daily_from_local_history(symbol, start, end)


def _load_hk_daily(symbol: str, years: int) -> pd.DataFrame:
    src = HKMarketSource()
    end = date.today()
    start = end - timedelta(days=365 * years + 30)
    df = fetch_with_akshare_retries(
        lambda: src.get_daily_data(symbol, start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), adjust="qfq")
    )
    return df


def _load_symbol(symbol: str, years: int) -> pd.DataFrame:
    return _load_symbol_cached(symbol, years).copy()


@lru_cache(maxsize=256)
def _load_symbol_cached(symbol: str, years: int) -> pd.DataFrame:
    if symbol.startswith("HK."):
        df = _load_hk_daily(symbol, years)
    else:
        df = _load_cn_daily(symbol, years)
    if df.empty:
        return df
    out = df[["date", "open", "close"]].copy()
    out["date"] = pd.to_datetime(out["date"])
    out["ret"] = out["close"].pct_change().fillna(0.0)
    out["oc_ret"] = (out["close"] / out["open"].replace(0, np.nan) - 1.0).fillna(0.0)
    for window in [3, 5, 10, 20, 60]:
        out[f"mom{window}"] = out["close"].pct_change(window)
        out[f"ma{window}"] = out["close"].rolling(window).mean()
    out["vol20"] = out["ret"].rolling(20).std() * np.sqrt(252)
    out = out.dropna().reset_index(drop=True)
    return out


def _load_cross_market_features(years: int, cfg: dict[str, Any]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for ticker in MARKET_TICKERS:
        df = fetch_yf_daily(ticker, years=years)
        if df.empty:
            continue
        d = df[["date", "close"]].copy()
        d["date"] = pd.to_datetime(d["date"])
        col = ticker.lower().replace("^", "").replace("=", "").replace("-", "_")
        d[f"{col}_ret"] = d["close"].pct_change()
        keep = ["date", f"{col}_ret"]
        if ticker == "^VIX":
            d["vix_close"] = d["close"]
            keep.append("vix_close")
        frames.append(d[keep])

    if not frames:
        return pd.DataFrame(columns=["date", "xmarket_score", "xmarket_magnitude_score", "risk_off", "risk_scale"])

    out = frames[0]
    for frame in frames[1:]:
        out = out.merge(frame, on="date", how="outer")
    out = out.sort_values("date").ffill()

    vix_level = float(cfg.get("vix_risk_off_level", 25))
    cny_pressure = float(cfg.get("cny_pressure_threshold", 0.003))
    z_window = int(cfg.get("magnitude_z_window", 252))
    z_min_periods = int(cfg.get("magnitude_z_min_periods", max(60, z_window // 4)))
    z_clip = float(cfg.get("magnitude_z_clip", 2.0))
    soft_risk_scale = float(cfg.get("soft_risk_scale", 0.5))
    for col in ["ndx_ret", "sox_ret", "nvda_ret", "kweb_ret", "vix_ret", "cnyx_ret"]:
        if col not in out.columns:
            out[col] = 0.0
    if "vix_close" not in out.columns:
        out["vix_close"] = np.nan
    out["xmarket_score"] = (
        0.30 * np.sign(out["ndx_ret"].fillna(0.0))
        + 0.25 * np.sign(out["sox_ret"].fillna(0.0))
        + 0.20 * np.sign(out["nvda_ret"].fillna(0.0))
        + 0.15 * np.sign(out["kweb_ret"].fillna(0.0))
        - 0.10 * np.sign(out["vix_ret"].fillna(0.0))
        - 0.10 * np.sign(out["cnyx_ret"].fillna(0.0))
    )
    for col in ["ndx_ret", "sox_ret", "nvda_ret", "kweb_ret", "vix_ret", "cnyx_ret"]:
        returns = out[col].fillna(0.0)
        rolling = returns.rolling(z_window, min_periods=z_min_periods)
        z_col = col.replace("_ret", "_z")
        out[z_col] = ((returns - rolling.mean()) / rolling.std(ddof=0).replace(0, np.nan)).clip(-z_clip, z_clip).fillna(0.0)

    out["xmarket_magnitude_score"] = (
        0.30 * out["ndx_z"]
        + 0.25 * out["sox_z"]
        + 0.20 * out["nvda_z"]
        + 0.15 * out["kweb_z"]
        - 0.10 * out["vix_z"]
        - 0.10 * out["cnyx_z"]
    ) / z_clip
    risk_event_count = (
        (out["vix_close"].ffill() > vix_level).astype(int)
        + (out["vix_ret"].fillna(0.0) > 0.08).astype(int)
        + (out["cnyx_ret"].fillna(0.0) > cny_pressure).astype(int)
    )
    out["risk_off"] = (risk_event_count > 0).astype(float)
    out["risk_scale"] = np.where(risk_event_count > 0, np.clip(soft_risk_scale, 0.0, 1.0), 1.0)
    return out[["date", "xmarket_score", "xmarket_magnitude_score", "risk_off", "risk_scale"]]


def _bucket_multiplier(symbol: str, mapped_symbols: dict[str, str]) -> float:
    bucket = mapped_symbols.get(symbol, "default")
    if bucket in {"ai_infra", "semiconductor", "tech_hardware"}:
        return 1.15
    if bucket in {"consumer_electronics", "ev"}:
        return 1.0
    if bucket in {"financial", "domestic_core"}:
        return 0.55
    if bucket in {"healthcare", "defensive"}:
        return 0.35
    return 0.75


def _add_cross_market_to_panel(
    panel: pd.DataFrame,
    years: int,
    strategy_cfg: dict[str, Any],
    features: pd.DataFrame | None = None,
) -> pd.DataFrame:
    xcfg = strategy_cfg.get("cross_market", {})
    if not xcfg.get("enabled", False) or panel.empty:
        panel = panel.copy()
        panel["xmarket_score"] = 0.0
        panel["xmarket_magnitude_score"] = 0.0
        panel["risk_off"] = 0.0
        panel["risk_scale"] = 1.0
        panel["xmarket_weight"] = 1.0
        panel["mapped_xmarket_score"] = 0.0
        panel["mapped_xmarket_magnitude_score"] = 0.0
        return panel

    if features is None:
        features = _load_cross_market_features(years, xcfg)
    d = panel.copy().sort_values(["symbol", "date"])
    d["date"] = pd.to_datetime(d["date"]).dt.normalize().astype("datetime64[ns]")
    if features.empty:
        d["xmarket_score"] = 0.0
        d["xmarket_magnitude_score"] = 0.0
        d["risk_off"] = 0.0
        d["risk_scale"] = 1.0
    else:
        features = features.sort_values("date").copy()
        # US close on date T is available to China trading decisions on T+1.
        features["source_date"] = pd.to_datetime(features["date"]).dt.normalize()
        features["date"] = (pd.to_datetime(features["date"]).dt.normalize() + pd.Timedelta(days=1)).astype("datetime64[ns]")
        d = pd.merge_asof(
            d.sort_values("date"),
            features.sort_values("date"),
            on="date",
            direction="backward",
        ).sort_values(["symbol", "date"])
        d["xmarket_score"] = d["xmarket_score"].fillna(0.0)
        d["xmarket_magnitude_score"] = d["xmarket_magnitude_score"].fillna(0.0)
        d["risk_off"] = d["risk_off"].fillna(0.0)
        d["risk_scale"] = d["risk_scale"].fillna(1.0).clip(0.0, 1.0)

    mapped = xcfg.get("mapped_symbols", {})
    d["xmarket_weight"] = d["symbol"].map(lambda s: _bucket_multiplier(str(s), mapped))
    d["mapped_xmarket_score"] = d["xmarket_score"] * d["xmarket_weight"]
    d["mapped_xmarket_magnitude_score"] = d["xmarket_magnitude_score"] * d["xmarket_weight"]
    return d


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
    xmarket_threshold: float = -1.0,
) -> tuple[pd.Series, pd.Series]:
    mom_col = f"mom{mom_window}"
    trend_col = f"ma{trend_window}"
    raw_signal = (
        (df[mom_col] > mom_threshold)
        & (df["close"] > df[trend_col])
        & (df["vol20"] <= vol_threshold)
        & (df.get("mapped_xmarket_score", pd.Series(0.0, index=df.index)) >= xmarket_threshold)
        & (df.get("risk_off", pd.Series(0.0, index=df.index)) < 1.0)
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
    xcfg = strategy_cfg.get("cross_market", {})
    xthresholds = xcfg.get("tech_score_thresholds", [-1.0])
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
                    for xthreshold in xthresholds:
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
                            xmarket_threshold=float(xthreshold),
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
                            "xmarket_threshold": float(xthreshold),
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
            "xmarket_threshold": -1.0,
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
        f"target_vol={params['target_vol']},"
        f"xscore>={params.get('xmarket_threshold', -1.0)}"
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
    xmarket_threshold: float = -1.0,
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
        & (d.get("mapped_xmarket_score", pd.Series(0.0, index=d.index)) >= xmarket_threshold)
        & (d.get("risk_off", pd.Series(0.0, index=d.index)) < 1.0)
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
    xcfg = strategy_cfg.get("cross_market", {})
    xthresholds = xcfg.get("tech_score_thresholds", [-1.0])

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
                    for xthreshold in xthresholds:
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
                            xmarket_threshold=float(xthreshold),
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
                            "xmarket_threshold": float(xthreshold),
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
            "xmarket_threshold": -1.0,
            "train_score": 0.0,
            "train_sharpe": 0.0,
            "train_trades": 0,
        }
    return best


def _format_portfolio_params(params: dict[str, Any]) -> str:
    return _format_params(params) + f",top_n={params.get('top_n', '')}"


def _apply_next_open_portfolio_strategy(
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
    xmarket_threshold: float = -1.0,
) -> tuple[pd.Series, pd.Series]:
    if panel.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)

    d = panel.copy().sort_values(["symbol", "date"])
    mom_col = f"mom{mom_window}"
    trend_col = f"ma{trend_window}"
    d["prev_mom"] = d.groupby("symbol")[mom_col].shift(1)
    d["prev_close"] = d.groupby("symbol")["close"].shift(1)
    d["prev_trend"] = d.groupby("symbol")[trend_col].shift(1)
    d["prev_vol20"] = d.groupby("symbol")["vol20"].shift(1)
    eligible = (
        (d["prev_mom"] > mom_threshold)
        & (d["prev_close"] > d["prev_trend"])
        & (d["prev_vol20"] <= vol_threshold)
        & (d.get("mapped_xmarket_score", pd.Series(0.0, index=d.index)) >= xmarket_threshold)
        & (d.get("risk_off", pd.Series(0.0, index=d.index)) < 1.0)
    )

    d["mom_rank_component"] = d.groupby("date")["prev_mom"].rank(method="first", pct=True)
    d["xmarket_rank_component"] = d.groupby("date")["mapped_xmarket_score"].rank(method="first", pct=True)
    d["rank_score"] = (d["mom_rank_component"] + d["xmarket_rank_component"]).where(eligible, np.nan)
    d["rank"] = d.groupby("date")["rank_score"].rank(method="first", ascending=False)
    d["selected"] = ((d["rank"] <= top_n) & d["rank_score"].notna()).astype(float)
    daily_count = d.groupby("date")["selected"].transform("sum").replace(0, np.nan)
    d["raw_weight"] = (d["selected"] / daily_count).fillna(0.0)
    vol_scale = np.minimum(1.0, target_vol / d["prev_vol20"].replace(0, np.nan)).fillna(0.0)
    d["weight"] = d["raw_weight"] * vol_scale
    d["position_ret"] = d["weight"] * d["oc_ret"]

    weights = d.pivot(index="date", columns="symbol", values="weight").fillna(0.0)
    turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
    sells = weights.diff().clip(upper=0).abs().sum(axis=1).fillna(0.0)
    gross = d.groupby("date")["position_ret"].sum()
    costs = turnover * (slippage + commission) + sells * stamp_duty_sell
    returns = gross.sub(costs, fill_value=0.0)
    exposure = weights.sum(axis=1)
    return returns, exposure


def _select_next_open_portfolio_params(
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
    xcfg = strategy_cfg.get("cross_market", {})
    xthresholds = xcfg.get("tech_score_thresholds", [-1.0])

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
                    for xthreshold in xthresholds:
                        returns, exposure = _apply_next_open_portfolio_strategy(
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
                            xmarket_threshold=float(xthreshold),
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
                            "xmarket_threshold": float(xthreshold),
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
            "xmarket_threshold": -1.0,
            "train_score": 0.0,
            "train_sharpe": 0.0,
            "train_trades": 0,
        }
    return best


def _format_next_open_params(params: dict[str, Any]) -> str:
    return _format_portfolio_params(params) + ",entry=next_open,ret=open_to_close"


def _apply_magnitude_soft_risk_portfolio_strategy(
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
    xmarket_threshold: float = 0.0,
) -> tuple[pd.Series, pd.Series]:
    if panel.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)

    d = panel.copy()
    mom_col = f"mom{mom_window}"
    trend_col = f"ma{trend_window}"
    xscore = d.get("mapped_xmarket_magnitude_score", pd.Series(0.0, index=d.index))
    d["_xscore"] = xscore
    eligible = (
        (d[mom_col] > mom_threshold)
        & (d["close"] > d[trend_col])
        & (d["vol20"] <= vol_threshold)
        & (d["_xscore"] >= xmarket_threshold)
    )
    d["mom_rank_component"] = d.groupby("date")[mom_col].rank(method="first", pct=True)
    d["xmarket_rank_component"] = d.groupby("date")["_xscore"].rank(method="first", pct=True)
    d["rank_score"] = (d["mom_rank_component"] + d["xmarket_rank_component"]).where(eligible, np.nan)
    d["rank"] = d.groupby("date")["rank_score"].rank(method="first", ascending=False)
    d["selected"] = ((d["rank"] <= top_n) & d["rank_score"].notna()).astype(float)
    daily_count = d.groupby("date")["selected"].transform("sum").replace(0, np.nan)
    d["raw_weight"] = (d["selected"] / daily_count).fillna(0.0)
    vol_scale = np.minimum(1.0, target_vol / d["vol20"].replace(0, np.nan)).fillna(0.0)
    risk_scale = d.get("risk_scale", pd.Series(1.0, index=d.index)).clip(0.0, 1.0)
    d["weight"] = d["raw_weight"] * vol_scale * risk_scale
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


def _select_magnitude_soft_risk_portfolio_params(
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
    xcfg = strategy_cfg.get("cross_market", {})
    xthresholds = xcfg.get("magnitude_score_thresholds", [0.0])

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
                    for xthreshold in xthresholds:
                        returns, exposure = _apply_magnitude_soft_risk_portfolio_strategy(
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
                            xmarket_threshold=float(xthreshold),
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
                            "xmarket_threshold": float(xthreshold),
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
            "xmarket_threshold": 0.0,
            "train_score": 0.0,
            "train_sharpe": 0.0,
            "train_trades": 0,
        }
    return best


def _format_magnitude_soft_risk_params(params: dict[str, Any]) -> str:
    base = _format_portfolio_params(params)
    return base.replace("xscore>=", "xmag>=") + ",risk=soft"


def _add_local_factor_features(panel: pd.DataFrame) -> pd.DataFrame:
    if panel.empty:
        return panel
    d = panel.copy().sort_values(["date", "symbol"])
    for window in [3, 5, 10, 20]:
        mom_col = f"mom{window}"
        if mom_col not in d.columns:
            continue
        market_mom = d.groupby("date")[mom_col].transform("mean")
        d[f"resid_mom{window}"] = d[mom_col] - market_mom
    return d


def _apply_residual_momentum_reversal_portfolio_strategy(
    panel: pd.DataFrame,
    *,
    residual_window: int,
    residual_threshold: float,
    reversal_window: int,
    reversal_threshold: float,
    trend_window: int,
    vol_threshold: float,
    target_vol: float,
    top_n: int,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
    use_xmarket_overlay: bool = True,
) -> tuple[pd.Series, pd.Series]:
    if panel.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)

    d = panel.copy()
    resid_col = f"resid_mom{residual_window}"
    reversal_col = f"mom{reversal_window}"
    trend_col = f"ma{trend_window}"
    eligible = (
        (d[resid_col] > residual_threshold)
        & (d[reversal_col] <= reversal_threshold)
        & (d["close"] > d[trend_col])
        & (d["vol20"] <= vol_threshold)
    )
    d["resid_rank_component"] = d.groupby("date")[resid_col].rank(method="first", pct=True)
    d["reversal_rank_component"] = (1.0 - d.groupby("date")[reversal_col].rank(method="first", pct=True)).clip(0.0, 1.0)
    d["rank_score"] = (d["resid_rank_component"] + 0.5 * d["reversal_rank_component"]).where(eligible, np.nan)
    d["rank"] = d.groupby("date")["rank_score"].rank(method="first", ascending=False)
    d["selected"] = ((d["rank"] <= top_n) & d["rank_score"].notna()).astype(float)
    daily_count = d.groupby("date")["selected"].transform("sum").replace(0, np.nan)
    d["raw_weight"] = (d["selected"] / daily_count).fillna(0.0)
    vol_scale = np.minimum(1.0, target_vol / d["vol20"].replace(0, np.nan)).fillna(0.0)
    risk_scale = d.get("risk_scale", pd.Series(1.0, index=d.index)).clip(0.0, 1.0) if use_xmarket_overlay else 1.0
    d["weight"] = d["raw_weight"] * vol_scale * risk_scale
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


def _select_residual_momentum_reversal_params(
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
    lcfg = strategy_cfg.get("local_factor", {})
    reversal_window = int(lcfg.get("reversal_window", 3))
    use_xmarket_overlay = bool(lcfg.get("use_xmarket_overlay", True))

    for residual_window in lcfg.get("residual_momentum_windows", [10, 20]):
        resid_col = f"resid_mom{int(residual_window)}"
        if resid_col not in train.columns:
            continue
        for residual_q in lcfg.get("residual_momentum_quantiles", [0.6]):
            residual_threshold = float(train[resid_col].quantile(float(residual_q)))
            reversal_col = f"mom{reversal_window}"
            if reversal_col not in train.columns:
                continue
            for reversal_q in lcfg.get("reversal_quantiles", [0.7]):
                reversal_threshold = float(train[reversal_col].quantile(float(reversal_q)))
                for trend_window in strategy_cfg.get("trend_windows", [20]):
                    trend_col = f"ma{trend_window}"
                    if trend_col not in train.columns:
                        continue
                    for vol_q in strategy_cfg.get("vol_quantiles", [0.75]):
                        vol_threshold = float(train["vol20"].quantile(float(vol_q)))
                        returns, exposure = _apply_residual_momentum_reversal_portfolio_strategy(
                            train,
                            residual_window=int(residual_window),
                            residual_threshold=residual_threshold,
                            reversal_window=reversal_window,
                            reversal_threshold=reversal_threshold,
                            trend_window=int(trend_window),
                            vol_threshold=vol_threshold,
                            target_vol=target_vol,
                            top_n=top_n,
                            slippage=slippage,
                            commission=commission,
                            stamp_duty_sell=stamp_duty_sell,
                            use_xmarket_overlay=use_xmarket_overlay,
                        )
                        metric = _calc_metrics(returns, exposure)
                        if metric["trades"] < min_trades:
                            continue
                        score = metric["sharpe"] + max(metric["max_drawdown"], -1.0) * 0.5
                        candidate = {
                            "residual_window": int(residual_window),
                            "residual_quantile": float(residual_q),
                            "residual_threshold": residual_threshold,
                            "reversal_window": reversal_window,
                            "reversal_quantile": float(reversal_q),
                            "reversal_threshold": reversal_threshold,
                            "trend_window": int(trend_window),
                            "vol_quantile": float(vol_q),
                            "vol_threshold": vol_threshold,
                            "target_vol": target_vol,
                            "top_n": top_n,
                            "use_xmarket_overlay": use_xmarket_overlay,
                            "train_score": float(score),
                            "train_sharpe": float(metric["sharpe"]),
                            "train_trades": int(metric["trades"]),
                        }
                        if best is None or candidate["train_score"] > best["train_score"]:
                            best = candidate

    if best is None:
        best = {
            "residual_window": 20,
            "residual_quantile": 0.6,
            "residual_threshold": float(train.get("resid_mom20", pd.Series(0.0)).median()),
            "reversal_window": reversal_window,
            "reversal_quantile": 0.7,
            "reversal_threshold": float(train.get(f"mom{reversal_window}", pd.Series(0.0)).quantile(0.7)),
            "trend_window": 20,
            "vol_quantile": 0.75,
            "vol_threshold": float(train["vol20"].quantile(0.75)),
            "target_vol": target_vol,
            "top_n": top_n,
            "use_xmarket_overlay": use_xmarket_overlay,
            "train_score": 0.0,
            "train_sharpe": 0.0,
            "train_trades": 0,
        }
    return best


def _format_residual_momentum_reversal_params(params: dict[str, Any]) -> str:
    return (
        f"resid_mom{params['residual_window']}@q{params['residual_quantile']},"
        f"reversal_mom{params['reversal_window']}<=q{params['reversal_quantile']},"
        f"ma{params['trend_window']},"
        f"vol@q{params['vol_quantile']},"
        f"target_vol={params['target_vol']},"
        f"top_n={params.get('top_n', '')},"
        f"xmarket_overlay={params.get('use_xmarket_overlay', True)}"
    )


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
    xfeatures: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    panel = _align_symbol_map(_load_symbol_map(symbols, years=years))
    if panel.empty:
        return []
    panel = _add_cross_market_to_panel(panel, years, strategy_cfg, xfeatures)

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
            xmarket_threshold=float(params.get("xmarket_threshold", -1.0)),
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
                "candidate": "xmarket_portfolio_v2" if _xmarket_enabled(strategy_cfg) else "portfolio_v2",
            }
        )
        start += fold_days_valid
    return rows


def _run_next_open_portfolio(
    symbols: list[str],
    years: int,
    train_years: int,
    validate_years: int,
    min_samples: int,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
    strategy_cfg: dict[str, Any],
    xfeatures: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    panel = _align_symbol_map(_load_symbol_map(symbols, years=years))
    if panel.empty:
        return []
    panel = _add_cross_market_to_panel(panel, years, strategy_cfg, xfeatures)

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

        params = _select_next_open_portfolio_params(
            train,
            strategy_cfg,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
        )
        returns, exposure = _apply_next_open_portfolio_strategy(
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
            xmarket_threshold=float(params.get("xmarket_threshold", -1.0)),
        )
        metric = _calc_metrics(returns, exposure)
        fold_idx += 1
        rows.append(
            {
                "symbol": "PORTFOLIO_NEXT_OPEN",
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
                "selected_params": _format_next_open_params(params),
                "candidate": "xmarket_next_open_v1",
            }
        )
        start += fold_days_valid
    return rows


def _run_magnitude_soft_risk_portfolio(
    symbols: list[str],
    years: int,
    train_years: int,
    validate_years: int,
    min_samples: int,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
    strategy_cfg: dict[str, Any],
    xfeatures: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    panel = _align_symbol_map(_load_symbol_map(symbols, years=years))
    if panel.empty:
        return []
    panel = _add_cross_market_to_panel(panel, years, strategy_cfg, xfeatures)

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

        params = _select_magnitude_soft_risk_portfolio_params(
            train,
            strategy_cfg,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
        )
        returns, exposure = _apply_magnitude_soft_risk_portfolio_strategy(
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
            xmarket_threshold=float(params.get("xmarket_threshold", 0.0)),
        )
        metric = _calc_metrics(returns, exposure)
        fold_idx += 1
        rows.append(
            {
                "symbol": "PORTFOLIO_MAG_SOFT_RISK",
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
                "selected_params": _format_magnitude_soft_risk_params(params),
                "candidate": "xmarket_magnitude_soft_risk_v1",
            }
        )
        start += fold_days_valid
    return rows


def _run_residual_momentum_reversal_portfolio(
    symbols: list[str],
    years: int,
    train_years: int,
    validate_years: int,
    min_samples: int,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
    strategy_cfg: dict[str, Any],
    xfeatures: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    panel = _align_symbol_map(_load_symbol_map(symbols, years=years))
    if panel.empty:
        return []
    panel = _add_cross_market_to_panel(panel, years, strategy_cfg, xfeatures)
    panel = _add_local_factor_features(panel)

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

        params = _select_residual_momentum_reversal_params(
            train,
            strategy_cfg,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
        )
        returns, exposure = _apply_residual_momentum_reversal_portfolio_strategy(
            valid,
            residual_window=int(params["residual_window"]),
            residual_threshold=float(params["residual_threshold"]),
            reversal_window=int(params["reversal_window"]),
            reversal_threshold=float(params["reversal_threshold"]),
            trend_window=int(params["trend_window"]),
            vol_threshold=float(params["vol_threshold"]),
            target_vol=float(params["target_vol"]),
            top_n=int(params.get("top_n", strategy_cfg.get("top_n", 2))),
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
            use_xmarket_overlay=bool(params.get("use_xmarket_overlay", True)),
        )
        metric = _calc_metrics(returns, exposure)
        fold_idx += 1
        rows.append(
            {
                "symbol": "PORTFOLIO_RESID_MOM_REVERSAL",
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
                "selected_params": _format_residual_momentum_reversal_params(params),
                "candidate": "residual_momentum_reversal_v1",
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
    if int(summary.get("fold_count", 0)) == 0:
        return -1_000_000.0
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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: dict[str, list[dict[str, Any]]] = {}
    xfeatures = _load_cross_market_features(years, strategy_cfg.get("cross_market", {})) if _xmarket_enabled(strategy_cfg) else None

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
            xfeatures=xfeatures,
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
                    "candidate": "xmarket_single_v2" if _xmarket_enabled(strategy_cfg) else "filtered_single_v2",
                }
            )

    candidates["legacy_momentum"] = legacy_rows
    candidates["xmarket_single_v2" if _xmarket_enabled(strategy_cfg) else "filtered_single_v2"] = filtered_rows
    candidates["xmarket_portfolio_v2" if _xmarket_enabled(strategy_cfg) else "portfolio_v2"] = _run_portfolio(
        symbols=symbols,
        years=years,
        train_years=train_years,
        validate_years=validate_years,
        min_samples=min_samples,
        slippage=slippage,
        commission=commission,
        stamp_duty_sell=stamp_duty_sell,
        strategy_cfg={**strategy_cfg, "mode": "portfolio"},
        xfeatures=xfeatures,
    )
    if _xmarket_enabled(strategy_cfg):
        candidates["xmarket_next_open_v1"] = _run_next_open_portfolio(
            symbols=symbols,
            years=years,
            train_years=train_years,
            validate_years=validate_years,
            min_samples=min_samples,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
            strategy_cfg={**strategy_cfg, "mode": "portfolio"},
            xfeatures=xfeatures,
        )
        candidates["xmarket_magnitude_soft_risk_v1"] = _run_magnitude_soft_risk_portfolio(
            symbols=symbols,
            years=years,
            train_years=train_years,
            validate_years=validate_years,
            min_samples=min_samples,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
            strategy_cfg={**strategy_cfg, "mode": "portfolio"},
            xfeatures=xfeatures,
        )
    if strategy_cfg.get("local_factor", {}).get("enabled", False):
        candidates["residual_momentum_reversal_v1"] = _run_residual_momentum_reversal_portfolio(
            symbols=symbols,
            years=years,
            train_years=train_years,
            validate_years=validate_years,
            min_samples=min_samples,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
            strategy_cfg={**strategy_cfg, "mode": "portfolio"},
            xfeatures=xfeatures,
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
    all_candidate_rows: list[dict[str, Any]] = []
    for name, rows in candidates.items():
        for row in rows:
            enriched = dict(row)
            enriched["candidate_summary"] = comparison
            enriched["selected_candidate"] = best_name
            enriched["is_selected_candidate"] = name == best_name
            all_candidate_rows.append(enriched)
    return selected, all_candidate_rows


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
    xfeatures: pd.DataFrame | None = None,
) -> list[FoldResult]:
    df = _load_symbol(symbol, years=years)
    if df.empty or len(df) < min_samples:
        return []
    df = _add_cross_market_to_panel(df.assign(symbol=symbol), years, strategy_cfg, xfeatures)

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
            xmarket_threshold=float(params.get("xmarket_threshold", -1.0)),
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
    configure_local_history(config.get("local_history", {}), Path.cwd())
    symbols = config["symbols"]
    universe_symbols = load_universe_symbols(config, Path.cwd()) if config.get("universe", {}).get("enabled", False) else []
    if universe_symbols:
        symbols = universe_symbols
    strategy_cfg = wcfg.get("strategy_v2", {})
    configure_akshare_throttle(config.get("data_sources", {}).get("akshare", {}))
    _load_symbol_cached.cache_clear()

    candidate_rows: list[dict[str, Any]] = []
    if strategy_cfg.get("mode") == "compare":
        all_rows, candidate_rows = _run_compare(
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
        xfeatures = _load_cross_market_features(years, strategy_cfg.get("cross_market", {})) if _xmarket_enabled(strategy_cfg) else None
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
                xfeatures=xfeatures,
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
                        "candidate": "xmarket_single_v2" if _xmarket_enabled(strategy_cfg) else "filtered_single_v2",
                    }
                )

    folds_df = pd.DataFrame(all_rows)
    candidate_folds_df = pd.DataFrame(candidate_rows)
    if folds_df.empty:
        return {
            "folds": folds_df,
            "candidate_folds": candidate_folds_df,
            "summary": {"status": "failed", "reason": "no valid folds"},
        }

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

    return {"folds": folds_df, "candidate_folds": candidate_folds_df, "summary": summary}


def save_walk_forward_csv(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8")
