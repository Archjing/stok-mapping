from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from quant.strategies.base import StrategyOutput


EPS = 1e-12
UNKNOWN_INDUSTRY = "UNKNOWN"


@dataclass(frozen=True)
class ConstraintEngineResult:
    output: StrategyOutput
    metrics: dict[str, Any]


def apply_strategy_constraints(
    output: StrategyOutput,
    *,
    strategy_name: str,
    panel_scope: str,
    strategy_cfg: dict[str, Any],
    panel: pd.DataFrame,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
) -> ConstraintEngineResult:
    """Apply configured portfolio constraints after a strategy emits target weights."""
    constraints_cfg = strategy_cfg.get("constraints", {})
    if not bool(constraints_cfg.get("enabled", False)):
        return ConstraintEngineResult(output=output, metrics={})

    apply_to = [str(item) for item in constraints_cfg.get("apply_to", [])]
    if apply_to and strategy_name not in apply_to:
        return ConstraintEngineResult(output=output, metrics={})

    industry_cfg = constraints_cfg.get("industry", {})
    if not bool(industry_cfg.get("enabled", False)):
        return ConstraintEngineResult(output=output, metrics={})

    mode = str(industry_cfg.get("mode", "off")).strip().lower()
    if mode not in {"audit", "enforce"}:
        return ConstraintEngineResult(output=output, metrics=_base_metrics(mode="off", enabled=False, status="disabled"))

    signal = _prepare_signal_frame(output.signal_frame, panel)
    if signal.empty:
        return ConstraintEngineResult(
            output=output,
            metrics=_base_metrics(mode=mode, enabled=True, status="skipped_empty_signal"),
        )

    audit_before = audit_industry_exposure(signal, industry_cfg)
    metrics = {
        **_base_metrics(mode=mode, enabled=True, status="audited"),
        **audit_before,
    }

    if mode == "audit":
        return ConstraintEngineResult(output=output, metrics=metrics)

    if str(panel_scope) != "portfolio":
        metrics["constraint_status"] = "skipped_non_portfolio"
        return ConstraintEngineResult(output=output, metrics=metrics)

    missing = [col for col in ["date", "symbol", "weight_unshifted", "ret", "industry"] if col not in signal.columns]
    if missing:
        metrics["constraint_status"] = "skipped_missing_columns:" + ",".join(missing)
        return ConstraintEngineResult(output=output, metrics=metrics)

    constrained = enforce_industry_constraints(signal, industry_cfg)
    constrained_output = _recompute_output(
        output,
        constrained,
        slippage=slippage,
        commission=commission,
        stamp_duty_sell=stamp_duty_sell,
    )
    metrics = {
        **_base_metrics(mode=mode, enabled=True, status="enforced"),
        **audit_industry_exposure(constrained_output.signal_frame, industry_cfg),
    }
    return ConstraintEngineResult(output=constrained_output, metrics=metrics)


def audit_industry_exposure(signal_frame: pd.DataFrame, industry_cfg: dict[str, Any]) -> dict[str, Any]:
    signal = _normalize_signal(signal_frame)
    if signal.empty or "weight" not in signal.columns:
        return _empty_industry_metrics()
    if "industry" not in signal.columns:
        metrics = _empty_industry_metrics()
        metrics["industry_constraint_violation_days"] = 0
        return metrics

    weight = pd.to_numeric(signal["weight"], errors="coerce").fillna(0.0)
    holding = signal[weight.abs() > EPS].copy()
    if holding.empty:
        return _empty_industry_metrics()

    holding["abs_weight"] = pd.to_numeric(holding["weight"], errors="coerce").fillna(0.0).abs()
    holding["industry"] = _clean_industry(holding["industry"])
    daily_count = holding.groupby("date", as_index=False)["symbol"].nunique().rename(columns={"symbol": "holding_count"})
    daily_industry_count = holding.groupby("date", as_index=False)["industry"].nunique().rename(columns={"industry": "industry_count"})

    industry_daily = holding.groupby(["date", "industry"], as_index=False).agg(
        abs_weight=("abs_weight", "sum"),
        name_count=("symbol", "nunique"),
    )
    top1 = (
        industry_daily.sort_values(["date", "abs_weight"], ascending=[True, False])
        .groupby("date", as_index=False)
        .first()[["date", "abs_weight"]]
        .rename(columns={"abs_weight": "top1_share"})
    )
    top3 = (
        industry_daily.sort_values(["date", "abs_weight"], ascending=[True, False])
        .groupby("date")
        .head(3)
        .groupby("date", as_index=False)["abs_weight"]
        .sum()
        .rename(columns={"abs_weight": "top3_share"})
    )
    daily = daily_count.merge(daily_industry_count, on="date").merge(top1, on="date").merge(top3, on="date")

    max_weight = _optional_float(industry_cfg.get("max_industry_weight"))
    max_names = _optional_int(industry_cfg.get("max_names_per_industry"))
    violation_dates: set[pd.Timestamp] = set()
    if max_weight is not None:
        violation_dates.update(industry_daily.loc[industry_daily["abs_weight"] > max_weight + EPS, "date"].tolist())
    if max_names is not None:
        violation_dates.update(industry_daily.loc[industry_daily["name_count"] > max_names, "date"].tolist())

    unknown = holding[holding["industry"] == UNKNOWN_INDUSTRY]
    unknown_daily = unknown.groupby("date")["abs_weight"].sum() if not unknown.empty else pd.Series(dtype=float)
    unknown_weight = unknown_daily.reindex(daily["date"], fill_value=0.0)

    return {
        "avg_industries": float(daily["industry_count"].mean()) if not daily.empty else 0.0,
        "top_industry_avg_share": float(daily["top1_share"].mean()) if not daily.empty else 0.0,
        "top_industry_p95_share": float(daily["top1_share"].quantile(0.95)) if not daily.empty else 0.0,
        "top_industry_max_share": float(daily["top1_share"].max()) if not daily.empty else 0.0,
        "top3_industries_avg_share": float(daily["top3_share"].mean()) if not daily.empty else 0.0,
        "industry_constraint_violation_days": int(len(violation_dates)),
        "unknown_industry_weight_avg": float(unknown_weight.mean()) if len(unknown_weight) else 0.0,
    }


def enforce_industry_constraints(signal_frame: pd.DataFrame, industry_cfg: dict[str, Any]) -> pd.DataFrame:
    signal = _normalize_signal(signal_frame)
    if signal.empty:
        return signal
    signal["industry"] = _clean_industry(signal["industry"])
    policy = str(industry_cfg.get("unknown_industry_policy", "allow")).strip().lower()
    if policy not in {"allow", "cap", "reject"}:
        policy = "allow"

    frames: list[pd.DataFrame] = []
    previous_original: dict[str, float] | None = None
    previous_constrained: dict[str, float] | None = None
    for _, day in signal.groupby("date", sort=True):
        adjusted = day.copy()
        adjusted["weight_unshifted"] = pd.to_numeric(adjusted["weight_unshifted"], errors="coerce").fillna(0.0)
        original_weights = _active_weight_map(adjusted, "weight_unshifted")
        if original_weights and previous_original is not None and previous_constrained is not None and _weights_equal(original_weights, previous_original):
            adjusted["weight_unshifted"] = adjusted["symbol"].astype(str).map(previous_constrained).fillna(0.0)
        elif original_weights:
            adjusted = _enforce_max_names(adjusted, industry_cfg, policy)
            adjusted = _enforce_max_industry_weight(adjusted, industry_cfg, policy)
            previous_original = original_weights
            previous_constrained = _active_weight_map(adjusted, "weight_unshifted")
        else:
            previous_original = {}
            previous_constrained = {}
        frames.append(adjusted)
    out = pd.concat(frames, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)
    out["selected"] = (pd.to_numeric(out["weight_unshifted"], errors="coerce").fillna(0.0).abs() > EPS).astype(float)
    if "raw_weight" in out.columns:
        out["raw_weight"] = out["selected"]
    return out


def _prepare_signal_frame(signal_frame: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    signal = _normalize_signal(signal_frame)
    if signal.empty:
        return signal
    if panel.empty:
        return signal
    meta_cols = [col for col in ["date", "symbol", "industry", "name"] if col in panel.columns]
    if "symbol" not in meta_cols:
        return signal
    meta = panel[meta_cols].copy()
    meta["symbol"] = meta["symbol"].astype(str)
    if "date" in meta.columns and "date" in signal.columns:
        meta["date"] = pd.to_datetime(meta["date"], errors="coerce").dt.normalize()
        join_cols = ["date", "symbol"]
    else:
        meta = meta.drop(columns=["date"], errors="ignore").drop_duplicates("symbol")
        join_cols = ["symbol"]
    meta = meta.drop_duplicates(join_cols)
    if meta.empty:
        return signal

    rename = {col: f"__panel_{col}" for col in meta.columns if col not in join_cols}
    merged = signal.merge(meta.rename(columns=rename), on=join_cols, how="left")
    for col in ["industry", "name"]:
        panel_col = f"__panel_{col}"
        if panel_col not in merged.columns:
            continue
        if col not in merged.columns:
            merged[col] = merged[panel_col]
        else:
            current = merged[col]
            missing = current.isna() | current.astype(str).str.strip().eq("")
            merged[col] = current.where(~missing, merged[panel_col])
    return merged.drop(columns=[col for col in merged.columns if col.startswith("__panel_")])


def _recompute_output(
    original: StrategyOutput,
    signal_frame: pd.DataFrame,
    *,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
) -> StrategyOutput:
    out = _normalize_signal(signal_frame)
    out["weight_unshifted"] = pd.to_numeric(out["weight_unshifted"], errors="coerce").fillna(0.0)
    out["ret"] = pd.to_numeric(out["ret"], errors="coerce").fillna(0.0)
    out = out.sort_values(["symbol", "date"]).reset_index(drop=True)
    out["weight"] = out.groupby("symbol")["weight_unshifted"].shift(1).fillna(0.0)
    out["position_ret"] = out["weight"] * out["ret"]

    weights = out.pivot(index="date", columns="symbol", values="weight").fillna(0.0)
    turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
    sells = weights.diff().clip(upper=0).abs().sum(axis=1).fillna(0.0)
    gross = out.groupby("date")["position_ret"].sum()
    costs = turnover * (float(slippage) + float(commission)) + sells * float(stamp_duty_sell)
    returns = gross.sub(costs, fill_value=0.0)
    exposure = weights.sum(axis=1)
    metadata = dict(original.metadata or {})
    metadata["constraints_applied"] = True
    return StrategyOutput(returns=returns, exposure=exposure, signal_frame=out, metadata=metadata)


def _enforce_max_names(day: pd.DataFrame, industry_cfg: dict[str, Any], policy: str) -> pd.DataFrame:
    max_names = _optional_int(industry_cfg.get("max_names_per_industry"))
    if max_names is None:
        return day
    adjusted = day.copy()
    active = adjusted[pd.to_numeric(adjusted["weight_unshifted"], errors="coerce").fillna(0.0).abs() > EPS].copy()
    if active.empty:
        return adjusted
    if policy == "reject":
        reject_idx = active.index[active["industry"] == UNKNOWN_INDUSTRY]
        adjusted.loc[reject_idx, "weight_unshifted"] = 0.0
        active = active.drop(index=reject_idx, errors="ignore")
    sortable = active.copy()
    sortable["_sort_score"] = pd.to_numeric(sortable.get("score", pd.Series(np.nan, index=sortable.index)), errors="coerce")
    sortable["_sort_weight"] = pd.to_numeric(sortable["weight_unshifted"], errors="coerce").fillna(0.0).abs()
    for industry, group in sortable.groupby("industry", sort=False):
        if policy == "allow" and industry == UNKNOWN_INDUSTRY:
            continue
        if len(group) <= max_names:
            continue
        keep = (
            group.sort_values(["_sort_score", "_sort_weight", "symbol"], ascending=[False, False, True])
            .head(max_names)
            .index
        )
        drop_idx = group.index.difference(keep)
        adjusted.loc[drop_idx, "weight_unshifted"] = 0.0
    return adjusted


def _enforce_max_industry_weight(day: pd.DataFrame, industry_cfg: dict[str, Any], policy: str) -> pd.DataFrame:
    max_weight = _optional_float(industry_cfg.get("max_industry_weight"))
    if max_weight is None or max_weight <= 0:
        return day
    max_weight = min(max_weight, 1.0)
    adjusted = day.copy()
    if policy == "reject":
        adjusted.loc[adjusted["industry"] == UNKNOWN_INDUSTRY, "weight_unshifted"] = 0.0
    active = adjusted[pd.to_numeric(adjusted["weight_unshifted"], errors="coerce").fillna(0.0).abs() > EPS].copy()
    if policy == "allow":
        active = active[active["industry"] != UNKNOWN_INDUSTRY]
    if active.empty:
        return adjusted
    weights = pd.to_numeric(active["weight_unshifted"], errors="coerce").fillna(0.0).abs()
    industry_weight = weights.groupby(active["industry"]).sum()
    for industry, group_total in industry_weight.items():
        group_total = float(group_total)
        if group_total <= max_weight + EPS:
            continue
        group_idx = active.index[active["industry"] == industry]
        scale = max_weight / group_total if group_total > EPS else 0.0
        adjusted.loc[group_idx, "weight_unshifted"] = pd.to_numeric(
            adjusted.loc[group_idx, "weight_unshifted"],
            errors="coerce",
        ).fillna(0.0) * scale
    return adjusted


def _active_weight_map(frame: pd.DataFrame, column: str) -> dict[str, float]:
    weights = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    active = frame.loc[weights.abs() > EPS, ["symbol"]].copy()
    if active.empty:
        return {}
    active["_weight"] = weights.loc[active.index].astype(float)
    return {str(row["symbol"]): float(row["_weight"]) for _, row in active.iterrows()}


def _weights_equal(left: dict[str, float], right: dict[str, float]) -> bool:
    if left.keys() != right.keys():
        return False
    return all(abs(float(left[key]) - float(right[key])) <= EPS for key in left)


def _normalize_signal(signal_frame: pd.DataFrame) -> pd.DataFrame:
    if signal_frame is None or signal_frame.empty:
        return pd.DataFrame()
    signal = signal_frame.copy()
    if "date" in signal.columns:
        signal["date"] = pd.to_datetime(signal["date"], errors="coerce").dt.normalize()
    if "symbol" in signal.columns:
        signal["symbol"] = signal["symbol"].astype(str)
    return signal


def _clean_industry(series: pd.Series) -> pd.Series:
    cleaned = series.fillna("").astype(str).str.strip()
    return cleaned.mask(cleaned.eq("") | cleaned.str.lower().eq("nan"), UNKNOWN_INDUSTRY)


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _base_metrics(*, mode: str, enabled: bool, status: str) -> dict[str, Any]:
    return {
        "constraint_mode": mode,
        "industry_constraint_enabled": bool(enabled),
        "constraint_status": status,
    }


def _empty_industry_metrics() -> dict[str, Any]:
    return {
        "avg_industries": 0.0,
        "top_industry_avg_share": 0.0,
        "top_industry_p95_share": 0.0,
        "top_industry_max_share": 0.0,
        "top3_industries_avg_share": 0.0,
        "industry_constraint_violation_days": 0,
        "unknown_industry_weight_avg": 0.0,
    }
