from __future__ import annotations

import ast
import hashlib
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StrategyExposureDiagnosticResult:
    csv_path: Path
    summary_csv_path: Path
    run_log_md_path: Path
    md_path: Path
    rows: int
    strong_lag_rows: int


def run_strategy_exposure_diagnostic(
    *,
    config: dict[str, Any] | None,
    root: Path,
    candidate_folds_path: Path,
    market_context_path: Path,
    output_dir: Path | None = None,
    universe_path: Path | None = None,
    config_path: Path | None = None,
    command: str | None = None,
) -> StrategyExposureDiagnosticResult:
    """Diagnose strong-benchmark lag from existing fold artifacts only."""
    output_dir = output_dir or market_context_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_folds = _read_required_csv(candidate_folds_path, "strategy_admission_candidate_folds.csv")
    market_context = _read_required_csv(market_context_path, "strategy_market_context_diagnostic.csv")
    _require_columns(
        candidate_folds,
        [
            "strategy_id",
            "walk_forward_preset",
            "fold",
            "valid_start",
            "valid_end",
            "annualized_return",
            "benchmark_annualized_return",
            "excess_annualized_return",
            "avg_live_holdings",
            "first_target_symbols",
            "top_industry_avg_share",
            "top3_industries_avg_share",
        ],
        candidate_folds_path,
    )
    _require_columns(
        market_context,
        [
            "strategy_id",
            "walk_forward_preset",
            "fold",
            "market_context_label",
            "benchmark_return_bucket",
            "benchmark_trend_bucket",
            "benchmark_above_trend_share",
            "excess_annualized_return",
        ],
        market_context_path,
    )
    fold_keys = ["strategy_id", "walk_forward_preset", "fold"]
    _validate_unique_keys(candidate_folds, fold_keys, candidate_folds_path)
    _validate_unique_keys(market_context, fold_keys, market_context_path)
    merge_audit = _assert_merge_coverage(
        candidate_folds,
        market_context,
        fold_keys,
        candidate_folds_path=candidate_folds_path,
        market_context_path=market_context_path,
    )
    universe = _load_universe_metadata(universe_path or root / "data" / "universe" / "local_factor_universe.csv")
    rows = _build_exposure_rows(candidate_folds, market_context, universe)
    summary = _build_summary(rows)

    csv_path = output_dir / "strong_benchmark_exposure_diagnostic.csv"
    summary_csv_path = output_dir / "strong_benchmark_exposure_summary.csv"
    run_log_md_path = output_dir / "strategy_experiment_run_log.md"
    md_path = output_dir / "strong_benchmark_exposure_diagnostic.md"
    rows.to_csv(csv_path, index=False)
    summary.to_csv(summary_csv_path, index=False)
    _write_markdown(
        md_path,
        rows,
        summary,
        candidate_folds_path=candidate_folds_path,
        market_context_path=market_context_path,
        universe_path=universe_path or root / "data" / "universe" / "local_factor_universe.csv",
        run_log_path=run_log_md_path,
    )
    _write_run_log(
        run_log_md_path,
        config=config or {},
        candidate_folds=candidate_folds,
        merge_audit=merge_audit,
        root=root,
        candidate_folds_path=candidate_folds_path,
        market_context_path=market_context_path,
        universe_path=universe_path or root / "data" / "universe" / "local_factor_universe.csv",
        output_dir=output_dir,
        output_artifacts=[csv_path, summary_csv_path, md_path],
        config_path=config_path,
        command=command,
    )
    strong_lag_rows = int((rows["market_context_label"] == "relative_lag_in_strong_benchmark_context").sum()) if not rows.empty else 0
    return StrategyExposureDiagnosticResult(
        csv_path=csv_path,
        summary_csv_path=summary_csv_path,
        run_log_md_path=run_log_md_path,
        md_path=md_path,
        rows=len(rows),
        strong_lag_rows=strong_lag_rows,
    )


def _build_exposure_rows(candidate_folds: pd.DataFrame, market_context: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    fold_keys = ["strategy_id", "walk_forward_preset", "fold"]
    folds = candidate_folds.copy()
    context_cols = [
        *fold_keys,
        "market_context_label",
        "benchmark_return_bucket",
        "benchmark_trend_bucket",
        "benchmark_vol_bucket",
        "benchmark_above_trend_share",
        "benchmark_risk_off_share",
        "benchmark_context_annualized_return",
    ]
    context_cols = [col for col in context_cols if col in market_context.columns]
    merged = folds.merge(market_context[context_cols], on=fold_keys, how="inner", suffixes=("", "_context"))
    metadata = universe.copy()
    if not metadata.empty and "symbol" in metadata.columns:
        metadata["symbol"] = metadata["symbol"].astype(str)
    rows: list[dict[str, Any]] = []
    for _, row in merged.iterrows():
        symbols = _parse_symbol_list(row.get("first_target_symbols"))
        meta = metadata[metadata["symbol"].isin(symbols)].copy() if symbols and not metadata.empty else pd.DataFrame()
        first_industry_counts = _industry_counts(meta)
        first_top_industry_share = _top_share(first_industry_counts, len(symbols))
        first_top3_industry_share = _top3_share(first_industry_counts, len(symbols))
        first_unknown_industry_share = _unknown_share(meta, len(symbols))
        first_metadata_as_of = _metadata_as_of(meta)
        participation_gap = _optional_float(row.get("benchmark_annualized_return")) - _optional_float(row.get("annualized_return"))
        rows.append(
            {
                "strategy_id": _safe_str(row.get("strategy_id")),
                "walk_forward_preset": _safe_str(row.get("walk_forward_preset")),
                "fold": _safe_int(row.get("fold")),
                "valid_start": _safe_str(row.get("valid_start")),
                "valid_end": _safe_str(row.get("valid_end")),
                "market_context_label": _safe_str(row.get("market_context_label")),
                "benchmark_return_bucket": _safe_str(row.get("benchmark_return_bucket")),
                "benchmark_trend_bucket": _safe_str(row.get("benchmark_trend_bucket")),
                "benchmark_vol_bucket": _safe_str(row.get("benchmark_vol_bucket")),
                "benchmark_above_trend_share": _optional_float(row.get("benchmark_above_trend_share")),
                "benchmark_risk_off_share": _optional_float(row.get("benchmark_risk_off_share")),
                "strategy_annualized_return": _optional_float(row.get("annualized_return")),
                "benchmark_annualized_return": _optional_float(row.get("benchmark_annualized_return")),
                "excess_annualized_return": _optional_float(row.get("excess_annualized_return")),
                "participation_gap_ann": participation_gap,
                "sharpe": _optional_float(row.get("sharpe")),
                "turnover_annual": _optional_float(row.get("turnover_annual")),
                "avg_live_holdings": _optional_float(row.get("avg_live_holdings")),
                "trade_days": _safe_int(row.get("trade_days")),
                "top_industry_avg_share": _optional_float(row.get("top_industry_avg_share")),
                "top3_industries_avg_share": _optional_float(row.get("top3_industries_avg_share")),
                "industry_constraint_violation_days": _safe_int(row.get("industry_constraint_violation_days")),
                "first_target_date": _safe_str(row.get("first_target_date")),
                "first_target_count": len(symbols),
                "first_target_symbols": ",".join(symbols),
                "first_target_top_industry": _top_industry(first_industry_counts),
                "first_target_top_industry_share": first_top_industry_share,
                "first_target_top3_industry_share": first_top3_industry_share,
                "first_target_unknown_industry_share": first_unknown_industry_share,
                "first_target_metadata_status": _metadata_status(symbols, meta),
                "first_target_metadata_scope": "current_snapshot_not_pit" if first_metadata_as_of else "not_available",
                "first_target_metadata_as_of": first_metadata_as_of,
                "exposure_proxy_label": _exposure_proxy_label(row),
                "i9_decision_hint": _i9_decision_hint(row),
            }
        )
    return pd.DataFrame(rows)


def _validate_unique_keys(df: pd.DataFrame, keys: list[str], path: Path) -> None:
    duplicate_count = int(df.duplicated(keys).sum())
    if duplicate_count:
        duplicates = df.loc[df.duplicated(keys, keep=False), keys].head(5).to_dict("records")
        raise ValueError(f"{path} has duplicate fold keys: count={duplicate_count}, examples={duplicates}")


def _assert_merge_coverage(
    candidate_folds: pd.DataFrame,
    market_context: pd.DataFrame,
    keys: list[str],
    *,
    candidate_folds_path: Path,
    market_context_path: Path,
) -> pd.DataFrame:
    audit = candidate_folds[keys].merge(
        market_context[keys],
        on=keys,
        how="outer",
        indicator=True,
    )
    unmatched_candidate = audit[audit["_merge"] == "left_only"]
    unmatched_context = audit[audit["_merge"] == "right_only"]
    if not unmatched_candidate.empty or not unmatched_context.empty:
        raise ValueError(
            "candidate folds and market context keys do not match: "
            f"candidate_only={len(unmatched_candidate)} from {candidate_folds_path}, "
            f"context_only={len(unmatched_context)} from {market_context_path}"
        )
    return audit


def _build_summary(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    summaries: list[dict[str, Any]] = []
    for label, group in rows.groupby("market_context_label", dropna=False):
        summaries.append(
            {
                "market_context_label": _safe_str(label),
                "fold_count": int(len(group)),
                "avg_strategy_ann": _mean(group, "strategy_annualized_return"),
                "avg_benchmark_ann": _mean(group, "benchmark_annualized_return"),
                "avg_excess_ann": _mean(group, "excess_annualized_return"),
                "avg_participation_gap_ann": _mean(group, "participation_gap_ann"),
                "avg_live_holdings": _mean(group, "avg_live_holdings"),
                "avg_top_industry_share": _mean(group, "top_industry_avg_share"),
                "avg_top3_industry_share": _mean(group, "top3_industries_avg_share"),
                "avg_current_first_target_top_industry_share": _mean(group, "first_target_top_industry_share"),
                "current_metadata_available_folds": int((group["first_target_metadata_status"] == "available").sum()),
                "dominant_exposure_proxy": _mode(group, "exposure_proxy_label"),
                "interpretation": _summary_interpretation(_safe_str(label), group),
            }
        )
    return pd.DataFrame(summaries).sort_values(["fold_count", "market_context_label"], ascending=[False, True])


def _write_markdown(
    path: Path,
    rows: pd.DataFrame,
    summary: pd.DataFrame,
    *,
    candidate_folds_path: Path,
    market_context_path: Path,
    universe_path: Path,
    run_log_path: Path,
) -> None:
    lines = [
        "# Iter 09 - Strong Benchmark Exposure Diagnostic",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Scope",
        "",
        "- This is a research-only diagnostic for I7/I8 strong-benchmark relative lag.",
        "- It reads existing admission candidate folds and I8 market-context CSV artifacts.",
        "- It does not rerun backtests, does not rerun admission, does not change strategy weights, and does not implement an overlay or trading rule.",
        "- Because existing I7 artifacts do not contain full daily holdings or benchmark constituent weights, this report uses fold-level participation and industry concentration proxies only.",
        "- First-target industry labels use the current universe metadata snapshot only; they are not point-in-time exposure evidence and are not used as promotion evidence.",
        "",
        "## Inputs",
        "",
        f"- Candidate folds: `{candidate_folds_path}`",
        f"- Market context: `{market_context_path}`",
        f"- Universe metadata: `{universe_path}` (current snapshot only; not PIT)",
        f"- Run log: `{run_log_path}`",
        "",
    ]
    if rows.empty:
        lines.append("No rows were generated. Check input artifact keys and required columns.")
        path.write_text("\n".join(lines), encoding="utf-8")
        return
    lines.extend(
        [
            "## Context Summary",
            "",
            _md_table(
                [
                    "market_context",
                    "folds",
                    "strategy_ann",
                    "benchmark_ann",
                    "excess_ann",
                    "participation_gap",
                    "avg_holdings",
                    "top1_industry",
                    "top3_industry",
                    "current_first_target_top1",
                    "proxy",
                ],
                [
                    [
                        _safe_str(row.get("market_context_label")),
                        str(_safe_int(row.get("fold_count"))),
                        _fmt(row.get("avg_strategy_ann")),
                        _fmt(row.get("avg_benchmark_ann")),
                        _fmt(row.get("avg_excess_ann")),
                        _fmt(row.get("avg_participation_gap_ann")),
                        _fmt(row.get("avg_live_holdings")),
                        _fmt(row.get("avg_top_industry_share")),
                        _fmt(row.get("avg_top3_industry_share")),
                        _fmt(row.get("avg_current_first_target_top_industry_share")),
                        _safe_str(row.get("dominant_exposure_proxy")),
                    ]
                    for _, row in summary.iterrows()
                ],
            ),
            "",
            "## Fold Diagnostics",
            "",
            _md_table(
                [
                    "preset",
                    "fold",
                    "context",
                    "strategy_ann",
                    "benchmark_ann",
                    "excess_ann",
                    "avg_holdings",
                    "top1",
                    "top3",
                    "current_first_target_top_industry",
                    "proxy",
                ],
                [
                    [
                        _safe_str(row.get("walk_forward_preset")),
                        str(_safe_int(row.get("fold"))),
                        _safe_str(row.get("market_context_label")),
                        _fmt(row.get("strategy_annualized_return")),
                        _fmt(row.get("benchmark_annualized_return")),
                        _fmt(row.get("excess_annualized_return")),
                        _fmt(row.get("avg_live_holdings")),
                        _fmt(row.get("top_industry_avg_share")),
                        _fmt(row.get("top3_industries_avg_share")),
                        _safe_str(row.get("first_target_top_industry")),
                        _safe_str(row.get("exposure_proxy_label")),
                    ]
                    for _, row in rows.iterrows()
                ],
            ),
            "",
            "## Interpretation",
            "",
            *_interpretation_lines(rows, summary),
            "",
            "## Decision Guardrail",
            "",
            "- I9 does not change I7 promotion status; I7 remains research-only unless a later admission run proves otherwise.",
            "- Do not implement a strong-benchmark overlay from these proxies alone.",
            "- If continuing to I10, first add or export auditable daily holdings and benchmark constituent/style exposure, then compare strong-benchmark lag folds against clean positive folds.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_run_log(
    path: Path,
    *,
    config: dict[str, Any],
    candidate_folds: pd.DataFrame,
    merge_audit: pd.DataFrame,
    root: Path,
    candidate_folds_path: Path,
    market_context_path: Path,
    universe_path: Path,
    output_dir: Path,
    output_artifacts: list[Path],
    config_path: Path | None,
    command: str | None,
) -> None:
    status = _git_status(root)
    lines = [
        "# Strategy Experiment Run Log",
        "",
        f"- iteration_id: `I9`",
        f"- parent_iteration: `I8`",
        f"- created_at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- git_head: `{_git_head(root)}`",
        f"- git_branch: `{_git_branch(root)}`",
        f"- dirty_status_summary: `{status['summary']}`",
        f"- config_path: `{config_path or ''}`",
        f"- command: `{command or ''}`",
        f"- strategy_scope: `price_volume_low_turnover_v1 / I7 candidate folds`",
        f"- data_as_of: `{_data_as_of(config, candidate_folds)}`",
        f"- price_mode: `{_price_mode(config)}`",
        f"- promotion_boundary: `research_only; no admission rerun; no trading rule`",
        f"- artifact_key_coverage: `matched={len(merge_audit)}, unmatched_candidate=0, unmatched_market_context=0`",
        "",
        "## Input Artifacts",
        "",
        _artifact_line("config", config_path),
        _artifact_line("candidate_folds", candidate_folds_path),
        _artifact_line("market_context", market_context_path),
        _artifact_line("universe_metadata_current_snapshot", universe_path),
        "",
        "## Output Artifacts",
        "",
        *[_artifact_line("output", artifact) for artifact in output_artifacts],
        f"- run_log_pending_hash: `{path}`",
        "",
        "## Artifact Key Coverage",
        "",
        f"- matched_fold_keys: `{len(merge_audit)}`",
        "- unmatched_candidate_folds: `0`",
        "- unmatched_market_context_folds: `0`",
        "",
        "## Git Dirty Status",
        "",
        "```text",
        status["details"],
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _interpretation_lines(rows: pd.DataFrame, summary: pd.DataFrame) -> list[str]:
    strong = rows[rows["market_context_label"] == "relative_lag_in_strong_benchmark_context"]
    clean = rows[rows["market_context_label"] == "clean_positive_context"]
    lines: list[str] = []
    if strong.empty:
        return ["- No strong-benchmark relative-lag folds were found in the merged artifact set."]
    lines.append(
        f"- Strong-benchmark lag folds: `{len(strong)}`, avg excess ann `{_fmt(strong['excess_annualized_return'].mean())}`, avg benchmark ann `{_fmt(strong['benchmark_annualized_return'].mean())}`."
    )
    lines.append(
        f"- Proxy portfolio breadth in strong-lag folds: avg live holdings `{_fmt(strong['avg_live_holdings'].mean())}`, avg top1 industry share `{_fmt(strong['top_industry_avg_share'].mean())}`, avg top3 industry share `{_fmt(strong['top3_industries_avg_share'].mean())}`."
    )
    if not clean.empty:
        lines.append(
            f"- Clean positive folds comparison: avg excess ann `{_fmt(clean['excess_annualized_return'].mean())}`, avg live holdings `{_fmt(clean['avg_live_holdings'].mean())}`, avg top1 industry share `{_fmt(clean['top_industry_avg_share'].mean())}`."
        )
    labels = strong["exposure_proxy_label"].value_counts()
    dominant = labels.index[0] if not labels.empty else "not_available"
    lines.append(f"- Dominant proxy label in strong-lag folds: `{dominant}`.")
    lines.append("- Current first-target industry labels are auxiliary current-snapshot metadata, not PIT holdings exposure.")
    lines.append(
        "- Current artifacts can support a participation/concentration proxy diagnosis, but not a full holdings-vs-CSI300 constituent or style exposure attribution."
    )
    return lines


def _load_universe_metadata(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame()
    cols = [col for col in ["symbol", "name", "industry", "as_of_date", "source"] if col in df.columns]
    return df[cols].copy() if cols else pd.DataFrame()


def _parse_symbol_list(value: object) -> list[str]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        parsed = [part.strip() for part in text.split(",") if part.strip()]
    if isinstance(parsed, (list, tuple, set)):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [str(parsed).strip()] if str(parsed).strip() else []


def _industry_counts(meta: pd.DataFrame) -> pd.Series:
    if meta.empty or "industry" not in meta.columns:
        return pd.Series(dtype=int)
    industries = meta["industry"].fillna("").astype(str).replace("", "UNKNOWN")
    return industries.value_counts()


def _top_industry(counts: pd.Series) -> str:
    return str(counts.index[0]) if not counts.empty else ""


def _top_share(counts: pd.Series, total: int) -> float:
    if total <= 0 or counts.empty:
        return np.nan
    return float(counts.iloc[0] / total)


def _top3_share(counts: pd.Series, total: int) -> float:
    if total <= 0 or counts.empty:
        return np.nan
    return float(counts.head(3).sum() / total)


def _unknown_share(meta: pd.DataFrame, total: int) -> float:
    if total <= 0:
        return np.nan
    if meta.empty or "industry" not in meta.columns:
        return 1.0
    unknown = meta["industry"].fillna("").astype(str).replace("", "UNKNOWN").eq("UNKNOWN").sum()
    missing = max(total - len(meta), 0)
    return float((unknown + missing) / total)


def _metadata_status(symbols: list[str], meta: pd.DataFrame) -> str:
    if not symbols:
        return "no_first_target_symbols"
    if meta.empty:
        return "missing_universe_metadata"
    if len(meta) < len(symbols):
        return "partial"
    return "available"


def _metadata_as_of(meta: pd.DataFrame) -> str:
    if meta.empty or "as_of_date" not in meta.columns:
        return ""
    values = meta["as_of_date"].dropna().astype(str)
    values = values[values.str.len() > 0]
    if values.empty:
        return ""
    unique = sorted(values.unique())
    return unique[0] if len(unique) == 1 else f"{unique[0]}..{unique[-1]}"


def _exposure_proxy_label(row: pd.Series) -> str:
    label = _safe_str(row.get("market_context_label"))
    excess = _optional_float(row.get("excess_annualized_return"))
    holdings = _optional_float(row.get("avg_live_holdings"))
    top1 = _optional_float(row.get("top_industry_avg_share"))
    if label == "relative_lag_in_strong_benchmark_context":
        if holdings < 5:
            return "possible_under_participation_breadth"
        if top1 >= 0.18:
            return "possible_style_or_industry_tilt"
        if excess < -0.05:
            return "strong_benchmark_beta_lag_proxy"
        return "mild_strong_benchmark_lag_proxy"
    if label in {"clean_positive_context", "risk_context_pressure", "absolute_loss_but_benchmark_weak_context"}:
        return "control_or_resilience_context"
    return "mixed_or_unresolved_proxy"


def _i9_decision_hint(row: pd.Series) -> str:
    proxy = _exposure_proxy_label(row)
    if proxy == "possible_under_participation_breadth":
        return "Check whether strong-index lag comes from too few names or low beta participation before adding overlay."
    if proxy == "possible_style_or_industry_tilt":
        return "I10 should compare holdings' industry/style exposure against CSI300 constituents or a stable proxy."
    if proxy == "strong_benchmark_beta_lag_proxy":
        return "A benchmark participation overlay is a hypothesis, but needs daily holdings and benchmark exposure evidence first."
    if proxy == "control_or_resilience_context":
        return "Use as control fold; avoid fitting a strong-market rule to non-lag contexts."
    return "Keep diagnostic-only; no strategy rule from this proxy."


def _summary_interpretation(label: str, group: pd.DataFrame) -> str:
    if label == "relative_lag_in_strong_benchmark_context":
        return "Strong benchmark folds show positive absolute returns but negative excess; diagnose participation and style exposure before overlay."
    if label == "clean_positive_context":
        return "Control folds with positive excess; compare construction breadth and industry proxies against strong-lag folds."
    if label == "absolute_loss_but_benchmark_weak_context":
        return "Weak benchmark context with relative resilience; not evidence for generic weak-market de-risking."
    if label == "risk_context_pressure":
        return "Risk-pressure context; keep separate from strong-benchmark lag hypothesis."
    return "Mixed context; no direct strategy-selection rule."


def _data_as_of(config: dict[str, Any], candidate_folds: pd.DataFrame) -> str:
    if "universe_as_of_date" in candidate_folds.columns:
        values = candidate_folds["universe_as_of_date"].dropna().astype(str)
        values = values[values.str.len() > 0]
        if not values.empty:
            unique = sorted(values.unique())
            return unique[0] if len(unique) == 1 else f"{unique[0]}..{unique[-1]}"
    universe = config.get("universe", {}) if isinstance(config, dict) else {}
    return str(universe.get("as_of_date") or universe.get("date") or "")


def _price_mode(config: dict[str, Any]) -> str:
    if not isinstance(config, dict):
        return ""
    local_history = config.get("local_history", {})
    walk = config.get("walk_forward", {})
    return str(
        local_history.get("price_adjustment_for_backtest")
        or walk.get("price_adjustment_for_backtest")
        or walk.get("price_adjustment")
        or config.get("price_adjustment", "")
    )


def _git_head(root: Path) -> str:
    return _run_git(root, ["rev-parse", "--short", "HEAD"])


def _git_branch(root: Path) -> str:
    return _run_git(root, ["branch", "--show-current"])


def _git_status(root: Path) -> dict[str, str]:
    details = _run_git(root, ["status", "--short"])
    count = len([line for line in details.splitlines() if line.strip()])
    return {"summary": f"{count} changed paths", "details": details}


def _run_git(root: Path, args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "not_available"


def _artifact_line(label: str, path: Path | None) -> str:
    if path is None:
        return f"- {label}: `not_available`"
    if not path.exists():
        return f"- {label}: `{path}` missing"
    stat = path.stat()
    return (
        f"- {label}: `{path}` "
        f"sha256={_sha256(path)} size={stat.st_size} mtime={datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds')}"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_required_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"missing required {label}: {path}")
    return pd.read_csv(path)


def _require_columns(df: pd.DataFrame, columns: list[str], path: Path) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"{path} missing required columns: {missing}")


def _mean(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns:
        return np.nan
    values = pd.to_numeric(df[column], errors="coerce")
    return float(values.mean()) if values.notna().any() else np.nan


def _mode(df: pd.DataFrame, column: str) -> str:
    if column not in df.columns:
        return ""
    mode = df[column].dropna().astype(str).mode()
    return str(mode.iloc[0]) if not mode.empty else ""


def _optional_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def _safe_int(value: object) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _safe_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    return str(value)


def _fmt(value: object) -> str:
    val = _optional_float(value)
    if np.isnan(val):
        return ""
    return f"{val:.4f}"


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)
