from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StrategyFoldAttributionResult:
    paired_fold_csv_path: Path
    daily_exposure_csv_path: Path
    top_holding_csv_path: Path
    top5_holding_csv_path: Path
    quality_bucket_csv_path: Path
    turnover_cost_csv_path: Path
    md_path: Path
    paired_rows: int


def run_strategy_fold_attribution(
    *,
    quality_fold_attribution_path: Path,
    price_volume_fold_attribution_path: Path,
    quality_market_context_path: Path,
    price_volume_market_context_path: Path,
    quality_holdings_path: Path,
    price_volume_holdings_path: Path,
    quality_daily_exposure_path: Path,
    price_volume_daily_exposure_path: Path,
    output_dir: Path,
    quality_label: str = "quality_i4_overlay",
    price_volume_label: str = "price_volume_i7",
) -> StrategyFoldAttributionResult:
    """Assemble read-only paired fold attribution from existing diagnostic artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    quality_folds = _read_csv(quality_fold_attribution_path, "quality fold attribution")
    price_volume_folds = _read_csv(price_volume_fold_attribution_path, "price-volume fold attribution")
    quality_context = _read_csv(quality_market_context_path, "quality market context")
    price_volume_context = _read_csv(price_volume_market_context_path, "price-volume market context")
    quality_holdings = _read_csv(quality_holdings_path, "quality holdings")
    price_volume_holdings = _read_csv(price_volume_holdings_path, "price-volume holdings")
    quality_daily = _read_csv(quality_daily_exposure_path, "quality daily exposure")
    price_volume_daily = _read_csv(price_volume_daily_exposure_path, "price-volume daily exposure")

    paired = _paired_fold_comparison(
        quality_folds,
        price_volume_folds,
        quality_context,
        price_volume_context,
        quality_label=quality_label,
        price_volume_label=price_volume_label,
    )
    daily = pd.concat(
        [
            _daily_exposure_summary(quality_daily, quality_label),
            _daily_exposure_summary(price_volume_daily, price_volume_label),
        ],
        ignore_index=True,
    )
    holdings = pd.concat(
        [
            _holding_contribution(quality_holdings, quality_label),
            _holding_contribution(price_volume_holdings, price_volume_label),
        ],
        ignore_index=True,
    )
    quality_bucket = _quality_bucket_contribution(quality_holdings)
    turnover_cost = pd.concat(
        [
            _turnover_cost_proxy(quality_holdings, quality_label),
            _turnover_cost_proxy(price_volume_holdings, price_volume_label),
        ],
        ignore_index=True,
    )

    paired_path = output_dir / "paired_fold_comparison.csv"
    daily_path = output_dir / "paired_daily_exposure_summary.csv"
    holdings_path = output_dir / "top_holding_contribution.csv"
    top5_path = output_dir / "top5_holding_contribution_by_fold.csv"
    quality_bucket_path = output_dir / "quality_bucket_contribution.csv"
    turnover_cost_path = output_dir / "turnover_cost_proxy.csv"
    md_path = output_dir / "strategy_fold_attribution_report.md"

    paired.to_csv(paired_path, index=False)
    daily.to_csv(daily_path, index=False)
    holdings.to_csv(holdings_path, index=False)
    holdings[holdings["rank_abs_contribution"] <= 5].to_csv(top5_path, index=False)
    quality_bucket.to_csv(quality_bucket_path, index=False)
    turnover_cost.to_csv(turnover_cost_path, index=False)
    _write_markdown(md_path, paired=paired, daily=daily, quality_bucket=quality_bucket, turnover_cost=turnover_cost)

    return StrategyFoldAttributionResult(
        paired_fold_csv_path=paired_path,
        daily_exposure_csv_path=daily_path,
        top_holding_csv_path=holdings_path,
        top5_holding_csv_path=top5_path,
        quality_bucket_csv_path=quality_bucket_path,
        turnover_cost_csv_path=turnover_cost_path,
        md_path=md_path,
        paired_rows=len(paired),
    )


def _paired_fold_comparison(
    quality_folds: pd.DataFrame,
    price_volume_folds: pd.DataFrame,
    quality_context: pd.DataFrame,
    price_volume_context: pd.DataFrame,
    *,
    quality_label: str,
    price_volume_label: str,
) -> pd.DataFrame:
    quality = _fold_base(quality_folds, quality_label).merge(
        _context_base(quality_context, quality_label),
        on=["line", "walk_forward_preset", "fold"],
        how="left",
    )
    price_volume = _fold_base(price_volume_folds, price_volume_label).merge(
        _context_base(price_volume_context, price_volume_label),
        on=["line", "walk_forward_preset", "fold"],
        how="left",
    )
    q = quality.add_prefix("quality_")
    p = price_volume.add_prefix("price_volume_")
    paired = q.merge(
        p,
        left_on=["quality_walk_forward_preset", "quality_fold", "quality_valid_start", "quality_valid_end"],
        right_on=["price_volume_walk_forward_preset", "price_volume_fold", "price_volume_valid_start", "price_volume_valid_end"],
        how="inner",
    )
    return pd.DataFrame(
        {
            "walk_forward_preset": paired["quality_walk_forward_preset"],
            "fold": paired["quality_fold"],
            "valid_start": paired["quality_valid_start"],
            "valid_end": paired["quality_valid_end"],
            "market_context_label": paired["quality_market_context_label"].combine_first(
                paired["price_volume_market_context_label"]
            ),
            "benchmark_return_bucket": paired["quality_benchmark_return_bucket"].combine_first(
                paired["price_volume_benchmark_return_bucket"]
            ),
            "quality_ann": paired["quality_annualized_return"],
            "price_volume_ann": paired["price_volume_annualized_return"],
            "quality_minus_price_volume_ann": paired["quality_annualized_return"] - paired["price_volume_annualized_return"],
            "quality_excess_ann": paired["quality_excess_annualized_return"],
            "price_volume_excess_ann": paired["price_volume_excess_annualized_return"],
            "quality_sharpe": paired["quality_sharpe"],
            "price_volume_sharpe": paired["price_volume_sharpe"],
            "quality_turnover": paired["quality_turnover_annual"],
            "price_volume_turnover": paired["price_volume_turnover_annual"],
            "quality_failure": paired["quality_primary_fold_failure"],
            "price_volume_failure": paired["price_volume_primary_fold_failure"],
        }
    ).sort_values(["walk_forward_preset", "fold"]).reset_index(drop=True)


def _fold_base(df: pd.DataFrame, label: str) -> pd.DataFrame:
    out = df.copy()
    out["line"] = label
    keep = [
        "line",
        "strategy_id",
        "walk_forward_preset",
        "fold",
        "valid_start",
        "valid_end",
        "primary_fold_failure",
        "fold_severity",
        "annualized_return",
        "benchmark_annualized_return",
        "excess_annualized_return",
        "sharpe",
        "max_drawdown",
        "turnover_annual",
        "recommended_next_action",
    ]
    for column in keep:
        if column not in out.columns:
            out[column] = np.nan
    return out[keep]


def _context_base(df: pd.DataFrame, label: str) -> pd.DataFrame:
    out = df.copy()
    out["line"] = label
    keep = [
        "line",
        "walk_forward_preset",
        "fold",
        "market_context_label",
        "benchmark_return_bucket",
        "benchmark_trend_bucket",
        "benchmark_vol_bucket",
        "benchmark_above_trend_share",
        "benchmark_risk_off_share",
        "benchmark_context_annualized_return",
    ]
    for column in keep:
        if column not in out.columns:
            out[column] = np.nan
    return out[keep]


def _daily_exposure_summary(daily: pd.DataFrame, label: str) -> pd.DataFrame:
    out = daily.copy()
    out["line"] = label
    keys = ["line", "strategy_id", "walk_forward_preset", "fold", "valid_start", "valid_end", "market_context_label"]
    for column in keys:
        if column not in out.columns:
            out[column] = ""
    for column in [
        "live_exposure",
        "live_holding_count",
        "live_top_industry_share",
        "live_top3_industries_share",
    ]:
        if column not in out.columns:
            out[column] = np.nan
        out[column] = pd.to_numeric(out[column], errors="coerce")
    return (
        out.groupby(keys, dropna=False)
        .agg(
            daily_count=("date", "count"),
            avg_live_exposure=("live_exposure", "mean"),
            avg_live_holding_count=("live_holding_count", "mean"),
            avg_live_top_industry_share=("live_top_industry_share", "mean"),
            p95_live_top_industry_share=("live_top_industry_share", lambda s: _quantile(s, 0.95)),
            avg_live_top3_industries_share=("live_top3_industries_share", "mean"),
        )
        .reset_index()
    )


def _holding_contribution(holdings: pd.DataFrame, label: str) -> pd.DataFrame:
    out = holdings.copy()
    out["line"] = label
    for column in ["position_ret", "live_weight", "target_weight", "quality_growth_score", "score"]:
        if column not in out.columns:
            out[column] = np.nan
        out[column] = pd.to_numeric(out[column], errors="coerce")
    out["abs_position_ret"] = out["position_ret"].abs()
    group_cols = ["line", "strategy_id", "walk_forward_preset", "fold", "symbol", "name", "industry"]
    for column in group_cols:
        if column not in out.columns:
            out[column] = ""
    grouped = (
        out.groupby(group_cols, dropna=False)
        .agg(
            total_position_ret=("position_ret", "sum"),
            abs_position_ret=("abs_position_ret", "sum"),
            avg_live_weight=("live_weight", "mean"),
            max_live_weight=("live_weight", "max"),
            avg_score=("score", "mean"),
            avg_quality_score=("quality_growth_score", "mean"),
            active_days=("live_weight", lambda s: int((pd.to_numeric(s, errors="coerce").fillna(0.0).abs() > 1e-12).sum())),
        )
        .reset_index()
    )
    grouped["rank_abs_contribution"] = grouped.groupby(["line", "walk_forward_preset", "fold"])["abs_position_ret"].rank(
        method="first",
        ascending=False,
    )
    return grouped.sort_values(["line", "walk_forward_preset", "fold", "rank_abs_contribution"]).reset_index(drop=True)


def _quality_bucket_contribution(quality_holdings: pd.DataFrame) -> pd.DataFrame:
    if "quality_growth_score" not in quality_holdings.columns:
        return pd.DataFrame(
            columns=[
                "walk_forward_preset",
                "fold",
                "quality_bucket",
                "rows",
                "active_rows",
                "avg_quality_score",
                "avg_live_weight",
                "total_position_ret",
            ]
        )
    out = quality_holdings.copy()
    out["quality_growth_score"] = pd.to_numeric(out["quality_growth_score"], errors="coerce")
    out["position_ret"] = pd.to_numeric(out.get("position_ret", 0.0), errors="coerce").fillna(0.0)
    out["live_weight"] = pd.to_numeric(out.get("live_weight", 0.0), errors="coerce").fillna(0.0)
    bucketed_frames = [
        _assign_quality_bucket(group)
        for _, group in out.groupby(["walk_forward_preset", "fold", "date"], dropna=False)
    ]
    out = pd.concat(bucketed_frames, ignore_index=True) if bucketed_frames else out.assign(quality_bucket=pd.Series(dtype=object))
    return (
        out.groupby(["walk_forward_preset", "fold", "quality_bucket"], dropna=False)
        .agg(
            rows=("symbol", "count"),
            active_rows=("live_weight", lambda s: int((pd.to_numeric(s, errors="coerce").fillna(0.0).abs() > 1e-12).sum())),
            avg_quality_score=("quality_growth_score", "mean"),
            avg_live_weight=("live_weight", "mean"),
            total_position_ret=("position_ret", "sum"),
        )
        .reset_index()
    )


def _assign_quality_bucket(group: pd.DataFrame) -> pd.DataFrame:
    out = group.copy()
    values = out["quality_growth_score"]
    if values.notna().sum() < 4:
        out["quality_bucket"] = "not_enough_data"
        return out
    try:
        out["quality_bucket"] = pd.qcut(values.rank(method="first"), 4, labels=["Q1_low", "Q2", "Q3", "Q4_high"])
    except ValueError:
        out["quality_bucket"] = "not_enough_data"
    return out


def _turnover_cost_proxy(
    holdings: pd.DataFrame,
    label: str,
    *,
    slippage: float = 0.00246,
    commission: float = 0.00025,
    stamp_duty_sell: float = 0.0005,
) -> pd.DataFrame:
    out = holdings.copy()
    out["line"] = label
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["live_weight"] = pd.to_numeric(out.get("live_weight", 0.0), errors="coerce").fillna(0.0)
    rows: list[dict[str, Any]] = []
    group_cols = ["line", "strategy_id", "walk_forward_preset", "fold"]
    for keys, group in out.groupby(group_cols, dropna=False):
        pivot = group.pivot_table(index="date", columns="symbol", values="live_weight", aggfunc="sum").sort_index().fillna(0.0)
        turnover = pivot.diff().abs().sum(axis=1).fillna(pivot.abs().sum(axis=1))
        sells = pivot.diff().clip(upper=0).abs().sum(axis=1).fillna(0.0)
        cost = turnover * (slippage + commission) + sells * stamp_duty_sell
        rows.append(
            {
                "line": keys[0],
                "strategy_id": keys[1],
                "walk_forward_preset": keys[2],
                "fold": keys[3],
                "days": int(len(pivot)),
                "turnover_sum": float(turnover.sum()),
                "turnover_mean_daily": float(turnover.mean()) if len(turnover) else 0.0,
                "estimated_cost_sum": float(cost.sum()),
                "estimated_cost_mean_daily": float(cost.mean()) if len(cost) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _write_markdown(
    path: Path,
    *,
    paired: pd.DataFrame,
    daily: pd.DataFrame,
    quality_bucket: pd.DataFrame,
    turnover_cost: pd.DataFrame,
) -> None:
    lines = [
        "# Strategy Fold Attribution Report",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        "- boundary: read-only diagnostic; no strategy rule, admission gate, paper review, simulated account, daily brief, watchlist, or trading signal is changed.",
        "",
        "## Paired Fold Comparison",
        "",
    ]
    paired_cols = [
        "walk_forward_preset",
        "fold",
        "market_context_label",
        "benchmark_return_bucket",
        "quality_ann",
        "price_volume_ann",
        "quality_minus_price_volume_ann",
        "quality_sharpe",
        "price_volume_sharpe",
        "quality_turnover",
        "price_volume_turnover",
    ]
    lines.extend(_markdown_table(paired[[col for col in paired_cols if col in paired.columns]]))
    lines.extend(["", "## Daily Exposure Summary", ""])
    daily_cols = [
        "line",
        "walk_forward_preset",
        "fold",
        "market_context_label",
        "avg_live_exposure",
        "avg_live_holding_count",
        "avg_live_top_industry_share",
        "avg_live_top3_industries_share",
    ]
    lines.extend(_markdown_table(daily[[col for col in daily_cols if col in daily.columns]].head(20)))
    lines.extend(["", "## Quality Bucket Contribution", ""])
    lines.extend(_markdown_table(quality_bucket.head(30)))
    lines.extend(["", "## Turnover Cost Proxy", ""])
    lines.extend(_markdown_table(turnover_cost))
    lines.extend(
        [
            "",
            "## Decision Boundary",
            "",
            "- The report can compare fold outcomes, market context, exposure, industry concentration, quality buckets, holding contribution, and cost proxies.",
            "- It cannot prove live profitability or authorize promotion.",
            "- CSI300 constituent and active-weight attribution still require point-in-time constituent and weight data.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _read_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    return pd.read_csv(path)


def _quantile(values: pd.Series, q: float) -> float:
    numeric = pd.to_numeric(values, errors="coerce")
    return float(numeric.quantile(q)) if numeric.notna().any() else 0.0


def _markdown_table(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return ["_No rows._"]
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_float_dtype(out[col]):
            out[col] = out[col].map(lambda v: "" if pd.isna(v) else f"{float(v):.4f}")
        else:
            out[col] = out[col].fillna("").astype(str)
    headers = list(out.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in out.iterrows():
        lines.append("| " + " | ".join(str(row[col]).replace("\n", " ") for col in headers) + " |")
    return lines
