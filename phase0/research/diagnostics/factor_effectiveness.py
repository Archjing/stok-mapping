from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from phase0.data_governance.external_market_history import configure_hk_market_history, configure_us_market_history
from phase0.data_access.daily_basic_history import merge_point_in_time_daily_basic
from phase0.data_access.local_history import configure_local_history
from phase0.research.factors.slow_multifactor import add_slow_multifactor_features
from phase0.reporting.paths import create_report_run
from phase0.walk_forward import _add_point_in_time_financial_factors, iter_point_in_time_universe_folds


DEFAULT_FORWARD_HORIZON = 20
DEFAULT_GROUP_COUNT = 5
DEFAULT_MIN_DAILY_SAMPLES = 30


@dataclass(frozen=True)
class FactorEffectivenessResult:
    output_dir: Path
    summary_csv: Path
    summary_md: Path
    group_returns_csv: Path
    ic_by_year_csv: Path
    correlation_csv: Path
    factor_count: int
    fold_count: int
    warnings: list[str]


@dataclass(frozen=True)
class FactorSpec:
    name: str
    column: str
    description: str


FACTOR_SPECS = [
    FactorSpec("low_vol20", "low_vol20", "-vol20"),
    FactorSpec("low_vol60", "low_vol60", "-vol60"),
    FactorSpec("low_turnover_rate", "low_turnover_rate", "-turnover_rate"),
    FactorSpec("low_amount_ratio20", "low_amount_ratio20", "-amount_ratio20"),
    FactorSpec("mom20", "mom20", "20-day momentum"),
    FactorSpec("mom60", "mom60", "60-day momentum"),
    FactorSpec("reversal_mom3", "reversal_mom3", "-mom3"),
    FactorSpec("reversal_mom5", "reversal_mom5", "-mom5"),
    FactorSpec("roe", "roe", "point-in-time ROE"),
    FactorSpec("cash_flow_quality", "cash_flow_quality", "point-in-time operating cash flow / net profit"),
    FactorSpec("profit_growth", "profit_growth", "point-in-time profit growth"),
    FactorSpec("revenue_growth", "revenue_growth", "point-in-time revenue growth"),
    FactorSpec("low_debt_to_asset", "low_debt_to_asset", "-debt_to_asset"),
    FactorSpec("ep", "ep", "1 / pe_ttm"),
    FactorSpec("low_pb", "low_pb", "-pb"),
    FactorSpec("slow_quality", "slow_quality_score", "PIT quality neutralized by industry and size"),
    FactorSpec(
        "slow_earnings",
        "slow_earnings_score",
        "PIT earnings improvement neutralized by industry and size",
    ),
    FactorSpec(
        "slow_value",
        "slow_value_score",
        "positive E/P and inverse P/B neutralized by industry and size",
    ),
    FactorSpec(
        "slow_low_vol",
        "slow_low_vol_score",
        "60-day low volatility neutralized by industry and size",
    ),
    FactorSpec(
        "slow_residual_momentum",
        "slow_residual_momentum_score",
        "120-to-20-day momentum neutralized by industry and size",
    ),
]


def _configured_strategy_cfg(config: dict[str, Any]) -> dict[str, Any]:
    walk_cfg = config.get("walk_forward", {})
    strategy_cfg = copy.deepcopy(walk_cfg.get("strategy_v2", {}))
    local_factor = strategy_cfg.setdefault("local_factor", {})
    quality_growth = local_factor.setdefault("quality_growth", {})
    quality_growth["enabled"] = True
    if "financial_table" not in quality_growth and "local_history" in config:
        quality_growth["financial_table"] = config.get("local_history", {}).get("financial_table", "market_financial_factors")
    return strategy_cfg


def _merge_daily_basic(panel: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    if panel.empty:
        return panel
    local_cfg = config.get("local_history", {})
    return merge_point_in_time_daily_basic(
        panel,
        as_of_date=panel["date"].max(),
        market=str(local_cfg.get("market", "CN")),
        table=str(local_cfg.get("daily_basic_table", "market_daily_basic")),
    )


def _add_factor_columns(panel: pd.DataFrame) -> pd.DataFrame:
    d = panel.copy().sort_values(["symbol", "date"]).reset_index(drop=True)
    for col in ["close", "ret", "vol20", "amount_ratio20", "turnover_rate", "pe_ttm", "pb"]:
        if col not in d.columns:
            d[col] = np.nan
        d[col] = pd.to_numeric(d[col], errors="coerce")
    group_keys = ["symbol"]
    if "fold" in d.columns:
        group_keys = ["fold", "symbol"]
    if "vol60" not in d.columns:
        d["vol60"] = d.groupby(group_keys)["ret"].transform(lambda x: x.rolling(60).std() * np.sqrt(252))
    if "mom60" not in d.columns:
        d["mom60"] = d.groupby(group_keys)["close"].transform(lambda x: x.pct_change(60))

    d["low_vol20"] = -d["vol20"]
    d["low_vol60"] = -pd.to_numeric(d["vol60"], errors="coerce")
    d["low_turnover_rate"] = -d["turnover_rate"]
    d["low_amount_ratio20"] = -d["amount_ratio20"]
    d["reversal_mom3"] = -pd.to_numeric(d.get("mom3", np.nan), errors="coerce")
    d["reversal_mom5"] = -pd.to_numeric(d.get("mom5", np.nan), errors="coerce")
    d["low_debt_to_asset"] = -pd.to_numeric(d.get("debt_to_asset", np.nan), errors="coerce")
    pe = pd.to_numeric(d["pe_ttm"], errors="coerce").replace(0, np.nan)
    d["ep"] = (1.0 / pe).replace([np.inf, -np.inf], np.nan)
    d["low_pb"] = -pd.to_numeric(d["pb"], errors="coerce")
    return add_slow_multifactor_features(d)


def _add_forward_returns(panel: pd.DataFrame, horizon: int) -> pd.DataFrame:
    d = panel.copy().sort_values(["symbol", "date"]).reset_index(drop=True)
    d["close"] = pd.to_numeric(d["close"], errors="coerce")
    group_keys = ["symbol"]
    if "fold" in d.columns:
        group_keys = ["fold", "symbol"]
        d = d.sort_values(["fold", "symbol", "date"]).reset_index(drop=True)
    d[f"forward_ret_{horizon}d"] = d.groupby(group_keys, sort=False)["close"].transform(
        lambda x: x.shift(-horizon) / x.replace(0, np.nan) - 1.0
    )
    return d


def _spearman_by_date(
    panel: pd.DataFrame,
    *,
    factor_col: str,
    label_col: str,
    min_daily_samples: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    cols = ["date", factor_col, label_col]
    d = panel[cols].dropna().copy()
    for dt, one_date in d.groupby("date", sort=True):
        if len(one_date) < min_daily_samples:
            continue
        x = pd.to_numeric(one_date[factor_col], errors="coerce")
        y = pd.to_numeric(one_date[label_col], errors="coerce")
        if x.nunique(dropna=True) < 2 or y.nunique(dropna=True) < 2:
            continue
        ic = x.rank(method="average").corr(y.rank(method="average"))
        if pd.notna(ic):
            rows.append({"date": pd.Timestamp(dt), "rank_ic": float(ic), "sample_count": int(len(one_date))})
    return pd.DataFrame(rows)


def _group_returns_by_date(
    panel: pd.DataFrame,
    *,
    factor_col: str,
    label_col: str,
    group_count: int,
    min_daily_samples: int,
) -> tuple[pd.DataFrame, float]:
    rows: list[dict[str, Any]] = []
    top_sets: list[set[str]] = []
    d = panel[["date", "symbol", factor_col, label_col]].dropna().copy()
    for dt, one_date in d.groupby("date", sort=True):
        if len(one_date) < min_daily_samples:
            continue
        one_date = one_date.copy()
        one_date["_rank"] = pd.to_numeric(one_date[factor_col], errors="coerce").rank(method="first", pct=True)
        one_date["_group"] = np.ceil(one_date["_rank"] * group_count).clip(lower=1, upper=group_count).astype(int)
        for group, group_frame in one_date.groupby("_group", sort=True):
            rows.append(
                {
                    "date": pd.Timestamp(dt).date().isoformat(),
                    "group": int(group),
                    "mean_forward_return": float(pd.to_numeric(group_frame[label_col], errors="coerce").mean()),
                    "sample_count": int(len(group_frame)),
                }
            )
        top_symbols = set(one_date.loc[one_date["_group"] == group_count, "symbol"].astype(str).tolist())
        if top_symbols:
            top_sets.append(top_symbols)

    daily_turnovers: list[float] = []
    previous: set[str] | None = None
    for current in top_sets:
        if previous is not None and previous:
            daily_turnovers.append(1.0 - len(previous & current) / max(len(previous), 1))
        previous = current
    annual_turnover_proxy = float(np.nanmean(daily_turnovers) * 252.0) if daily_turnovers else np.nan
    return pd.DataFrame(rows), annual_turnover_proxy


def _recommendation(
    *,
    coverage_ratio: float,
    mean_rank_ic: float,
    icir: float,
    long_short_return_mean: float,
) -> tuple[str, str]:
    if not np.isfinite(coverage_ratio) or coverage_ratio < 0.05:
        return "missing", "coverage below 5%"
    if coverage_ratio < 0.20:
        return "missing", "coverage below 20%"
    if mean_rank_ic > 0.02 and long_short_return_mean > 0 and (not np.isfinite(icir) or icir > 0):
        return "use", "positive IC and positive top-bottom return"
    if mean_rank_ic > 0 or long_short_return_mean > 0:
        return "observe", "weak but non-negative IC or top-bottom return"
    return "reject", "negative IC and no positive top-bottom return"


def _factor_summary(
    panel: pd.DataFrame,
    *,
    factor: FactorSpec,
    label_col: str,
    group_count: int,
    min_daily_samples: int,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    denominator = int(panel[label_col].notna().sum())
    usable = int(panel[[factor.column, label_col]].dropna().shape[0]) if factor.column in panel.columns else 0
    coverage_ratio = usable / denominator if denominator else np.nan
    missing_ratio = 1.0 - coverage_ratio if np.isfinite(coverage_ratio) else np.nan

    if factor.column not in panel.columns or usable == 0:
        rec, reason = "missing", "factor column unavailable"
        summary = {
            "factor": factor.name,
            "description": factor.description,
            "coverage_ratio": coverage_ratio,
            "missing_ratio": missing_ratio,
            "mean_rank_ic": np.nan,
            "icir": np.nan,
            "positive_ic_ratio": np.nan,
            "group_count": group_count,
            "top_group_return_mean": np.nan,
            "bottom_group_return_mean": np.nan,
            "long_short_return_mean": np.nan,
            "annual_turnover_proxy": np.nan,
            "recommendation": rec,
            "main_reason": reason,
        }
        return summary, pd.DataFrame(), pd.DataFrame()

    ic_daily = _spearman_by_date(
        panel,
        factor_col=factor.column,
        label_col=label_col,
        min_daily_samples=min_daily_samples,
    )
    if ic_daily.empty:
        mean_rank_ic = np.nan
        icir = np.nan
        positive_ic_ratio = np.nan
    else:
        mean_rank_ic = float(ic_daily["rank_ic"].mean())
        std_rank_ic = float(ic_daily["rank_ic"].std(ddof=1)) if len(ic_daily) > 1 else np.nan
        icir = float(mean_rank_ic / std_rank_ic) if np.isfinite(std_rank_ic) and std_rank_ic > 0 else np.nan
        positive_ic_ratio = float((ic_daily["rank_ic"] > 0).mean())

    group_daily, annual_turnover_proxy = _group_returns_by_date(
        panel,
        factor_col=factor.column,
        label_col=label_col,
        group_count=group_count,
        min_daily_samples=min_daily_samples,
    )
    if group_daily.empty:
        top_group_return_mean = np.nan
        bottom_group_return_mean = np.nan
        long_short_return_mean = np.nan
    else:
        group_mean = group_daily.groupby("group")["mean_forward_return"].mean()
        top_group_return_mean = float(group_mean.get(group_count, np.nan))
        bottom_group_return_mean = float(group_mean.get(1, np.nan))
        long_short_return_mean = top_group_return_mean - bottom_group_return_mean

    rec, reason = _recommendation(
        coverage_ratio=coverage_ratio,
        mean_rank_ic=mean_rank_ic if np.isfinite(mean_rank_ic) else -1.0,
        icir=icir,
        long_short_return_mean=long_short_return_mean if np.isfinite(long_short_return_mean) else -1.0,
    )
    summary = {
        "factor": factor.name,
        "description": factor.description,
        "coverage_ratio": coverage_ratio,
        "missing_ratio": missing_ratio,
        "mean_rank_ic": mean_rank_ic,
        "icir": icir,
        "positive_ic_ratio": positive_ic_ratio,
        "group_count": group_count,
        "top_group_return_mean": top_group_return_mean,
        "bottom_group_return_mean": bottom_group_return_mean,
        "long_short_return_mean": long_short_return_mean,
        "annual_turnover_proxy": annual_turnover_proxy,
        "recommendation": rec,
        "main_reason": reason,
    }
    if not group_daily.empty:
        group_daily.insert(0, "factor", factor.name)
    if not ic_daily.empty:
        ic_daily.insert(0, "factor", factor.name)
    return summary, group_daily, ic_daily


def _ic_by_year(ic_daily_frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not ic_daily_frames:
        return pd.DataFrame(columns=["factor", "year", "mean_rank_ic", "icir", "positive_ic_ratio", "sample_days"])
    daily = pd.concat(ic_daily_frames, ignore_index=True)
    if daily.empty:
        return pd.DataFrame(columns=["factor", "year", "mean_rank_ic", "icir", "positive_ic_ratio", "sample_days"])
    daily["year"] = pd.to_datetime(daily["date"]).dt.year
    rows: list[dict[str, Any]] = []
    for (factor, year), group in daily.groupby(["factor", "year"], sort=True):
        mean_rank_ic = float(group["rank_ic"].mean())
        std_rank_ic = float(group["rank_ic"].std(ddof=1)) if len(group) > 1 else np.nan
        rows.append(
            {
                "factor": factor,
                "year": int(year),
                "mean_rank_ic": mean_rank_ic,
                "icir": float(mean_rank_ic / std_rank_ic) if np.isfinite(std_rank_ic) and std_rank_ic > 0 else np.nan,
                "positive_ic_ratio": float((group["rank_ic"] > 0).mean()),
                "sample_days": int(len(group)),
            }
        )
    return pd.DataFrame(rows)


def _factor_correlation(panel: pd.DataFrame, factors: list[FactorSpec]) -> pd.DataFrame:
    rank_frames: list[pd.DataFrame] = []
    for factor in factors:
        if factor.column not in panel.columns:
            continue
        values = panel[["date", "symbol", factor.column]].dropna().copy()
        if values.empty:
            continue
        values[factor.name] = values.groupby("date")[factor.column].rank(method="average", pct=True)
        rank_frames.append(values[["date", "symbol", factor.name]])
    if not rank_frames:
        return pd.DataFrame()
    merged = rank_frames[0]
    for frame in rank_frames[1:]:
        merged = merged.merge(frame, on=["date", "symbol"], how="outer")
    corr = merged.drop(columns=["date", "symbol"], errors="ignore").corr(method="spearman")
    corr.index.name = "factor"
    return corr


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return ""
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.{digits}f}"
    return str(value)


def _markdown_table(df: pd.DataFrame, columns: list[str], *, max_rows: int = 30) -> str:
    if df.empty:
        return "_No rows._"
    view = df.loc[:, [col for col in columns if col in df.columns]].head(max_rows).copy()
    header = "| " + " | ".join(view.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = []
    for _, row in view.iterrows():
        rows.append("| " + " | ".join(_fmt(row[col]) for col in view.columns) + " |")
    return "\n".join([header, sep, *rows])


def _write_markdown_report(
    *,
    output_path: Path,
    summary: pd.DataFrame,
    group_returns: pd.DataFrame,
    ic_by_year: pd.DataFrame,
    correlation: pd.DataFrame,
    warnings: list[str],
    horizon: int,
    fold_count: int,
) -> None:
    rec_counts = summary["recommendation"].value_counts().to_dict() if not summary.empty else {}
    usable = ", ".join(summary.loc[summary["recommendation"] == "use", "factor"].tolist()) or "None"
    observe = ", ".join(summary.loc[summary["recommendation"] == "observe", "factor"].tolist()) or "None"
    reject = ", ".join(summary.loc[summary["recommendation"] == "reject", "factor"].tolist()) or "None"
    missing = ", ".join(summary.loc[summary["recommendation"] == "missing", "factor"].tolist()) or "None"

    group_summary = pd.DataFrame()
    if not group_returns.empty:
        group_summary = (
            group_returns.groupby(["factor", "group"], as_index=False)
            .agg(mean_forward_return=("mean_forward_return", "mean"), sample_count=("sample_count", "sum"))
            .sort_values(["factor", "group"])
        )

    corr_view = correlation.reset_index() if not correlation.empty else pd.DataFrame()
    lines = [
        "# Factor Effectiveness Diagnostic",
        "",
        "## Running Assumptions",
        "",
        "- Price adjustment: qfq_asof, recomputed per historical as-of fold.",
        "- Universe: point-in-time universe from each fold train-end date.",
        f"- Forward return label: same-symbol close.shift(-{horizon}) / close - 1 inside validation folds only.",
        f"- Valid fold count: {fold_count}.",
        "- This report is a factor diagnostic only; it is not proof that a strategy is ready for live simulation.",
        "",
        "## Conclusion",
        "",
        f"- use: {rec_counts.get('use', 0)} ({usable})",
        f"- observe: {rec_counts.get('observe', 0)} ({observe})",
        f"- reject: {rec_counts.get('reject', 0)} ({reject})",
        f"- missing: {rec_counts.get('missing', 0)} ({missing})",
        "",
        "## Factor Summary",
        "",
        _markdown_table(
            summary,
            [
                "factor",
                "coverage_ratio",
                "mean_rank_ic",
                "icir",
                "positive_ic_ratio",
                "long_short_return_mean",
                "annual_turnover_proxy",
                "recommendation",
                "main_reason",
            ],
        ),
        "",
        "## Group Returns Summary",
        "",
        _markdown_table(group_summary, ["factor", "group", "mean_forward_return", "sample_count"], max_rows=80),
        "",
        "## Yearly IC Summary",
        "",
        _markdown_table(ic_by_year, ["factor", "year", "mean_rank_ic", "icir", "positive_ic_ratio", "sample_days"], max_rows=120),
        "",
        "## Factor Correlation",
        "",
        _markdown_table(corr_view, list(corr_view.columns), max_rows=40),
        "",
        "## Warnings / Data Coverage",
        "",
    ]
    if warnings:
        lines.extend([f"- {warning}" for warning in warnings])
    else:
        lines.append("- No material warning generated by this diagnostic run.")
    lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_factor_effectiveness_report(
    *,
    config: dict[str, Any],
    root: Path,
    output_dir: Path | None = None,
    forward_horizon: int = DEFAULT_FORWARD_HORIZON,
    group_count: int = DEFAULT_GROUP_COUNT,
    min_daily_samples: int = DEFAULT_MIN_DAILY_SAMPLES,
) -> FactorEffectivenessResult:
    cfg = copy.deepcopy(config)
    local_cfg = cfg.setdefault("local_history", {})
    local_cfg["price_adjustment_for_backtest"] = "qfq_asof"
    configure_local_history(local_cfg, root)
    configure_us_market_history(cfg.get("us_market_history", {}), root)
    configure_hk_market_history(cfg.get("hk_market_history", {}), root)

    if output_dir is None:
        report_run = create_report_run(root=root, config=cfg, command="factor-effectiveness", scope="qfq_asof")
        output = report_run.run_dir
        summary_csv = report_run.artifact("factor_effectiveness", "summary", "csv")
        summary_md = report_run.artifact("factor_effectiveness", "report", "md")
        group_returns_csv = report_run.artifact("factor_effectiveness", "group_returns", "csv")
        ic_by_year_csv = report_run.artifact("factor_effectiveness", "ic_by_year", "csv")
        correlation_csv = report_run.artifact("factor_effectiveness", "correlation", "csv")
    else:
        output = output_dir
        summary_csv = output / "factor_effectiveness.csv"
        summary_md = output / "factor_effectiveness.md"
        group_returns_csv = output / "factor_group_returns.csv"
        ic_by_year_csv = output / "factor_ic_by_year.csv"
        correlation_csv = output / "factor_correlation.csv"
    output.mkdir(parents=True, exist_ok=True)

    walk_cfg = cfg.get("walk_forward", {})
    strategy_cfg = _configured_strategy_cfg(cfg)
    years = int(cfg.get("years", 7))
    train_years = int(walk_cfg.get("train_years", 2))
    validate_years = int(walk_cfg.get("validate_years", 1))
    min_samples = int(walk_cfg.get("min_samples", 200))

    contexts, audit = iter_point_in_time_universe_folds(
        cfg,
        years=years,
        train_years=train_years,
        validate_years=validate_years,
        min_samples=min_samples,
        strategy_cfg=strategy_cfg,
    )
    warnings: list[str] = []
    if audit.empty:
        warnings.append("No point-in-time fold audit rows were generated.")
    else:
        skipped = audit[audit.get("warning", "").astype(str).str.contains("fold skipped", na=False)]
        if not skipped.empty:
            warnings.append(f"{len(skipped)} point-in-time folds were skipped before factor diagnostics.")
    if not contexts:
        empty_summary = pd.DataFrame(columns=["factor", "recommendation", "main_reason"])
        empty_summary.to_csv(summary_csv, index=False)
        pd.DataFrame().to_csv(group_returns_csv, index=False)
        pd.DataFrame().to_csv(ic_by_year_csv, index=False)
        pd.DataFrame().to_csv(correlation_csv)
        warnings.append("No valid validation folds available; factor diagnostics are empty.")
        _write_markdown_report(
            output_path=summary_md,
            summary=empty_summary,
            group_returns=pd.DataFrame(),
            ic_by_year=pd.DataFrame(),
            correlation=pd.DataFrame(),
            warnings=warnings,
            horizon=forward_horizon,
            fold_count=0,
        )
        return FactorEffectivenessResult(
            output_dir=output,
            summary_csv=summary_csv,
            summary_md=summary_md,
            group_returns_csv=group_returns_csv,
            ic_by_year_csv=ic_by_year_csv,
            correlation_csv=correlation_csv,
            factor_count=0,
            fold_count=0,
            warnings=warnings,
        )

    frames: list[pd.DataFrame] = []
    for ctx in contexts:
        valid = ctx["valid"].copy()
        valid["date"] = pd.to_datetime(valid["date"]).dt.normalize()
        valid["fold"] = int(ctx["fold"])
        valid = _merge_daily_basic(valid, cfg)
        valid = _add_point_in_time_financial_factors(valid, strategy_cfg)
        frames.append(valid)
    panel = pd.concat(frames, ignore_index=True).sort_values(["fold", "symbol", "date"]).reset_index(drop=True)
    panel = _add_factor_columns(panel)
    panel = _add_forward_returns(panel, forward_horizon)
    label_col = f"forward_ret_{forward_horizon}d"

    summary_rows: list[dict[str, Any]] = []
    group_frames: list[pd.DataFrame] = []
    ic_daily_frames: list[pd.DataFrame] = []
    for factor in FACTOR_SPECS:
        row, group_daily, ic_daily = _factor_summary(
            panel,
            factor=factor,
            label_col=label_col,
            group_count=group_count,
            min_daily_samples=min_daily_samples,
        )
        summary_rows.append(row)
        if not group_daily.empty:
            group_frames.append(group_daily)
        if not ic_daily.empty:
            ic_daily_frames.append(ic_daily)
    summary = pd.DataFrame(summary_rows).sort_values(
        ["recommendation", "mean_rank_ic"],
        ascending=[True, False],
        na_position="last",
    )
    recommendation_order = {"use": 0, "observe": 1, "reject": 2, "missing": 3}
    summary["_rec_order"] = summary["recommendation"].map(recommendation_order).fillna(9)
    summary = summary.sort_values(["_rec_order", "mean_rank_ic"], ascending=[True, False], na_position="last").drop(
        columns=["_rec_order"]
    )
    group_returns = pd.concat(group_frames, ignore_index=True) if group_frames else pd.DataFrame()
    ic_by_year = _ic_by_year(ic_daily_frames)
    correlation = _factor_correlation(panel, FACTOR_SPECS)

    for factor_name in summary.loc[summary["recommendation"] == "missing", "factor"].tolist():
        reason = summary.loc[summary["factor"] == factor_name, "main_reason"].iloc[0]
        warnings.append(f"{factor_name}: {reason}.")
    low_coverage = summary[(summary["coverage_ratio"].fillna(0) < 0.5) & (summary["recommendation"] != "missing")]
    for _, row in low_coverage.iterrows():
        warnings.append(f"{row['factor']}: low coverage ratio {row['coverage_ratio']:.4f}.")

    summary.to_csv(summary_csv, index=False)
    group_returns.to_csv(group_returns_csv, index=False)
    ic_by_year.to_csv(ic_by_year_csv, index=False)
    if correlation.empty:
        pd.DataFrame().to_csv(correlation_csv)
    else:
        correlation.to_csv(correlation_csv)
    _write_markdown_report(
        output_path=summary_md,
        summary=summary,
        group_returns=group_returns,
        ic_by_year=ic_by_year,
        correlation=correlation,
        warnings=warnings,
        horizon=forward_horizon,
        fold_count=len(contexts),
    )

    return FactorEffectivenessResult(
        output_dir=output,
        summary_csv=summary_csv,
        summary_md=summary_md,
        group_returns_csv=group_returns_csv,
        ic_by_year_csv=ic_by_year_csv,
        correlation_csv=correlation_csv,
        factor_count=len(summary),
        fold_count=len(contexts),
        warnings=warnings,
    )
