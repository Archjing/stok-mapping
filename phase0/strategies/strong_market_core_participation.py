from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from phase0.local_history import load_daily_from_local_history, local_history_path
from phase0.strategies.base import BaseStrategy, StrategyOutput
from phase0.strategies.low_vol_low_turnover_quality import LowVolLowTurnoverQualityStrategy
from phase0.strategies.registry import register
from phase0.strategies.strong_index_participation import _add_index_context_features, _rank_component


@register
class StrongMarketCoreParticipationStrategy(BaseStrategy):
    name = "strong_market_core_participation_v1"
    candidate_name = "strong_market_core_participation_v1"
    display_name = "Strong Market Core Participation"
    category = "strong_market_participation"
    panel_scope = "portfolio"
    supports_brief = False
    supports_paper_trade = False

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return bool(_strategy_cfg(strategy_cfg).get("enabled", False))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        from phase0.walk_forward import _add_local_factor_features

        cfg = _strategy_cfg(strategy_cfg)
        d = _add_local_factor_features(panel)
        if d.empty:
            return d
        d = d.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        d["date"] = pd.to_datetime(d["date"], errors="coerce").dt.normalize().astype("datetime64[ns]")
        d["symbol"] = d["symbol"].astype(str).str.strip()
        d["benchmark_seeded_core"] = False

        d = _seed_core_panel(d, cfg, strategy_cfg.get("_fold_prepare_context", {}))
        d = _add_index_context_features(d, cfg)
        d = _attach_benchmark_weights(d, _fixed_params(cfg))
        if "industry" in d.columns:
            d["industry"] = d["industry"].fillna("").astype(str).str.strip().replace({"": "UNKNOWN", "nan": "UNKNOWN"})
        d = _add_industry_relative_features(d)
        return d.sort_values(["date", "symbol"]).reset_index(drop=True)

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        del slippage, commission, stamp_duty_sell
        cfg = _strategy_cfg(strategy_cfg)
        params = _fixed_params(cfg)
        reason = _ineligible_reason(train)
        if reason:
            params["eligible"] = False
            params["ineligible_reason"] = reason
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
        if panel.empty:
            return _all_cash_output(panel, params, self, reason="empty_panel")
        if not bool(params.get("eligible", True)):
            return _all_cash_output(panel, params, self, reason=str(params.get("ineligible_reason", "ineligible")))
        reason = _ineligible_reason(panel)
        if reason:
            return _all_cash_output(panel, params, self, reason=reason)

        d = panel.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        d["date"] = pd.to_datetime(d["date"], errors="coerce").dt.normalize().astype("datetime64[ns]")
        d["symbol"] = d["symbol"].astype(str).str.strip()
        for col in [
            "close",
            "mom20",
            "mom60",
            "ma60",
            "amount_ratio20",
            "vol20",
            "ret",
            "benchmark_weight",
            "industry_relative_mom20",
        ]:
            if col in d.columns:
                d[col] = pd.to_numeric(d[col], errors="coerce")
        d["benchmark_weight"] = d.get("benchmark_weight", pd.Series(0.0, index=d.index)).fillna(0.0).clip(lower=0.0)
        d["strong_index_context"] = d.get("strong_index_context", pd.Series(False, index=d.index)).fillna(False).astype(bool)
        d["benchmark_seeded_core"] = d.get("benchmark_seeded_core", pd.Series(False, index=d.index)).fillna(False).astype(bool)

        eligible = _basic_eligible(d, params)
        benchmark_eligible = eligible & d["benchmark_weight"].gt(0)
        satellite_eligible = eligible & d["benchmark_weight"].le(0)
        weights_cfg = params.get("factor_weights", {})
        d["benchmark_rank_component"] = _rank_component(d, "benchmark_weight", benchmark_eligible, higher_is_better=True)
        d["mom60_rank_component"] = _rank_component(d, "mom60", eligible, higher_is_better=True)
        d["mom20_rank_component"] = _rank_component(d, "mom20", eligible, higher_is_better=True)
        d["amount_rank_component"] = _rank_component(d, "amount_ratio20", eligible, higher_is_better=True)
        d["low_vol_rank_component"] = _rank_component(d, "vol20", eligible, higher_is_better=False)
        d["industry_relative_rank_component"] = _rank_component(
            d, "industry_relative_mom20", eligible, higher_is_better=True
        )
        d["core_score"] = (
            float(weights_cfg.get("benchmark_weight", 0.40)) * d["benchmark_rank_component"]
            + float(weights_cfg.get("mom60", 0.20)) * d["mom60_rank_component"]
            + float(weights_cfg.get("mom20", 0.10)) * d["mom20_rank_component"]
            + float(weights_cfg.get("amount_ratio20", 0.15)) * d["amount_rank_component"]
            + float(weights_cfg.get("low_vol20", 0.10)) * d["low_vol_rank_component"]
            + float(weights_cfg.get("industry_relative_mom20", 0.05)) * d["industry_relative_rank_component"]
        )
        d["satellite_score"] = (
            0.35 * d["mom60_rank_component"]
            + 0.20 * d["mom20_rank_component"]
            + 0.20 * d["amount_rank_component"]
            + 0.15 * d["industry_relative_rank_component"]
            + 0.10 * d["low_vol_rank_component"]
        )
        d["rank_score"] = np.where(benchmark_eligible, d["core_score"], np.where(satellite_eligible, d["satellite_score"], np.nan))
        d["rank"] = np.nan
        ranked = d[d["rank_score"].notna()].sort_values(["date", "rank_score", "symbol"], ascending=[True, False, True])
        if not ranked.empty:
            d.loc[ranked.index, "rank"] = ranked.groupby("date").cumcount() + 1

        current_weights: dict[str, float] = {}
        held_days: dict[str, int] = {}
        frames: list[pd.DataFrame] = []
        for _, day in d.groupby("date", sort=True):
            day = day.copy()
            if bool(day["strong_index_context"].any()):
                current_weights = _target_weights_for_day(
                    day,
                    target_exposure=float(params.get("target_exposure", 0.70)),
                    core_budget_ratio=float(params.get("core_budget_ratio", 0.80)),
                    satellite_budget_ratio=float(params.get("satellite_budget_ratio", 0.20)),
                    core_top_n=int(params.get("core_top_n", 40)),
                    satellite_top_n=int(params.get("satellite_top_n", 8)),
                    max_symbol_weight=float(params.get("max_symbol_weight", 0.08)),
                    benchmark_weight_multiplier=float(params.get("benchmark_weight_multiplier", 1.8)),
                    max_names_per_industry=LowVolLowTurnoverQualityStrategy._optional_positive_int(
                        params.get("max_names_per_industry", 8)
                    ),
                )
            else:
                current_weights = {}
                held_days = {}

            day["review_day"] = True
            day["review_reason"] = "strong_context_core_seed" if current_weights else "not_strong_context"
            day["raw_weight"] = day["symbol"].map(lambda symbol: 1.0 if str(symbol) in current_weights else 0.0)
            day["weight_unshifted"] = day["symbol"].map(lambda symbol: current_weights.get(str(symbol), 0.0))
            day["selected"] = (day["weight_unshifted"] > 0).astype(float)
            day["held_days"] = day["symbol"].map(lambda symbol: held_days.get(str(symbol), 0)).fillna(0).astype(int)
            frames.append(day)
            held_days = {symbol: held_days.get(symbol, 0) + 1 for symbol in current_weights}

        out = pd.concat(frames, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)
        out["weight"] = out.groupby("symbol")["weight_unshifted"].shift(1).fillna(0.0)
        out["position_ret"] = out["weight"] * out["ret"].fillna(0.0)
        portfolio_weights = out.pivot(index="date", columns="symbol", values="weight").fillna(0.0)
        turnover = portfolio_weights.diff().abs().sum(axis=1).fillna(portfolio_weights.abs().sum(axis=1))
        sells = portfolio_weights.diff().clip(upper=0).abs().sum(axis=1).fillna(0.0)
        gross = out.groupby("date")["position_ret"].sum()
        costs = turnover * (slippage + commission) + sells * stamp_duty_sell
        returns = gross.sub(costs, fill_value=0.0)
        exposure = portfolio_weights.sum(axis=1)
        signal_cols = [
            "date",
            "symbol",
            "score",
            "rank",
            "selected",
            "raw_weight",
            "weight_unshifted",
            "weight",
            "held_days",
            "review_day",
            "review_reason",
            "ret",
            "position_ret",
            "benchmark_weight",
            "benchmark_weight_date",
            "benchmark_seeded_core",
            "strong_index_context",
            "strong_index_close",
            "strong_index_ret20",
            "strong_index_ret60",
            "strong_index_ma120",
            "strong_index_vol20",
            "strong_index_vol_threshold",
            "strong_index_drawdown",
            "benchmark_rank_component",
            "mom60_rank_component",
            "mom20_rank_component",
            "amount_rank_component",
            "low_vol_rank_component",
            "industry_relative_rank_component",
            "industry_relative_mom20",
            "industry",
            "name",
        ]
        out["score"] = out["rank_score"]
        signal_frame = out[[col for col in signal_cols if col in out.columns]].copy()
        return StrategyOutput(returns, exposure, signal_frame, self.build_metadata(params))

    def format_params(self, params: dict[str, Any]) -> str:
        return (
            "strong_market_core_participation@"
            f"index={params.get('benchmark_symbol', '')},"
            f"target_exposure={params.get('target_exposure', '')},"
            f"core_budget={params.get('core_budget_ratio', '')},"
            f"core_top={params.get('core_top_n', '')},"
            f"satellite_top={params.get('satellite_top_n', '')},"
            f"max_w={params.get('max_symbol_weight', '')},"
            f"threshold_status={params.get('threshold_status', '')}"
        )


def _strategy_cfg(strategy_cfg: dict[str, Any]) -> dict[str, Any]:
    return strategy_cfg.get("local_factor", {}).get("strong_market_core_participation", {})


def _fixed_params(cfg: dict[str, Any]) -> dict[str, Any]:
    factor_weights = cfg.get("factor_weights", {})
    return {
        "eligible": True,
        "benchmark_symbol": str(cfg.get("benchmark_symbol", "SH.000300")),
        "threshold_status": str(cfg.get("threshold_status", "pre_registered_i45_first_pass")),
        "trend_window": int(cfg.get("trend_window", 120)),
        "return_short_window": int(cfg.get("return_short_window", 20)),
        "return_long_window": int(cfg.get("return_long_window", 60)),
        "vol_window": int(cfg.get("vol_window", 20)),
        "vol_quantile": float(cfg.get("vol_quantile", 0.70)),
        "vol_threshold_lookback_days": int(cfg.get("vol_threshold_lookback_days", 252)),
        "drawdown_min": float(cfg.get("drawdown_min", -0.12)),
        "seed_top_n": int(cfg.get("seed_top_n", 20)),
        "seed_core_top_n": int(cfg.get("seed_core_top_n", 60)),
        "seed_core_cumulative_weight": float(cfg.get("seed_core_cumulative_weight", 0.60)),
        "core_top_n": int(cfg.get("core_top_n", 40)),
        "satellite_top_n": int(cfg.get("satellite_top_n", 8)),
        "target_exposure": float(cfg.get("target_exposure", 0.70)),
        "core_budget_ratio": float(cfg.get("core_budget_ratio", 0.80)),
        "satellite_budget_ratio": float(cfg.get("satellite_budget_ratio", 0.20)),
        "benchmark_weight_multiplier": float(cfg.get("benchmark_weight_multiplier", 1.8)),
        "max_symbol_weight": float(cfg.get("max_symbol_weight", 0.08)),
        "max_names_per_industry": int(cfg.get("max_names_per_industry", 8)),
        "amount_min": float(cfg.get("amount_min", 0.0)),
        "amount_ratio_min": float(cfg.get("amount_ratio_min", 0.0)),
        "factor_weights": {
            "benchmark_weight": float(factor_weights.get("benchmark_weight", 0.40)),
            "mom60": float(factor_weights.get("mom60", 0.20)),
            "mom20": float(factor_weights.get("mom20", 0.10)),
            "amount_ratio20": float(factor_weights.get("amount_ratio20", 0.15)),
            "low_vol20": float(factor_weights.get("low_vol20", 0.10)),
            "industry_relative_mom20": float(factor_weights.get("industry_relative_mom20", 0.05)),
        },
    }


def _seed_core_panel(panel: pd.DataFrame, cfg: dict[str, Any], fold_context: dict[str, Any]) -> pd.DataFrame:
    params = _fixed_params(cfg)
    train_start = _parse_date(fold_context.get("train_start"))
    train_end = _parse_date(fold_context.get("train_end"))
    valid_start = _parse_date(fold_context.get("valid_start"))
    valid_end = _parse_date(fold_context.get("valid_end"))
    if train_start is None or train_end is None or valid_start is None or valid_end is None:
        return panel
    weights = _load_benchmark_weights(
        str(params["benchmark_symbol"]),
        max(train_end, valid_end),
    )
    if weights.empty:
        return panel
    frames = [panel.copy()]
    frames.extend(
        _seed_window(
            panel,
            weights,
            start=train_start,
            end=train_end,
            as_of=train_end,
            params=params,
            window_label="train",
        )
    )
    frames.extend(
        _seed_window(
            panel,
            weights,
            start=valid_start,
            end=valid_end,
            as_of=valid_end,
            params=params,
            window_label="valid",
        )
    )
    combined = pd.concat(frames, ignore_index=True, sort=False)
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce").dt.normalize()
    combined["symbol"] = combined["symbol"].astype(str).str.strip()
    return combined.drop_duplicates(["date", "symbol"], keep="first").sort_values(["date", "symbol"]).reset_index(drop=True)


def _seed_window(
    panel: pd.DataFrame,
    weights: pd.DataFrame,
    *,
    start: date,
    end: date,
    as_of: date,
    params: dict[str, Any],
    window_label: str,
) -> list[pd.DataFrame]:
    del window_label
    weight_slice = weights[weights["trade_date_dt"].dt.date <= as_of].copy()
    if weight_slice.empty:
        return []
    seed_symbols = _select_seed_symbols(
        weight_slice,
        seed_top_n=int(params["seed_top_n"]),
        seed_core_top_n=int(params["seed_core_top_n"]),
        seed_core_cumulative_weight=float(params["seed_core_cumulative_weight"]),
    )
    missing_symbols = sorted(seed_symbols)
    frames: list[pd.DataFrame] = []
    for symbol in missing_symbols:
        hist = load_daily_from_local_history(
            symbol,
            start=start - timedelta(days=260),
            end=end,
            price_adjustment="qfq_asof",
            as_of_date=as_of,
        )
        if hist.empty:
            continue
        features = _price_features(hist)
        features = features[(features["date"].dt.date >= start) & (features["date"].dt.date <= end)].copy()
        if features.empty:
            continue
        features["symbol"] = symbol
        meta = _lookup_stock_metadata(symbol)
        features["name"] = meta.get("name", "")
        features["industry"] = meta.get("industry", "")
        features["benchmark_seeded_core"] = True
        frames.append(features)
    return frames


def _price_features(hist: pd.DataFrame) -> pd.DataFrame:
    out = hist.copy().sort_values("date").reset_index(drop=True)
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        out[col] = pd.to_numeric(out.get(col, np.nan), errors="coerce")
    out["ret"] = out["close"].pct_change().fillna(0.0)
    out["oc_ret"] = (out["close"] / out["open"].replace(0, np.nan) - 1.0).fillna(0.0)
    real_body = (out["close"] - out["open"]).abs()
    out["upper_shadow_pct"] = ((out["high"] - out[["open", "close"]].max(axis=1)) / real_body.replace(0, np.nan)).replace(
        [np.inf, -np.inf], np.nan
    ).fillna(0.0)
    for window in [20, 60]:
        out[f"mom{window}"] = out["close"].pct_change(window)
        out[f"ma{window}"] = out["close"].rolling(window).mean()
    out["vol20"] = out["ret"].rolling(20).std() * np.sqrt(252)
    out["amount_ma20"] = out["amount"].rolling(20).mean()
    out["amount_ratio20"] = (out["amount"] / out["amount_ma20"].replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
    out["breakout20"] = (out["close"] > out["high"].rolling(20).max().shift(1)).astype(float)
    return out.dropna(subset=["date", "close", "ret"]).reset_index(drop=True)


def _select_seed_symbols(
    weights: pd.DataFrame,
    *,
    seed_top_n: int,
    seed_core_top_n: int,
    seed_core_cumulative_weight: float,
) -> set[str]:
    symbols: set[str] = set()
    latest_dates = sorted(weights["trade_date_dt"].dropna().unique())
    for weight_date in latest_dates:
        day = weights[weights["trade_date_dt"].eq(pd.Timestamp(weight_date))].copy()
        if day.empty:
            continue
        day = day.sort_values(["benchmark_weight", "symbol"], ascending=[False, True]).reset_index(drop=True)
        day["rank"] = np.arange(1, len(day) + 1)
        day["cumulative_weight"] = day["benchmark_weight"].cumsum()
        keep = day["rank"].le(seed_core_top_n) | day["cumulative_weight"].le(seed_core_cumulative_weight)
        symbols.update(day.head(max(1, seed_top_n))["symbol"].astype(str).tolist())
        symbols.update(day[keep]["symbol"].astype(str).tolist())
    return symbols


def _attach_benchmark_weights(panel: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    if panel.empty or {"date", "symbol"}.difference(panel.columns):
        return panel
    dates = pd.to_datetime(panel["date"], errors="coerce").dropna().dt.normalize()
    if dates.empty:
        out = panel.copy()
        out["benchmark_weight"] = 0.0
        out["benchmark_weight_date"] = ""
        return out
    weights = _load_benchmark_weights(str(params.get("benchmark_symbol", "SH.000300")), dates.max().date())
    if weights.empty:
        out = panel.copy()
        out["benchmark_weight"] = 0.0
        out["benchmark_weight_date"] = ""
        return out
    unique_dates = pd.DataFrame({"date": pd.to_datetime(sorted(dates.unique())).astype("datetime64[ns]")})
    unique_dates["lookup_date"] = unique_dates["date"] - pd.Timedelta(days=1)
    unique_weight_dates = pd.DataFrame(
        {"benchmark_weight_date": pd.to_datetime(sorted(weights["trade_date_dt"].unique())).astype("datetime64[ns]")}
    )
    date_map = pd.merge_asof(
        unique_dates,
        unique_weight_dates,
        left_on="lookup_date",
        right_on="benchmark_weight_date",
        direction="backward",
    )[["date", "benchmark_weight_date"]]
    keyed = weights[["trade_date_dt", "symbol", "benchmark_weight"]].rename(columns={"trade_date_dt": "benchmark_weight_date"})
    out = panel.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out["symbol"] = out["symbol"].astype(str).str.strip()
    out = out.merge(date_map, on="date", how="left")
    out = out.merge(keyed, on=["benchmark_weight_date", "symbol"], how="left")
    out["benchmark_weight"] = pd.to_numeric(out["benchmark_weight"], errors="coerce").fillna(0.0)
    out["benchmark_weight_date"] = out["benchmark_weight_date"].dt.strftime("%Y-%m-%d").fillna("")
    return out


def _load_benchmark_weights(benchmark_symbol: str, max_date: date) -> pd.DataFrame:
    db_path = local_history_path()
    if not db_path.exists():
        return pd.DataFrame()
    try:
        with sqlite3.connect(db_path) as conn:
            has_table = bool(
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
                    ("cn_index_weights_asof",),
                ).fetchone()
            )
            if not has_table:
                return pd.DataFrame()
            weights = pd.read_sql_query(
                """
                SELECT trade_date, symbol, weight
                FROM cn_index_weights_asof
                WHERE index_code = ?
                  AND trade_date <= ?
                ORDER BY trade_date, symbol
                """,
                conn,
                params=(benchmark_symbol, max_date.isoformat()),
            )
    except sqlite3.Error:
        return pd.DataFrame()
    if weights.empty:
        return weights
    weights["trade_date_dt"] = pd.to_datetime(weights["trade_date"], errors="coerce").dt.normalize()
    weights = weights.dropna(subset=["trade_date_dt"]).copy()
    weights["symbol"] = weights["symbol"].astype(str).str.strip()
    weights["benchmark_weight"] = pd.to_numeric(weights["weight"], errors="coerce").fillna(0.0)
    sums = weights.groupby("trade_date_dt")["benchmark_weight"].transform("sum")
    weights["benchmark_weight"] = weights["benchmark_weight"] / np.where(sums > 2.0, 100.0, 1.0)
    return weights[["trade_date_dt", "symbol", "benchmark_weight"]].copy()


def _add_industry_relative_features(panel: pd.DataFrame) -> pd.DataFrame:
    d = panel.copy()
    if not {"date", "industry", "mom20"}.issubset(d.columns):
        d["industry_relative_mom20"] = 0.0
        return d
    industries = d["industry"].astype("string").str.strip()
    valid_industry = industries.notna() & (industries != "") & (industries.str.lower() != "nan")
    d["_industry_key"] = industries.where(valid_industry, pd.NA)
    d["industry_mom20"] = d.groupby(["date", "_industry_key"], dropna=True)["mom20"].transform("mean")
    d["industry_relative_mom20"] = d["industry_mom20"] - d.groupby("date")["mom20"].transform("mean")
    return d.drop(columns=["_industry_key"])


def _basic_eligible(d: pd.DataFrame, params: dict[str, Any]) -> pd.Series:
    required = d[["close", "amount", "ret"]].notna().all(axis=1)
    return (
        required
        & d["close"].gt(0)
        & d["amount"].ge(float(params.get("amount_min", 0.0)))
        & d["amount_ratio20"].ge(float(params.get("amount_ratio_min", 0.0)))
    )


def _target_weights_for_day(
    day: pd.DataFrame,
    *,
    target_exposure: float,
    core_budget_ratio: float,
    satellite_budget_ratio: float,
    core_top_n: int,
    satellite_top_n: int,
    max_symbol_weight: float,
    benchmark_weight_multiplier: float,
    max_names_per_industry: int | None,
) -> dict[str, float]:
    core_budget = max(0.0, min(target_exposure, target_exposure * core_budget_ratio))
    satellite_budget = max(0.0, min(target_exposure - core_budget, target_exposure * satellite_budget_ratio))
    selected: dict[str, float] = {}
    core = day[day["benchmark_weight"].gt(0) & day["core_score"].notna()].sort_values(
        ["core_score", "symbol"], ascending=[False, True]
    )
    caps: dict[str, float] = {}
    for _, row in core.iterrows():
        if len(selected) >= core_top_n:
            break
        symbol = str(row["symbol"])
        cap = min(max_symbol_weight, max(0.01, float(row["benchmark_weight"]) * benchmark_weight_multiplier))
        selected[symbol] = cap
        caps[symbol] = max_symbol_weight
        if sum(selected.values()) >= core_budget:
            break
    selected = _scale_to_budget(selected, core_budget, caps=caps)

    satellite: dict[str, float] = {}
    if satellite_budget > 0:
        satellite_candidates = day[day["benchmark_weight"].le(0) & day["satellite_score"].notna()].sort_values(
            ["satellite_score", "symbol"], ascending=[False, True]
        )
        for _, row in satellite_candidates.iterrows():
            if len(satellite) >= satellite_top_n:
                break
            symbol = str(row["symbol"])
            if not _industry_slot_available(day, [*selected.keys(), *satellite.keys()], symbol, max_names_per_industry):
                continue
            satellite[symbol] = max_symbol_weight
    selected.update(_scale_to_budget(satellite, satellite_budget))
    return {symbol: weight for symbol, weight in selected.items() if weight > 1e-12}


def _scale_to_budget(
    weights: dict[str, float],
    budget: float,
    *,
    caps: dict[str, float] | None = None,
) -> dict[str, float]:
    if not weights or budget <= 0:
        return {}
    total = sum(weights.values())
    if total <= 0:
        return {}
    if total >= budget:
        scale = budget / total
        return {symbol: weight * scale for symbol, weight in weights.items()}
    out = dict(weights)
    caps = caps or {symbol: max(weight, budget) for symbol, weight in weights.items()}
    for _ in range(len(out) + 2):
        current_total = sum(out.values())
        deficit = budget - current_total
        if deficit <= 1e-12:
            break
        expandable = [symbol for symbol in out if out[symbol] < float(caps.get(symbol, out[symbol])) - 1e-12]
        if not expandable:
            break
        base_total = sum(max(weights[symbol], 1e-12) for symbol in expandable)
        for symbol in expandable:
            cap = float(caps.get(symbol, out[symbol]))
            add = deficit * max(weights[symbol], 1e-12) / base_total
            out[symbol] = min(cap, out[symbol] + add)
    total = sum(out.values())
    if total > budget:
        scale = budget / total
        out = {symbol: weight * scale for symbol, weight in out.items()}
    return out


def _industry_slot_available(
    day: pd.DataFrame,
    selected_symbols: list[str],
    symbol: str,
    max_names_per_industry: int | None,
) -> bool:
    if max_names_per_industry is None or max_names_per_industry <= 0:
        return True
    indexed = day.set_index(day["symbol"].astype(str))
    if symbol not in indexed.index:
        return False
    industry = str(indexed.loc[symbol].get("industry", "")).strip()
    if not industry:
        return True
    selected_industries = [
        str(indexed.loc[item].get("industry", "")).strip()
        for item in selected_symbols
        if item in indexed.index
    ]
    return selected_industries.count(industry) < int(max_names_per_industry)


def _lookup_stock_metadata(symbol: str) -> dict[str, str]:
    db_path = local_history_path()
    if not db_path.exists():
        return {"name": "", "industry": ""}
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT name, industry FROM market_stocks WHERE market = ? AND symbol = ? LIMIT 1",
                ("CN", symbol),
            ).fetchone()
    except sqlite3.Error:
        return {"name": "", "industry": ""}
    if not row:
        return {"name": "", "industry": ""}
    return {"name": "" if row[0] is None else str(row[0]), "industry": "" if row[1] is None else str(row[1])}


def _parse_date(value: Any) -> date | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return pd.Timestamp(value).date()
    except (TypeError, ValueError):
        return None


def _ineligible_reason(panel: pd.DataFrame) -> str | None:
    required = [
        "date",
        "symbol",
        "close",
        "mom20",
        "mom60",
        "ma60",
        "amount",
        "amount_ratio20",
        "vol20",
        "ret",
        "industry",
        "benchmark_weight",
        "strong_index_context",
    ]
    missing = [col for col in required if col not in panel.columns]
    if missing:
        return "missing_required_fields:" + ",".join(missing)
    return None


def _all_cash_output(
    panel: pd.DataFrame,
    params: dict[str, Any],
    strategy: StrongMarketCoreParticipationStrategy,
    *,
    reason: str,
) -> StrategyOutput:
    dates = pd.Index([])
    if "date" in panel.columns:
        dates = pd.Index(sorted(pd.to_datetime(panel["date"], errors="coerce").dropna().unique()))
    empty = pd.Series(0.0, index=dates)
    metadata = strategy.build_metadata(params)
    metadata["ineligible_reason"] = reason
    return StrategyOutput(empty, empty, pd.DataFrame(), metadata)
