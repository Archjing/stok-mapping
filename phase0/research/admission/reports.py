from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _write_report(
    path: Path,
    matrix: pd.DataFrame,
    review: pd.DataFrame,
    presets: list[str],
    strategies: list[str],
    *,
    root: Path,
    strategy_scope: dict[str, Any],
    gate_cfg: dict[str, Any],
    diagnostics_suites: list[str],
) -> None:
    factor_evidence = _load_quality_factor_evidence(root)
    lines = [
        "# Strategy Admission Report",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Scope",
        "",
        f"- Presets: `{', '.join(presets)}`",
        f"- Strategy scope source: `{_safe_str(strategy_scope.get('source', ''))}`",
        f"- Strategy set: `{_safe_str(strategy_scope.get('strategy_set', ''))}`",
        f"- Strategies: `{', '.join(strategies)}`",
        f"- Diagnostics suites: `{', '.join(diagnostics_suites) if diagnostics_suites else 'none'}`",
        "",
        "## Global Admission Gate",
        "",
        _md_table(
            ["gate", "value"],
            [[str(key), str(value)] for key, value in gate_cfg.items()],
        ),
        "",
        "## Constraint Review",
        "",
        _md_table(
            [
                "strategy_id",
                "action",
                "window_pass",
                "turnover_fail",
                "param_unstable",
                "industry_missing",
                "industry_conc",
                "factor_missing",
                "price_fail",
                "paper_trade",
                "overfit",
                "reasons",
            ],
            [
                [
                    str(row["strategy_id"]),
                    str(row["admission_action"]),
                    f"{_safe_int(row['window_pass_count'])}/{_safe_int(row['window_count'])}",
                    str(_safe_int(row["turnover_fail_count"])),
                    str(_safe_int(row["parameter_unstable_window_count"])),
                    str(_safe_int(row.get("industry_diagnostic_missing_window_count", 0))),
                    str(_safe_int(row.get("industry_concentration_window_count", 0))),
                    str(_safe_int(row.get("factor_diagnostic_missing_window_count", 0))),
                    str(_safe_int(row.get("price_adjustment_fail_window_count", 0))),
                    str(bool(row.get("supports_paper_trade", True))),
                    str(row["overfit_risk_level"]),
                    str(row["main_reasons"]),
                ]
                for _, row in review.iterrows()
            ],
        ),
        "",
        "## Window Matrix",
        "",
        _md_table(
            [
                "strategy_id",
                "preset",
                "status",
                "folds",
                "window",
                "expected",
                "actual",
                "warning",
                "price_status",
                "ann",
                "sharpe",
                "mdd",
                "turnover",
                "industry_status",
                "top1_ind",
                "top3_ind",
                "account_status",
                "acct_ann",
                "acct_sharpe",
                "acct_orders",
                "pass",
            ],
            [
                [
                    str(row["strategy_id"]),
                    _safe_str(row["walk_forward_preset"]),
                    _safe_str(row["status"]),
                    str(_safe_int(row["fold_count"])),
                    f"{_safe_str(row.get('walk_forward_start_date', ''))}~{_safe_str(row.get('walk_forward_end_date', ''))}",
                    _safe_str(row.get("walk_forward_expected_folds", "")),
                    _safe_str(row.get("walk_forward_actual_folds", "")),
                    _safe_str(row.get("walk_forward_fold_generation_warning", "")),
                    _safe_str(row.get("price_adjustment_status", "")),
                    f"{_safe_float(row['annualized_return_mean']):.4f}",
                    f"{_safe_float(row['sharpe_mean']):.4f}",
                    f"{_safe_float(row['max_drawdown_worst']):.4f}",
                    f"{_safe_float(row['turnover_annual_mean']):.2f}",
                    _safe_str(row.get("industry_diagnostic_status", "not_enabled")),
                    _format_status_float(row, "top_industry_avg_share_mean", "industry_diagnostic_status"),
                    _format_status_float(row, "top3_industries_avg_share_mean", "industry_diagnostic_status"),
                    _safe_str(row.get("account_execution_status", "not_enabled")),
                    _format_status_float(row, "account_annualized_return_mean", "account_execution_status"),
                    _format_status_float(row, "account_sharpe_mean", "account_execution_status"),
                    _format_status_int(row, "account_executed_order_count_total", "account_execution_status"),
                    str(bool(row["is_window_pass"])),
                ]
                for _, row in matrix.iterrows()
            ],
        ),
        "",
        "## Benchmark / Excess Diagnostics",
        "",
        "Supplemental only: these relative benchmark fields explain regime-adjusted behavior and do not change `is_window_pass` or `admission_action` in this run.",
        "",
        _md_table(
            [
                "strategy_id",
                "preset",
                "benchmark_status",
                "bench_folds",
                "bench_ann",
                "excess_ann",
                "excess_min",
                "pos_abs",
                "pos_excess",
                "neg_abs",
                "neg_pos_excess",
                "neg_neg_excess",
                "neg_bench_na",
            ],
            [
                [
                    str(row["strategy_id"]),
                    str(row["walk_forward_preset"]),
                    _safe_str(row.get("benchmark_status", "not_available")),
                    str(_safe_int(row.get("benchmark_available_fold_count", 0))),
                    _format_benchmark_float(row, "benchmark_annualized_return_mean", precision=4),
                    _format_benchmark_float(row, "excess_annualized_return_mean", precision=4),
                    _format_benchmark_float(row, "excess_annualized_return_min", precision=4),
                    f"{_safe_float(row.get('positive_fold_ratio', 0.0)):.2f}",
                    _format_benchmark_float(row, "positive_excess_fold_ratio", precision=2),
                    str(_safe_int(row.get("negative_absolute_fold_count", 0))),
                    str(_safe_int(row.get("negative_absolute_positive_excess_count", 0))),
                    str(_safe_int(row.get("negative_absolute_negative_excess_count", 0))),
                    str(_safe_int(row.get("negative_absolute_benchmark_unavailable_count", 0))),
                ]
                for _, row in matrix.iterrows()
            ],
        ),
        "",
        "## Strategy Quality Diagnostics",
        "",
        _md_table(
            [
                "strategy_id",
                "preset",
                "status",
                "pit_ann",
                "field_cov",
                "selected_field_cov",
                "missing_blocked",
                "quality_lift",
                "cash_flow_evidence",
                "failure_attribution",
            ],
            [
                [
                    str(row["strategy_id"]),
                    str(row["walk_forward_preset"]),
                    _safe_str(row.get("financial_diagnostic_status", "not_available")),
                    _format_status_float(row, "financial_pit_announce_coverage_mean", "financial_diagnostic_status"),
                    _format_status_float(row, "financial_field_coverage_mean", "financial_diagnostic_status"),
                    _format_status_float(row, "selected_financial_field_coverage_mean", "financial_diagnostic_status"),
                    _format_status_float(row, "financial_missing_blocked_ratio_mean", "financial_diagnostic_status"),
                    _format_status_float(row, "selected_quality_score_lift_mean", "financial_diagnostic_status", precision=3),
                    _quality_factor_evidence_label(factor_evidence),
                    _quality_failure_attribution(row, factor_evidence),
                ]
                for _, row in matrix.iterrows()
            ],
        ),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _admission_command_hint(
    *,
    config_arg: str = "config.yaml",
    presets: list[str],
    strategy_scope: dict[str, Any],
    output_dir: Path | None,
) -> str:
    parts = [
        "phase0.cli",
        "strategy-admission",
        f"--config {config_arg}",
        "--presets " + " ".join(presets),
    ]
    strategy_set = _safe_str(strategy_scope.get("strategy_set", ""))
    strategies = [str(item) for item in strategy_scope.get("strategies", [])]
    if strategy_set:
        parts.append(f"--strategy-set {strategy_set}")
    elif strategies:
        parts.append("--strategies " + " ".join(strategies))
    if output_dir is not None:
        parts.append(f"--output-dir {output_dir}")
    return " ".join(parts)


def _config_command_arg(config_path: Path | None, root: Path) -> str:
    if config_path is None:
        return "config.yaml"
    try:
        return config_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return config_path.as_posix()


def _required_artifact_names(
    *,
    output_dir: Path,
    folds_csv: Path,
    matrix_csv: Path,
    constraint_csv: Path,
    report_md: Path,
    overfit_csv: Path,
) -> list[str]:
    artifacts = [folds_csv, matrix_csv, constraint_csv, report_md, overfit_csv]
    names: list[str] = []
    for artifact in artifacts:
        try:
            names.append(artifact.relative_to(output_dir).as_posix())
        except ValueError:
            names.append(artifact.name)
    return names


def _write_governance_report(
    path: Path,
    matrix: pd.DataFrame,
    review: pd.DataFrame,
    presets: list[str],
    strategies: list[str],
    *,
    strategy_scope: dict[str, Any],
    gate_cfg: dict[str, Any],
    diagnostics_suites: list[str],
    required_artifacts: list[str] | None = None,
    command_hint: str,
) -> None:
    action_counts = _value_counts(review, "admission_action")
    price_counts = _value_counts(matrix, "price_adjustment_status")
    industry_counts = _value_counts(matrix, "industry_diagnostic_status")
    financial_counts = _value_counts(matrix, "financial_diagnostic_status")
    account_counts = _value_counts(matrix, "account_execution_status")
    research_or_reject = (
        review[
            review.get("admission_action", pd.Series(dtype=object)).astype(str).isin(
                {"reject", "retest", "research_only"}
            )
        ]
        if not review.empty and "admission_action" in review.columns
        else pd.DataFrame()
    )

    lines = [
        "# Strategy Admission Governance Report",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Run Context",
        "",
        f"- Command: `{command_hint}`",
        f"- Strategy scope source: `{_safe_str(strategy_scope.get('source', ''))}`",
        f"- Strategy set: `{_safe_str(strategy_scope.get('strategy_set', ''))}`",
        f"- Strategy set description: {_safe_str(strategy_scope.get('description', '')) or 'n/a'}",
        f"- Presets: `{', '.join(presets)}`",
        f"- Strategies: `{', '.join(strategies)}`",
        f"- Diagnostics suites: `{', '.join(diagnostics_suites) if diagnostics_suites else 'none'}`",
        "",
        "## Governance Boundary",
        "",
        f"- Required price口径: `qfq_asof` = `{bool(gate_cfg.get('require_qfq_asof', True))}`",
        f"- Max overfit risk: `{_safe_str(gate_cfg.get('overfit_risk_max', 'medium'))}`",
        "- Agent、compare、admission 报告和 workflow 成功都不等于策略准入通过。",
        "- `reject`、`retest`、`research_only` 不得进入 paper review / 模拟账户 / 日报 / watchlist。",
        "- 只有 `eligible_for_paper_review` 且 qfq_asof、PIT、成本、overfit、行业和因子诊断均满足门禁时，才允许进入下一阶段人工复核。",
        "",
        "## Required Artifacts",
        "",
        *[
            f"- `{artifact}`"
            for artifact in (
                required_artifacts
                or [
                    "strategy_admission_candidate_folds.csv",
                    "strategy_admission_window_matrix.csv",
                    "strategy_admission_constraint_review.csv",
                    "strategy_admission_report.md",
                    "overfit_diagnostic/strategy_overfit_diagnostic.csv",
                ]
            )
        ],
        "",
        "## Summary",
        "",
        f"- Strategy count: `{len(strategies)}`",
        f"- Preset count: `{len(presets)}`",
        f"- Matrix rows: `{len(matrix)}`",
        f"- Action counts: `{_format_count_map(action_counts)}`",
        f"- Price adjustment status: `{_format_count_map(price_counts)}`",
        f"- Industry diagnostic status: `{_format_count_map(industry_counts)}`",
        f"- Financial diagnostic status: `{_format_count_map(financial_counts)}`",
        f"- Account execution status: `{_format_count_map(account_counts)}`",
        "",
        "## Candidate Actions",
        "",
        _md_table(
            ["strategy_id", "action", "window_pass", "reasons"],
            [
                [
                    _safe_str(row.get("strategy_id", "")),
                    _safe_str(row.get("admission_action", "")),
                    f"{_safe_int(row.get('window_pass_count', 0))}/{_safe_int(row.get('window_count', 0))}",
                    _safe_str(row.get("main_reasons", "")),
                ]
                for _, row in review.iterrows()
            ],
        ),
        "",
    ]
    if not research_or_reject.empty:
        lines.extend(
            [
                "## Next Research Actions",
                "",
                "- 对 `reject` / `research_only` 候选先运行或复用 `strategy-failure-attribution`，再决定是否进入 T2.12 组合构造修正。",
                "- 不新增高换手价格行为策略作为绕行路径；优先处理收益、Sharpe、正收益折比例、换手、行业集中、参数稳定性和 overfit risk。",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _value_counts(df: pd.DataFrame, column: str) -> dict[str, int]:
    if df.empty or column not in df.columns:
        return {}
    values = df[column].fillna("not_available").astype(str)
    return {str(key): int(value) for key, value in values.value_counts().sort_index().items()}


def _format_count_map(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _load_quality_factor_evidence(root: Path) -> dict[str, str]:
    paths = [
        root / "reports" / "factor_effectiveness" / "factor_effectiveness.csv",
        root / "reports" / "2026-06-05" / "stok-factor-effectiveness-gated" / "factor_effectiveness.csv",
    ]
    evidence: dict[str, str] = {}
    for path in paths:
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if "factor" not in df.columns or "recommendation" not in df.columns:
            continue
        for _, row in df.iterrows():
            evidence[str(row["factor"])] = str(row["recommendation"])
        if evidence:
            break
    return evidence


def _quality_factor_evidence_label(evidence: dict[str, str]) -> str:
    quality_factors = ["roe", "cash_flow_quality", "profit_growth", "revenue_growth", "low_debt_to_asset"]
    usable = [name for name in quality_factors if evidence.get(name) == "use"]
    observed = [name for name in quality_factors if evidence.get(name) == "observe"]
    if usable:
        return "use:" + ",".join(usable)
    if observed:
        return "observe:" + ",".join(observed)
    if evidence:
        return "none"
    return "not_available"


def _quality_failure_attribution(row: pd.Series, evidence: dict[str, str]) -> str:
    status = _safe_str(row.get("financial_diagnostic_status", "not_available"))
    if status == "not_applicable":
        return "not_applicable"
    if status == "not_available":
        return "diagnostic_missing: financial factor diagnostics not available"
    if _safe_float(row.get("financial_pit_announce_coverage_mean", 0.0)) < 0.95:
        return "data_quality: PIT announce coverage below 95%"
    if _safe_float(row.get("financial_field_coverage_mean", 0.0)) < 0.80:
        return "data_quality: financial field coverage below 80%"
    if _quality_factor_evidence_label(evidence) in {"none", "not_available"}:
        return "factor_invalid: no positive quality subfactor evidence"
    if _safe_float(row.get("selected_quality_score_lift_mean", 0.0)) <= 0:
        return "construction_invalid: selected names do not improve quality score"
    if not bool(row.get("is_return_pass", False)) or not bool(row.get("is_sharpe_pass", False)):
        return "construction_or_regime: quality exposure did not convert to return"
    if not bool(row.get("is_turnover_pass", False)):
        return "construction_invalid: turnover threshold failed"
    return "passed"


def _format_status_float(row: pd.Series, value_col: str, status_col: str, *, precision: int = 2) -> str:
    status = _safe_str(row.get(status_col, ""))
    if status in {"not_enabled", "not_available", "not_applicable"} or status.startswith("mixed:"):
        return "n/a"
    return f"{_safe_float(row.get(value_col, 0.0)):.{precision}f}"


def _format_benchmark_float(row: pd.Series, value_col: str, *, precision: int = 4) -> str:
    parsed = pd.to_numeric(pd.Series([row.get(value_col, np.nan)]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return "n/a"
    return f"{float(parsed):.{precision}f}"


def _format_status_int(row: pd.Series, value_col: str, status_col: str) -> str:
    status = _safe_str(row.get(status_col, ""))
    if status in {"not_enabled", "not_available", "not_applicable"} or status.startswith("mixed:"):
        return "n/a"
    return str(_safe_int(row.get(value_col, 0)))


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |")
    return "\n".join(out)


def _safe_float(value: Any, default: float = 0.0) -> float:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return default if pd.isna(parsed) else float(parsed)


def _safe_int(value: Any, default: int = 0) -> int:
    return int(round(_safe_float(value, float(default))))


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, float) and np.isnan(value):
        return default
    text = str(value)
    return default if text.lower() == "nan" else text


write_report = _write_report
write_governance_report = _write_governance_report
admission_command_hint = _admission_command_hint
config_command_arg = _config_command_arg
required_artifact_names = _required_artifact_names
safe_float = _safe_float
safe_int = _safe_int
safe_str = _safe_str
