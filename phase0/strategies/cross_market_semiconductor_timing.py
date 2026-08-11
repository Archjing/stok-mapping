from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from phase0.strategies.base import BaseStrategy, StrategyOutput
from phase0.strategies.registry import register

ETF_DB_PATH = "data/etf_history.sqlite"
US_DB_PATH = "data/us_market_history.sqlite"
ETF_SYMBOL = "SH.512480"
US_SOX_SYMBOL = "^SOX"
US_VIX_SYMBOL = "^VIX"


@dataclass
class _Trade:
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    ret: float


@register
class CrossMarketSemiconductorTimingStrategy(BaseStrategy):
    """SOX + VIX dual-condition semiconductor timing strategy.

    Signal: SOX overnight return > threshold AND VIX level < threshold.
    Action: next-day buy 512480 at open, T+1 close forced exit.
    Position: configurable fraction of capital (default 55%).
    Optimal: SOX>0.5%, VIX<19, pos=55%, Sharpe 0.81 (research costs).
    """

    name = "cross_market_semiconductor_timing_v1"
    candidate_name = "cross_market_semiconductor_timing_v1"
    display_name = "Cross-Market Semiconductor Timing (SOX+VIX)"
    category = "cross_market_timing"
    panel_scope = "portfolio"
    strategy_role = "candidate"

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _load_etf_daily(years: int) -> pd.DataFrame:
        end = date.today()
        start = end - timedelta(days=365 * years + 30)
        with sqlite3.connect(ETF_DB_PATH) as conn:
            df = pd.read_sql_query(
                "SELECT date, open, high, low, close, volume, amount "
                "FROM market_etf_daily_bars "
                "WHERE symbol = ? AND date >= ? AND date <= ? "
                "ORDER BY date",
                conn,
                params=[ETF_SYMBOL, start.isoformat(), end.isoformat()],
            )
        if df.empty:
            return df
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        for col in ["open", "high", "low", "close", "volume", "amount"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["open", "close"])
        df["ret"] = df["close"].pct_change()
        df["symbol"] = ETF_SYMBOL
        return df.sort_values("date").reset_index(drop=True)

    @staticmethod
    def _load_us_features(years: int) -> pd.DataFrame:
        """Load SOX return and VIX level, aligned to A-share dates.

        US close on date T is known before A-share open on T+1.
        We store the signal on T+1's row so that no weight shift is needed.
        """
        end = date.today()
        start = end - timedelta(days=365 * years + 30)
        with sqlite3.connect(US_DB_PATH) as conn:
            sox = pd.read_sql_query(
                "SELECT date, close FROM us_daily_bars WHERE symbol = ? AND date >= ? AND date <= ? ORDER BY date",
                conn,
                params=[US_SOX_SYMBOL, start.isoformat(), end.isoformat()],
            )
            vix = pd.read_sql_query(
                "SELECT date, close FROM us_daily_bars WHERE symbol = ? AND date >= ? AND date <= ? ORDER BY date",
                conn,
                params=[US_VIX_SYMBOL, start.isoformat(), end.isoformat()],
            )
        out = pd.DataFrame()
        if sox.empty or vix.empty:
            out["date"] = pd.DatetimeIndex([])
            out["sox_ret"] = pd.Series(dtype=float)
            out["vix_close"] = pd.Series(dtype=float)
            return out

        sox = sox.copy()
        sox["date"] = pd.to_datetime(sox["date"]).dt.normalize()
        sox["close"] = pd.to_numeric(sox["close"], errors="coerce")
        sox["sox_ret"] = sox["close"].pct_change()

        vix = vix.copy()
        vix["date"] = pd.to_datetime(vix["date"]).dt.normalize()
        vix["vix_close"] = pd.to_numeric(vix["close"], errors="coerce")

        merged = sox[["date", "sox_ret"]].merge(
            vix[["date", "vix_close"]], on="date", how="outer"
        )
        merged = merged.sort_values("date").ffill()
        merged = merged.dropna(subset=["sox_ret", "vix_close"])

        # Shift: US data on date T → usable on A-share date T+1
        merged["trade_date"] = merged["date"] + pd.Timedelta(days=1)
        out = pd.DataFrame()
        out["date"] = merged["trade_date"]
        out["sox_ret"] = merged["sox_ret"]
        out["vix_close"] = merged["vix_close"]
        return out.sort_values("date").reset_index(drop=True)

    # ── BaseStrategy interface ────────────────────────────────────────

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return bool(strategy_cfg.get("cross_market_semiconductor_timing", {}).get("enabled", True))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        """Replace the A-share stock panel with ETF + cross-market data."""
        cfg = strategy_cfg.get("cross_market_semiconductor_timing", {})
        years = int(cfg.get("years", 7))

        etf = self._load_etf_daily(years=years)
        if etf.empty:
            return pd.DataFrame()

        us = self._load_us_features(years=years)
        merged = etf.merge(us, on="date", how="left")
        merged["sox_ret"] = merged["sox_ret"].fillna(0.0)
        merged["vix_close"] = merged["vix_close"].fillna(999.0)

        # Only keep rows where US data is actually available (no fill)
        merged = merged[merged["vix_close"] < 900].copy()

        # Buy at D open, sell at D+1 close (T+1 constraint)
        merged["timing_ret"] = (merged["close"].shift(-1) / merged["open"] - 1.0).fillna(0.0)

        # Standard features needed by the framework
        merged["vol20"] = merged["ret"].rolling(20).std() * np.sqrt(252)
        for w in [3, 5, 10, 20, 60]:
            merged[f"mom{w}"] = merged["close"].pct_change(w)
            merged[f"ma{w}"] = merged["close"].rolling(w).mean()

        merged = merged.dropna().reset_index(drop=True)
        return merged

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        cfg = strategy_cfg.get("cross_market_semiconductor_timing", {})
        sox_thresholds = cfg.get("sox_thresholds", [0.005, 0.008, 0.01, 0.012, 0.015, 0.02])
        vix_thresholds = cfg.get("vix_thresholds", [19, 20, 21, 22, 23, 24, 25])
        position_sizes = cfg.get("position_sizes", [0.50, 0.55, 0.60])
        min_signals = int(cfg.get("train_min_signals", 5))

        best: dict[str, Any] | None = None
        for sox_t in sox_thresholds:
            for vix_t in vix_thresholds:
                for pos in position_sizes:
                    params = {
                        "sox_threshold": float(sox_t),
                        "vix_threshold": float(vix_t),
                        "position_size": float(pos),
                    }
                    output = self.apply(
                        train, params,
                        slippage=slippage, commission=commission,
                        stamp_duty_sell=stamp_duty_sell,
                    )
                    from phase0.research.metrics import calc_metrics as _calc_metrics

                    metric = _calc_metrics(output.returns, output.exposure)
                    if metric["trades"] < min_signals:
                        continue
                    score = metric["sharpe"]
                    candidate = {
                        **params,
                        "train_score": float(score),
                        "train_sharpe": float(metric["sharpe"]),
                        "train_trades": int(metric["trades"]),
                        "train_return": float(metric["annualized_return"]),
                        "train_mdd": float(metric["max_drawdown"]),
                    }
                    if best is None or candidate["train_score"] > best["train_score"]:
                        best = candidate

        if best is None:
            best = {
                "sox_threshold": 0.01,
                "vix_threshold": 22.0,
                "position_size": 0.55,
                "train_score": 0.0,
                "train_sharpe": 0.0,
                "train_trades": 0,
                "train_return": 0.0,
                "train_mdd": 0.0,
            }
        return best

    def apply(
        self,
        panel: pd.DataFrame,
        params: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> StrategyOutput:
        sox_t = float(params["sox_threshold"])
        vix_t = float(params["vix_threshold"])
        position_size = float(params["position_size"])

        d = panel.copy()
        d["date"] = pd.to_datetime(d["date"]).dt.normalize()
        d = d.sort_values("date").reset_index(drop=True)

        # Signal: SOX overnight > threshold AND VIX < threshold
        sox_ret = pd.to_numeric(d["sox_ret"], errors="coerce").fillna(0.0)
        vix_close = pd.to_numeric(d["vix_close"], errors="coerce").fillna(999.0)
        d["signal"] = ((sox_ret > sox_t) & (vix_close < vix_t)).astype(float)

        # No weight shift: US data already aligned to A-share T+1
        # Signal at D means: act on D open (buy)
        d["weight"] = d["signal"] * position_size

        # Use timing_ret: buy at D open, sell at D+1 close
        timing_ret = pd.to_numeric(d.get("timing_ret", d["ret"]), errors="coerce").fillna(0.0)
        d["position_ret"] = d["weight"] * timing_ret

        # Costs based on turnover
        turnover = d["weight"].diff().abs().fillna(d["weight"].abs())
        sells = d["weight"].diff().clip(upper=0).abs().fillna(0.0)
        costs = turnover * (slippage + commission) + sells * stamp_duty_sell

        returns = d.groupby("date")["position_ret"].sum().sub(
            pd.Series(costs.values, index=d["date"]), fill_value=0.0
        )
        exposure = d.set_index("date")["weight"].reindex(returns.index, fill_value=0.0)

        signal_frame = d[
            [c for c in ["date", "symbol", "signal", "weight", "sox_ret", "vix_close",
                          "open", "close", "ret", "timing_ret", "position_ret"]
             if c in d.columns]
        ].copy()
        signal_frame["score"] = d["signal"]

        return StrategyOutput(
            returns=returns,
            exposure=exposure,
            signal_frame=signal_frame,
            metadata=self.build_metadata(params),
        )

    def format_params(self, params: dict[str, Any]) -> str:
        return (
            f"SOX>{params.get('sox_threshold', 0.01):.1%},"
            f"VIX<{params.get('vix_threshold', 22):.0f},"
            f"pos={params.get('position_size', 0.55):.0%}"
        )
