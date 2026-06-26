from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


ADMISSION_PASS_ACTIONS = {"admission_pass_candidate", "paper_review_candidate", "pass"}


@dataclass(frozen=True)
class StrategyRoleCardResult:
    rule_csv_path: Path
    report_md_path: Path
    rows: int
    strategy_id: str
    admission_action: str


def run_strategy_role_card(
    *,
    strategy_id: str,
    matrix_path: Path,
    constraints_path: Path,
    output_dir: Path,
    fold_attribution_path: Path | None = None,
    market_context_path: Path | None = None,
    holdings_summary_path: Path | None = None,
    overlay_summary_path: Path | None = None,
) -> StrategyRoleCardResult:
    """Build a read-only strategy-pool role card from existing diagnostic artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    matrix = _read_required_csv(matrix_path, "strategy_admission_window_matrix.csv")
    constraints = _read_required_csv(constraints_path, "strategy_admission_constraint_review.csv")
    _require_columns(matrix, ["strategy_id", "walk_forward_preset"], matrix_path)
    _require_columns(constraints, ["strategy_id", "admission_action"], constraints_path)

    strategy_matrix = matrix[matrix["strategy_id"].astype(str) == strategy_id].copy()
    if strategy_matrix.empty:
        raise ValueError(f"{matrix_path} has no rows for strategy_id={strategy_id!r}")
    strategy_review = constraints[constraints["strategy_id"].astype(str) == strategy_id].copy()
    if strategy_review.empty:
        raise ValueError(f"{constraints_path} has no rows for strategy_id={strategy_id!r}")
    review_row = strategy_review.iloc[0]
    admission_action = _safe_str(review_row.get("admission_action"), "unknown")

    fold_attribution = _read_optional_csv(fold_attribution_path, "strategy_failure_fold_attribution.csv")
    market_context = _read_optional_csv(market_context_path, "strategy_market_context_diagnostic.csv")
    holdings_summary = _read_optional_csv(holdings_summary_path, "strategy_holdings_exposure_summary.csv")
    overlay_summary = _read_optional_csv(overlay_summary_path, "strategy_participation_overlay_summary.csv")

    rows: list[dict[str, Any]] = []
    rows.append(_promotion_rule(strategy_id, strategy_matrix, review_row, admission_action))
    rows.extend(_market_context_rules(strategy_id, market_context, holdings_summary, admission_action=admission_action))
    rows.extend(_fold_attribution_rules(strategy_id, fold_attribution))
    rows.extend(_overlay_rules(strategy_id, overlay_summary))
    rows.append(_formal_workflow_rule(strategy_id, admission_action))

    rule_df = pd.DataFrame(rows)
    rule_df = _deduplicate_rules(rule_df)
    rule_csv_path = output_dir / "strategy_role_card_rules.csv"
    report_md_path = output_dir / "strategy_role_card.md"
    rule_df.to_csv(rule_csv_path, index=False)
    _write_markdown(
        report_md_path,
        strategy_id=strategy_id,
        matrix=strategy_matrix,
        review_row=review_row,
        rules=rule_df,
        input_paths={
            "window_matrix": matrix_path,
            "constraint_review": constraints_path,
            "fold_attribution": fold_attribution_path,
            "market_context": market_context_path,
            "holdings_summary": holdings_summary_path,
            "overlay_summary": overlay_summary_path,
        },
    )
    return StrategyRoleCardResult(
        rule_csv_path=rule_csv_path,
        report_md_path=report_md_path,
        rows=len(rule_df),
        strategy_id=strategy_id,
        admission_action=admission_action,
    )


def _promotion_rule(strategy_id: str, matrix: pd.DataFrame, review_row: pd.Series, admission_action: str) -> dict[str, Any]:
    window_count = len(matrix)
    pass_count = int(pd.Series(matrix.get("is_window_pass", False)).astype(bool).sum())
    overfit = _safe_str(review_row.get("overfit_risk_level"), "unknown")
    supports_paper = _safe_bool(review_row.get("supports_paper_trade", False))
    if admission_action in ADMISSION_PASS_ACTIONS and supports_paper:
        state = "paper_review_precondition_possible"
        next_step = "Run paper-review eligibility checks with human review."
    else:
        state = "promotion_blocked_until_admission"
        next_step = "Rerun current admission presets before any paper-review eligibility check."
    return {
        "rule_id": "promotion_path",
        "strategy_id": strategy_id,
        "market_context": "any",
        "research_state": state,
        "evidence": (
            f"admission_action={admission_action}; window_pass={pass_count}/{window_count}; "
            f"overfit={overfit}; supports_paper_trade={supports_paper}"
        ),
        "allowed_research_action": "Document promotion prerequisites and missing evidence.",
        "blocked_action": "Do not promote from scoped evidence, compare rank, or a single favorable window.",
        "next_step": next_step,
    }


def _market_context_rules(
    strategy_id: str,
    market_context: pd.DataFrame,
    holdings_summary: pd.DataFrame,
    *,
    admission_action: str,
) -> list[dict[str, Any]]:
    if market_context.empty:
        return []
    _require_columns(
        market_context,
        ["strategy_id", "market_context_label", "strategy_annualized_return", "benchmark_annualized_return", "excess_annualized_return"],
        Path("market_context"),
    )
    data = market_context[market_context["strategy_id"].astype(str) == strategy_id].copy()
    if data.empty:
        return []
    rows: list[dict[str, Any]] = []
    weak = data[data["market_context_label"].astype(str).isin(["risk_context_pressure", "absolute_loss_but_benchmark_weak_context", "clean_positive_context"])]
    if not weak.empty:
        avg_strategy_ann = _mean(weak, "strategy_annualized_return")
        avg_excess_ann = _mean(weak, "excess_annualized_return")
        positive_excess_ratio = _positive_ratio(weak, "excess_annualized_return")
        weak_state = _weak_context_state(
            admission_action=admission_action,
            avg_strategy_ann=avg_strategy_ann,
            avg_excess_ann=avg_excess_ann,
            positive_excess_ratio=positive_excess_ratio,
        )
        rows.append(
            {
                "rule_id": "weak_or_risk_pressure",
                "strategy_id": strategy_id,
                "market_context": "weak benchmark or risk pressure",
                "research_state": weak_state,
                "evidence": (
                    f"folds={len(weak)}; avg_strategy_ann={_fmt_pct(avg_strategy_ann)}; "
                    f"avg_excess={_fmt_pct(avg_excess_ann)}; "
                    f"positive_excess_ratio={_fmt_ratio(positive_excess_ratio)}"
                ),
                "allowed_research_action": _weak_context_allowed_action(weak_state),
                "blocked_action": "Do not output paper-review, simulated, daily-brief, watchlist, or live signal.",
                "next_step": _weak_context_next_step(weak_state),
            }
        )
    strong = data[data["market_context_label"].astype(str) == "relative_lag_in_strong_benchmark_context"]
    if not strong.empty:
        evidence = (
            f"folds={len(strong)}; avg_strategy_ann={_fmt_pct(_mean(strong, 'strategy_annualized_return'))}; "
            f"avg_benchmark_ann={_fmt_pct(_mean(strong, 'benchmark_annualized_return'))}; "
            f"avg_excess={_fmt_pct(_mean(strong, 'excess_annualized_return'))}"
        )
        holdings = _holdings_summary_for_label(holdings_summary, "relative_lag_in_strong_benchmark_context")
        if holdings:
            evidence = f"{evidence}; {holdings}"
        rows.append(
            {
                "rule_id": "strong_benchmark_lag",
                "strategy_id": strategy_id,
                "market_context": "strong CSI300 or broad risk-on",
                "research_state": "downgrade_role_fit",
                "evidence": evidence,
                "allowed_research_action": "Record as a strong-market participation gap and compare with separate strong-market candidates.",
                "blocked_action": "Do not call this a strong-index participation strategy or fix it by default exposure lifting.",
                "next_step": "If no admitted strong-market candidate exists, formal workflows must return no eligible strategy.",
            }
        )
    return rows


def _weak_context_state(
    *,
    admission_action: str,
    avg_strategy_ann: float | None,
    avg_excess_ann: float | None,
    positive_excess_ratio: float | None,
) -> str:
    if admission_action == "reject":
        return "weak_context_diagnostic_only"
    has_positive_abs = avg_strategy_ann is not None and avg_strategy_ann > 0
    has_positive_excess = avg_excess_ann is not None and avg_excess_ann > 0
    has_repeated_positive_excess = positive_excess_ratio is not None and positive_excess_ratio >= 0.5
    if admission_action == "research_only" and has_positive_abs and has_positive_excess and has_repeated_positive_excess:
        return "defensive_selective_research_sample"
    return "weak_context_diagnostic_only"


def _weak_context_allowed_action(state: str) -> str:
    if state == "defensive_selective_research_sample":
        return "Use as defensive/selective research comparator and failure-attribution sample."
    return "Use only as diagnostic evidence for why the candidate did or did not hold up in weak/risk-pressure contexts."


def _weak_context_next_step(state: str) -> str:
    if state == "defensive_selective_research_sample":
        return "Refresh admission before any promotion; keep research-only unless the global gate passes."
    return "Do not claim defensive fit; inspect failure attribution or require a new pre-registered hypothesis."


def _fold_attribution_rules(strategy_id: str, folds: pd.DataFrame) -> list[dict[str, Any]]:
    if folds.empty:
        return []
    _require_columns(folds, ["strategy_id", "primary_fold_failure"], Path("fold_attribution"))
    data = folds[folds["strategy_id"].astype(str) == strategy_id].copy()
    if data.empty:
        return []
    counts = data["primary_fold_failure"].fillna("unknown").astype(str).value_counts()
    dominant = _safe_str(counts.index[0]) if len(counts) else "unknown"
    return [
        {
            "rule_id": "failure_mode_watch",
            "strategy_id": strategy_id,
            "market_context": "all observed folds",
            "research_state": "monitor_failure_modes",
            "evidence": f"dominant_failure={dominant}; label_counts={_format_counts(counts.to_dict())}",
            "allowed_research_action": "Use failure labels to choose the next research task.",
            "blocked_action": "Do not turn diagnostic labels into trading filters without a pre-registered test.",
            "next_step": "Keep the failure taxonomy attached to future admission refreshes.",
        }
    ]


def _overlay_rules(strategy_id: str, overlay: pd.DataFrame) -> list[dict[str, Any]]:
    if overlay.empty:
        return []
    required = [
        "base_annualized_return",
        "overlay_annualized_return",
        "base_sharpe",
        "overlay_sharpe",
        "base_max_drawdown",
        "overlay_max_drawdown",
    ]
    _require_columns(overlay, required, Path("overlay_summary"))
    row = _overlay_all_row(overlay)
    base_ann = _optional_float(row.get("base_annualized_return"))
    overlay_ann = _optional_float(row.get("overlay_annualized_return"))
    base_sharpe = _optional_float(row.get("base_sharpe"))
    overlay_sharpe = _optional_float(row.get("overlay_sharpe"))
    base_mdd = _optional_float(row.get("base_max_drawdown"))
    overlay_mdd = _optional_float(row.get("overlay_max_drawdown"))
    worsened = (
        (overlay_ann is not None and base_ann is not None and overlay_ann < base_ann)
        or (overlay_sharpe is not None and base_sharpe is not None and overlay_sharpe < base_sharpe)
        or (overlay_mdd is not None and base_mdd is not None and overlay_mdd < base_mdd)
    )
    return [
        {
            "rule_id": "exposure_overlay_counterevidence",
            "strategy_id": strategy_id,
            "market_context": _safe_str(row.get("market_context_label"), "overlay_scope"),
            "research_state": "rejected_overlay" if worsened else "overlay_requires_retest",
            "evidence": (
                f"ann={_fmt_pct(base_ann)}->{_fmt_pct(overlay_ann)}; "
                f"sharpe={_fmt(base_sharpe)}->{_fmt(overlay_sharpe)}; "
                f"mdd={_fmt_pct(base_mdd)}->{_fmt_pct(overlay_mdd)}"
            ),
            "allowed_research_action": "Keep as counterevidence for shallow exposure fixes.",
            "blocked_action": "Do not make this overlay a default rule or live trading rule.",
            "next_step": "Any future exposure rule must be a separate T-1 visible candidate and rerun through admission.",
        }
    ]


def _formal_workflow_rule(strategy_id: str, admission_action: str) -> dict[str, Any]:
    if admission_action in ADMISSION_PASS_ACTIONS:
        state = "requires_paper_review_eligibility_check"
        next_step = "Run paper-review eligibility before any formal workflow signal."
    else:
        state = "no_eligible_strategy"
        next_step = "Formal workflows must return no eligible strategy."
    return {
        "rule_id": "formal_workflow_boundary",
        "strategy_id": strategy_id,
        "market_context": "paper, simulated, daily brief, watchlist, live",
        "research_state": state,
        "evidence": f"admission_action={admission_action}",
        "allowed_research_action": "Use the role card for methodology and next research planning.",
        "blocked_action": "Do not convert research-only or rejected evidence into user-facing trading signals.",
        "next_step": next_step,
    }


def _write_markdown(
    path: Path,
    *,
    strategy_id: str,
    matrix: pd.DataFrame,
    review_row: pd.Series,
    rules: pd.DataFrame,
    input_paths: dict[str, Path | None],
) -> None:
    admission_action = _safe_str(review_row.get("admission_action"), "unknown")
    lines = [
        f"# Strategy Role Card - {strategy_id}",
        "",
        "This is a research-only governance report. It does not create buy, sell, paper-review, simulated-account, daily-brief, watchlist, or live trading signals.",
        "",
        "## Metadata",
        "",
        f"- Generated at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Strategy: `{strategy_id}`",
        f"- Admission action: `{admission_action}`",
        "",
        "## Input Artifacts",
        "",
        _md_table(
            ["Input", "Path"],
            [[name, _safe_str(path_value)] for name, path_value in input_paths.items() if path_value is not None],
        ),
        "",
        "## Window Summary",
        "",
        _window_table(matrix),
        "",
        "## Constraint Review",
        "",
        _md_table(
            ["Field", "Value"],
            [
                ["admission_action", admission_action],
                ["window_pass", f"{_safe_int(review_row.get('window_pass_count'))}/{_safe_int(review_row.get('window_count'))}"],
                ["overfit_risk", _safe_str(review_row.get("overfit_risk_level"), "unknown")],
                ["supports_paper_trade", _safe_str(review_row.get("supports_paper_trade"), "False")],
                ["main_reasons", _safe_str(review_row.get("main_reasons"), "")],
            ],
        ),
        "",
        "## Role Rules",
        "",
        _rule_table(rules),
        "",
        "## Guardrails",
        "",
        "- Research-fit, downgrade, and stop rules are not trading enablement rules.",
        "- Diagnostic market-context labels are not admission gates and not trading filters.",
        "- Missing benchmark constituent or style data must be stated when the claim depends on it.",
        "- Formal workflows must return `no eligible strategy` unless admission and paper-review eligibility support promotion.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _window_table(matrix: pd.DataFrame) -> str:
    rows = []
    for _, row in matrix.iterrows():
        rows.append(
            [
                _safe_str(row.get("walk_forward_preset")),
                _fmt_pct(row.get("annualized_return_mean")),
                _fmt(row.get("sharpe_mean")),
                _fmt_pct(row.get("max_drawdown_worst")),
                _fmt(row.get("turnover_annual_mean")),
                _fmt_ratio(row.get("positive_fold_ratio")),
                _fmt_ratio(row.get("positive_excess_fold_ratio")),
                _safe_str(row.get("is_window_pass")),
            ]
        )
    return _md_table(
        ["Preset", "Ann", "Sharpe", "Worst MDD", "Turnover", "Positive Fold", "Positive Excess", "Pass"],
        rows,
    )


def _rule_table(rules: pd.DataFrame) -> str:
    if rules.empty:
        return "No role rules generated."
    return _md_table(
        ["Rule", "Context", "State", "Evidence", "Blocked Action", "Next Step"],
        [
            [
                _safe_str(row.get("rule_id")),
                _safe_str(row.get("market_context")),
                _safe_str(row.get("research_state")),
                _safe_str(row.get("evidence")),
                _safe_str(row.get("blocked_action")),
                _safe_str(row.get("next_step")),
            ]
            for _, row in rules.iterrows()
        ],
    )


def _deduplicate_rules(rules: pd.DataFrame) -> pd.DataFrame:
    if rules.empty:
        return rules
    return rules.drop_duplicates(["rule_id", "strategy_id"], keep="first").reset_index(drop=True)


def _holdings_summary_for_label(holdings_summary: pd.DataFrame, label: str) -> str:
    if holdings_summary.empty or "market_context_label" not in holdings_summary.columns:
        return ""
    data = holdings_summary[holdings_summary["market_context_label"].astype(str) == label]
    if data.empty:
        return ""
    row = data.iloc[0]
    return (
        f"avg_live_exposure={_fmt_pct(row.get('avg_live_exposure'))}; "
        f"avg_live_holding_count={_fmt(row.get('avg_live_holding_count'))}; "
        f"avg_top_industry_share={_fmt_pct(row.get('avg_live_top_industry_share'))}"
    )


def _overlay_all_row(overlay: pd.DataFrame) -> pd.Series:
    if "scope" in overlay.columns:
        all_rows = overlay[overlay["scope"].astype(str) == "all"]
        if not all_rows.empty:
            return all_rows.iloc[0]
    if "walk_forward_preset" in overlay.columns:
        all_rows = overlay[overlay["walk_forward_preset"].astype(str).str.upper() == "ALL"]
        if not all_rows.empty:
            return all_rows.iloc[0]
    return overlay.iloc[0]


def _read_required_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    return pd.read_csv(path)


def _read_optional_csv(path: Path | None, label: str) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()
    return _read_required_csv(path, label)


def _require_columns(df: pd.DataFrame, columns: list[str], path: Path) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"{path} missing required columns: {missing}")


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(_safe_str(cell).replace("|", "\\|") for cell in row) + " |")
    return "\n".join(out)


def _format_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) if counts else "none"


def _mean(df: pd.DataFrame, column: str) -> float | None:
    if column not in df.columns:
        return None
    values = pd.to_numeric(df[column], errors="coerce")
    return float(values.mean()) if values.notna().any() else None


def _positive_ratio(df: pd.DataFrame, column: str) -> float | None:
    if column not in df.columns:
        return None
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    return float((values > 0).mean()) if len(values) else None


def _optional_float(value: Any) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _fmt(value: Any) -> str:
    parsed = _optional_float(value)
    return "n/a" if parsed is None else f"{parsed:.4f}"


def _fmt_pct(value: Any) -> str:
    parsed = _optional_float(value)
    return "n/a" if parsed is None else f"{parsed * 100:.2f}%"


def _fmt_ratio(value: Any) -> str:
    parsed = _optional_float(value)
    return "n/a" if parsed is None else f"{parsed:.2f}"


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = _safe_str(value).strip().lower()
    return text in {"true", "1", "yes", "y"}


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
