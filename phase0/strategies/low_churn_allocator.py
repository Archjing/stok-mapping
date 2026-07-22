from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from phase0.strategies.base import StrategyOutput


def optional_positive_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def allocate_low_churn(
    scored_panel: pd.DataFrame,
    *,
    params: dict[str, Any],
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
    signal_columns: list[str],
    metadata: dict[str, Any],
) -> StrategyOutput:
    if scored_panel.empty:
        empty = pd.Series(dtype=float)
        return StrategyOutput(empty, empty, pd.DataFrame(), metadata)

    required = {"date", "symbol", "final_score", "risk_overlay_scale", "ret"}
    if not required.issubset(scored_panel.columns):
        dates = pd.Index(sorted(scored_panel.get("date", pd.Series(dtype=object)).dropna().unique()))
        empty = pd.Series(0.0, index=dates)
        return StrategyOutput(empty, empty, pd.DataFrame(), metadata)

    d = scored_panel.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
    d["rank"] = d.groupby("date")["final_score"].rank(method="first", ascending=False)
    d["rank_score"] = d["final_score"].where(d["final_score"].notna(), np.nan)
    buy_top_n = max(1, int(params.get("buy_top_n", params.get("top_n", 10))))
    hold_top_n = max(buy_top_n, int(params.get("hold_top_n", buy_top_n * 2)))
    rebalance_days = max(1, int(params.get("rebalance_days", 20)))
    min_hold_days = max(0, int(params.get("min_hold_days", 20)))
    max_symbol_weight = max(0.0, float(params.get("max_symbol_weight", 0.10)))
    max_names_per_industry = optional_positive_int(params.get("max_names_per_industry"))

    current_weights: dict[str, float] = {}
    held_days: dict[str, int] = {}
    frames: list[pd.DataFrame] = []
    for idx, (_, day) in enumerate(d.groupby("date", sort=True)):
        day = day.copy()
        review_reason = ""
        if idx % rebalance_days == 0:
            review_reason = "fixed_rebalance"
            indexed = day.set_index(day["symbol"].astype(str))
            for symbol in list(current_weights):
                if symbol not in indexed.index:
                    rank = np.nan
                    score = np.nan
                else:
                    row = indexed.loc[symbol]
                    rank = row["rank"]
                    score = row["rank_score"]
                old_enough = held_days.get(symbol, 0) >= min_hold_days
                outside_hold_band = pd.isna(rank) or float(rank) > hold_top_n or pd.isna(score)
                if old_enough and outside_hold_band:
                    current_weights.pop(symbol, None)
                    held_days.pop(symbol, None)

            candidates = day[day["rank_score"].notna()].sort_values(["rank", "symbol"])
            for symbol in candidates["symbol"].astype(str):
                if len(current_weights) >= buy_top_n:
                    break
                if not _industry_slot_available(
                    symbol=symbol,
                    day=day,
                    current_weights=current_weights,
                    max_names_per_industry=max_names_per_industry,
                ):
                    continue
                if symbol not in current_weights:
                    current_weights[symbol] = 0.0
                    held_days[symbol] = 0

            active = [symbol for symbol in current_weights if symbol in set(day["symbol"].astype(str))]
            if active:
                indexed = day.set_index(day["symbol"].astype(str))
                raw_weight = min(max_symbol_weight, 1.0 / len(active))
                current_weights = {
                    symbol: raw_weight
                    * float(
                        pd.to_numeric(
                            pd.Series([indexed.loc[symbol, "risk_overlay_scale"]]), errors="coerce"
                        )
                        .fillna(1.0)
                        .iloc[0]
                    )
                    for symbol in active
                }
            else:
                current_weights = {}

        day["review_reason"] = review_reason
        day["raw_weight"] = day["symbol"].astype(str).map(lambda symbol: 1.0 if symbol in current_weights else 0.0)
        day["weight_unshifted"] = day["symbol"].astype(str).map(lambda symbol: current_weights.get(symbol, 0.0))
        day["selected"] = (day["weight_unshifted"] > 0).astype(float)
        day["held_days"] = day["symbol"].astype(str).map(lambda symbol: held_days.get(symbol, 0)).fillna(0).astype(int)
        frames.append(day)
        for symbol in list(current_weights):
            held_days[symbol] = held_days.get(symbol, 0) + 1

    out = pd.concat(frames, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)
    out["weight"] = out.groupby("symbol")["weight_unshifted"].shift(1).fillna(0.0)
    out["position_ret"] = out["weight"] * pd.to_numeric(out["ret"], errors="coerce").fillna(0.0)

    weights = out.pivot(index="date", columns="symbol", values="weight").fillna(0.0)
    turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
    sells = weights.diff().clip(upper=0).abs().sum(axis=1).fillna(0.0)
    gross = out.groupby("date")["position_ret"].sum()
    costs = turnover * (slippage + commission) + sells * stamp_duty_sell
    returns = gross.sub(costs, fill_value=0.0)
    exposure = weights.sum(axis=1)
    signal_frame = out[[col for col in signal_columns if col in out.columns]].copy()
    return StrategyOutput(returns=returns, exposure=exposure, signal_frame=signal_frame, metadata=metadata)


def _industry_slot_available(
    *,
    symbol: str,
    day: pd.DataFrame,
    current_weights: dict[str, float],
    max_names_per_industry: int | None,
) -> bool:
    if max_names_per_industry is None or "industry" not in day.columns:
        return True
    indexed = day.set_index(day["symbol"].astype(str))
    if symbol not in indexed.index:
        return True
    industry = _clean_industry(indexed.loc[symbol, "industry"])
    active_symbols = [active for active in current_weights if active in indexed.index]
    same_industry_count = 0
    for active in active_symbols:
        if _clean_industry(indexed.loc[active, "industry"]) == industry:
            same_industry_count += 1
    return same_industry_count < max_names_per_industry


def _clean_industry(value: Any) -> str:
    industry = str(value).strip()
    if industry.lower() in {"", "nan", "none", "<na>", "nat"}:
        return "UNKNOWN"
    return industry
