from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_CONTEXT_LABEL = "relative_lag_in_strong_benchmark_context"


@dataclass(frozen=True)
class StrategyAlphaSourceAuditResult:
    fold_comparison_csv_path: Path
    symbol_contribution_csv_path: Path
    industry_contribution_csv_path: Path
    missed_top_csv_path: Path
    report_md_path: Path
    fold_rows: int
    symbol_rows: int
    industry_rows: int


def run_strategy_alpha_source_audit(
    *,
    baseline_label: str,
    treatment_label: str,
    baseline_csi300_fold_path: Path,
    treatment_csi300_fold_path: Path,
    baseline_holdings_path: Path,
    treatment_holdings_path: Path,
    output_dir: Path,
    baseline_missed_top_path: Path | None = None,
    treatment_missed_top_path: Path | None = None,
    context_label: str = DEFAULT_CONTEXT_LABEL,
) -> StrategyAlphaSourceAuditResult:
    """Compare two research iterations and explain alpha source changes.

    This diagnostic is intentionally read-only. It consumes existing admission,
    CSI300 attribution, and holdings exposure artifacts, then writes compact
    comparison tables suitable for strategy-governance reports.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline_folds = _filter_context(
        _read_required_csv(baseline_csi300_fold_path, "baseline CSI300 fold attribution"),
        context_label,
    )
    treatment_folds = _filter_context(
        _read_required_csv(treatment_csi300_fold_path, "treatment CSI300 fold attribution"),
        context_label,
    )
    baseline_holdings = _filter_context(
        _read_required_csv(baseline_holdings_path, "baseline holdings"),
        context_label,
    )
    treatment_holdings = _filter_context(
        _read_required_csv(treatment_holdings_path, "treatment holdings"),
        context_label,
    )
    baseline_missed = _filter_context(_read_optional_csv(baseline_missed_top_path), context_label)
    treatment_missed = _filter_context(_read_optional_csv(treatment_missed_top_path), context_label)

    _require_columns(
        baseline_folds,
        ["strategy_id", "walk_forward_preset", "fold", "valid_start", "valid_end", "market_context_label"],
        baseline_csi300_fold_path,
    )
    _require_columns(
        treatment_folds,
        ["strategy_id", "walk_forward_preset", "fold", "valid_start", "valid_end", "market_context_label"],
        treatment_csi300_fold_path,
    )
    _require_columns(
        baseline_holdings,
        ["strategy_id", "walk_forward_preset", "fold", "date", "symbol", "industry", "live_weight", "position_ret"],
        baseline_holdings_path,
    )
    _require_columns(
        treatment_holdings,
        ["strategy_id", "walk_forward_preset", "fold", "date", "symbol", "industry", "live_weight", "position_ret"],
        treatment_holdings_path,
    )

    fold_comparison = _fold_comparison(
        baseline_folds,
        treatment_folds,
        baseline_label=baseline_label,
        treatment_label=treatment_label,
    )
    symbol_contribution = _entity_contribution_comparison(
        baseline_holdings,
        treatment_holdings,
        group_column="symbol",
        baseline_label=baseline_label,
        treatment_label=treatment_label,
    )
    industry_contribution = _entity_contribution_comparison(
        baseline_holdings,
        treatment_holdings,
        group_column="industry",
        baseline_label=baseline_label,
        treatment_label=treatment_label,
    )
    missed_top = _missed_top_comparison(
        baseline_missed,
        treatment_missed,
        baseline_label=baseline_label,
        treatment_label=treatment_label,
    )

    fold_path = output_dir / "strategy_alpha_source_fold_comparison.csv"
    symbol_path = output_dir / "strategy_alpha_source_symbol_contribution.csv"
    industry_path = output_dir / "strategy_alpha_source_industry_contribution.csv"
    missed_path = output_dir / "strategy_alpha_source_missed_top_comparison.csv"
    md_path = output_dir / "strategy_alpha_source_audit.md"

    fold_comparison.to_csv(fold_path, index=False)
    symbol_contribution.to_csv(symbol_path, index=False)
    industry_contribution.to_csv(industry_path, index=False)
    missed_top.to_csv(missed_path, index=False)
    _write_markdown(
        md_path,
        fold_comparison=fold_comparison,
        symbol_contribution=symbol_contribution,
        industry_contribution=industry_contribution,
        missed_top=missed_top,
        baseline_label=baseline_label,
        treatment_label=treatment_label,
        context_label=context_label,
        input_paths={
            "baseline_csi300_fold": baseline_csi300_fold_path,
            "treatment_csi300_fold": treatment_csi300_fold_path,
            "baseline_holdings": baseline_holdings_path,
            "treatment_holdings": treatment_holdings_path,
            "baseline_missed_top": baseline_missed_top_path,
            "treatment_missed_top": treatment_missed_top_path,
        },
    )

    return StrategyAlphaSourceAuditResult(
        fold_comparison_csv_path=fold_path,
        symbol_contribution_csv_path=symbol_path,
        industry_contribution_csv_path=industry_path,
        missed_top_csv_path=missed_path,
        report_md_path=md_path,
        fold_rows=len(fold_comparison),
        symbol_rows=len(symbol_contribution),
        industry_rows=len(industry_contribution),
    )


def _fold_comparison(
    baseline: pd.DataFrame,
    treatment: pd.DataFrame,
    *,
    baseline_label: str,
    treatment_label: str,
) -> pd.DataFrame:
    keys = ["walk_forward_preset", "fold", "valid_start", "valid_end", "market_context_label"]
    baseline_prepared = _prepare_fold_frame(baseline, baseline_label)
    treatment_prepared = _prepare_fold_frame(treatment, treatment_label)
    merged = baseline_prepared.merge(treatment_prepared, on=keys, how="outer", suffixes=("_baseline", "_treatment"))
    rows: list[dict[str, Any]] = []
    for _, row in merged.sort_values(["walk_forward_preset", "fold"], na_position="last").iterrows():
        base_excess = _to_float(row.get("excess_total_return_baseline"))
        treatment_excess = _to_float(row.get("excess_total_return_treatment"))
        base_live = _to_float(row.get("avg_live_exposure_baseline"))
        treatment_live = _to_float(row.get("avg_live_exposure_treatment"))
        base_held = _to_float(row.get("avg_benchmark_weight_held_baseline"))
        treatment_held = _to_float(row.get("avg_benchmark_weight_held_treatment"))
        base_top = _to_float(row.get("avg_top_n_coverage_ratio_baseline"))
        treatment_top = _to_float(row.get("avg_top_n_coverage_ratio_treatment"))
        base_industry_gap = _to_float(row.get("avg_industry_l1_gap_normalized_baseline"))
        treatment_industry_gap = _to_float(row.get("avg_industry_l1_gap_normalized_treatment"))
        rows.append(
            {
                "baseline_label": baseline_label,
                "treatment_label": treatment_label,
                "walk_forward_preset": row.get("walk_forward_preset"),
                "fold": row.get("fold"),
                "valid_start": row.get("valid_start"),
                "valid_end": row.get("valid_end"),
                "market_context_label": row.get("market_context_label"),
                "baseline_strategy_id": row.get("strategy_id_baseline"),
                "treatment_strategy_id": row.get("strategy_id_treatment"),
                "baseline_avg_live_exposure": base_live,
                "treatment_avg_live_exposure": treatment_live,
                "live_exposure_delta": _delta(treatment_live, base_live),
                "baseline_avg_benchmark_weight_held": base_held,
                "treatment_avg_benchmark_weight_held": treatment_held,
                "benchmark_weight_held_delta": _delta(treatment_held, base_held),
                "baseline_avg_top_n_coverage_ratio": base_top,
                "treatment_avg_top_n_coverage_ratio": treatment_top,
                "top_n_coverage_ratio_delta": _delta(treatment_top, base_top),
                "baseline_avg_industry_l1_gap_normalized": base_industry_gap,
                "treatment_avg_industry_l1_gap_normalized": treatment_industry_gap,
                "industry_l1_gap_delta": _delta(treatment_industry_gap, base_industry_gap),
                "baseline_excess_total_return": base_excess,
                "treatment_excess_total_return": treatment_excess,
                "excess_total_return_delta": _delta(treatment_excess, base_excess),
                "baseline_primary_driver": row.get("primary_driver_baseline"),
                "treatment_primary_driver": row.get("primary_driver_treatment"),
                "dominant_gap": _dominant_gap(
                    base_driver=row.get("primary_driver_baseline"),
                    treatment_driver=row.get("primary_driver_treatment"),
                    live_exposure=treatment_live,
                    benchmark_weight_held=treatment_held,
                    industry_gap=treatment_industry_gap,
                ),
            }
        )
    return pd.DataFrame(rows)


def _prepare_fold_frame(df: pd.DataFrame, label: str) -> pd.DataFrame:
    out = df.copy()
    out["line_label"] = label
    keep = [
        "strategy_id",
        "walk_forward_preset",
        "fold",
        "valid_start",
        "valid_end",
        "market_context_label",
        "avg_live_exposure",
        "avg_benchmark_weight_held",
        "avg_top_n_coverage_ratio",
        "avg_industry_l1_gap_normalized",
        "strategy_total_return",
        "benchmark_total_return",
        "excess_total_return",
        "primary_driver",
    ]
    for column in keep:
        if column not in out.columns:
            out[column] = np.nan
    return out[keep]


def _entity_contribution_comparison(
    baseline: pd.DataFrame,
    treatment: pd.DataFrame,
    *,
    group_column: str,
    baseline_label: str,
    treatment_label: str,
) -> pd.DataFrame:
    baseline_summary = _holding_entity_summary(baseline, group_column, "baseline")
    treatment_summary = _holding_entity_summary(treatment, group_column, "treatment")
    merged = baseline_summary.merge(treatment_summary, on=[group_column], how="outer")
    if group_column == "symbol":
        merged["name"] = merged["name_baseline"].combine_first(merged["name_treatment"])
        merged["industry"] = merged["industry_baseline"].combine_first(merged["industry_treatment"])
        leading_columns = ["symbol", "name", "industry"]
    else:
        leading_columns = ["industry"]
    for prefix in ["baseline", "treatment"]:
        for column in ["days", "folds", "avg_live_weight", "total_position_ret"]:
            name = f"{prefix}_{column}"
            if name not in merged.columns:
                merged[name] = 0
            merged[name] = pd.to_numeric(merged[name], errors="coerce").fillna(0)
    merged["position_ret_delta"] = (merged["treatment_total_position_ret"] - merged["baseline_total_position_ret"]).round(12)
    merged["avg_live_weight_delta"] = (merged["treatment_avg_live_weight"] - merged["baseline_avg_live_weight"]).round(12)
    merged["baseline_label"] = baseline_label
    merged["treatment_label"] = treatment_label
    merged = merged.sort_values(
        ["position_ret_delta", "treatment_total_position_ret", group_column],
        ascending=[True, True, True],
        na_position="last",
    ).reset_index(drop=True)
    merged["rank_abs_position_ret_delta"] = (
        merged["position_ret_delta"].abs().rank(method="first", ascending=False).astype(int)
    )
    columns = [
        "baseline_label",
        "treatment_label",
        *leading_columns,
        "baseline_days",
        "treatment_days",
        "baseline_folds",
        "treatment_folds",
        "baseline_avg_live_weight",
        "treatment_avg_live_weight",
        "avg_live_weight_delta",
        "baseline_total_position_ret",
        "treatment_total_position_ret",
        "position_ret_delta",
        "rank_abs_position_ret_delta",
    ]
    return merged[columns]


def _holding_entity_summary(df: pd.DataFrame, group_column: str, prefix: str) -> pd.DataFrame:
    if df.empty:
        columns = [group_column, f"{prefix}_days", f"{prefix}_folds", f"{prefix}_avg_live_weight", f"{prefix}_total_position_ret"]
        if group_column == "symbol":
            columns.extend([f"name_{prefix}", f"industry_{prefix}"])
        return pd.DataFrame(columns=columns)
    frame = df.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["live_weight"] = pd.to_numeric(frame["live_weight"], errors="coerce").fillna(0)
    frame["position_ret"] = pd.to_numeric(frame["position_ret"], errors="coerce").fillna(0)
    grouped = frame.groupby(group_column, dropna=False)
    summary = grouped.agg(
        **{
            f"{prefix}_days": ("date", "nunique"),
            f"{prefix}_folds": ("fold", "nunique"),
            f"{prefix}_avg_live_weight": ("live_weight", "mean"),
            f"{prefix}_total_position_ret": ("position_ret", "sum"),
        }
    ).reset_index()
    if group_column == "symbol":
        summary[f"name_{prefix}"] = grouped["name"].first().values if "name" in frame.columns else ""
        summary[f"industry_{prefix}"] = grouped["industry"].first().values if "industry" in frame.columns else ""
    for column in [f"{prefix}_avg_live_weight", f"{prefix}_total_position_ret"]:
        summary[column] = summary[column].round(12)
    return summary


def _missed_top_comparison(
    baseline: pd.DataFrame,
    treatment: pd.DataFrame,
    *,
    baseline_label: str,
    treatment_label: str,
) -> pd.DataFrame:
    baseline_summary = _missed_top_summary(baseline, "baseline")
    treatment_summary = _missed_top_summary(treatment, "treatment")
    merged = baseline_summary.merge(treatment_summary, on="symbol", how="outer")
    if merged.empty:
        return pd.DataFrame(
            columns=[
                "baseline_label",
                "treatment_label",
                "symbol",
                "name",
                "industry",
                "baseline_missed_days",
                "treatment_missed_days",
                "missed_days_delta",
                "avg_benchmark_weight",
                "avg_benchmark_rank",
            ]
        )
    merged["name"] = merged["name_baseline"].combine_first(merged["name_treatment"])
    merged["industry"] = merged["industry_baseline"].combine_first(merged["industry_treatment"])
    for prefix in ["baseline", "treatment"]:
        for column in ["missed_days", "avg_benchmark_weight", "avg_benchmark_rank"]:
            name = f"{prefix}_{column}"
            if name not in merged.columns:
                merged[name] = 0
            merged[name] = pd.to_numeric(merged[name], errors="coerce").fillna(0)
    merged["missed_days_delta"] = (merged["treatment_missed_days"] - merged["baseline_missed_days"]).round(12)
    merged["avg_benchmark_weight"] = merged[["baseline_avg_benchmark_weight", "treatment_avg_benchmark_weight"]].max(axis=1)
    merged["avg_benchmark_rank"] = merged[["baseline_avg_benchmark_rank", "treatment_avg_benchmark_rank"]].replace(0, np.nan).min(axis=1)
    merged["baseline_label"] = baseline_label
    merged["treatment_label"] = treatment_label
    merged = merged.sort_values(
        ["treatment_missed_days", "avg_benchmark_weight", "symbol"],
        ascending=[False, False, True],
        na_position="last",
    ).reset_index(drop=True)
    return merged[
        [
            "baseline_label",
            "treatment_label",
            "symbol",
            "name",
            "industry",
            "baseline_missed_days",
            "treatment_missed_days",
            "missed_days_delta",
            "avg_benchmark_weight",
            "avg_benchmark_rank",
        ]
    ]


def _missed_top_summary(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    columns = [
        "symbol",
        f"name_{prefix}",
        f"industry_{prefix}",
        f"{prefix}_missed_days",
        f"{prefix}_avg_benchmark_weight",
        f"{prefix}_avg_benchmark_rank",
    ]
    if df.empty:
        return pd.DataFrame(columns=columns)
    _require_columns(df, ["symbol", "missed_days", "avg_benchmark_weight"], Path("missed_top"))
    frame = df.copy()
    frame["missed_days"] = pd.to_numeric(frame["missed_days"], errors="coerce").fillna(0)
    frame["avg_benchmark_weight"] = pd.to_numeric(frame["avg_benchmark_weight"], errors="coerce").fillna(0)
    if "avg_benchmark_rank" not in frame.columns:
        frame["avg_benchmark_rank"] = np.nan
    frame["avg_benchmark_rank"] = pd.to_numeric(frame["avg_benchmark_rank"], errors="coerce")
    grouped = frame.groupby("symbol", dropna=False)
    return grouped.agg(
        **{
            f"name_{prefix}": ("name", "first") if "name" in frame.columns else ("symbol", "first"),
            f"industry_{prefix}": ("industry", "first") if "industry" in frame.columns else ("symbol", "first"),
            f"{prefix}_missed_days": ("missed_days", "sum"),
            f"{prefix}_avg_benchmark_weight": ("avg_benchmark_weight", "mean"),
            f"{prefix}_avg_benchmark_rank": ("avg_benchmark_rank", "mean"),
        }
    ).reset_index()[columns]


def _dominant_gap(
    *,
    base_driver: Any,
    treatment_driver: Any,
    live_exposure: float,
    benchmark_weight_held: float,
    industry_gap: float,
) -> str:
    base = _safe_str(base_driver)
    treatment = _safe_str(treatment_driver)
    if treatment and treatment == base:
        return treatment
    if treatment:
        return treatment
    if not np.isnan(live_exposure) and live_exposure < 0.40:
        return "low_participation"
    if not np.isnan(benchmark_weight_held) and benchmark_weight_held < 0.75:
        return "benchmark_weight_gap"
    if not np.isnan(industry_gap) and industry_gap > 0.25:
        return "industry_structure_gap"
    return "mixed_or_stock_selection"


def _write_markdown(
    path: Path,
    *,
    fold_comparison: pd.DataFrame,
    symbol_contribution: pd.DataFrame,
    industry_contribution: pd.DataFrame,
    missed_top: pd.DataFrame,
    baseline_label: str,
    treatment_label: str,
    context_label: str,
    input_paths: dict[str, Path | None],
) -> None:
    lines = [
        "# Strategy Alpha Source Audit",
        "",
        f"- Baseline: `{baseline_label}`",
        f"- Treatment: `{treatment_label}`",
        f"- Context label: `{context_label}`",
        "- Diagnostic type: research-only alpha source audit.",
        "- Purpose: explain whether a new strategy iteration improved participation, benchmark-head coverage, industry alignment, or holding-level contribution.",
        "",
        "## Inputs",
    ]
    for name, input_path in input_paths.items():
        lines.append(f"- {name}: `{input_path}`")
    lines.extend(["", "## Fold Comparison"])
    lines.extend(_frame_to_markdown(fold_comparison.head(10)))
    lines.extend(["", "## Largest Negative Holding Contribution Deltas"])
    lines.extend(_frame_to_markdown(symbol_contribution.head(12)))
    lines.extend(["", "## Largest Negative Industry Contribution Deltas"])
    lines.extend(_frame_to_markdown(industry_contribution.head(12)))
    lines.extend(["", "## Missed Top Benchmark Constituents"])
    lines.extend(_frame_to_markdown(missed_top.head(12)))
    lines.extend(
        [
            "",
            "## Reading Guide",
            "",
            "- `excess_total_return_delta` below zero means the treatment iteration lagged the baseline in the same fold.",
            "- `position_ret_delta` below zero means the treatment iteration worsened contribution for that symbol or industry.",
            "- `dominant_gap` identifies the first-order issue to inspect before designing the next strategy variant.",
            "- This audit does not certify a strategy for paper trading; it only narrows the next research hypothesis.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _frame_to_markdown(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return ["", "No rows."]
    display = df.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{float(value):.6f}")
    return ["", display.to_markdown(index=False)]


def _filter_context(df: pd.DataFrame, context_label: str) -> pd.DataFrame:
    if df.empty or not context_label or context_label == "all" or "market_context_label" not in df.columns:
        return df.copy()
    return df[df["market_context_label"].astype(str) == str(context_label)].copy()


def _read_required_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    return pd.read_csv(path)


def _read_optional_csv(path: Path | None) -> pd.DataFrame:
    if path is None or not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _require_columns(df: pd.DataFrame, columns: list[str], path: Path) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"{path} missing required columns: {', '.join(missing)}")


def _to_float(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return np.nan
    if np.isfinite(numeric):
        return numeric
    return np.nan


def _delta(new: float, old: float) -> float:
    if np.isnan(new) or np.isnan(old):
        return np.nan
    return round(new - old, 12)


def _safe_str(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value)
