"""Momentum + MACD golden cross + MA-trend portfolio strategy (weekly rebalance).

Signal logic:
- ranking score: 20-day momentum (mom20) — higher is better
- trend filter: close above ma60 (long-term uptrend) — removes downtrend stocks
- entry trigger: MACD golden cross (DIF crosses above DEA) OR MA5 crosses above MA20
- rebalance: weekly (5 days) to bi-weekly (10 days)

The strategy is a weekly~bi-weekly portfolio rebalancer, distinct from the
monthly quality factor line.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from quant.strategies.base import BaseStrategy, StrategyOutput
from quant.strategies.registry import register


def _add_macd(panel: pd.DataFrame) -> pd.DataFrame:
    """Add MACD DIF/DEA/histogram and MA/MA golden-cross flags, grouped per symbol."""
    d = panel.copy().sort_values(["symbol", "date"]).reset_index(drop=True)
    grouped = d.groupby("symbol", sort=False)

    ema12 = grouped["close"].transform(lambda s: s.ewm(span=12, adjust=False).mean())
    ema26 = grouped["close"].transform(lambda s: s.ewm(span=26, adjust=False).mean())
    d["macd_dif"] = ema12 - ema26
    d["macd_dea"] = d.groupby("symbol", sort=False)["macd_dif"].transform(
        lambda s: s.ewm(span=9, adjust=False).mean()
    )
    d["macd_hist"] = d["macd_dif"] - d["macd_dea"]

    # golden cross: DIF crosses above DEA (prev DIF <= prev DEA and now DIF > DEA)
    prev_dif = d.groupby("symbol", sort=False)["macd_dif"].shift(1)
    prev_dea = d.groupby("symbol", sort=False)["macd_dea"].shift(1)
    d["macd_golden_cross"] = ((prev_dif <= prev_dea) & (d["macd_dif"] > d["macd_dea"])).astype(float)

    # MA golden cross: ma5 crosses above ma20
    if "ma5" not in d.columns:
        d["ma5"] = grouped["close"].transform(lambda s: s.rolling(5).mean())
    if "ma20" not in d.columns:
        d["ma20"] = grouped["close"].transform(lambda s: s.rolling(20).mean())
    prev_ma5 = d.groupby("symbol", sort=False)["ma5"].shift(1)
    prev_ma20 = d.groupby("symbol", sort=False)["ma20"].shift(1)
    d["ma_golden_cross"] = ((prev_ma5 <= prev_ma20) & (d["ma5"] > d["ma20"])).astype(float)

    return d


def _join_event_direction(panel: pd.DataFrame, event_cfg: dict[str, Any]) -> pd.DataFrame:
    """Join point-in-time earnings-forecast direction onto the panel.

    Reads the AI corpus (``provider='cninfo' AND event_type='earnings_forecast'``),
    extracts the ``direction=`` tag, and marks each symbol with its most recent
    forecast direction as-of each date (point-in-time, no lookahead: only
    announcements published on or before that date count).
    """
    import sqlite3
    from pathlib import Path

    corpus_db = Path(event_cfg.get("corpus_db", "data/ai_corpus/ai_corpus.sqlite"))
    if not corpus_db.is_file():
        return panel
    conn = sqlite3.connect(corpus_db)
    events = pd.read_sql_query(
        """SELECT symbols, published_at, topics
           FROM ai_corpus_documents
           WHERE provider='cninfo' AND event_type='earnings_forecast'""",
        conn,
    )
    conn.close()
    if events.empty:
        panel["event_direction"] = ""
        return panel

    events["direction"] = events["topics"].str.extract(r"direction=([^|]+)")
    events = events[events["direction"].notna()]
    events["symbol"] = events["symbols"].apply(_norm_symbol)
    events = events[events["symbol"].notna()]
    events["pub_date"] = pd.to_datetime(events["published_at"]).dt.normalize()

    # point-in-time join: latest direction per symbol as-of each panel date
    panel = panel.copy()
    panel["date_ts"] = pd.to_datetime(panel["date"]).dt.normalize()
    panel["event_direction"] = ""
    # merge_asof per symbol: last announcement date <= panel date
    for symbol, grp in events.groupby("symbol"):
        sym_events = grp.sort_values("pub_date")
        mask = panel["symbol"] == symbol
        if not mask.any():
            continue
        panel_dates = panel.loc[mask, "date_ts"].sort_values().values
        sym_events = sym_events.set_index("pub_date")["direction"]
        # for each panel date, find last direction <= that date
        dirs = sym_events.sort_index()
        idx = pd.Index(panel_dates)
        # use searchsorted on sorted event dates
        event_dates = dirs.index.values
        pos = np.searchsorted(event_dates, panel_dates, side="right") - 1
        mapped = [dirs.iloc[p] if p >= 0 else "" for p in pos]
        panel.loc[mask, "event_direction"] = mapped
    return panel


def _norm_symbol(code: str) -> str | None:
    code = str(code).strip()
    if code.startswith(("SH.", "SZ.")):
        return code
    if len(code) == 6 and code.isdigit():
        if code.startswith(("60", "68", "90")):
            return f"SH.{code}"
        if code.startswith(("00", "30")):
            return f"SZ.{code}"
    return None


@register
class MomentumMacdGoldenCrossStrategy(BaseStrategy):
    name = "momentum_macd_golden_cross_v1"
    candidate_name = "momentum_macd_golden_cross_v1"
    display_name = "Momentum + MACD Golden Cross (Weekly)"
    category = "factor"
    panel_scope = "portfolio"
    supports_brief = False
    supports_paper_trade = False

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        cfg = strategy_cfg.get("local_factor", {}).get("momentum_macd_golden_cross", {})
        return bool(cfg.get("enabled", True))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        """Add MACD and golden-cross flags; ensure mom20/ma60 exist.

        When ``event_overlay.enabled`` is set, join the earnings-forecast
        direction (from the AI corpus) as a point-in-time ``event_direction``
        column (预增/扭亏/预减/首亏) so ``apply`` can avoid 首亏 and boost 预增.
        """
        if panel.empty:
            return panel
        d = _add_macd(panel)
        if "ma60" not in d.columns:
            d["ma60"] = d.groupby("symbol", sort=False)["close"].transform(
                lambda s: s.rolling(60).mean()
            )
        event_cfg = strategy_cfg.get("local_factor", {}).get("momentum_macd_golden_cross", {}).get("event_overlay", {})
        if bool(event_cfg.get("enabled", False)):
            d = _join_event_direction(d, event_cfg)
        return d

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        """Search momentum quantile, rebalance days, golden-cross mode, top_n."""
        from quant.research.metrics import calc_metrics as _calc_metrics

        cfg = strategy_cfg.get("local_factor", {}).get("momentum_macd_golden_cross", {})
        target_vol = float(cfg.get("target_vol", strategy_cfg.get("target_vol", 0.18)))
        min_trades = int(strategy_cfg.get("train_min_trades", 5))
        momentum_scores = train.get("mom20", pd.Series(dtype=float)).dropna()
        if train.empty or momentum_scores.empty:
            return self._fallback_params(cfg, target_vol)

        best: dict[str, Any] | None = None
        momentum_quantiles = [float(item) for item in cfg.get("momentum_quantiles", [0.5, 0.6, 0.7])]
        rebalance_days_values = [int(item) for item in cfg.get("rebalance_days_values", [5, 10])]
        top_n_values = [int(item) for item in cfg.get("top_n_values", [10, 15, 20])]
        cross_modes = [str(item) for item in cfg.get("cross_modes", ["macd", "any"])]
        require_trend = bool(cfg.get("require_trend", True))
        max_symbol_weight = float(cfg.get("max_symbol_weight", 0.10))

        for momentum_q in momentum_quantiles:
            momentum_threshold = float(momentum_scores.quantile(momentum_q))
            for rebalance_days in rebalance_days_values:
                for top_n in top_n_values:
                    for cross_mode in cross_modes:
                        params = {
                            "eligible": True,
                            "momentum_quantile": momentum_q,
                            "momentum_threshold": momentum_threshold,
                            "rebalance_days": rebalance_days,
                            "top_n": top_n,
                            "cross_mode": cross_mode,
                            "require_trend": require_trend,
                            "target_vol": target_vol,
                            "max_symbol_weight": max_symbol_weight,
                        }
                        output = self.apply(
                            train, params,
                            slippage=slippage, commission=commission,
                            stamp_duty_sell=stamp_duty_sell,
                        )
                        metric = _calc_metrics(output.returns, output.exposure)
                        if metric["trades"] < min_trades:
                            continue
                        score = metric["sharpe"] + max(metric["max_drawdown"], -1.0) * 0.5 - 0.02 * metric["turnover_annual"]
                        candidate = {**params, "train_score": float(score),
                                     "train_sharpe": float(metric["sharpe"]),
                                     "train_trades": int(metric["trades"])}
                        if best is None or candidate["train_score"] > best["train_score"]:
                            best = candidate

        return best if best is not None else self._fallback_params(cfg, target_vol)

    def apply(
        self,
        panel: pd.DataFrame,
        params: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> StrategyOutput:
        """Build a weekly-rebalanced momentum portfolio with golden-cross entry."""
        if panel.empty:
            return StrategyOutput(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame(), self.build_metadata(params))

        d = panel.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        required = ["mom20", "close", "ma60", "macd_golden_cross", "ret"]
        if any(col not in d.columns for col in required) or not bool(params.get("eligible", True)):
            dates = pd.Index(sorted(d["date"].dropna().unique()))
            empty = pd.Series(0.0, index=dates)
            return StrategyOutput(empty, empty, pd.DataFrame(), self.build_metadata(params))

        rebalance_days = max(1, int(params.get("rebalance_days", 5)))
        top_n = int(params.get("top_n", 10))
        cross_mode = str(params.get("cross_mode", "macd"))
        require_trend = bool(params.get("require_trend", True))
        momentum_threshold = float(params.get("momentum_threshold", 0.0))
        max_symbol_weight = float(params.get("max_symbol_weight", 0.10))
        target_vol = float(params.get("target_vol", 0.18))

        # trend filter: close above ma60
        trend_ok = (d["close"] > d["ma60"]) if require_trend else pd.Series(True, index=d.index)
        # golden-cross entry trigger
        if cross_mode == "macd":
            cross_ok = d["macd_golden_cross"] > 0
        elif cross_mode == "any":
            cross_ok = (d["macd_golden_cross"] > 0) | (d.get("ma_golden_cross", pd.Series(0, index=d.index)) > 0)
        else:
            cross_ok = pd.Series(True, index=d.index)

        d["momentum_score"] = d["mom20"]
        eligible = (d["mom20"] >= momentum_threshold) & trend_ok & d["mom20"].notna()

        # event overlay: avoid 首亏 (strong negative), boost 预增 (positive)
        event_overlay = bool(params.get("use_event_overlay", False))
        if event_overlay and "event_direction" in d.columns:
            avoid_mask = d["event_direction"].isin(["首亏"])
            boost_mask = d["event_direction"].isin(["预增"])
            eligible = eligible & (~avoid_mask)
            # boost: rank 预增 higher by adding a momentum bonus
            d.loc[boost_mask, "momentum_score"] = d.loc[boost_mask, "mom20"] + float(params.get("event_boost", 0.02))

        # entry: golden cross OR already held (handled in loop)
        d["rank_score"] = d["momentum_score"].where(eligible, np.nan)
        d["rank"] = d.groupby("date")["rank_score"].rank(method="first", ascending=False)

        # vol scaling
        vol_col = "vol20" if "vol20" in d.columns else None
        if vol_col:
            d["vol_scale"] = np.minimum(1.0, target_vol / d[vol_col].replace(0, np.nan)).fillna(0.0)
        else:
            d["vol_scale"] = 1.0

        current_weights: dict[str, float] = {}
        frames: list[pd.DataFrame] = []
        day_idx = 0
        for _, day in d.groupby("date", sort=True):
            day = day.copy()
            if day_idx % rebalance_days == 0:
                # sell existing holdings that dropped out of the hold band
                indexed = day.set_index(day["symbol"].astype(str))
                for symbol in list(current_weights):
                    if symbol in indexed.index:
                        row = indexed.loc[symbol]
                        rank = row["rank"]
                        score = row["rank_score"]
                    else:
                        rank = np.nan
                        score = np.nan
                    outside = pd.isna(rank) or float(rank) > top_n * 2 or pd.isna(score)
                    if outside:
                        current_weights.pop(symbol, None)

                # buy new: must be eligible AND have a golden cross (entry trigger)
                candidates = day[
                    day["rank_score"].notna()
                    & (cross_ok.loc[day.index] if hasattr(cross_ok, "loc") else pd.Series(True, index=day.index))
                ].sort_values(["rank", "symbol"])
                for symbol in candidates["symbol"].head(top_n).astype(str):
                    if len(current_weights) >= top_n:
                        break
                    if symbol not in current_weights:
                        current_weights[symbol] = 0.0

                active = [s for s in current_weights if s in set(day["symbol"].astype(str))]
                if active:
                    indexed = day.set_index(day["symbol"].astype(str))
                    raw = min(max_symbol_weight, 1.0 / len(active))
                    current_weights = {
                        s: raw * float(indexed.loc[s, "vol_scale"]) for s in active
                    }
                else:
                    current_weights = {}

            day["weight_unshifted"] = day["symbol"].astype(str).map(
                lambda s: current_weights.get(s, 0.0)
            )
            frames.append(day)
            day_idx += 1

        out = pd.concat(frames, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)
        out["weight"] = out.groupby("symbol")["weight_unshifted"].shift(1).fillna(0.0)
        out["position_ret"] = out["weight"] * out["ret"]

        weights = out.pivot(index="date", columns="symbol", values="weight").fillna(0.0)
        turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
        sells = weights.diff().clip(upper=0).abs().sum(axis=1).fillna(0.0)
        gross = out.groupby("date")["position_ret"].sum()
        costs = turnover * (slippage + commission) + sells * stamp_duty_sell
        returns = gross.sub(costs, fill_value=0.0)
        exposure = weights.sum(axis=1)

        keep = [c for c in ["date", "symbol", "momentum_score", "rank", "weight_unshifted", "weight", "ret", "position_ret", "macd_dif", "macd_dea", "macd_golden_cross", "ma_golden_cross"] if c in out.columns]
        signal_frame = out[keep].copy()
        return StrategyOutput(returns=returns, exposure=exposure, signal_frame=signal_frame, metadata=self.build_metadata(params))

    def format_params(self, params: dict[str, Any]) -> str:
        return (
            f"momentum_macd_golden_cross@mom_q={params.get('momentum_quantile','')},"
            f"rebalance={params.get('rebalance_days','')}d,"
            f"top_n={params.get('top_n','')},"
            f"cross={params.get('cross_mode','')},"
            f"trend={params.get('require_trend','')}"
        )

    def _fallback_params(self, cfg: dict[str, Any], target_vol: float) -> dict[str, Any]:
        return {
            "eligible": False,
            "momentum_quantile": float(cfg.get("momentum_quantiles", [0.6])[0]),
            "momentum_threshold": 1.1,
            "rebalance_days": int(cfg.get("rebalance_days_values", [5])[0]),
            "top_n": int(cfg.get("top_n_values", [10])[0]),
            "cross_mode": "macd",
            "require_trend": True,
            "target_vol": target_vol,
            "max_symbol_weight": 0.10,
        }
