from __future__ import annotations

import copy
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from phase0.accounts import SimulatedAccountConfig, run_signal_account_execution
from phase0.data_sources import fetch_cn_daily, fetch_hk_daily, fetch_yf_daily
from phase0.external_market_history import (
    configure_us_market_history,
    load_us_daily_from_history,
    us_market_history_runtime_fallback_enabled,
)
from phase0.local_history import (
    configure_local_history,
    load_daily_from_local_history,
    load_trading_dates_from_local_history,
    local_history_path,
    local_history_prefer_daily_for_backtest,
)
from phase0.strategies import available_strategies, get_strategy
from phase0.strategies.base import StrategyOutput
from phase0.strategy_constraints import apply_strategy_constraints
from phase0.throttle import configure_akshare_throttle
from phase0.universe import load_point_in_time_universe, load_universe_symbols


MARKET_TICKERS = ["^NDX", "^SOX", "NVDA", "KWEB", "^VIX", "CNY=X"]
FINANCIAL_FACTOR_COLUMNS = [
    "roe",
    "revenue_growth",
    "profit_growth",
    "cash_flow_quality",
    "debt_to_asset",
]
FINANCIAL_DIAGNOSTIC_STRATEGIES = {
    "core_selection_quality_momentum_v1",
    "low_vol_low_turnover_quality_v1",
    "multifactor_volume_price_filter_v1",
    "quality_growth_price_v1",
    "quality_low_turnover_monthly_v1",
    "sleeve_composite_v1",
}

TraceCallback = Callable[[dict[str, Any]], None]


def _parse_optional_date(value: Any) -> date | None:
    if value is None or str(value).strip() == "":
        return None
    return pd.Timestamp(value).date()


def _xmarket_enabled(strategy_cfg: dict[str, Any]) -> bool:
    return bool(strategy_cfg.get("cross_market", {}).get("enabled", False))


def _resolve_walk_forward_window(wcfg: dict[str, Any]) -> dict[str, Any]:
    preset_name = str(wcfg.get("preset_name", "") or "").strip()
    presets = wcfg.get("presets", {})
    if preset_name:
        if not isinstance(presets, dict) or preset_name not in presets:
            raise ValueError(f"walk_forward preset_name not found: {preset_name}")
        preset = presets[preset_name] or {}
        return {
            "preset_name": preset_name,
            "train_years": int(preset["train_years"]),
            "validate_years": int(preset["validate_years"]),
            "start_date": _parse_optional_date(preset.get("start_date")),
            "end_date": _parse_optional_date(preset.get("end_date")),
            "expected_folds": int(preset["expected_folds"]) if preset.get("expected_folds") is not None else None,
            "description": str(preset.get("description", "")),
        }

    # Backward-compatible fallback for older config files. New project config should use preset_name.
    return {
        "preset_name": "legacy_inline",
        "train_years": int(wcfg["train_years"]),
        "validate_years": int(wcfg["validate_years"]),
        "start_date": _parse_optional_date(wcfg.get("start_date")),
        "end_date": _parse_optional_date(wcfg.get("end_date")),
        "expected_folds": int(wcfg["expected_folds"]) if wcfg.get("expected_folds") is not None else None,
        "description": "Legacy inline train_years/validate_years config.",
    }


def describe_walk_forward_preset(wcfg: dict[str, Any], preset_name: str | None = None) -> str:
    """Return a concise human-readable description of a walk-forward preset."""
    scoped = copy.deepcopy(wcfg)
    if preset_name is not None:
        scoped["preset_name"] = preset_name
    window = _resolve_walk_forward_window(scoped)
    train_years = int(window["train_years"])
    validate_years = int(window["validate_years"])
    start = window.get("start_date")
    end = window.get("end_date")
    expected = window.get("expected_folds")
    if start and end:
        window_text = f"固定研究区间 {start.isoformat()} 至 {end.isoformat()}"
    elif start:
        window_text = f"固定起点 {start.isoformat()}，终点由可用数据末端决定"
    elif end:
        window_text = f"固定终点 {end.isoformat()}，起点由 config years 和可用数据推导"
    else:
        window_text = "未固定起止日期，由 config years 和可用数据末端推导"
    fold_text = f"预计 {expected} 折" if expected is not None else "折数由数据覆盖自动决定"
    description = str(window.get("description", "")).strip()
    suffix = f"；{description}" if description else ""
    return (
        f"Walk-forward preset `{window['preset_name']}`：每折用 {train_years} 年训练选参，"
        f"紧随其后 {validate_years} 年做样本外验证；{window_text}；{fold_text}；"
        f"窗口每次向前滚动 {validate_years} 年{suffix}"
    )


def describe_walk_forward_presets(
    wcfg: dict[str, Any],
    preset_names: list[str] | None = None,
    *,
    default_all: bool = False,
) -> list[str]:
    presets = wcfg.get("presets", {}) or {}
    if preset_names:
        names = preset_names
    elif default_all:
        names = list(presets.keys())
    else:
        names = [str(wcfg.get("preset_name"))] if wcfg.get("preset_name") else list(presets.keys())
    return [describe_walk_forward_preset(wcfg, str(name)) for name in names]


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


def _load_cn_daily(
    symbol: str,
    years: int,
    as_of_date: date | None = None,
    price_adjustment: str | None = None,
) -> pd.DataFrame:
    end = date.today()
    start = end - timedelta(days=365 * years + 30)
    if local_history_prefer_daily_for_backtest():
        local_df = load_daily_from_local_history(
            symbol,
            start,
            end,
            price_adjustment=price_adjustment,
            as_of_date=as_of_date,
        )
        if not local_df.empty:
            return local_df
    df = fetch_cn_daily(symbol, years=years, adjust="qfq")
    if not df.empty:
        return df
    return load_daily_from_local_history(
        symbol,
        start,
        end,
        price_adjustment=price_adjustment,
        as_of_date=as_of_date,
    )


def _load_hk_daily(symbol: str, years: int) -> pd.DataFrame:
    return fetch_hk_daily(symbol, years=years, adjust="qfq")


def _load_symbol(
    symbol: str,
    years: int,
    as_of_date: date | str | None = None,
    price_adjustment: str | None = None,
) -> pd.DataFrame:
    as_of_key = "" if as_of_date is None else pd.Timestamp(as_of_date).date().isoformat()
    adjust_key = str(price_adjustment or "")
    return _load_symbol_cached(symbol, years, as_of_key, adjust_key).copy()


def _shadow_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return (numerator / denominator.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)


@lru_cache(maxsize=512)
def _load_symbol_cached(
    symbol: str,
    years: int,
    as_of_key: str = "",
    price_adjustment: str = "",
) -> pd.DataFrame:
    as_of_date = pd.Timestamp(as_of_key).date() if as_of_key else None
    if symbol.startswith("HK."):
        df = _load_hk_daily(symbol, years)
    else:
        df = _load_cn_daily(
            symbol,
            years,
            as_of_date=as_of_date,
            price_adjustment=price_adjustment or None,
        )
    if df.empty:
        return df

    # 将原始日 K 整理成回测统一字段，并生成看盘会用到的收益、影线、动量、均线、波动和成交额特征。
    out = pd.DataFrame()
    out["date"] = pd.to_datetime(df["date"])
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        if col in df.columns:
            out[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            out[col] = np.nan

    out["ret"] = out["close"].pct_change().fillna(0.0)
    out["oc_ret"] = (out["close"] / out["open"].replace(0, np.nan) - 1.0).fillna(0.0)
    out["gap_ret"] = (out["open"] / out["close"].shift(1).replace(0, np.nan) - 1.0).fillna(0.0)
    out["range_pct"] = _shadow_ratio(out["high"] - out["low"], out["open"])
    out["body_pct"] = _shadow_ratio((out["close"] - out["open"]).abs(), out["open"])
    real_body = (out["close"] - out["open"]).abs()
    out["upper_shadow_pct"] = _shadow_ratio(out["high"] - out[["open", "close"]].max(axis=1), real_body)
    out["lower_shadow_pct"] = _shadow_ratio(out[["open", "close"]].min(axis=1) - out["low"], real_body)

    for window in [3, 5, 10, 20, 60]:
        out[f"mom{window}"] = out["close"].pct_change(window)
        out[f"ma{window}"] = out["close"].rolling(window).mean()
    out["vol20"] = out["ret"].rolling(20).std() * np.sqrt(252)
    out["amount_ma20"] = out["amount"].rolling(20).mean()
    out["amount_ratio20"] = _shadow_ratio(out["amount"], out["amount_ma20"])
    out["close_vs_ma20"] = _shadow_ratio(out["close"] - out["ma20"], out["ma20"])
    rolling_high20 = out["high"].rolling(20).max().shift(1)
    out["breakout20"] = (out["close"] > rolling_high20).astype(float)
    out = out.dropna().reset_index(drop=True)
    return out


def _load_cross_market_features(years: int, cfg: dict[str, Any]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    end = date.today()
    start = end - timedelta(days=365 * years + 20)
    history = load_us_daily_from_history(MARKET_TICKERS, start, end)
    for ticker in MARKET_TICKERS:
        if not history.empty:
            df = history[history["symbol"] == ticker].copy()
        else:
            df = pd.DataFrame()
        if df.empty and us_market_history_runtime_fallback_enabled():
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


def _load_symbol_map(
    symbols: list[str],
    years: int,
    as_of_date: date | str | None = None,
    price_adjustment: str | None = None,
) -> dict[str, pd.DataFrame]:
    data: dict[str, pd.DataFrame] = {}
    # 回测前逐只加载股票历史行情，模拟实盘研究阶段先准备可观察股票池的数据。
    for sym in symbols:
        df = _load_symbol(sym, years=years, as_of_date=as_of_date, price_adjustment=price_adjustment)
        if not df.empty:
            data[sym] = df
    return data


def _align_symbol_map(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = []
    # 多只股票合成长表，后续才能在同一交易日做横截面排名和组合调仓。
    for sym, df in data.items():
        d = df.copy()
        d["symbol"] = sym
        frames.append(d)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)


def _emit_trace(callback: TraceCallback | None, payload: dict[str, Any]) -> None:
    if callback is None:
        return
    callback(payload)


def _signal_trace_summary(output: StrategyOutput, *, top_n: int = 5) -> dict[str, Any]:
    signal = output.signal_frame.copy()
    if signal.empty:
        return {
            "target_days": 0,
            "live_days": 0,
            "avg_target_holdings": 0.0,
            "avg_live_holdings": 0.0,
            "trade_days": 0,
            "first_target_date": "",
            "first_target_symbols": [],
        }

    if "date" in signal.columns:
        signal["date"] = pd.to_datetime(signal["date"], errors="coerce").dt.normalize()
    if "symbol" in signal.columns:
        signal["symbol"] = signal["symbol"].astype(str)

    target_col = "weight_unshifted" if "weight_unshifted" in signal.columns else "selected"
    target = pd.to_numeric(signal.get(target_col, pd.Series(0.0, index=signal.index)), errors="coerce").fillna(0.0)
    live = pd.to_numeric(signal.get("weight", pd.Series(0.0, index=signal.index)), errors="coerce").fillna(0.0)

    target_frame = signal[target.abs() > 1e-12].copy()
    live_frame = signal[live.abs() > 1e-12].copy()
    target_counts = target_frame.groupby("date")["symbol"].nunique() if not target_frame.empty else pd.Series(dtype=int)
    live_counts = live_frame.groupby("date")["symbol"].nunique() if not live_frame.empty else pd.Series(dtype=int)

    trade_days = 0
    if not signal.empty and "date" in signal.columns and "symbol" in signal.columns and "weight" in signal.columns:
        weights = (
            signal.pivot(index="date", columns="symbol", values="weight")
            .fillna(0.0)
            .sort_index()
        )
        trade_days = int(weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1)).gt(1e-12).sum())

    first_target_date = ""
    first_target_symbols: list[str] = []
    if not target_frame.empty:
        first_target_date = str(pd.Timestamp(target_frame["date"].min()).date())
        first_day = target_frame[target_frame["date"] == pd.Timestamp(first_target_date)]
        sort_col = "score" if "score" in first_day.columns else None
        if sort_col is not None:
            first_day = first_day.sort_values([sort_col, "symbol"], ascending=[False, True], na_position="last")
        else:
            first_day = first_day.sort_values(["symbol"])
        first_target_symbols = first_day["symbol"].head(top_n).astype(str).tolist()

    return {
        "target_days": int(target_counts.shape[0]),
        "live_days": int(live_counts.shape[0]),
        "avg_target_holdings": float(target_counts.mean()) if not target_counts.empty else 0.0,
        "avg_live_holdings": float(live_counts.mean()) if not live_counts.empty else 0.0,
        "trade_days": trade_days,
        "first_target_date": first_target_date,
        "first_target_symbols": first_target_symbols,
    }


def _add_fold_metadata(panel: pd.DataFrame, metadata: pd.DataFrame | None) -> pd.DataFrame:
    if panel.empty or metadata is None or metadata.empty or "symbol" not in metadata.columns:
        return panel
    meta_cols = [col for col in ["symbol", "name", "industry"] if col in metadata.columns]
    if len(meta_cols) <= 1:
        return panel
    meta = metadata[meta_cols].copy().drop_duplicates("symbol")
    meta["symbol"] = meta["symbol"].astype(str)
    out = panel.copy()
    out["symbol"] = out["symbol"].astype(str)
    merged = out.merge(meta, on="symbol", how="left", suffixes=("", "_meta"))
    for col in ["name", "industry"]:
        meta_col = f"{col}_meta"
        if meta_col not in merged.columns:
            continue
        if col not in merged.columns:
            merged[col] = merged[meta_col]
        else:
            current = merged[col]
            missing = current.isna() | current.astype(str).str.strip().eq("")
            merged[col] = current.where(~missing, merged[meta_col])
    return merged.drop(columns=[col for col in merged.columns if col.endswith("_meta")])


def _load_current_symbol_metadata(symbols: list[str]) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame()
    db_path = local_history_path()
    if not db_path.exists():
        return pd.DataFrame()
    placeholders = ",".join("?" for _ in symbols)
    query = f"""
        SELECT symbol, name, industry
        FROM market_stocks
        WHERE market = ?
          AND symbol IN ({placeholders})
    """
    try:
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql_query(query, conn, params=["CN", *symbols])
    except sqlite3.Error:
        return pd.DataFrame()
    if df.empty:
        return df
    df["symbol"] = df["symbol"].astype(str)
    return df


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
    # 每天收盘后做一次看盘筛选：动量、趋势、波动、外盘映射和风险关闭信号同时达标才进入候选。
    eligible = (
        (d[mom_col] > mom_threshold)
        & (d["close"] > d[trend_col])
        & (d["vol20"] <= vol_threshold)
        & (d.get("mapped_xmarket_score", pd.Series(0.0, index=d.index)) >= xmarket_threshold)
        & (d.get("risk_off", pd.Series(0.0, index=d.index)) < 1.0)
    )
    # 同一天的候选股按动量强弱排名，取前 top_n，模拟盘后生成买入清单。
    d["rank_score"] = d[mom_col].where(eligible, np.nan)
    d["rank"] = d.groupby("date")["rank_score"].rank(method="first", ascending=False)
    d["selected"] = ((d["rank"] <= top_n) & d["rank_score"].notna()).astype(float)
    daily_count = d.groupby("date")["selected"].transform("sum").replace(0, np.nan)
    d["raw_weight"] = (d["selected"] / daily_count).fillna(0.0)
    # 入选股票先等权，再按近期波动缩放仓位，模拟实盘中对高波动标的少配一点。
    vol_scale = np.minimum(1.0, target_vol / d["vol20"].replace(0, np.nan)).fillna(0.0)
    d["weight"] = d["raw_weight"] * vol_scale
    # 收盘后得到的目标仓位从下一交易日开始生效，避免把当天信号当成当天已成交。
    d["weight"] = d.groupby("symbol")["weight"].shift(1).fillna(0.0)
    d["position_ret"] = d["weight"] * d["ret"]

    weights = d.pivot(index="date", columns="symbol", values="weight").fillna(0.0)
    turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
    sells = weights.diff().clip(upper=0).abs().sum(axis=1).fillna(0.0)
    gross = d.groupby("date")["position_ret"].sum()
    # 组合毛收益扣掉调仓产生的滑点、佣金和卖出印花税，近似真实账户成交后的收益。
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


def _safe_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Unsafe SQL identifier: {value}")
    return value


def _load_financial_factor_frame(symbols: list[str], strategy_cfg: dict[str, Any]) -> pd.DataFrame:
    lcfg = strategy_cfg.get("local_factor", {})
    qcfg = lcfg.get("quality_growth", {})
    table = _safe_identifier(str(qcfg.get("financial_table", "market_financial_factors")))
    db_path = local_history_path()
    if not db_path.exists() or not symbols:
        return pd.DataFrame()

    placeholders = ",".join("?" for _ in symbols)
    query = f"""
        SELECT
            symbol,
            report_date,
            announce_date,
            roe,
            revenue_growth,
            profit_growth,
            operating_cash_flow_to_net_profit AS cash_flow_quality,
            debt_to_asset
        FROM {table}
        WHERE market = ?
          AND symbol IN ({placeholders})
          AND announce_date IS NOT NULL
        ORDER BY symbol, announce_date, report_date
    """
    try:
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql_query(query, conn, params=["CN", *symbols])
    except (sqlite3.Error, ValueError):
        return pd.DataFrame()
    if df.empty:
        return df

    df["symbol"] = df["symbol"].astype(str)
    df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce")
    df["announce_date"] = pd.to_datetime(df["announce_date"], errors="coerce")
    for col in FINANCIAL_FACTOR_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["symbol", "announce_date"]).sort_values(["symbol", "announce_date", "report_date"])


def _add_point_in_time_financial_factors(panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
    if panel.empty:
        return panel
    lcfg = strategy_cfg.get("local_factor", {})
    qcfg = lcfg.get("quality_growth", {})
    if not qcfg.get("enabled", False):
        return panel

    symbols = sorted(panel["symbol"].astype(str).dropna().unique().tolist())
    factors = _load_financial_factor_frame(symbols, strategy_cfg)
    if factors.empty:
        return panel

    financial_lag_days = int(qcfg.get("financial_lag_days", 1))
    factors = factors.copy()
    factors["available_date"] = (
        factors["announce_date"] + pd.to_timedelta(financial_lag_days, unit="D")
    ).dt.normalize().astype("datetime64[ns]")
    factors["report_date"] = pd.to_datetime(factors["report_date"], errors="coerce").dt.normalize().astype("datetime64[ns]")
    factors = factors.dropna(subset=["available_date"]).sort_values(["symbol", "available_date", "report_date"])

    frames: list[pd.DataFrame] = []
    d = panel.copy()
    d["date"] = pd.to_datetime(d["date"]).dt.normalize().astype("datetime64[ns]")
    for symbol, one_symbol in d.sort_values(["symbol", "date"]).groupby("symbol", sort=False):
        one_factors = factors[factors["symbol"] == symbol]
        if one_factors.empty:
            frames.append(one_symbol)
            continue
        one_symbol = one_symbol.copy()
        one_symbol["date"] = pd.to_datetime(one_symbol["date"]).dt.normalize().astype("datetime64[ns]")
        one_factors = one_factors.copy()
        one_factors["available_date"] = (
            pd.to_datetime(one_factors["available_date"], errors="coerce").dt.normalize().astype("datetime64[ns]")
        )
        merged = pd.merge_asof(
            one_symbol.sort_values("date"),
            one_factors.drop(columns=["symbol"]).sort_values("available_date"),
            left_on="date",
            right_on="available_date",
            direction="backward",
        )
        frames.append(merged)
    if not frames:
        return d
    return pd.concat(frames, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)


def _rank_pct_by_date(d: pd.DataFrame, column: str, *, ascending: bool = True) -> pd.Series:
    if column not in d.columns:
        return pd.Series(np.nan, index=d.index)
    return d.groupby("date")[column].rank(method="average", pct=True, ascending=ascending)


def _clip_numeric(series: pd.Series, bounds: list[Any] | tuple[Any, Any] | None) -> pd.Series:
    out = pd.to_numeric(series, errors="coerce")
    if not bounds or len(bounds) != 2:
        return out
    return out.clip(lower=float(bounds[0]), upper=float(bounds[1]))


def _add_quality_growth_features(panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
    if panel.empty:
        return panel
    lcfg = strategy_cfg.get("local_factor", {})
    qcfg = lcfg.get("quality_growth", {})
    if not qcfg.get("enabled", False):
        return panel

    d = _add_point_in_time_financial_factors(panel, strategy_cfg)
    if d.empty:
        return d
    for col in FINANCIAL_FACTOR_COLUMNS:
        if col not in d.columns:
            d[col] = np.nan

    d["_roe_score"] = _rank_pct_by_date(d, "roe")
    d["_cash_flow_quality_clipped"] = _clip_numeric(
        d["cash_flow_quality"],
        qcfg.get("cash_flow_quality_clip", [-5, 5]),
    )
    d["_profit_growth_clipped"] = _clip_numeric(d["profit_growth"], qcfg.get("growth_clip", [-100, 300]))
    d["_revenue_growth_clipped"] = _clip_numeric(d["revenue_growth"], qcfg.get("growth_clip", [-100, 300]))
    d["_debt_to_asset_clipped"] = _clip_numeric(d["debt_to_asset"], qcfg.get("debt_to_asset_clip", [0, 100]))
    d["_cash_flow_score"] = _rank_pct_by_date(d, "_cash_flow_quality_clipped")
    d["_profit_growth_score"] = _rank_pct_by_date(d, "_profit_growth_clipped")
    d["_revenue_growth_score"] = _rank_pct_by_date(d, "_revenue_growth_clipped")
    d["_low_debt_score"] = _rank_pct_by_date(d, "_debt_to_asset_clipped", ascending=False)

    weights = qcfg.get("weights", {})
    roe_weight = float(weights.get("roe", 0.30))
    cash_flow_weight = float(weights.get("cash_flow_quality", 0.20))
    profit_growth_weight = float(weights.get("profit_growth", 0.20))
    revenue_growth_weight = float(weights.get("revenue_growth", 0.15))
    low_debt_weight = float(weights.get("low_debt", 0.15))
    d["financial_available_fields"] = d[FINANCIAL_FACTOR_COLUMNS].notna().sum(axis=1)
    score_weights = {
        "_roe_score": roe_weight,
        "_cash_flow_score": cash_flow_weight,
        "_profit_growth_score": profit_growth_weight,
        "_revenue_growth_score": revenue_growth_weight,
        "_low_debt_score": low_debt_weight,
    }
    weighted_sum = pd.Series(0.0, index=d.index)
    available_weight = pd.Series(0.0, index=d.index)
    for col, weight in score_weights.items():
        values = d[col]
        present = values.notna()
        weighted_sum = weighted_sum.add(values.fillna(0.0) * weight, fill_value=0.0)
        available_weight = available_weight.add(present.astype(float) * weight, fill_value=0.0)
    d["quality_growth_score"] = weighted_sum / available_weight.replace(0, np.nan)
    min_available_fields = int(qcfg.get("min_available_fields", 4))
    d.loc[d["financial_available_fields"] < min_available_fields, "quality_growth_score"] = np.nan
    if "announce_date" in d.columns and "financial_announce_date" not in d.columns:
        d["financial_announce_date"] = d["announce_date"]
    return d


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
    window_cfg: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    panel = _align_symbol_map(_load_symbol_map(symbols, years=years))
    if panel.empty:
        return []
    panel = _add_cross_market_to_panel(panel, years, strategy_cfg, xfeatures)

    rows: list[dict[str, Any]] = []
    fold_windows = _date_window_slices(
        panel["date"].dropna().tolist(),
        train_years=train_years,
        validate_years=validate_years,
        min_samples=min_samples,
        start_date=(window_cfg or {}).get("start_date"),
        end_date=(window_cfg or {}).get("end_date"),
    )
    for fold_idx, train_dates, valid_dates in fold_windows:
        train = panel[panel["date"].isin(train_dates)].copy()
        valid = panel[panel["date"].isin(valid_dates)].copy()

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
    window_cfg: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    panel = _align_symbol_map(_load_symbol_map(symbols, years=years))
    if panel.empty:
        return []
    panel = _add_cross_market_to_panel(panel, years, strategy_cfg, xfeatures)

    rows: list[dict[str, Any]] = []
    fold_windows = _date_window_slices(
        panel["date"].dropna().tolist(),
        train_years=train_years,
        validate_years=validate_years,
        min_samples=min_samples,
        start_date=(window_cfg or {}).get("start_date"),
        end_date=(window_cfg or {}).get("end_date"),
    )
    for fold_idx, train_dates, valid_dates in fold_windows:
        train = panel[panel["date"].isin(train_dates)].copy()
        valid = panel[panel["date"].isin(valid_dates)].copy()

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
    window_cfg: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    panel = _align_symbol_map(_load_symbol_map(symbols, years=years))
    if panel.empty:
        return []
    panel = _add_cross_market_to_panel(panel, years, strategy_cfg, xfeatures)

    rows: list[dict[str, Any]] = []
    fold_windows = _date_window_slices(
        panel["date"].dropna().tolist(),
        train_years=train_years,
        validate_years=validate_years,
        min_samples=min_samples,
        start_date=(window_cfg or {}).get("start_date"),
        end_date=(window_cfg or {}).get("end_date"),
    )
    for fold_idx, train_dates, valid_dates in fold_windows:
        train = panel[panel["date"].isin(train_dates)].copy()
        valid = panel[panel["date"].isin(valid_dates)].copy()

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
    return rows


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    df = pd.DataFrame(rows)
    if df.empty:
        return {"fold_count": 0, "symbol_count": 0, "panel_scope": "", "annualized_return_mean": 0.0, "sharpe_mean": 0.0, "max_drawdown_mean": 0.0}
    panel_scope = str(df["panel_scope"].dropna().iloc[0]) if "panel_scope" in df.columns and df["panel_scope"].notna().any() else ""
    return {
        "fold_count": int(len(df)),
        "symbol_count": int(df["symbol"].nunique()) if "symbol" in df.columns else 0,
        "panel_scope": panel_scope,
        "annualized_return_mean": float(df["annualized_return"].mean()),
        "sharpe_mean": float(df["sharpe"].mean()),
        "max_drawdown_mean": float(df["max_drawdown"].mean()),
        "win_rate_mean": float(df["win_rate"].mean()),
        "turnover_annual_mean": float(df["turnover_annual"].mean()),
    }


def _candidate_raw_score(summary: dict[str, Any]) -> float:
    if int(summary.get("fold_count", 0)) == 0:
        return -1_000_000.0
    return (
        float(summary.get("sharpe_mean", 0.0))
        + float(summary.get("annualized_return_mean", 0.0)) * 0.5
        + max(float(summary.get("max_drawdown_mean", 0.0)), -1.0) * 0.5
    )


def _candidate_governance(summary: dict[str, Any], governance_cfg: dict[str, Any]) -> tuple[bool, str]:
    if not bool(governance_cfg.get("enabled", True)):
        return True, "governance_disabled"

    fold_count = int(summary.get("fold_count", 0))
    symbol_count = int(summary.get("symbol_count", 0))
    panel_scope = str(summary.get("panel_scope", ""))
    selection_panel_scope = str(governance_cfg.get("selection_panel_scope", "") or "")
    if selection_panel_scope and panel_scope != selection_panel_scope:
        return False, f"panel_scope!={selection_panel_scope}"
    if panel_scope == "portfolio":
        min_portfolio_fold_count = int(governance_cfg.get("min_portfolio_fold_count", 4))
        if fold_count < min_portfolio_fold_count:
            return False, f"portfolio_fold_count<{min_portfolio_fold_count}"
        return True, "eligible"

    min_fold_count = int(governance_cfg.get("min_fold_count", 20))
    min_symbol_count = int(governance_cfg.get("min_symbol_count", 20))
    failed = []
    if fold_count < min_fold_count:
        failed.append(f"fold_count<{min_fold_count}")
    if symbol_count < min_symbol_count:
        failed.append(f"symbol_count<{min_symbol_count}")
    if failed:
        return False, ",".join(failed)
    return True, "eligible"


def _candidate_selection_score(summary: dict[str, Any], governance_cfg: dict[str, Any]) -> float:
    eligible, _ = _candidate_governance(summary, governance_cfg)
    if not eligible:
        return -1_000_000.0
    return _candidate_raw_score(summary)


def _candidate_summary_rows(summaries: dict[str, dict[str, Any]], governance_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, summary in summaries.items():
        eligible, reason = _candidate_governance(summary, governance_cfg)
        rows.append(
            {
                "candidate": name,
                "score": _candidate_raw_score(summary),
                "selection_score": _candidate_selection_score(summary, governance_cfg),
                "eligible_for_selection": eligible,
                "governance_reason": reason,
                "fold_count": int(summary.get("fold_count", 0)),
                "symbol_count": int(summary.get("symbol_count", 0)),
                "panel_scope": str(summary.get("panel_scope", "")),
                "annualized_return_mean": float(summary.get("annualized_return_mean", 0.0)),
                "sharpe_mean": float(summary.get("sharpe_mean", 0.0)),
                "max_drawdown_mean": float(summary.get("max_drawdown_mean", 0.0)),
                "win_rate_mean": float(summary.get("win_rate_mean", 0.0)),
                "turnover_annual_mean": float(summary.get("turnover_annual_mean", 0.0)),
            }
        )
    return sorted(rows, key=lambda row: row["selection_score"], reverse=True)


def _resolve_compare_strategies(strategy_cfg: dict[str, Any]) -> list[str]:
    configured = strategy_cfg.get("compare_strategies")
    if configured:
        return [str(name) for name in configured]

    names = ["legacy_momentum"]
    if strategy_cfg.get("mode") != "compare":
        return names
    if strategy_cfg.get("local_factor", {}).get("enabled", False):
        names.append("residual_momentum_reversal_v1")
    return names


def _normalize_strategy_output(
    result: StrategyOutput | tuple[pd.Series, pd.Series],
    panel: pd.DataFrame,
    strategy_name: str,
    params: dict[str, Any],
) -> StrategyOutput:
    strategy = get_strategy(strategy_name)
    if isinstance(result, StrategyOutput):
        signal_frame = _merge_signal_metadata(result.signal_frame, panel)
        return StrategyOutput(
            returns=result.returns,
            exposure=result.exposure,
            signal_frame=signal_frame,
            metadata=result.metadata,
        )

    returns, exposure = result
    d = panel.copy()
    if strategy.panel_scope == "symbol":
        d["score"] = d.get("mom5", pd.Series(np.nan, index=d.index))
    else:
        d["score"] = d.get("rank_score", pd.Series(np.nan, index=d.index))
    d["selected"] = exposure.shift(-1).fillna(0.0).gt(0).astype(float)
    d["raw_weight"] = d["selected"]
    d["weight"] = exposure
    d["position_ret"] = returns
    signal_frame = d[
        [
            c
            for c in [
                "date",
                "symbol",
                "score",
                "selected",
                "raw_weight",
                "weight",
                "ret",
                "position_ret",
                "industry",
                "name",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "amount",
                "previous_close",
            ]
            if c in d.columns
        ]
    ].copy()
    return StrategyOutput(
        returns=returns,
        exposure=exposure,
        signal_frame=signal_frame,
        metadata=strategy.build_metadata(params),
    )


def _merge_signal_metadata(signal_frame: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    if signal_frame is None or signal_frame.empty or panel.empty:
        return signal_frame
    if "symbol" not in signal_frame.columns or "symbol" not in panel.columns:
        return signal_frame

    signal = signal_frame.copy()
    signal["symbol"] = signal["symbol"].astype(str)
    price_cols = ["open", "high", "low", "close", "volume", "amount", "previous_close"]
    merge_cols = ["industry", "name"]
    if "date" in signal.columns and "date" in panel.columns:
        merge_cols.extend(price_cols)
    meta_cols = [col for col in ["date", "symbol", *merge_cols] if col in panel.columns]
    if "symbol" not in meta_cols or len(meta_cols) <= 1:
        return signal

    meta = panel[meta_cols].copy()
    meta["symbol"] = meta["symbol"].astype(str)
    if "date" in signal.columns and "date" in meta.columns:
        signal["date"] = pd.to_datetime(signal["date"], errors="coerce").dt.normalize()
        meta["date"] = pd.to_datetime(meta["date"], errors="coerce").dt.normalize()
        join_cols = ["date", "symbol"]
    else:
        meta = meta.drop(columns=["date"], errors="ignore")
        join_cols = ["symbol"]
    meta = meta.drop_duplicates(join_cols)
    if meta.empty:
        return signal

    merged = signal.merge(meta.rename(columns={col: f"__meta_{col}" for col in meta.columns if col not in join_cols}), on=join_cols, how="left")
    for col in ["industry", "name", *price_cols]:
        meta_col = f"__meta_{col}"
        if meta_col not in merged.columns:
            continue
        if col not in merged.columns:
            merged[col] = merged[meta_col]
        else:
            current = merged[col]
            missing = current.isna() | current.astype(str).str.strip().eq("")
            merged[col] = current.where(~missing, merged[meta_col])
    return merged.drop(columns=[col for col in merged.columns if col.startswith("__meta_")])
def _date_window_slices(
    dates: list[Any],
    train_years: int,
    validate_years: int,
    min_samples: int,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
) -> list[tuple[int, set[pd.Timestamp], set[pd.Timestamp]]]:
    normalized = sorted(pd.to_datetime(pd.Series(dates).dropna()).dt.normalize().unique())
    rows: list[tuple[int, set[pd.Timestamp], set[pd.Timestamp]]] = []
    if not normalized:
        return rows
    configured_start = _parse_optional_date(start_date)
    configured_end = _parse_optional_date(end_date)
    if configured_start is not None:
        lower = pd.Timestamp(configured_start).normalize()
        normalized = [value for value in normalized if pd.Timestamp(value).normalize() >= lower]
    if configured_end is not None:
        upper = pd.Timestamp(configured_end).normalize()
        normalized = [value for value in normalized if pd.Timestamp(value).normalize() <= upper]
    if not normalized:
        return rows
    first_date = pd.Timestamp(configured_start).normalize() if configured_start is not None else pd.Timestamp(normalized[0]).normalize()
    train_start = first_date
    fold_idx = 0
    while True:
        train_end_exclusive = (train_start + pd.DateOffset(years=int(train_years))).normalize()
        valid_start = train_end_exclusive
        valid_end_exclusive = (valid_start + pd.DateOffset(years=int(validate_years))).normalize()
        # 窗口边界按自然日期滚动，再用交易日历过滤；不再用固定 252 个交易日近似一年。
        train_dates = {
            pd.Timestamp(value).normalize()
            for value in normalized
            if train_start <= pd.Timestamp(value).normalize() < train_end_exclusive
        }
        valid_dates = {
            pd.Timestamp(value).normalize()
            for value in normalized
            if valid_start <= pd.Timestamp(value).normalize() < valid_end_exclusive
        }
        if len(train_dates) < min_samples or len(valid_dates) < min_samples // 2:
            break
        fold_idx += 1
        rows.append((fold_idx, train_dates, valid_dates))
        train_start = (train_start + pd.DateOffset(years=int(validate_years))).normalize()
    return rows


def _price_adjustment_mode(config: dict[str, Any]) -> str:
    local_cfg = config.get("local_history", {})
    adjust_type = str(local_cfg.get("adjust_type", "qfq"))
    return str(local_cfg.get("price_adjustment_for_backtest", "qfq_current" if adjust_type == "qfq" else adjust_type))


def _strict_qfq_asof_enabled(config: dict[str, Any]) -> bool:
    return _price_adjustment_mode(config) == "qfq_asof"


def _build_account_execution_config(
    config: dict[str, Any],
    wcfg: dict[str, Any],
    strategy_cfg: dict[str, Any],
) -> SimulatedAccountConfig | None:
    cfg = strategy_cfg.get("account_execution", {})
    if not bool(cfg.get("enabled", False)):
        return None
    execution_cfg = config.get("execution", {})
    return SimulatedAccountConfig(
        account_id="walk_forward_fold",
        name="Walk-forward fold execution profile",
        initial_cash=float(cfg.get("initial_cash", wcfg.get("initial_cash", 1_000_000))),
        ledger_path=Path(""),
        database_path=Path(""),
        enabled=True,
        execution_price_mode=str(cfg.get("execution_price_mode", execution_cfg.get("price_mode", "next_open"))),
        max_participation_rate=float(cfg.get("max_participation_rate", execution_cfg.get("max_participation_rate", 0.05))),
        lot_size=int(cfg.get("lot_size", execution_cfg.get("lot_size", 100))),
        commission=float(cfg.get("commission", wcfg.get("commission", 0.0))),
        stamp_duty_sell=float(cfg.get("stamp_duty_sell", wcfg.get("stamp_duty_sell", 0.0))),
        slippage=float(cfg.get("slippage", wcfg.get("slippage", 0.0))),
        conservative_price_buffer=float(cfg.get("conservative_price_buffer", execution_cfg.get("conservative_price_buffer", 0.001))),
        enable_limit_check=bool(cfg.get("enable_limit_check", execution_cfg.get("enable_limit_check", True))),
        enable_suspension_check=bool(cfg.get("enable_suspension_check", execution_cfg.get("enable_suspension_check", True))),
        limit_up_down_pct={
            "default": float(execution_cfg.get("limit_up_down_pct", {}).get("default", 0.10)),
            "star": float(execution_cfg.get("limit_up_down_pct", {}).get("star", 0.20)),
            "chinext": float(execution_cfg.get("limit_up_down_pct", {}).get("chinext", 0.20)),
            "bj": float(execution_cfg.get("limit_up_down_pct", {}).get("bj", 0.30)),
        },
    )


def _account_execution_metrics(output: StrategyOutput, account: SimulatedAccountConfig | None, panel_scope: str) -> dict[str, Any]:
    if account is None:
        return {"account_execution_status": "not_enabled", "account_execution_enabled": False}
    if panel_scope != "portfolio":
        return {"account_execution_status": "not_applicable", "account_execution_enabled": False}
    result = run_signal_account_execution(signal_frame=output.signal_frame, account=account)
    return {"account_execution_status": "enabled", **result.metrics}


def _quality_signal_diagnostics(output: StrategyOutput, strategy_name: str) -> dict[str, Any]:
    signal = output.signal_frame
    if strategy_name not in FINANCIAL_DIAGNOSTIC_STRATEGIES:
        return {"financial_diagnostic_status": "not_applicable"}
    if signal is None or signal.empty or "financial_available_fields" not in signal.columns:
        return {"financial_diagnostic_status": "not_available"}
    total = len(signal)
    selected = signal[pd.to_numeric(signal.get("weight_unshifted", 0.0), errors="coerce").fillna(0.0) > 0].copy()
    financial_fields = pd.to_numeric(signal["financial_available_fields"], errors="coerce")
    selected_fields = pd.to_numeric(selected.get("financial_available_fields", pd.Series(dtype=float)), errors="coerce")
    component_cols = [
        "quality_roe_component",
        "quality_cash_flow_component",
        "quality_profit_growth_component",
        "quality_revenue_growth_component",
        "quality_low_debt_component",
    ]
    component_coverage = {
        col.replace("quality_", "").replace("_component", "_coverage"): float(pd.to_numeric(signal[col], errors="coerce").notna().mean())
        for col in component_cols
        if col in signal.columns
    }
    selected_component_means = {
        f"selected_{col}_mean": float(pd.to_numeric(selected[col], errors="coerce").mean())
        for col in component_cols
        if col in selected.columns and not selected.empty
    }
    score = pd.to_numeric(signal.get("quality_growth_score", pd.Series(dtype=float)), errors="coerce")
    selected_score = pd.to_numeric(selected.get("quality_growth_score", pd.Series(dtype=float)), errors="coerce")
    min_required_fields = int((financial_fields[score.notna()].min() if score.notna().any() else 4) or 4)
    missing_quality_rows = int((financial_fields < min_required_fields).sum()) if total else 0
    announce_col = signal.get("financial_announce_date")
    announce_coverage = 0.0
    if announce_col is not None:
        announce = pd.Series(announce_col)
        announce_coverage = float((announce.notna() & announce.astype(str).str.strip().ne("")).mean())
    selected_announce_coverage = 0.0
    if "financial_announce_date" in selected.columns and not selected.empty:
        announce = selected["financial_announce_date"]
        selected_announce_coverage = float((announce.notna() & announce.astype(str).str.strip().ne("")).mean())
    return {
        "financial_diagnostic_status": "available",
        "quality_explain_rows": int(total),
        "quality_selected_rows": int(len(selected)),
        "financial_pit_announce_coverage": announce_coverage,
        "selected_financial_pit_announce_coverage": selected_announce_coverage,
        "financial_field_coverage_mean": float(financial_fields.mean() / len(FINANCIAL_FACTOR_COLUMNS)) if total else 0.0,
        "selected_financial_field_coverage_mean": float(selected_fields.mean() / len(FINANCIAL_FACTOR_COLUMNS)) if len(selected_fields) else 0.0,
        "financial_missing_blocked_ratio": float(missing_quality_rows / total) if total else 0.0,
        "quality_score_mean": float(score.mean()) if score.notna().any() else 0.0,
        "selected_quality_score_mean": float(selected_score.mean()) if selected_score.notna().any() else 0.0,
        "selected_quality_score_lift": float(selected_score.mean() - score.mean()) if selected_score.notna().any() and score.notna().any() else 0.0,
        **component_coverage,
        **selected_component_means,
    }


def _build_panel_for_fold_asof(
    symbols: list[str],
    *,
    years: int,
    train_dates: set[pd.Timestamp],
    valid_dates: set[pd.Timestamp],
    train_as_of_date: date,
    valid_as_of_date: date,
    strategy_cfg: dict[str, Any],
    xfeatures: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_panel = _align_symbol_map(_load_symbol_map(symbols, years=years, as_of_date=train_as_of_date))
    valid_panel = _align_symbol_map(_load_symbol_map(symbols, years=years, as_of_date=valid_as_of_date))
    if train_panel.empty or valid_panel.empty:
        return pd.DataFrame(), pd.DataFrame()
    train_panel["date"] = pd.to_datetime(train_panel["date"]).dt.normalize()
    valid_panel["date"] = pd.to_datetime(valid_panel["date"]).dt.normalize()
    train_panel = train_panel[train_panel["date"].isin(train_dates)].copy()
    valid_panel = valid_panel[valid_panel["date"].isin(valid_dates)].copy()
    if train_panel.empty or valid_panel.empty:
        return train_panel, valid_panel
    train_panel = _add_cross_market_to_panel(train_panel, years, strategy_cfg, xfeatures)
    valid_panel = _add_cross_market_to_panel(valid_panel, years, strategy_cfg, xfeatures)
    return train_panel, valid_panel


def _empty_pit_fold_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "fold",
            "universe_as_of_date",
            "universe_symbol_count",
            "universe_snapshot_count",
            "universe_source",
            "train_start",
            "train_end",
            "valid_start",
            "valid_end",
            "warning",
        ]
    )


def iter_point_in_time_universe_folds(
    config: dict[str, Any],
    *,
    years: int,
    train_years: int,
    validate_years: int,
    min_samples: int,
    strategy_cfg: dict[str, Any],
    xfeatures: pd.DataFrame | None = None,
    window_cfg: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    """Build read-only, fold-local panels from historical point-in-time universes."""
    window_cfg = window_cfg or {}
    explicit_start = _parse_optional_date(window_cfg.get("start_date"))
    explicit_end = _parse_optional_date(window_cfg.get("end_date"))
    end = explicit_end or date.today()
    start = explicit_start or (end - timedelta(days=365 * int(years) + 30))
    trading_dates = load_trading_dates_from_local_history(start, end)
    fold_windows = _date_window_slices(
        trading_dates,
        train_years=train_years,
        validate_years=validate_years,
        min_samples=min_samples,
        start_date=explicit_start,
        end_date=explicit_end,
    )
    if not fold_windows:
        return [], _empty_pit_fold_frame()

    root = Path.cwd()
    contexts: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    universe_cfg = config.get("universe", {})
    min_usable = int(universe_cfg.get("min_usable_size", min(100, universe_cfg.get("target_size", 500))))
    use_strict_asof = _strict_qfq_asof_enabled(config)

    for fold_idx, train_dates, valid_dates in fold_windows:
        train_end_date = pd.Timestamp(max(train_dates)).date()
        train_start_date = pd.Timestamp(min(train_dates)).date()
        valid_start_date = pd.Timestamp(min(valid_dates)).date()
        valid_end_date = pd.Timestamp(max(valid_dates)).date()
        universe = load_point_in_time_universe(config, root, train_end_date)
        warnings = list(universe.warnings)
        audit = {
            "fold": fold_idx,
            "universe_as_of_date": universe.as_of_date,
            "universe_symbol_count": universe.selected_count,
            "universe_snapshot_count": universe.snapshot_count,
            "universe_source": universe.source,
            "train_start": train_start_date.isoformat(),
            "train_end": train_end_date.isoformat(),
            "valid_start": valid_start_date.isoformat(),
            "valid_end": valid_end_date.isoformat(),
            "warning": "; ".join(warnings),
        }
        if len(universe.symbols) < min_usable:
            audit_rows.append({**audit, "warning": "; ".join(warnings + ["fold skipped: universe below min_usable_size"])})
            continue

        if use_strict_asof:
            train, valid = _build_panel_for_fold_asof(
                universe.symbols,
                years=years,
                train_dates=train_dates,
                valid_dates=valid_dates,
                train_as_of_date=train_end_date,
                valid_as_of_date=valid_end_date,
                strategy_cfg=strategy_cfg,
                xfeatures=xfeatures,
            )
        else:
            panel = _align_symbol_map(_load_symbol_map(universe.symbols, years=years))
            if panel.empty:
                audit_rows.append({**audit, "warning": "; ".join(warnings + ["fold skipped: empty price panel"])})
                continue
            panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
            panel = panel[panel["date"].isin(train_dates | valid_dates)].copy()
            if panel.empty:
                audit_rows.append({**audit, "warning": "; ".join(warnings + ["fold skipped: panel has no fold dates"])})
                continue
            panel = _add_cross_market_to_panel(panel, years, strategy_cfg, xfeatures)
            train = panel[panel["date"].isin(train_dates)].copy()
            valid = panel[panel["date"].isin(valid_dates)].copy()
        if train.empty or valid.empty:
            audit_rows.append({**audit, "warning": "; ".join(warnings + ["fold skipped: empty as-of price panel" if use_strict_asof else "fold skipped: empty price panel"])})
            continue
        if train["date"].nunique() < min_samples or valid["date"].nunique() < min_samples // 2:
            audit_rows.append({**audit, "warning": "; ".join(warnings + ["fold skipped: insufficient train/valid samples"])})
            continue
        train = _add_fold_metadata(train, universe.universe)
        valid = _add_fold_metadata(valid, universe.universe)

        audit["price_adjustment_for_backtest"] = _price_adjustment_mode(config)
        audit["train_price_as_of_date"] = train_end_date.isoformat() if use_strict_asof else ""
        audit["valid_price_as_of_date"] = valid_end_date.isoformat() if use_strict_asof else ""
        audit_rows.append(audit)
        contexts.append(
            {
                "fold": fold_idx,
                "train": train,
                "valid": valid,
                "symbols": universe.symbols,
                "universe": universe,
                "audit": audit,
            }
        )

    return contexts, pd.DataFrame(audit_rows)


def _run_strategy_on_explicit_fold(
    strategy_name: str,
    *,
    fold: int,
    train: pd.DataFrame,
    valid: pd.DataFrame,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
    strategy_cfg: dict[str, Any],
    account_execution: SimulatedAccountConfig | None = None,
    extra: dict[str, Any] | None = None,
    trace_callback: TraceCallback | None = None,
) -> list[dict[str, Any]]:
    strategy = get_strategy(strategy_name)
    if not strategy.is_enabled(strategy_cfg):
        return []
    if train.empty or valid.empty:
        return []

    prepared = strategy.prepare_panel(pd.concat([train, valid], ignore_index=True), strategy_cfg)
    if prepared.empty:
        return []
    prepared["date"] = pd.to_datetime(prepared["date"]).dt.normalize()
    train_dates = set(pd.to_datetime(train["date"]).dt.normalize().unique())
    valid_dates = set(pd.to_datetime(valid["date"]).dt.normalize().unique())
    fold_train = prepared[prepared["date"].isin(train_dates)].copy()
    fold_valid = prepared[prepared["date"].isin(valid_dates)].copy()
    if fold_train.empty or fold_valid.empty:
        return []

    _emit_trace(
        trace_callback,
        {
            "event": "fold_start",
            "strategy_id": strategy_name,
            "fold": int(fold),
            "panel_scope": strategy.panel_scope,
            "train_start": str(pd.Timestamp(fold_train["date"].min()).date()),
            "train_end": str(pd.Timestamp(fold_train["date"].max()).date()),
            "valid_start": str(pd.Timestamp(fold_valid["date"].min()).date()),
            "valid_end": str(pd.Timestamp(fold_valid["date"].max()).date()),
            "train_rows": int(len(fold_train)),
            "valid_rows": int(len(fold_valid)),
            "train_symbols": int(fold_train["symbol"].astype(str).nunique()) if "symbol" in fold_train.columns else 0,
            "valid_symbols": int(fold_valid["symbol"].astype(str).nunique()) if "symbol" in fold_valid.columns else 0,
        },
    )
    params = strategy.select_params(
        fold_train,
        strategy_cfg,
        slippage=slippage,
        commission=commission,
        stamp_duty_sell=stamp_duty_sell,
    )
    _emit_trace(
        trace_callback,
        {
            "event": "fold_params",
            "strategy_id": strategy_name,
            "fold": int(fold),
            "eligible": bool(params.get("eligible", True)),
            "formatted_params": strategy.format_params(params),
        },
    )
    result = strategy.apply(
        fold_valid,
        params,
        slippage=slippage,
        commission=commission,
        stamp_duty_sell=stamp_duty_sell,
    )
    output = _normalize_strategy_output(result, fold_valid, strategy_name, params)
    constraint_result = apply_strategy_constraints(
        output,
        strategy_name=strategy_name,
        panel_scope=strategy.panel_scope,
        strategy_cfg=strategy_cfg,
        panel=fold_valid,
        slippage=slippage,
        commission=commission,
        stamp_duty_sell=stamp_duty_sell,
    )
    output = constraint_result.output
    metric = _calc_metrics(output.returns, output.exposure)
    account_metrics = _account_execution_metrics(output, account_execution, strategy.panel_scope)
    quality_metrics = _quality_signal_diagnostics(output, strategy_name)
    meta = output.metadata or strategy.build_metadata(params)
    row = {
        "symbol": str(fold_valid["symbol"].iloc[0]) if strategy.panel_scope == "symbol" else "PORTFOLIO",
        "fold": fold,
        "train_start": str(pd.Timestamp(fold_train["date"].min()).date()),
        "train_end": str(pd.Timestamp(fold_train["date"].max()).date()),
        "valid_start": str(pd.Timestamp(fold_valid["date"].min()).date()),
        "valid_end": str(pd.Timestamp(fold_valid["date"].max()).date()),
        "annualized_return": metric["annualized_return"],
        "sharpe": metric["sharpe"],
        "max_drawdown": metric["max_drawdown"],
        "win_rate": metric["win_rate"],
        "turnover_annual": metric["turnover_annual"],
        "trades": metric["trades"],
        "passed_min_samples": True,
        "selected_params": meta.get("formatted_params", strategy.format_params(params)),
        "candidate": strategy.candidate_name,
        "strategy_id": meta.get("strategy_id", strategy.name),
        "strategy_display_name": meta.get("display_name", strategy.name),
        "strategy_category": meta.get("category", "generic"),
        "panel_scope": meta.get("panel_scope", strategy.panel_scope),
        "supports_brief": meta.get("supports_brief", True),
        "supports_paper_trade": meta.get("supports_paper_trade", True),
    }
    row.update(constraint_result.metrics)
    row.update(account_metrics)
    row.update(quality_metrics)
    trace_summary = _signal_trace_summary(output)
    row.update(trace_summary)
    _emit_trace(
        trace_callback,
        {
            "event": "fold_result",
            "strategy_id": strategy_name,
            "fold": int(fold),
            "annualized_return": float(metric["annualized_return"]),
            "sharpe": float(metric["sharpe"]),
            "max_drawdown": float(metric["max_drawdown"]),
            "turnover_annual": float(metric["turnover_annual"]),
            "trades": int(metric["trades"]),
            "constraint_mode": row.get("constraint_mode", ""),
            "constraint_status": row.get("constraint_status", ""),
            **trace_summary,
        },
    )
    if extra:
        row.update(extra)
    return [row]


def _run_strategy_on_symbol_panel(
    strategy_name: str,
    panel: pd.DataFrame,
    *,
    years: int,
    train_years: int,
    validate_years: int,
    min_samples: int,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
    strategy_cfg: dict[str, Any],
    account_execution: SimulatedAccountConfig | None = None,
    window_cfg: dict[str, Any] | None = None,
    trace_callback: TraceCallback | None = None,
) -> list[dict[str, Any]]:
    strategy = get_strategy(strategy_name)
    if not strategy.is_enabled(strategy_cfg):
        return []
    panel = strategy.prepare_panel(panel, strategy_cfg)
    if panel.empty:
        return []

    # walk-forward 模拟滚动实盘：每一折只用历史训练窗选参数，再把规则前推到紧随其后的验证窗。
    rows: list[dict[str, Any]] = []
    fold_windows = _date_window_slices(
        panel["date"].dropna().tolist(),
        train_years=train_years,
        validate_years=validate_years,
        min_samples=min_samples,
        start_date=(window_cfg or {}).get("start_date"),
        end_date=(window_cfg or {}).get("end_date"),
    )
    for fold_idx, train_dates, valid_dates in fold_windows:
        train = panel[panel["date"].isin(train_dates)].copy()
        valid = panel[panel["date"].isin(valid_dates)].copy()

        # 选参阶段只能“看见”训练窗，验证窗用固定参数执行，避免事后挑最优。
        params = strategy.select_params(
            train,
            strategy_cfg,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
        )
        result = strategy.apply(
            valid,
            params,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
        )
        output = _normalize_strategy_output(result, valid, strategy_name, params)
        constraint_result = apply_strategy_constraints(
            output,
            strategy_name=strategy_name,
            panel_scope=strategy.panel_scope,
            strategy_cfg=strategy_cfg,
            panel=valid,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
        )
        output = constraint_result.output
        # 验证窗输出每日收益和持仓暴露，再汇总为年化收益、Sharpe、回撤、胜率和换手等指标。
        metric = _calc_metrics(output.returns, output.exposure)
        account_metrics = _account_execution_metrics(output, account_execution, strategy.panel_scope)
        quality_metrics = _quality_signal_diagnostics(output, strategy_name)
        meta = output.metadata or strategy.build_metadata(params)
        trace_summary = _signal_trace_summary(output)
        rows.append(
            {
                "symbol": str(valid["symbol"].iloc[0]) if strategy.panel_scope == "symbol" else "PORTFOLIO",
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
                "selected_params": meta.get("formatted_params", strategy.format_params(params)),
                "candidate": strategy.candidate_name,
                "strategy_id": meta.get("strategy_id", strategy.name),
                "strategy_display_name": meta.get("display_name", strategy.name),
                "strategy_category": meta.get("category", "generic"),
                "panel_scope": meta.get("panel_scope", strategy.panel_scope),
                "supports_brief": meta.get("supports_brief", True),
                "supports_paper_trade": meta.get("supports_paper_trade", True),
                **constraint_result.metrics,
                **account_metrics,
                **quality_metrics,
                **trace_summary,
            }
        )
        _emit_trace(
            trace_callback,
            {
                "event": "fold_result",
                "strategy_id": strategy_name,
                "fold": int(fold_idx),
                "symbol": str(valid["symbol"].iloc[0]) if "symbol" in valid.columns and not valid.empty else "",
                "annualized_return": float(metric["annualized_return"]),
                "sharpe": float(metric["sharpe"]),
                "max_drawdown": float(metric["max_drawdown"]),
                "turnover_annual": float(metric["turnover_annual"]),
                "trades": int(metric["trades"]),
                "constraint_mode": constraint_result.metrics.get("constraint_mode", ""),
                "constraint_status": constraint_result.metrics.get("constraint_status", ""),
                **trace_summary,
            },
        )
    return rows


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
    account_execution: SimulatedAccountConfig | None = None,
    window_cfg: dict[str, Any] | None = None,
    trace_callback: TraceCallback | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: dict[str, list[dict[str, Any]]] = {}
    # compare 模式先准备可复用的外盘特征，保证多个候选策略面对同一份外部市场信息。
    xfeatures = _load_cross_market_features(years, strategy_cfg.get("cross_market", {})) if _xmarket_enabled(strategy_cfg) else None
    compare_strategies = _resolve_compare_strategies(strategy_cfg)

    combined_panel: pd.DataFrame | None = None
    current_metadata = _load_current_symbol_metadata(symbols)
    # 逐个候选策略跑同一套滚动回测；单票策略逐只测，组合策略用同一横截面股票池测。
    for strategy_name in compare_strategies:
        if strategy_name not in available_strategies():
            continue
        strategy_rows: list[dict[str, Any]] = []
        strategy = get_strategy(strategy_name)
        if strategy.panel_scope == "symbol":
            for sym in symbols:
                panel = _load_symbol(sym, years=years)
                if panel.empty:
                    continue
                panel = panel.assign(symbol=sym)
                strategy_rows.extend(
                    _run_strategy_on_symbol_panel(
                        strategy_name,
                        panel,
                        years=years,
                        train_years=train_years,
                        validate_years=validate_years,
                        min_samples=min_samples,
                        slippage=slippage,
                        commission=commission,
                        stamp_duty_sell=stamp_duty_sell,
                        strategy_cfg=strategy_cfg,
                        account_execution=account_execution,
                        window_cfg=window_cfg,
                        trace_callback=trace_callback,
                    )
                )
        else:
            if combined_panel is None:
                # 组合策略需要同日横截面排名，因此先把所有股票行情合并成一个 panel。
                combined_panel = _align_symbol_map(_load_symbol_map(symbols, years=years))
                if not combined_panel.empty:
                    combined_panel = _add_fold_metadata(combined_panel, current_metadata)
                    combined_panel = _add_cross_market_to_panel(combined_panel, years, strategy_cfg, xfeatures)
            if combined_panel is None or combined_panel.empty:
                candidates[strategy.candidate_name] = []
                continue
            strategy_rows.extend(
                _run_strategy_on_symbol_panel(
                    strategy_name,
                    combined_panel,
                    years=years,
                    train_years=train_years,
                    validate_years=validate_years,
                    min_samples=min_samples,
                    slippage=slippage,
                    commission=commission,
                    stamp_duty_sell=stamp_duty_sell,
                    strategy_cfg={**strategy_cfg, "mode": "portfolio"},
                    account_execution=account_execution,
                    window_cfg=window_cfg,
                    trace_callback=trace_callback,
                )
            )
        candidates[strategy.candidate_name] = strategy_rows

    candidates = {name: rows for name, rows in candidates.items() if rows}
    if not candidates:
        return [], [], []

    # 所有候选跑完后，先比较折均值，再按治理规则挑出 Phase 0 允许采用的主候选。
    summaries = {name: _summarize_rows(rows) for name, rows in candidates.items()}
    governance_cfg = strategy_cfg.get("candidate_governance", {})
    eligible_names = [name for name, summary in summaries.items() if _candidate_governance(summary, governance_cfg)[0]]
    if eligible_names:
        best_name = max(eligible_names, key=lambda name: _candidate_selection_score(summaries[name], governance_cfg))
    else:
        best_name = max(candidates, key=lambda name: _candidate_raw_score(summaries[name]))
    comparison = "; ".join(
        (
            f"{name}: score={_candidate_raw_score(summary):.4f}, "
            f"selection_score={_candidate_selection_score(summary, governance_cfg):.4f}, "
            f"eligible={_candidate_governance(summary, governance_cfg)[0]}, "
            f"ann={summary.get('annualized_return_mean', 0.0):.4f}, "
            f"sharpe={summary.get('sharpe_mean', 0.0):.4f}, "
            f"mdd={summary.get('max_drawdown_mean', 0.0):.4f}"
        )
        for name, summary in summaries.items()
    )
    candidate_summary_rows = _candidate_summary_rows(summaries, governance_cfg)
    selected = candidates[best_name]
    selected_eligible, selected_reason = _candidate_governance(summaries[best_name], governance_cfg)
    for row in selected:
        row["candidate_summary"] = comparison
        row["selected_candidate"] = best_name
        row["selected_candidate_eligible"] = selected_eligible
        row["selected_candidate_governance_reason"] = selected_reason
    all_candidate_rows: list[dict[str, Any]] = []
    for name, rows in candidates.items():
        candidate_eligible, candidate_reason = _candidate_governance(summaries[name], governance_cfg)
        for row in rows:
            enriched = dict(row)
            enriched["candidate_summary"] = comparison
            enriched["selected_candidate"] = best_name
            enriched["is_selected_candidate"] = name == best_name
            enriched["candidate_eligible_for_selection"] = candidate_eligible
            enriched["candidate_governance_reason"] = candidate_reason
            all_candidate_rows.append(enriched)
    return selected, all_candidate_rows, candidate_summary_rows


def _run_compare_qfq_asof_static(
    symbols: list[str],
    *,
    years: int,
    train_years: int,
    validate_years: int,
    min_samples: int,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
    strategy_cfg: dict[str, Any],
    account_execution: SimulatedAccountConfig | None = None,
    window_cfg: dict[str, Any] | None = None,
    trace_callback: TraceCallback | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], pd.DataFrame]:
    window_cfg = window_cfg or {}
    explicit_start = _parse_optional_date(window_cfg.get("start_date"))
    explicit_end = _parse_optional_date(window_cfg.get("end_date"))
    end = explicit_end or date.today()
    start = explicit_start or (end - timedelta(days=365 * int(years) + 30))
    trading_dates = load_trading_dates_from_local_history(start, end)
    fold_windows = _date_window_slices(
        trading_dates,
        train_years=train_years,
        validate_years=validate_years,
        min_samples=min_samples,
        start_date=explicit_start,
        end_date=explicit_end,
    )
    if not fold_windows:
        return [], [], [], _empty_pit_fold_frame()

    xfeatures = _load_cross_market_features(years, strategy_cfg.get("cross_market", {})) if _xmarket_enabled(strategy_cfg) else None
    compare_strategies = _resolve_compare_strategies(strategy_cfg)
    candidates: dict[str, list[dict[str, Any]]] = {}
    audit_rows: list[dict[str, Any]] = []

    for strategy_name in compare_strategies:
        if strategy_name not in available_strategies():
            continue
        strategy = get_strategy(strategy_name)
        candidates[strategy.candidate_name] = []

    for fold_idx, train_dates, valid_dates in fold_windows:
        train_end_date = pd.Timestamp(max(train_dates)).date()
        valid_end_date = pd.Timestamp(max(valid_dates)).date()
        train_panel, valid_panel = _build_panel_for_fold_asof(
            symbols,
            years=years,
            train_dates=train_dates,
            valid_dates=valid_dates,
            train_as_of_date=train_end_date,
            valid_as_of_date=valid_end_date,
            strategy_cfg=strategy_cfg,
            xfeatures=xfeatures,
        )
        audit = {
            "fold": fold_idx,
            "universe_as_of_date": train_end_date.isoformat(),
            "universe_symbol_count": len(symbols),
            "universe_snapshot_count": len(symbols),
            "universe_source": "static_config",
            "train_start": pd.Timestamp(min(train_dates)).date().isoformat(),
            "train_end": train_end_date.isoformat(),
            "valid_start": pd.Timestamp(min(valid_dates)).date().isoformat(),
            "valid_end": valid_end_date.isoformat(),
            "price_adjustment_for_backtest": "qfq_asof",
            "train_price_as_of_date": train_end_date.isoformat(),
            "valid_price_as_of_date": valid_end_date.isoformat(),
            "warning": "",
        }
        if train_panel.empty or valid_panel.empty:
            audit_rows.append({**audit, "warning": "fold skipped: empty as-of price panel"})
            continue
        if train_panel["date"].nunique() < min_samples or valid_panel["date"].nunique() < min_samples // 2:
            audit_rows.append({**audit, "warning": "fold skipped: insufficient train/valid samples"})
            continue
        current_metadata = _load_current_symbol_metadata(symbols)
        train_panel = _add_fold_metadata(train_panel, current_metadata)
        valid_panel = _add_fold_metadata(valid_panel, current_metadata)
        audit_rows.append(audit)
        for strategy_name in compare_strategies:
            if strategy_name not in available_strategies():
                continue
            strategy = get_strategy(strategy_name)
            extra = {
                "price_adjustment_for_backtest": "qfq_asof",
                "train_price_as_of_date": train_end_date.isoformat(),
                "valid_price_as_of_date": valid_end_date.isoformat(),
            }
            if strategy.panel_scope == "symbol":
                for sym in symbols:
                    train = train_panel[train_panel["symbol"] == sym].copy()
                    valid = valid_panel[valid_panel["symbol"] == sym].copy()
                    candidates[strategy.candidate_name].extend(
                        _run_strategy_on_explicit_fold(
                            strategy_name,
                            fold=fold_idx,
                            train=train,
                            valid=valid,
                            slippage=slippage,
                            commission=commission,
                            stamp_duty_sell=stamp_duty_sell,
                            strategy_cfg=strategy_cfg,
                            account_execution=account_execution,
                            extra=extra,
                            trace_callback=trace_callback,
                        )
                    )
            else:
                candidates[strategy.candidate_name].extend(
                    _run_strategy_on_explicit_fold(
                        strategy_name,
                        fold=fold_idx,
                        train=train_panel,
                        valid=valid_panel,
                        slippage=slippage,
                        commission=commission,
                        stamp_duty_sell=stamp_duty_sell,
                        strategy_cfg={**strategy_cfg, "mode": "portfolio"},
                        account_execution=account_execution,
                        extra=extra,
                        trace_callback=trace_callback,
                    )
                )

    candidates = {name: rows for name, rows in candidates.items() if rows}
    if not candidates:
        return [], [], [], pd.DataFrame(audit_rows)

    summaries = {name: _summarize_rows(rows) for name, rows in candidates.items()}
    governance_cfg = strategy_cfg.get("candidate_governance", {})
    eligible_names = [name for name, summary in summaries.items() if _candidate_governance(summary, governance_cfg)[0]]
    if eligible_names:
        best_name = max(eligible_names, key=lambda name: _candidate_selection_score(summaries[name], governance_cfg))
    else:
        best_name = max(candidates, key=lambda name: _candidate_raw_score(summaries[name]))
    comparison = "; ".join(
        (
            f"{name}: score={_candidate_raw_score(summary):.4f}, "
            f"selection_score={_candidate_selection_score(summary, governance_cfg):.4f}, "
            f"eligible={_candidate_governance(summary, governance_cfg)[0]}, "
            f"ann={summary.get('annualized_return_mean', 0.0):.4f}, "
            f"sharpe={summary.get('sharpe_mean', 0.0):.4f}, "
            f"mdd={summary.get('max_drawdown_mean', 0.0):.4f}"
        )
        for name, summary in summaries.items()
    )
    candidate_summary_rows = _candidate_summary_rows(summaries, governance_cfg)
    selected = candidates[best_name]
    selected_eligible, selected_reason = _candidate_governance(summaries[best_name], governance_cfg)
    for row in selected:
        row["candidate_summary"] = comparison
        row["selected_candidate"] = best_name
        row["selected_candidate_eligible"] = selected_eligible
        row["selected_candidate_governance_reason"] = selected_reason
    all_candidate_rows: list[dict[str, Any]] = []
    for name, rows in candidates.items():
        candidate_eligible, candidate_reason = _candidate_governance(summaries[name], governance_cfg)
        for row in rows:
            enriched = dict(row)
            enriched["candidate_summary"] = comparison
            enriched["selected_candidate"] = best_name
            enriched["is_selected_candidate"] = name == best_name
            enriched["candidate_eligible_for_selection"] = candidate_eligible
            enriched["candidate_governance_reason"] = candidate_reason
            all_candidate_rows.append(enriched)
    return selected, all_candidate_rows, candidate_summary_rows, pd.DataFrame(audit_rows)


def _run_compare_point_in_time(
    config: dict[str, Any],
    *,
    years: int,
    train_years: int,
    validate_years: int,
    min_samples: int,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
    strategy_cfg: dict[str, Any],
    account_execution: SimulatedAccountConfig | None = None,
    window_cfg: dict[str, Any] | None = None,
    trace_callback: TraceCallback | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], pd.DataFrame]:
    candidates: dict[str, list[dict[str, Any]]] = {}
    xfeatures = _load_cross_market_features(years, strategy_cfg.get("cross_market", {})) if _xmarket_enabled(strategy_cfg) else None
    fold_contexts, universe_audit = iter_point_in_time_universe_folds(
        config,
        years=years,
        train_years=train_years,
        validate_years=validate_years,
        min_samples=min_samples,
        strategy_cfg=strategy_cfg,
        xfeatures=xfeatures,
        window_cfg=window_cfg,
    )
    compare_strategies = _resolve_compare_strategies(strategy_cfg)

    for strategy_name in compare_strategies:
        if strategy_name not in available_strategies():
            continue
        strategy = get_strategy(strategy_name)
        strategy_rows: list[dict[str, Any]] = []
        for ctx in fold_contexts:
            extra = {
                "universe_mode": "point_in_time",
                "universe_as_of_date": ctx["audit"].get("universe_as_of_date", ""),
                "universe_symbol_count": ctx["audit"].get("universe_symbol_count", 0),
                "universe_snapshot_count": ctx["audit"].get("universe_snapshot_count", 0),
                "universe_source": ctx["audit"].get("universe_source", ""),
            }
            if strategy.panel_scope == "symbol":
                for sym in ctx["symbols"]:
                    train = ctx["train"][ctx["train"]["symbol"] == sym].copy()
                    valid = ctx["valid"][ctx["valid"]["symbol"] == sym].copy()
                    strategy_rows.extend(
                        _run_strategy_on_explicit_fold(
                            strategy_name,
                            fold=int(ctx["fold"]),
                            train=train,
                            valid=valid,
                            slippage=slippage,
                            commission=commission,
                            stamp_duty_sell=stamp_duty_sell,
                            strategy_cfg=strategy_cfg,
                            account_execution=account_execution,
                            extra=extra,
                            trace_callback=trace_callback,
                        )
                    )
            else:
                strategy_rows.extend(
                    _run_strategy_on_explicit_fold(
                        strategy_name,
                        fold=int(ctx["fold"]),
                        train=ctx["train"],
                        valid=ctx["valid"],
                        slippage=slippage,
                        commission=commission,
                        stamp_duty_sell=stamp_duty_sell,
                        strategy_cfg={**strategy_cfg, "mode": "portfolio"},
                        account_execution=account_execution,
                        extra=extra,
                        trace_callback=trace_callback,
                    )
                )
        candidates[strategy.candidate_name] = strategy_rows

    candidates = {name: rows for name, rows in candidates.items() if rows}
    if not candidates:
        return [], [], [], universe_audit

    summaries = {name: _summarize_rows(rows) for name, rows in candidates.items()}
    governance_cfg = strategy_cfg.get("candidate_governance", {})
    eligible_names = [name for name, summary in summaries.items() if _candidate_governance(summary, governance_cfg)[0]]
    if eligible_names:
        best_name = max(eligible_names, key=lambda name: _candidate_selection_score(summaries[name], governance_cfg))
    else:
        best_name = max(candidates, key=lambda name: _candidate_raw_score(summaries[name]))
    comparison = "; ".join(
        (
            f"{name}: score={_candidate_raw_score(summary):.4f}, "
            f"selection_score={_candidate_selection_score(summary, governance_cfg):.4f}, "
            f"eligible={_candidate_governance(summary, governance_cfg)[0]}, "
            f"ann={summary.get('annualized_return_mean', 0.0):.4f}, "
            f"sharpe={summary.get('sharpe_mean', 0.0):.4f}, "
            f"mdd={summary.get('max_drawdown_mean', 0.0):.4f}"
        )
        for name, summary in summaries.items()
    )
    candidate_summary_rows = _candidate_summary_rows(summaries, governance_cfg)
    selected = candidates[best_name]
    selected_eligible, selected_reason = _candidate_governance(summaries[best_name], governance_cfg)
    for row in selected:
        row["candidate_summary"] = comparison
        row["selected_candidate"] = best_name
        row["selected_candidate_eligible"] = selected_eligible
        row["selected_candidate_governance_reason"] = selected_reason

    all_candidate_rows: list[dict[str, Any]] = []
    for name, rows in candidates.items():
        candidate_eligible, candidate_reason = _candidate_governance(summaries[name], governance_cfg)
        for row in rows:
            enriched = dict(row)
            enriched["candidate_summary"] = comparison
            enriched["selected_candidate"] = best_name
            enriched["is_selected_candidate"] = name == best_name
            enriched["candidate_eligible_for_selection"] = candidate_eligible
            enriched["candidate_governance_reason"] = candidate_reason
            all_candidate_rows.append(enriched)
    return selected, all_candidate_rows, candidate_summary_rows, universe_audit


def _run_portfolio_on_explicit_fold(
    *,
    fold: int,
    train: pd.DataFrame,
    valid: pd.DataFrame,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
    strategy_cfg: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if train.empty or valid.empty:
        return []
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
    row = {
        "symbol": "PORTFOLIO",
        "fold": fold,
        "train_start": str(pd.Timestamp(train["date"].min()).date()),
        "train_end": str(pd.Timestamp(train["date"].max()).date()),
        "valid_start": str(pd.Timestamp(valid["date"].min()).date()),
        "valid_end": str(pd.Timestamp(valid["date"].max()).date()),
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
    if extra:
        row.update(extra)
    return [row]


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
    window_cfg: dict[str, Any] | None = None,
) -> list[FoldResult]:
    df = _load_symbol(symbol, years=years)
    if df.empty or len(df) < min_samples:
        return []
    df = _add_cross_market_to_panel(df.assign(symbol=symbol), years, strategy_cfg, xfeatures)

    folds: list[FoldResult] = []
    fold_windows = _date_window_slices(
        df["date"].dropna().tolist(),
        train_years=train_years,
        validate_years=validate_years,
        min_samples=min_samples,
        start_date=(window_cfg or {}).get("start_date"),
        end_date=(window_cfg or {}).get("end_date"),
    )
    for fold_idx, train_dates, valid_dates in fold_windows:
        train = df[df["date"].isin(train_dates)].copy()
        valid = df[df["date"].isin(valid_dates)].copy()
        passed = len(train) >= min_samples and len(valid) >= min_samples // 2
        if not passed:
            continue

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
    return folds


def _effective_history_years(configured_years: int, window_cfg: dict[str, Any]) -> int:
    start = _parse_optional_date(window_cfg.get("start_date"))
    end = _parse_optional_date(window_cfg.get("end_date")) or date.today()
    if start is None:
        return int(configured_years)
    required_years = int(np.ceil(max((end - start).days, 1) / 365.0)) + 1
    return max(int(configured_years), required_years)


def _window_summary_fields(window_cfg: dict[str, Any], folds_df: pd.DataFrame) -> dict[str, Any]:
    expected_folds = window_cfg.get("expected_folds")
    actual_folds = int(folds_df["fold"].nunique()) if not folds_df.empty and "fold" in folds_df.columns else 0
    warning = ""
    if expected_folds is not None and actual_folds != int(expected_folds):
        warning = f"expected_folds={int(expected_folds)} actual_folds={actual_folds}"
    return {
        "walk_forward_start_date": str(window_cfg.get("start_date") or ""),
        "walk_forward_end_date": str(window_cfg.get("end_date") or ""),
        "walk_forward_expected_folds": "" if expected_folds is None else int(expected_folds),
        "walk_forward_actual_folds": actual_folds,
        "walk_forward_fold_generation_warning": warning,
    }


def run_walk_forward(config: dict[str, Any], *, trace_callback: TraceCallback | None = None) -> dict[str, Any]:
    wcfg = config["walk_forward"]
    window_cfg = _resolve_walk_forward_window(wcfg)
    years = _effective_history_years(int(config["years"]), window_cfg)
    train_years = int(window_cfg["train_years"])
    validate_years = int(window_cfg["validate_years"])
    configure_local_history(config.get("local_history", {}), Path.cwd())
    configure_us_market_history(config.get("us_market_history", {}), Path.cwd())
    symbols = config["symbols"]
    universe_cfg = config.get("universe", {})
    use_point_in_time_universe = bool(
        universe_cfg.get("enabled", False)
        and universe_cfg.get("point_in_time_for_backtest", True)
        and config.get("local_history", {}).get("enabled", True)
    )
    universe_symbols: list[str] = []
    if universe_cfg.get("enabled", False) and not use_point_in_time_universe:
        # Legacy fallback only: historical research should normally use fold-local PIT universes.
        universe_symbols = load_universe_symbols(config, Path.cwd())
    if universe_symbols:
        symbols = universe_symbols
    strategy_cfg = wcfg.get("strategy_v2", {})
    account_execution = _build_account_execution_config(config, wcfg, strategy_cfg)
    configure_akshare_throttle(config.get("data_sources", {}).get("akshare", {}))
    _load_symbol_cached.cache_clear()

    candidate_rows: list[dict[str, Any]] = []
    candidate_summary_rows: list[dict[str, Any]] = []
    universe_audit_df = pd.DataFrame()
    # compare 用于 Phase 0 候选策略选拔；portfolio 和单票分支保留给独立组合/单标的回测。
    if strategy_cfg.get("mode") == "compare":
        if use_point_in_time_universe:
            all_rows, candidate_rows, candidate_summary_rows, universe_audit_df = _run_compare_point_in_time(
                config,
                years=years,
                train_years=train_years,
                validate_years=validate_years,
                min_samples=int(wcfg["min_samples"]),
                slippage=float(wcfg["slippage"]),
                commission=float(wcfg["commission"]),
                stamp_duty_sell=float(wcfg["stamp_duty_sell"]),
                strategy_cfg=strategy_cfg,
                account_execution=account_execution,
                window_cfg=window_cfg,
                trace_callback=trace_callback,
            )
        elif _strict_qfq_asof_enabled(config):
            all_rows, candidate_rows, candidate_summary_rows, universe_audit_df = _run_compare_qfq_asof_static(
                symbols=symbols,
                years=years,
                train_years=train_years,
                validate_years=validate_years,
                min_samples=int(wcfg["min_samples"]),
                slippage=float(wcfg["slippage"]),
                commission=float(wcfg["commission"]),
                stamp_duty_sell=float(wcfg["stamp_duty_sell"]),
                strategy_cfg=strategy_cfg,
                account_execution=account_execution,
                window_cfg=window_cfg,
                trace_callback=trace_callback,
            )
        else:
            all_rows, candidate_rows, candidate_summary_rows = _run_compare(
                symbols=symbols,
                years=years,
                train_years=train_years,
                validate_years=validate_years,
                min_samples=int(wcfg["min_samples"]),
                slippage=float(wcfg["slippage"]),
                commission=float(wcfg["commission"]),
                stamp_duty_sell=float(wcfg["stamp_duty_sell"]),
                strategy_cfg=strategy_cfg,
                account_execution=account_execution,
                window_cfg=window_cfg,
                trace_callback=trace_callback,
            )
    elif strategy_cfg.get("mode") == "portfolio":
        if use_point_in_time_universe:
            fold_contexts, universe_audit_df = iter_point_in_time_universe_folds(
                config,
                years=years,
                train_years=train_years,
                validate_years=validate_years,
                min_samples=int(wcfg["min_samples"]),
                strategy_cfg=strategy_cfg,
                xfeatures=_load_cross_market_features(years, strategy_cfg.get("cross_market", {}))
                if _xmarket_enabled(strategy_cfg)
                else None,
                window_cfg=window_cfg,
            )
            all_rows = []
            for ctx in fold_contexts:
                all_rows.extend(
                    _run_portfolio_on_explicit_fold(
                        fold=int(ctx["fold"]),
                        train=ctx["train"],
                        valid=ctx["valid"],
                        slippage=float(wcfg["slippage"]),
                        commission=float(wcfg["commission"]),
                        stamp_duty_sell=float(wcfg["stamp_duty_sell"]),
                        strategy_cfg={**strategy_cfg, "mode": "portfolio"},
                        extra={
                            "universe_mode": "point_in_time",
                            "universe_as_of_date": ctx["audit"].get("universe_as_of_date", ""),
                            "universe_symbol_count": ctx["audit"].get("universe_symbol_count", 0),
                            "universe_snapshot_count": ctx["audit"].get("universe_snapshot_count", 0),
                            "universe_source": ctx["audit"].get("universe_source", ""),
                        },
                    )
                )
        else:
            all_rows = _run_portfolio(
                symbols=symbols,
                years=years,
                train_years=train_years,
                validate_years=validate_years,
                min_samples=int(wcfg["min_samples"]),
                slippage=float(wcfg["slippage"]),
                commission=float(wcfg["commission"]),
                stamp_duty_sell=float(wcfg["stamp_duty_sell"]),
                strategy_cfg=strategy_cfg,
                window_cfg=window_cfg,
            )
    else:
        all_rows: list[dict[str, Any]] = []
        xfeatures = _load_cross_market_features(years, strategy_cfg.get("cross_market", {})) if _xmarket_enabled(strategy_cfg) else None
        for sym in symbols:
            folds = _run_single_symbol(
                symbol=sym,
                years=years,
                train_years=train_years,
                validate_years=validate_years,
                min_samples=int(wcfg["min_samples"]),
                slippage=float(wcfg["slippage"]),
                commission=float(wcfg["commission"]),
                stamp_duty_sell=float(wcfg["stamp_duty_sell"]),
                strategy_cfg=strategy_cfg,
                xfeatures=xfeatures,
                window_cfg=window_cfg,
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
        empty_summary_df = pd.DataFrame()
        return {
            "folds": folds_df,
            "candidate_folds": candidate_folds_df,
            "universe_audit": universe_audit_df,
            "summary": {
                "status": "failed",
                "reason": "no valid folds",
                "walk_forward_preset": window_cfg["preset_name"],
                "walk_forward_train_years": train_years,
                "walk_forward_validate_years": validate_years,
                **_window_summary_fields(window_cfg, empty_summary_df),
                "universe_mode": "point_in_time" if use_point_in_time_universe else "static_current_snapshot",
                "universe_lookahead_guard": bool(use_point_in_time_universe),
            },
        }

    summary = {
        "status": "ok",
        "walk_forward_preset": window_cfg["preset_name"],
        "walk_forward_train_years": train_years,
        "walk_forward_validate_years": validate_years,
        **_window_summary_fields(window_cfg, folds_df),
        "universe_mode": "point_in_time" if use_point_in_time_universe else "static_current_snapshot",
        "universe_lookahead_guard": bool(use_point_in_time_universe),
        "fold_count": int(len(folds_df)),
        "symbol_count": int(folds_df["symbol"].nunique()),
        "annualized_return_mean": float(folds_df["annualized_return"].mean()),
        "sharpe_mean": float(folds_df["sharpe"].mean()),
        "max_drawdown_mean": float(folds_df["max_drawdown"].mean()),
        "win_rate_mean": float(folds_df["win_rate"].mean()),
        "turnover_annual_mean": float(folds_df["turnover_annual"].mean()),
        "positive_fold_count": int((folds_df["annualized_return"] > 0).sum()),
        "negative_fold_count": int((folds_df["annualized_return"] < 0).sum()),
        "positive_fold_ratio": float((folds_df["annualized_return"] > 0).mean()),
        "min_fold_annualized_return": float(folds_df["annualized_return"].min()),
        "min_fold_sharpe": float(folds_df["sharpe"].min()),
    }
    if "candidate" in folds_df.columns:
        summary["selected_candidate"] = str(folds_df["candidate"].iloc[0])
    if "selected_candidate_eligible" in folds_df.columns:
        summary["selected_candidate_eligible"] = bool(folds_df["selected_candidate_eligible"].iloc[0])
    if "selected_candidate_governance_reason" in folds_df.columns:
        summary["selected_candidate_governance_reason"] = str(folds_df["selected_candidate_governance_reason"].iloc[0])
    if "candidate_summary" in folds_df.columns:
        summary["candidate_comparison"] = str(folds_df["candidate_summary"].iloc[0])
    if candidate_summary_rows:
        summary["candidate_summary_rows"] = candidate_summary_rows
    if not universe_audit_df.empty:
        summary["universe_fold_count"] = int(len(universe_audit_df))
        summary["universe_symbol_count_mean"] = float(universe_audit_df["universe_symbol_count"].mean())
        summary["universe_symbol_count_min"] = int(universe_audit_df["universe_symbol_count"].min())
        summary["universe_source"] = str(universe_audit_df["universe_source"].dropna().iloc[0])

    # 用最后 20% 折作为最近样本的近似留出段，检查策略在较新行情里的衰减。
    cutoff = max(1, int(len(folds_df) * 0.2))
    oos = folds_df.sort_values(["valid_end"]).tail(cutoff)
    train_like = folds_df.sort_values(["valid_end"]).head(len(folds_df) - cutoff)
    summary["oos_fold_count"] = int(len(oos))
    summary["oos_annualized_return_mean"] = float(oos["annualized_return"].mean())
    summary["oos_sharpe_mean"] = float(oos["sharpe"].mean())
    summary["oos_positive_fold_count"] = int((oos["annualized_return"] > 0).sum())
    summary["oos_positive_fold_ratio"] = float((oos["annualized_return"] > 0).mean()) if len(oos) else 0.0
    summary["oos_min_fold_annualized_return"] = float(oos["annualized_return"].min()) if len(oos) else 0.0
    if len(train_like) > 0 and np.isfinite(train_like["annualized_return"].mean()):
        base = float(train_like["annualized_return"].mean())
        oosv = float(oos["annualized_return"].mean())
        if base != 0:
            summary["oos_return_decay_ratio"] = float((base - oosv) / abs(base))
        else:
            summary["oos_return_decay_ratio"] = 0.0
    else:
        summary["oos_return_decay_ratio"] = 0.0

    return {"folds": folds_df, "candidate_folds": candidate_folds_df, "universe_audit": universe_audit_df, "summary": summary}


def run_cost_sensitivity(config: dict[str, Any]) -> pd.DataFrame:
    sensitivity_cfg = config.get("cost_sensitivity", {})
    if not bool(sensitivity_cfg.get("enabled", False)):
        return pd.DataFrame()

    base_wcfg = config.get("walk_forward", {})
    scenarios = sensitivity_cfg.get("scenarios", [])
    if not scenarios:
        scenarios = [
            {
                "name": "base_research_cost",
                "slippage": 0.001,
                "commission": base_wcfg.get("commission", 0.0),
                "stamp_duty_sell": base_wcfg.get("stamp_duty_sell", 0.0),
            },
            {
                "name": "main_personal_execution",
                "slippage": base_wcfg.get("slippage", 0.0),
                "commission": base_wcfg.get("commission", 0.0),
                "stamp_duty_sell": base_wcfg.get("stamp_duty_sell", 0.0),
            },
            {
                "name": "stress_slippage_0_003",
                "slippage": 0.003,
                "commission": base_wcfg.get("commission", 0.0),
                "stamp_duty_sell": base_wcfg.get("stamp_duty_sell", 0.0),
            },
            {
                "name": "stress_slippage_0_005",
                "slippage": 0.005,
                "commission": base_wcfg.get("commission", 0.0),
                "stamp_duty_sell": base_wcfg.get("stamp_duty_sell", 0.0),
            },
            {"name": "zero_cost", "slippage": 0.0, "commission": 0.0, "stamp_duty_sell": 0.0},
        ]

    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        scenario_cfg = copy.deepcopy(config)
        scenario_wcfg = scenario_cfg.setdefault("walk_forward", {})
        scenario_wcfg["slippage"] = float(scenario.get("slippage", scenario_wcfg.get("slippage", 0.0)))
        scenario_wcfg["commission"] = float(scenario.get("commission", scenario_wcfg.get("commission", 0.0)))
        scenario_wcfg["stamp_duty_sell"] = float(scenario.get("stamp_duty_sell", scenario_wcfg.get("stamp_duty_sell", 0.0)))
        result = run_walk_forward(scenario_cfg)
        summary = result.get("summary", {})
        scenario_name = str(scenario.get("name", "scenario"))
        candidate_rows = summary.get("candidate_summary_rows", []) or []
        if candidate_rows:
            for row in candidate_rows:
                rows.append(
                    {
                        "scenario": scenario_name,
                        "slippage": scenario_wcfg["slippage"],
                        "commission": scenario_wcfg["commission"],
                        "stamp_duty_sell": scenario_wcfg["stamp_duty_sell"],
                        "candidate": row.get("candidate", ""),
                        "selected_candidate": summary.get("selected_candidate", ""),
                        "eligible_for_selection": bool(row.get("eligible_for_selection", False)),
                        "governance_reason": row.get("governance_reason", ""),
                        "fold_count": int(row.get("fold_count", 0)),
                        "panel_scope": row.get("panel_scope", ""),
                        "annualized_return_mean": float(row.get("annualized_return_mean", 0.0)),
                        "sharpe_mean": float(row.get("sharpe_mean", 0.0)),
                        "max_drawdown_mean": float(row.get("max_drawdown_mean", 0.0)),
                        "win_rate_mean": float(row.get("win_rate_mean", 0.0)),
                        "turnover_annual_mean": float(row.get("turnover_annual_mean", 0.0)),
                    }
                )
        else:
            rows.append(
                {
                    "scenario": scenario_name,
                    "slippage": scenario_wcfg["slippage"],
                    "commission": scenario_wcfg["commission"],
                    "stamp_duty_sell": scenario_wcfg["stamp_duty_sell"],
                    "candidate": summary.get("selected_candidate", ""),
                    "selected_candidate": summary.get("selected_candidate", ""),
                    "eligible_for_selection": bool(summary.get("selected_candidate_eligible", False)),
                    "governance_reason": summary.get("selected_candidate_governance_reason", ""),
                    "fold_count": int(summary.get("fold_count", 0)),
                    "panel_scope": "",
                    "annualized_return_mean": float(summary.get("annualized_return_mean", 0.0)),
                    "sharpe_mean": float(summary.get("sharpe_mean", 0.0)),
                    "max_drawdown_mean": float(summary.get("max_drawdown_mean", 0.0)),
                    "win_rate_mean": float(summary.get("win_rate_mean", 0.0)),
                    "turnover_annual_mean": float(summary.get("turnover_annual_mean", 0.0)),
                }
            )
    return pd.DataFrame(rows)


def save_walk_forward_csv(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8")
