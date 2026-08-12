from __future__ import annotations

from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd

from quant.data_access.local_history import load_index_daily_from_local_history
from quant.strategies.base import StrategyOutput
from quant.strategies.low_vol_low_turnover_quality import LowVolLowTurnoverQualityStrategy
from quant.strategies.registry import register


@register
class QualityLowTurnoverRegimeGateStrategy(LowVolLowTurnoverQualityStrategy):
    name = "quality_low_turnover_regime_gate_v1"
    candidate_name = "quality_low_turnover_regime_gate_v1"
    display_name = "Quality Low Turnover Regime Gate"
    category = "factor_regime_overlay"
    supports_brief = False
    supports_paper_trade = False

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        cfg = strategy_cfg.get("local_factor", {}).get("quality_low_turnover_regime_gate", {})
        return bool(cfg.get("enabled", False))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        d = super().prepare_panel(panel, strategy_cfg)
        if d.empty:
            return d
        cfg = strategy_cfg.get("local_factor", {}).get("quality_low_turnover_regime_gate", {})
        return _add_index_regime_features(d, cfg)

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        cfg = strategy_cfg.get("local_factor", {}).get("quality_low_turnover_regime_gate", {})
        patched_cfg = {
            **strategy_cfg,
            "local_factor": {
                **strategy_cfg.get("local_factor", {}),
                "low_vol_low_turnover_quality": cfg,
            },
        }
        params = super().select_params(
            train,
            patched_cfg,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
        )
        params["regime_index_symbol"] = str(cfg.get("index_symbol", "SH.000300"))
        params["regime_trend_window"] = int(cfg.get("regime_trend_window", 120))
        params["regime_vol_window"] = int(cfg.get("regime_vol_window", 20))
        params["regime_vol_quantile"] = float(cfg.get("regime_vol_quantile", 0.70))
        params["regime_risk_scale"] = float(cfg.get("regime_risk_scale", 0.35))
        params["regime_scale_mode"] = str(cfg.get("regime_scale_mode", "trend_or_high_vol"))
        return params

    def apply(
        self,
        panel: pd.DataFrame,
        params: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> StrategyOutput:
        output = super().apply(
            panel,
            params,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
        )
        if (
            output.signal_frame is not None
            and not output.signal_frame.empty
            and "regime_scale" not in output.signal_frame.columns
        ):
            regime_cols = [
                "date",
                "symbol",
                "regime_index_close",
                "regime_index_trend_ma",
                "regime_index_vol",
                "regime_index_vol_threshold",
                "regime_risk_off",
                "regime_scale",
            ]
            available = [col for col in regime_cols if col in panel.columns]
            if {"date", "symbol", "regime_scale"}.issubset(set(available)):
                regime = panel[available].drop_duplicates(["date", "symbol"])
                signal = output.signal_frame.merge(regime, on=["date", "symbol"], how="left")
                output = StrategyOutput(output.returns, output.exposure, signal, output.metadata)
        return _apply_regime_gate(output, params, slippage=slippage, commission=commission, stamp_duty_sell=stamp_duty_sell)

    def format_params(self, params: dict[str, Any]) -> str:
        return (
            "quality_low_turnover_regime_gate@"
            f"{super().format_params(params)},"
            f"index={params.get('regime_index_symbol', '')},"
            f"trend={params.get('regime_trend_window', '')}d,"
            f"vol={params.get('regime_vol_window', '')}d@q{params.get('regime_vol_quantile', '')},"
            f"risk_scale={params.get('regime_risk_scale', '')},"
            f"mode={params.get('regime_scale_mode', '')}"
        )


def _add_index_regime_features(panel: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    if panel.empty:
        return panel
    d = panel.copy()
    dates = pd.to_datetime(d["date"]).dt.normalize()
    start = dates.min().date() - timedelta(days=max(260, int(cfg.get("regime_trend_window", 120)) * 3))
    end = dates.max().date()
    symbol = str(cfg.get("index_symbol", "SH.000300"))
    index_df = load_index_daily_from_local_history(symbol, start, end)
    if index_df.empty:
        d["regime_scale"] = 1.0
        d["regime_risk_off"] = 0.0
        d["regime_index_close"] = np.nan
        d["regime_index_trend_ma"] = np.nan
        d["regime_index_vol"] = np.nan
        d["regime_index_vol_threshold"] = np.nan
        return d

    trend_window = int(cfg.get("regime_trend_window", 120))
    vol_window = int(cfg.get("regime_vol_window", 20))
    vol_quantile = float(cfg.get("regime_vol_quantile", 0.70))
    risk_scale = float(cfg.get("regime_risk_scale", 0.35))
    mode = str(cfg.get("regime_scale_mode", "trend_or_high_vol"))
    index_features = index_df[["date", "close"]].copy().sort_values("date")
    index_features["date"] = pd.to_datetime(index_features["date"]).dt.normalize()
    index_features["regime_index_close"] = pd.to_numeric(index_features["close"], errors="coerce")
    index_features["regime_index_ret"] = index_features["regime_index_close"].pct_change()
    index_features["regime_index_trend_ma"] = index_features["regime_index_close"].rolling(
        trend_window, min_periods=min(trend_window, max(20, trend_window // 2))
    ).mean()
    index_features["regime_index_vol"] = index_features["regime_index_ret"].rolling(
        vol_window, min_periods=min(vol_window, max(5, vol_window // 2))
    ).std() * np.sqrt(252)
    index_features["regime_index_vol_threshold"] = index_features["regime_index_vol"].rolling(
        252, min_periods=60
    ).quantile(vol_quantile)
    trend_off = index_features["regime_index_close"] < index_features["regime_index_trend_ma"]
    high_vol = index_features["regime_index_vol"] > index_features["regime_index_vol_threshold"]
    if mode == "trend_and_high_vol":
        risk_off = trend_off & high_vol
    elif mode == "trend_only":
        risk_off = trend_off
    elif mode == "high_vol_only":
        risk_off = high_vol
    else:
        risk_off = trend_off | high_vol
    index_features["regime_risk_off"] = risk_off.fillna(False).astype(float)
    index_features["regime_scale"] = np.where(index_features["regime_risk_off"] > 0, np.clip(risk_scale, 0.0, 1.0), 1.0)

    # Index close at T is only known after close, so trade decisions on T use the last index feature as of T-1.
    index_features["date"] = (index_features["date"] + pd.Timedelta(days=1)).astype("datetime64[ns]")
    features = index_features[
        [
            "date",
            "regime_index_close",
            "regime_index_trend_ma",
            "regime_index_vol",
            "regime_index_vol_threshold",
            "regime_risk_off",
            "regime_scale",
        ]
    ].sort_values("date")
    d["date"] = pd.to_datetime(d["date"]).dt.normalize().astype("datetime64[ns]")
    out = pd.merge_asof(d.sort_values("date"), features, on="date", direction="backward").sort_values(["symbol", "date"])
    out["regime_scale"] = pd.to_numeric(out["regime_scale"], errors="coerce").fillna(1.0).clip(0.0, 1.0)
    out["regime_risk_off"] = pd.to_numeric(out["regime_risk_off"], errors="coerce").fillna(0.0)
    return out


def _apply_regime_gate(
    output: StrategyOutput,
    params: dict[str, Any],
    *,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
) -> StrategyOutput:
    signal = output.signal_frame
    if signal is None or signal.empty or "regime_scale" not in signal.columns:
        return output
    d = signal.copy().sort_values(["symbol", "date"]).reset_index(drop=True)
    d["regime_scale"] = pd.to_numeric(d["regime_scale"], errors="coerce").fillna(1.0).clip(0.0, 1.0)
    d["weight_unshifted"] = pd.to_numeric(d.get("weight_unshifted", 0.0), errors="coerce").fillna(0.0) * d["regime_scale"]
    d["weight"] = d.groupby("symbol")["weight_unshifted"].shift(1).fillna(0.0)
    d["position_ret"] = d["weight"] * pd.to_numeric(d.get("ret", 0.0), errors="coerce").fillna(0.0)
    weights = d.pivot(index="date", columns="symbol", values="weight").fillna(0.0)
    turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
    sells = weights.diff().clip(upper=0).abs().sum(axis=1).fillna(0.0)
    gross = d.groupby("date")["position_ret"].sum()
    costs = turnover * (slippage + commission) + sells * stamp_duty_sell
    returns = gross.sub(costs, fill_value=0.0)
    exposure = weights.sum(axis=1)
    metadata = {**(output.metadata or {}), "formatted_params": QualityLowTurnoverRegimeGateStrategy().format_params(params)}
    return StrategyOutput(returns=returns, exposure=exposure, signal_frame=d, metadata=metadata)
