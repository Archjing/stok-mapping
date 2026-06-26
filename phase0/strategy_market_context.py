from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from phase0.local_history import load_index_daily_from_local_history


@dataclass(frozen=True)
class StrategyMarketContextResult:
    csv_path: Path
    summary_csv_path: Path
    coverage_csv_path: Path
    md_path: Path
    rows: int
    benchmark_symbol: str


def run_strategy_market_context(
    *,
    config: dict[str, Any] | None,
    root: Path,
    fold_attribution_path: Path,
    output_dir: Path | None = None,
    benchmark_symbol: str | None = None,
    trend_window: int = 120,
    vol_window: int = 20,
    vol_quantile: float = 0.70,
) -> StrategyMarketContextResult:
    """Diagnose fold-level benchmark context from existing attribution CSVs only."""
    output_dir = output_dir or fold_attribution_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    folds = _read_required_csv(fold_attribution_path, "strategy_failure_fold_attribution.csv")
    _require_columns(
        folds,
        [
            "strategy_id",
            "walk_forward_preset",
            "fold",
            "valid_start",
            "valid_end",
            "primary_fold_failure",
            "annualized_return",
            "benchmark_annualized_return",
            "excess_annualized_return",
        ],
        fold_attribution_path,
    )
    phase_cfg = config or {}
    symbol = benchmark_symbol or str(phase_cfg.get("benchmark_symbol", "SH.000300"))
    context = _build_context_rows(
        folds,
        benchmark_symbol=symbol,
        trend_window=trend_window,
        vol_window=vol_window,
        vol_quantile=vol_quantile,
    )
    csv_path = output_dir / "strategy_market_context_diagnostic.csv"
    summary_csv_path = output_dir / "strategy_market_context_label_summary.csv"
    coverage_csv_path = output_dir / "strategy_market_context_data_coverage.csv"
    md_path = output_dir / "strategy_market_context_diagnostic.md"
    context.to_csv(csv_path, index=False)
    summary = _label_summary(context)
    coverage = _coverage_summary(
        folds,
        benchmark_symbol=symbol,
        trend_window=trend_window,
        vol_window=vol_window,
        status_series=context.get("benchmark_context_status", pd.Series(dtype=object)),
    )
    summary.to_csv(summary_csv_path, index=False)
    coverage.to_csv(coverage_csv_path, index=False)
    _write_markdown(
        md_path,
        context,
        summary=summary,
        coverage=coverage,
        fold_attribution_path=fold_attribution_path,
        benchmark_symbol=symbol,
        trend_window=trend_window,
        vol_window=vol_window,
        vol_quantile=vol_quantile,
    )
    return StrategyMarketContextResult(
        csv_path=csv_path,
        summary_csv_path=summary_csv_path,
        coverage_csv_path=coverage_csv_path,
        md_path=md_path,
        rows=len(context),
        benchmark_symbol=symbol,
    )


def _build_context_rows(
    folds: pd.DataFrame,
    *,
    benchmark_symbol: str,
    trend_window: int,
    vol_window: int,
    vol_quantile: float,
) -> pd.DataFrame:
    parsed_starts = pd.to_datetime(folds["valid_start"], errors="coerce")
    parsed_ends = pd.to_datetime(folds["valid_end"], errors="coerce")
    valid_dates = pd.concat([parsed_starts.dropna(), parsed_ends.dropna()])
    if valid_dates.empty:
        index_features = pd.DataFrame()
    else:
        start = valid_dates.min().date() - timedelta(days=max(260, trend_window * 3))
        end = valid_dates.max().date()
        index_features = _index_context_features(
            benchmark_symbol,
            start=start,
            end=end,
            trend_window=trend_window,
            vol_window=vol_window,
            vol_quantile=vol_quantile,
        )

    rows: list[dict[str, Any]] = []
    for _, fold in folds.iterrows():
        valid_start = pd.to_datetime(fold.get("valid_start"), errors="coerce")
        valid_end = pd.to_datetime(fold.get("valid_end"), errors="coerce")
        window_index = _window_index_features(index_features, valid_start, valid_end)
        row = {
            "strategy_id": _safe_str(fold.get("strategy_id")),
            "walk_forward_preset": _safe_str(fold.get("walk_forward_preset")),
            "fold": _safe_int(fold.get("fold")),
            "valid_start": _safe_str(fold.get("valid_start")),
            "valid_end": _safe_str(fold.get("valid_end")),
            "primary_fold_failure": _safe_str(fold.get("primary_fold_failure")),
            "fold_severity": _safe_str(fold.get("fold_severity")),
            "strategy_annualized_return": _optional_float(fold.get("annualized_return")),
            "benchmark_annualized_return": _optional_float(fold.get("benchmark_annualized_return")),
            "excess_annualized_return": _optional_float(fold.get("excess_annualized_return")),
            "strategy_sharpe": _optional_float(fold.get("sharpe")),
            "benchmark_symbol": benchmark_symbol,
            **window_index,
        }
        label, evidence = _market_context_label(row)
        row["market_context_label"] = label
        row["market_context_evidence"] = evidence
        row["i8_decision_hint"] = _i8_decision_hint(row)
        rows.append(row)
    return pd.DataFrame(rows)


def _index_context_features(
    benchmark_symbol: str,
    *,
    start: Any,
    end: Any,
    trend_window: int,
    vol_window: int,
    vol_quantile: float,
) -> pd.DataFrame:
    index_df = load_index_daily_from_local_history(benchmark_symbol, start, end)
    if index_df.empty or "close" not in index_df.columns:
        return pd.DataFrame()
    d = index_df[["date", "close"]].copy().sort_values("date")
    d["date"] = pd.to_datetime(d["date"]).dt.normalize()
    d["close"] = pd.to_numeric(d["close"], errors="coerce")
    d["benchmark_daily_return"] = d["close"].pct_change()
    d["trend_ma"] = d["close"].rolling(
        trend_window,
        min_periods=min(trend_window, max(20, trend_window // 2)),
    ).mean()
    raw_above_trend = d["close"] >= d["trend_ma"]
    d["vol"] = d["benchmark_daily_return"].rolling(
        vol_window,
        min_periods=min(vol_window, max(5, vol_window // 2)),
    ).std() * np.sqrt(252)
    d["vol_threshold"] = d["vol"].rolling(252, min_periods=60).quantile(vol_quantile)
    raw_high_vol = d["vol"] > d["vol_threshold"]
    d["drawdown"] = d["close"] / d["close"].cummax() - 1.0
    d["context_vol"] = d["vol"].shift(1)
    d["context_vol_threshold"] = d["vol_threshold"].shift(1)
    d["context_above_trend"] = raw_above_trend.shift(1)
    d["context_high_vol"] = raw_high_vol.shift(1)
    return d


def _window_index_features(index_features: pd.DataFrame, valid_start: pd.Timestamp, valid_end: pd.Timestamp) -> dict[str, Any]:
    if index_features.empty or pd.isna(valid_start) or pd.isna(valid_end):
        return _empty_window_features("not_available")
    start = pd.Timestamp(valid_start).normalize()
    end = pd.Timestamp(valid_end).normalize()
    window = index_features[(index_features["date"] >= start) & (index_features["date"] <= end)].copy()
    if window.empty:
        return _empty_window_features("not_available")
    returns = pd.to_numeric(window["benchmark_daily_return"], errors="coerce").fillna(0.0)
    close = pd.to_numeric(window["close"], errors="coerce")
    if close.dropna().empty:
        return _empty_window_features("not_available")
    total_return = float(close.iloc[-1] / close.iloc[0] - 1.0) if close.iloc[0] > 0 else np.nan
    annualized_return = _annualized_return(returns)
    vol_mean = _mean_optional(window, "context_vol")
    vol_last = _last_optional(window, "context_vol")
    vol_threshold_mean = _mean_optional(window, "context_vol_threshold")
    above_trend_share = _share_true(window, "context_above_trend")
    high_vol_share = _share_true(window, "context_high_vol")
    risk_off_share = _risk_off_share(window)
    return {
        "benchmark_context_status": "available",
        "benchmark_days": int(len(window)),
        "benchmark_total_return": total_return,
        "benchmark_context_annualized_return": annualized_return,
        "benchmark_context_vol_mean": vol_mean,
        "benchmark_context_vol_last": vol_last,
        "benchmark_context_vol_threshold_mean": vol_threshold_mean,
        "benchmark_above_trend_share": above_trend_share,
        "benchmark_high_vol_share": high_vol_share,
        "benchmark_risk_off_share": risk_off_share,
        "benchmark_max_drawdown": float(window["drawdown"].min()) if "drawdown" in window.columns else np.nan,
        "benchmark_return_bucket": _return_bucket(annualized_return),
        "benchmark_trend_bucket": _trend_bucket(above_trend_share),
        "benchmark_vol_bucket": _vol_bucket(high_vol_share),
    }


def _empty_window_features(status: str) -> dict[str, Any]:
    return {
        "benchmark_context_status": status,
        "benchmark_days": 0,
        "benchmark_total_return": np.nan,
        "benchmark_context_annualized_return": np.nan,
        "benchmark_context_vol_mean": np.nan,
        "benchmark_context_vol_last": np.nan,
        "benchmark_context_vol_threshold_mean": np.nan,
        "benchmark_above_trend_share": np.nan,
        "benchmark_high_vol_share": np.nan,
        "benchmark_risk_off_share": np.nan,
        "benchmark_max_drawdown": np.nan,
        "benchmark_return_bucket": "not_available",
        "benchmark_trend_bucket": "not_available",
        "benchmark_vol_bucket": "not_available",
    }


def _market_context_label(row: dict[str, Any]) -> tuple[str, str]:
    if row.get("benchmark_context_status") != "available":
        return "benchmark_context_unavailable", "benchmark index context could not be loaded"
    failure = _safe_str(row.get("primary_fold_failure"))
    return_bucket = _safe_str(row.get("benchmark_return_bucket"))
    trend_bucket = _safe_str(row.get("benchmark_trend_bucket"))
    vol_bucket = _safe_str(row.get("benchmark_vol_bucket"))
    excess = _optional_float(row.get("excess_annualized_return"))
    strategy_ann = _optional_float(row.get("strategy_annualized_return"))
    benchmark_ann = _optional_float(row.get("benchmark_annualized_return"))
    if failure == "relative_failure_benchmark_strong" and return_bucket == "strong_up":
        return (
            "relative_lag_in_strong_benchmark_context",
            f"strategy_ann={_fmt(strategy_ann)}, benchmark_ann={_fmt(benchmark_ann)}, excess={_fmt(excess)}, return_bucket={return_bucket}",
        )
    if failure == "absolute_failure_market_weak_but_outperform" and return_bucket in {"weak_down", "down"}:
        return (
            "absolute_loss_but_benchmark_weak_context",
            f"strategy_ann={_fmt(strategy_ann)}, benchmark_ann={_fmt(benchmark_ann)}, excess={_fmt(excess)}, return_bucket={return_bucket}",
        )
    if trend_bucket == "mostly_below_trend" or vol_bucket == "mostly_high_vol":
        return (
            "risk_context_pressure",
            f"trend_bucket={trend_bucket}, vol_bucket={vol_bucket}, risk_off_share={_fmt(row.get('benchmark_risk_off_share'))}",
        )
    if failure == "clean_positive_fold":
        return (
            "clean_positive_context",
            f"strategy_ann={_fmt(strategy_ann)}, benchmark_ann={_fmt(benchmark_ann)}, excess={_fmt(excess)}, return_bucket={return_bucket}",
        )
    return (
        "mixed_or_unresolved_context",
        f"failure={failure}, return_bucket={return_bucket}, trend_bucket={trend_bucket}, vol_bucket={vol_bucket}",
    )


def _i8_decision_hint(row: dict[str, Any]) -> str:
    label = _safe_str(row.get("market_context_label"))
    if label == "relative_lag_in_strong_benchmark_context":
        return "Do not test weak-market risk-off first; diagnose why I7 lags a strong benchmark."
    if label == "absolute_loss_but_benchmark_weak_context":
        return "Treat as weak-market resilience evidence, not standalone alpha failure."
    if label == "risk_context_pressure":
        return "A later fixed risk-scaling test may be justified only if this pattern repeats across folds."
    if label == "clean_positive_context":
        return "Use as control fold; avoid fitting new rules to this fold."
    return "Keep diagnostic only; do not derive a trading rule from this fold."


def _write_markdown(
    path: Path,
    context: pd.DataFrame,
    *,
    summary: pd.DataFrame,
    coverage: pd.DataFrame,
    fold_attribution_path: Path,
    benchmark_symbol: str,
    trend_window: int,
    vol_window: int,
    vol_quantile: float,
) -> None:
    lines = [
        "# Strategy Market Context Diagnostic",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Scope",
        "",
        "- This is a research-only market-context diagnostic overlay.",
        "- It reads existing fold attribution and local benchmark index history only.",
        "- It does not rerun backtests, does not rerun admission, does not change strategy weights, and does not implement risk scaling.",
        "- Market-context labels are explanatory diagnostics, not admission gates and not trading rules.",
        "",
        "## Inputs",
        "",
        f"- Fold attribution: `{fold_attribution_path}`",
        f"- Benchmark symbol: `{benchmark_symbol}`",
        f"- Trend window: `{trend_window}` trading days",
        f"- Volatility window: `{vol_window}` trading days",
        f"- Volatility high threshold: rolling `{vol_quantile:.2f}` quantile",
        "",
    ]
    if context.empty:
        lines.append("No market-context rows were generated.")
        path.write_text("\n".join(lines), encoding="utf-8")
        return
    lines.extend(
        [
            "## Fold Context Summary",
            "",
            _md_table(
                [
                    "preset",
                    "fold",
                    "failure_label",
                    "market_context",
                    "bench_bucket",
                    "trend_bucket",
                    "vol_bucket",
                    "above_trend",
                    "risk_off",
                    "strategy_ann",
                    "bench_ann",
                    "excess_ann",
                ],
                [
                    [
                        _safe_str(row["walk_forward_preset"]),
                        str(_safe_int(row["fold"])),
                        _safe_str(row["primary_fold_failure"]),
                        _safe_str(row["market_context_label"]),
                        _safe_str(row["benchmark_return_bucket"]),
                        _safe_str(row["benchmark_trend_bucket"]),
                        _safe_str(row["benchmark_vol_bucket"]),
                        _fmt(row.get("benchmark_above_trend_share")),
                        _fmt(row.get("benchmark_risk_off_share")),
                        _fmt(row.get("strategy_annualized_return")),
                        _fmt(row.get("benchmark_annualized_return")),
                        _fmt(row.get("excess_annualized_return")),
                    ]
                    for _, row in context.iterrows()
                ],
            ),
            "",
            "## Label Counts",
            "",
            _label_count_table(context, "market_context_label"),
            "",
            "## Label Summary",
            "",
            _summary_table(summary),
            "",
            "## Data Coverage",
            "",
            _coverage_table(coverage),
            "",
            "## Interpretation",
            "",
        ]
    )
    strong_lag = int((context["market_context_label"] == "relative_lag_in_strong_benchmark_context").sum())
    weak_resilience = int((context["market_context_label"] == "absolute_loss_but_benchmark_weak_context").sum())
    risk_pressure = int((context["market_context_label"] == "risk_context_pressure").sum())
    lines.extend(
        [
            f"- Relative lag in strong benchmark context folds: `{strong_lag}`",
            f"- Absolute loss but weak benchmark context folds: `{weak_resilience}`",
            f"- Generic risk-context pressure folds: `{risk_pressure}`",
            "",
        ]
    )
    if strong_lag > weak_resilience:
        lines.append(
            "Current evidence points more toward benchmark-relative lag in strong index regimes than toward broad weak-market failure."
        )
    elif weak_resilience > 0:
        lines.append(
            "Current evidence includes weak-market pressure, but weak-market folds also show relative resilience; risk-off logic is not proven."
        )
    else:
        lines.append("Current evidence is mixed; do not proceed to risk scaling without stronger context concentration.")
    lines.extend(
        [
            "",
            "## I8 Decision Guardrail",
            "",
            "- Do not implement a regime filter from this diagnostic alone.",
            "- If I8b is pursued, keep I7 selection logic fixed and test one pre-declared variable only.",
            "- A weak-market risk-off filter is not the first hypothesis if relative lag is concentrated in strong benchmark regimes.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _read_required_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"missing required {label}: {path}")
    return pd.read_csv(path)


def _require_columns(df: pd.DataFrame, columns: list[str], path: Path) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"{path} missing required columns: {missing}")


def _annualized_return(returns: pd.Series) -> float:
    clean = pd.to_numeric(returns, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if clean.empty:
        return np.nan
    equity = float((1.0 + clean).prod())
    return float(equity ** (252 / len(clean)) - 1.0) if equity > 0 else -1.0


def _mean_optional(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns:
        return np.nan
    values = pd.to_numeric(df[column], errors="coerce")
    return float(values.mean()) if values.notna().any() else np.nan


def _last_optional(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns:
        return np.nan
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    return float(values.iloc[-1]) if not values.empty else np.nan


def _share_true(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns:
        return np.nan
    values = df[column].dropna()
    return float(values.astype(bool).mean()) if not values.empty else np.nan


def _risk_off_share(df: pd.DataFrame) -> float:
    if "context_above_trend" not in df.columns or "context_high_vol" not in df.columns:
        return np.nan
    trend_off = ~df["context_above_trend"].fillna(False).astype(bool)
    high_vol = df["context_high_vol"].fillna(False).astype(bool)
    return float((trend_off | high_vol).mean()) if len(df) else np.nan


def _label_summary(context: pd.DataFrame) -> pd.DataFrame:
    if context.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for label, group in context.groupby("primary_fold_failure", dropna=False):
        rows.append(
            {
                "primary_fold_failure": _safe_str(label),
                "fold_count": int(len(group)),
                "avg_excess_ann": _mean_series(group.get("excess_annualized_return")),
                "avg_index_ann_return": _mean_series(group.get("benchmark_context_annualized_return")),
                "avg_pct_days_above_trend": _mean_series(group.get("benchmark_above_trend_share")),
                "avg_pct_days_high_vol": _mean_series(group.get("benchmark_high_vol_share")),
                "avg_pct_days_risk_off_context": _mean_series(group.get("benchmark_risk_off_share")),
                "dominant_market_context": _safe_str(group["market_context_label"].mode().iloc[0]) if "market_context_label" in group and not group["market_context_label"].mode().empty else "",
                "interpretation": _summary_interpretation(_safe_str(label), group),
            }
        )
    return pd.DataFrame(rows).sort_values(["fold_count", "primary_fold_failure"], ascending=[False, True])


def _coverage_summary(
    folds: pd.DataFrame,
    *,
    benchmark_symbol: str,
    trend_window: int,
    vol_window: int,
    status_series: pd.Series,
) -> pd.DataFrame:
    starts = pd.to_datetime(folds.get("valid_start", pd.Series(dtype=object)), errors="coerce").dropna()
    ends = pd.to_datetime(folds.get("valid_end", pd.Series(dtype=object)), errors="coerce").dropna()
    if starts.empty or ends.empty:
        return pd.DataFrame(
            [
                {
                    "index_symbol": benchmark_symbol,
                    "requested_start": "",
                    "requested_end": "",
                    "loaded_start": "",
                    "loaded_end": "",
                    "trading_days": 0,
                    "missing_days_estimate": np.nan,
                    "source": "local_history_sqlite",
                    "coverage_status": "invalid_fold_dates",
                    "asof_shift_applied": True,
                    "trend_window": trend_window,
                    "vol_window": vol_window,
                }
            ]
        )
    requested_start = starts.min().date()
    requested_end = ends.max().date()
    load_start = requested_start - timedelta(days=max(260, trend_window * 3))
    index_df = load_index_daily_from_local_history(benchmark_symbol, load_start, requested_end)
    if index_df.empty:
        loaded_start = ""
        loaded_end = ""
        trading_days = 0
        missing_estimate = np.nan
        source = "local_history_sqlite"
        coverage_status = "not_available"
    else:
        dates = pd.to_datetime(index_df["date"], errors="coerce").dropna()
        loaded_start = dates.min().date().isoformat() if not dates.empty else ""
        loaded_end = dates.max().date().isoformat() if not dates.empty else ""
        trading_days = int(len(dates))
        expected_days = len(pd.bdate_range(requested_start, requested_end))
        in_window_days = int(((dates.dt.date >= requested_start) & (dates.dt.date <= requested_end)).sum())
        missing_estimate = max(expected_days - in_window_days, 0)
        source = _safe_str(index_df.get("data_source", pd.Series(["local_history_sqlite"])).iloc[0], "local_history_sqlite")
        unavailable = int((status_series.fillna("").astype(str) != "available").sum()) if status_series is not None else 0
        coverage_status = "available" if unavailable == 0 else "partial"
    return pd.DataFrame(
        [
            {
                "index_symbol": benchmark_symbol,
                "requested_start": requested_start.isoformat(),
                "requested_end": requested_end.isoformat(),
                "loaded_start": loaded_start,
                "loaded_end": loaded_end,
                "trading_days": trading_days,
                "missing_days_estimate": missing_estimate,
                "source": source,
                "coverage_status": coverage_status,
                "asof_shift_applied": True,
                "trend_window": trend_window,
                "vol_window": vol_window,
            }
        ]
    )


def _summary_interpretation(label: str, group: pd.DataFrame) -> str:
    context_label = ""
    if "market_context_label" in group and not group["market_context_label"].mode().empty:
        context_label = _safe_str(group["market_context_label"].mode().iloc[0])
    if label == "relative_failure_benchmark_strong":
        return f"Positive absolute folds lagged the benchmark; dominant context={context_label}."
    if label == "absolute_failure_market_weak_but_outperform":
        return f"Negative absolute fold still outperformed the benchmark; dominant context={context_label}."
    if label == "clean_positive_fold":
        return f"Control folds with positive absolute and excess returns; dominant context={context_label}."
    return f"Mixed diagnostic context; dominant context={context_label or 'n/a'}."


def _return_bucket(annualized_return: float) -> str:
    if pd.isna(annualized_return):
        return "not_available"
    if annualized_return >= 0.10:
        return "strong_up"
    if annualized_return > 0.00:
        return "mild_up"
    if annualized_return <= -0.10:
        return "weak_down"
    return "flat_or_mild_down"


def _trend_bucket(above_trend_share: float) -> str:
    if pd.isna(above_trend_share):
        return "not_available"
    if above_trend_share >= 0.70:
        return "mostly_above_trend"
    if above_trend_share <= 0.30:
        return "mostly_below_trend"
    return "mixed_trend"


def _vol_bucket(high_vol_share: float) -> str:
    if pd.isna(high_vol_share):
        return "not_available"
    if high_vol_share >= 0.50:
        return "mostly_high_vol"
    if high_vol_share <= 0.20:
        return "mostly_normal_vol"
    return "mixed_vol"


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |")
    return "\n".join(out)


def _label_count_table(df: pd.DataFrame, column: str) -> str:
    counts = df[column].fillna("").astype(str).value_counts().reset_index()
    counts.columns = [column, "count"]
    return _md_table([column, "count"], [[_safe_str(row[column]), str(_safe_int(row["count"]))] for _, row in counts.iterrows()])


def _summary_table(summary: pd.DataFrame) -> str:
    if summary.empty:
        return "No summary rows."
    return _md_table(
        [
            "primary_fold_failure",
            "folds",
            "avg_excess",
            "avg_index_ann",
            "avg_above_trend",
            "avg_high_vol",
            "avg_risk_off",
            "dominant_context",
        ],
        [
            [
                _safe_str(row["primary_fold_failure"]),
                str(_safe_int(row["fold_count"])),
                _fmt(row.get("avg_excess_ann")),
                _fmt(row.get("avg_index_ann_return")),
                _fmt(row.get("avg_pct_days_above_trend")),
                _fmt(row.get("avg_pct_days_high_vol")),
                _fmt(row.get("avg_pct_days_risk_off_context")),
                _safe_str(row.get("dominant_market_context")),
            ]
            for _, row in summary.iterrows()
        ],
    )


def _coverage_table(coverage: pd.DataFrame) -> str:
    if coverage.empty:
        return "No coverage rows."
    return _md_table(
        [
            "index_symbol",
            "requested",
            "loaded",
            "trading_days",
            "missing_est",
            "source",
            "status",
            "asof_shift",
        ],
        [
            [
                _safe_str(row["index_symbol"]),
                f"{_safe_str(row['requested_start'])}..{_safe_str(row['requested_end'])}",
                f"{_safe_str(row['loaded_start'])}..{_safe_str(row['loaded_end'])}",
                str(_safe_int(row["trading_days"])),
                _fmt(row.get("missing_days_estimate")),
                _safe_str(row["source"]),
                _safe_str(row["coverage_status"]),
                _safe_str(row["asof_shift_applied"]),
            ]
            for _, row in coverage.iterrows()
        ],
    )


def _mean_series(series: pd.Series | None) -> float:
    if series is None:
        return np.nan
    values = pd.to_numeric(series, errors="coerce")
    return float(values.mean()) if values.notna().any() else np.nan


def _optional_float(value: Any) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _fmt(value: Any) -> str:
    parsed = _optional_float(value)
    return "n/a" if parsed is None else f"{parsed:.4f}"


def _safe_int(value: Any, default: int = 0) -> int:
    parsed = _optional_float(value)
    return int(round(parsed if parsed is not None else default))


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except ValueError:
        pass
    text = str(value)
    return default if text.lower() == "nan" else text
