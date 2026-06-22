from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from phase0.strategy_admission import (
    _industry_concentration_window_count,
    _parameter_unstable_window_count,
    _price_adjustment_fail_window_count,
    _resolve_admission_gate,
)


SEVERITY_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
SEVERITY_LABELS = {"none": "无", "low": "低", "medium": "中", "high": "高", "critical": "严重"}


@dataclass(frozen=True)
class StrategyFailureAttributionResult:
    csv_path: Path
    md_path: Path
    rows: int
    strategies: int


def run_strategy_failure_attribution(
    *,
    config: dict[str, Any] | None,
    root: Path,
    admission_dir: Path | None = None,
    folds_path: Path | None = None,
    matrix_path: Path | None = None,
    constraint_path: Path | None = None,
    overfit_path: Path | None = None,
    output_dir: Path | None = None,
) -> StrategyFailureAttributionResult:
    """Attribute failed admission decisions from existing CSV artifacts only."""
    admission_dir = admission_dir or root / "reports" / "strategy_admission"
    output_dir = output_dir or admission_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    folds_path = folds_path or admission_dir / "strategy_admission_candidate_folds.csv"
    matrix_path = matrix_path or admission_dir / "strategy_admission_window_matrix.csv"
    constraint_path = constraint_path or admission_dir / "strategy_admission_constraint_review.csv"
    overfit_path = overfit_path or admission_dir / "overfit_diagnostic" / "strategy_overfit_diagnostic.csv"

    folds = _read_required_csv(folds_path, "strategy_admission_candidate_folds.csv")
    matrix = _read_required_csv(matrix_path, "strategy_admission_window_matrix.csv")
    review = _read_required_csv(constraint_path, "strategy_admission_constraint_review.csv")
    overfit = _read_required_csv(overfit_path, "strategy_overfit_diagnostic.csv")
    _require_columns(matrix, ["strategy_id", "walk_forward_preset"], matrix_path)
    _require_columns(review, ["strategy_id", "admission_action"], constraint_path)
    _require_columns(overfit, ["strategy_id", "overfit_risk_level"], overfit_path)

    phase_cfg = config or {}
    gate_cfg = _resolve_admission_gate(phase_cfg.get("walk_forward", {}) if phase_cfg else {})
    review_by_strategy = {str(row["strategy_id"]): row for _, row in review.iterrows()}
    overfit_by_strategy = {str(row["strategy_id"]): row for _, row in overfit.iterrows()}

    rows: list[dict[str, Any]] = []
    for _, window in matrix.iterrows():
        strategy_id = _safe_str(window.get("strategy_id"))
        preset = _safe_str(window.get("walk_forward_preset"))
        strategy_review = review_by_strategy.get(strategy_id, pd.Series(dtype=object))
        overfit_row = overfit_by_strategy.get(strategy_id, pd.Series(dtype=object))
        fold_group = _fold_group(folds, strategy_id, preset)
        attribution = _attribute_window(
            window=window,
            strategy_review=strategy_review,
            overfit_row=overfit_row,
            fold_group=fold_group,
            gate_cfg=gate_cfg,
        )
        rows.append(
            {
                "strategy_id": strategy_id,
                "walk_forward_preset": preset,
                "admission_action": _safe_str(strategy_review.get("admission_action", "")),
                "window_status": _safe_str(window.get("status", "")),
                "severity": attribution["severity"],
                "primary_failure_dimension": attribution["primary_failure_dimension"],
                "return_failure": attribution["return_failure"],
                "execution_failure": attribution["execution_failure"],
                "construction_failure": attribution["construction_failure"],
                "factor_failure": attribution["factor_failure"],
                "parameter_failure": attribution["parameter_failure"],
                "regime_failure": attribution["regime_failure"],
                "data_failure": attribution["data_failure"],
                "evidence": attribution["evidence"],
                "recommended_next_action": attribution["recommended_next_action"],
                "annualized_return_mean": _safe_float(window.get("annualized_return_mean")),
                "sharpe_mean": _safe_float(window.get("sharpe_mean")),
                "max_drawdown_worst": _safe_float(window.get("max_drawdown_worst")),
                "positive_fold_ratio": _safe_float(window.get("positive_fold_ratio")),
                "turnover_annual_mean": _safe_float(window.get("turnover_annual_mean")),
                "parameter_unique_count": _safe_int(window.get("parameter_unique_count")),
                "overfit_risk_level": _safe_str(overfit_row.get("overfit_risk_level", "unknown")),
                "overfit_score": _safe_int(overfit_row.get("overfit_score", 0)),
                "last_fold_lift_risk": _safe_bool(overfit_row.get("last_fold_lift_risk", False)),
                "main_reasons": _safe_str(strategy_review.get("main_reasons", "")),
            }
        )

    attribution_df = pd.DataFrame(rows)
    csv_path = output_dir / "strategy_failure_attribution.csv"
    md_path = output_dir / "strategy_failure_attribution.md"
    attribution_df.to_csv(csv_path, index=False)
    _write_markdown(
        md_path,
        attribution_df,
        input_paths={
            "folds": folds_path,
            "window_matrix": matrix_path,
            "constraint_review": constraint_path,
            "overfit": overfit_path,
        },
    )
    return StrategyFailureAttributionResult(
        csv_path=csv_path,
        md_path=md_path,
        rows=len(attribution_df),
        strategies=int(attribution_df["strategy_id"].nunique()) if "strategy_id" in attribution_df.columns else 0,
    )


def _attribute_window(
    *,
    window: pd.Series,
    strategy_review: pd.Series,
    overfit_row: pd.Series,
    fold_group: pd.DataFrame,
    gate_cfg: dict[str, Any],
) -> dict[str, str]:
    dimension_evidence: dict[str, list[str]] = {
        "return_failure": [],
        "execution_failure": [],
        "construction_failure": [],
        "factor_failure": [],
        "parameter_failure": [],
        "regime_failure": [],
        "data_failure": [],
    }
    dimension_severity: dict[str, str] = {key: "none" for key in dimension_evidence}

    _attribute_return(window, gate_cfg, dimension_evidence, dimension_severity)
    _attribute_execution(window, fold_group, dimension_evidence, dimension_severity)
    _attribute_construction(window, fold_group, dimension_evidence, dimension_severity)
    _attribute_factor(window, dimension_evidence, dimension_severity)
    _attribute_parameter(window, dimension_evidence, dimension_severity)
    _attribute_regime(overfit_row, window, dimension_evidence, dimension_severity)
    _attribute_data(window, strategy_review, gate_cfg, dimension_evidence, dimension_severity)

    primary = _primary_dimension(dimension_severity)
    severity = dimension_severity[primary] if primary else "none"
    evidence_parts: list[str] = []
    for dimension in _dimension_order():
        if dimension_evidence[dimension]:
            evidence_parts.append(f"{_dimension_label(dimension)}：" + "；".join(dimension_evidence[dimension]))
    if not evidence_parts:
        evidence_parts.append("未发现高优先级失败归因；如 admission_action 仍非准入，需要复核 constraint review 的 main_reasons。")

    action = _recommended_next_action(
        primary_dimension=primary,
        admission_action=_safe_str(strategy_review.get("admission_action", "")),
        severity=severity,
    )
    out = {dimension: dimension_severity[dimension] for dimension in _dimension_order()}
    out.update(
        {
            "severity": severity,
            "primary_failure_dimension": primary or "none",
            "evidence": " | ".join(evidence_parts),
            "recommended_next_action": action,
        }
    )
    return out


def _attribute_return(
    window: pd.Series,
    gate_cfg: dict[str, Any],
    evidence: dict[str, list[str]],
    severity: dict[str, str],
) -> None:
    failed: list[str] = []
    if not _safe_bool(window.get("is_return_pass", True)):
        failed.append(
            f"年化收益均值 {_safe_float(window.get('annualized_return_mean')):.4f} 未通过 gate "
            f"{float(gate_cfg['annualized_return_min']):.4f}"
        )
    if not _safe_bool(window.get("is_sharpe_pass", True)):
        failed.append(
            f"Sharpe 均值 {_safe_float(window.get('sharpe_mean')):.4f} 未通过 gate "
            f"{float(gate_cfg['sharpe_min']):.4f}"
        )
    if not _safe_bool(window.get("is_drawdown_pass", True)):
        failed.append(
            f"最大回撤最差值 {_safe_float(window.get('max_drawdown_worst')):.4f} 未通过 gate "
            f"{float(gate_cfg['max_drawdown_min']):.4f}"
        )
    if not _safe_bool(window.get("is_positive_fold_pass", True)):
        failed.append(
            f"正收益折比例 {_safe_float(window.get('positive_fold_ratio')):.2%} 未通过 gate "
            f"{float(gate_cfg['positive_fold_ratio_min']):.2%}"
        )
    if not failed:
        return
    evidence["return_failure"].extend(failed)
    severity["return_failure"] = "high" if len(failed) >= 2 else "medium"


def _attribute_execution(
    window: pd.Series,
    fold_group: pd.DataFrame,
    evidence: dict[str, list[str]],
    severity: dict[str, str],
) -> None:
    if not _safe_bool(window.get("is_turnover_pass", True)):
        evidence["execution_failure"].append(
            f"换手未通过 admission gate：mean={_safe_float(window.get('turnover_annual_mean')):.2f}, "
            f"max={_safe_float(window.get('turnover_annual_max')):.2f}"
        )
        severity["execution_failure"] = "high"
    account_status = _safe_str(window.get("account_execution_status", ""))
    if account_status and account_status not in {"not_enabled", "not_available"} and "fail" in account_status.lower():
        evidence["execution_failure"].append(f"账户执行诊断状态为 {account_status}")
        severity["execution_failure"] = _max_severity(severity["execution_failure"], "high")
    if _safe_float(window.get("account_unfilled_or_partial_order_ratio_mean")) > 0:
        evidence["execution_failure"].append(
            f"账户未完全成交订单占比均值 {_safe_float(window.get('account_unfilled_or_partial_order_ratio_mean')):.2%}"
        )
        severity["execution_failure"] = _max_severity(severity["execution_failure"], "medium")
    if not fold_group.empty and "trades" in fold_group.columns:
        trades = pd.to_numeric(fold_group["trades"], errors="coerce")
        if trades.notna().any() and float(trades.sum()) == 0.0:
            evidence["execution_failure"].append("fold 明细显示交易次数为 0，收益结论可能缺少可执行性。")
            severity["execution_failure"] = _max_severity(severity["execution_failure"], "medium")


def _attribute_construction(
    window: pd.Series,
    fold_group: pd.DataFrame,
    evidence: dict[str, list[str]],
    severity: dict[str, str],
) -> None:
    single_window = pd.DataFrame([window.to_dict()])
    if _industry_concentration_window_count(single_window) > 0:
        evidence["construction_failure"].append(
            "行业集中度触发 admission 审计阈值："
            f"top1_mean={_safe_float(window.get('top_industry_avg_share_mean')):.2%}, "
            f"top3_mean={_safe_float(window.get('top3_industries_avg_share_mean')):.2%}, "
            f"violation_days={_safe_int(window.get('industry_violation_days_total'))}"
        )
        severity["construction_failure"] = "high"
    if not fold_group.empty:
        avg_live = _mean_numeric(fold_group, "avg_live_holdings")
        universe_count = _mean_numeric(fold_group, "universe_symbol_count")
        if avg_live is not None and avg_live < 5:
            evidence["construction_failure"].append(f"归因层观察到平均实盘持仓数偏低：{avg_live:.2f}")
            severity["construction_failure"] = _max_severity(severity["construction_failure"], "medium")
        if universe_count is not None and universe_count < 30:
            evidence["construction_failure"].append(f"归因层观察到候选股票池偏窄：mean_universe={universe_count:.1f}")
            severity["construction_failure"] = _max_severity(severity["construction_failure"], "medium")


def _attribute_factor(
    window: pd.Series,
    evidence: dict[str, list[str]],
    severity: dict[str, str],
) -> None:
    status = _safe_str(window.get("financial_diagnostic_status", "not_available"))
    if status in {"not_available", "not_enabled", ""}:
        return
    quality_lift = _safe_float(window.get("selected_quality_score_lift_mean"))
    if quality_lift > 0 and (
        not _safe_bool(window.get("is_return_pass", True)) or not _safe_bool(window.get("is_sharpe_pass", True))
    ):
        evidence["factor_failure"].append(
            f"财务 PIT 可用且选股质量分提升 {quality_lift:.3f}，但收益/Sharpe 未转化为 gate 通过。"
        )
        severity["factor_failure"] = "medium"
    if _safe_float(window.get("financial_missing_blocked_ratio_mean")) > 0:
        evidence["factor_failure"].append(
            f"财务缺失拦截比例 {_safe_float(window.get('financial_missing_blocked_ratio_mean')):.2%}"
        )
        severity["factor_failure"] = _max_severity(severity["factor_failure"], "medium")


def _attribute_parameter(
    window: pd.Series,
    evidence: dict[str, list[str]],
    severity: dict[str, str],
) -> None:
    single_window = pd.DataFrame([window.to_dict()])
    if _parameter_unstable_window_count(single_window) <= 0:
        return
    evidence["parameter_failure"].append(
        f"参数组合数量 {_safe_int(window.get('parameter_unique_count'))} 相对 fold_count="
        f"{_safe_int(window.get('fold_count'))} 偏高，触发 admission 参数稳定性规则。"
    )
    severity["parameter_failure"] = "high"


def _attribute_regime(
    overfit_row: pd.Series,
    window: pd.Series,
    evidence: dict[str, list[str]],
    severity: dict[str, str],
) -> None:
    if _safe_bool(overfit_row.get("last_fold_lift_risk", False)):
        preset = _safe_str(overfit_row.get("last_fold_lift_preset", ""))
        if not preset or preset == _safe_str(window.get("walk_forward_preset")):
            evidence["regime_failure"].append(
                "最后一折显著拉高："
                f"last={_safe_float(overfit_row.get('last_fold_annualized_return')):.4f}, "
                f"prior_mean={_safe_float(overfit_row.get('prior_fold_annualized_return_mean')):.4f}, "
                f"lift={_safe_float(overfit_row.get('last_fold_lift')):.4f}"
            )
            severity["regime_failure"] = "high"
        else:
            evidence["regime_failure"].append(f"策略级 overfit 诊断显示 {preset} 存在最后一折拉高风险。")
            severity["regime_failure"] = "medium"
    overfit_level = _safe_str(overfit_row.get("overfit_risk_level", "unknown"))
    if overfit_level in {"high", "critical"}:
        evidence["regime_failure"].append(f"策略级 overfit_risk_level={overfit_level}")
        severity["regime_failure"] = _max_severity(severity["regime_failure"], "high")


def _attribute_data(
    window: pd.Series,
    strategy_review: pd.Series,
    gate_cfg: dict[str, Any],
    evidence: dict[str, list[str]],
    severity: dict[str, str],
) -> None:
    if _safe_str(window.get("status")) != "ok":
        evidence["data_failure"].append(f"窗口无有效 fold：{_safe_str(window.get('failure_reason', 'no valid folds'))}")
        severity["data_failure"] = "high"
    single_window = pd.DataFrame([window.to_dict()])
    if bool(gate_cfg.get("require_qfq_asof", True)) and _price_adjustment_fail_window_count(single_window) > 0:
        evidence["data_failure"].append(f"价格口径状态为 {_safe_str(window.get('price_adjustment_status', 'unknown'))}，未满足 qfq_asof 要求。")
        severity["data_failure"] = _max_severity(severity["data_failure"], "critical")
    industry_status = _safe_str(window.get("industry_diagnostic_status", "not_available"))
    if bool(gate_cfg.get("require_industry_concentration_check", True)) and industry_status in {"not_enabled", "not_available", ""}:
        evidence["data_failure"].append(f"行业诊断缺失：{industry_status or 'empty'}")
        severity["data_failure"] = _max_severity(severity["data_failure"], "high")
    financial_status = _safe_str(window.get("financial_diagnostic_status", "not_available"))
    if bool(gate_cfg.get("require_factor_diagnostics", True)) and financial_status in {"not_available", ""}:
        evidence["data_failure"].append(f"财务/因子诊断缺失：{financial_status or 'empty'}")
        severity["data_failure"] = _max_severity(severity["data_failure"], "high")
    missing_windows = _safe_int(strategy_review.get("missing_window_count", 0))
    if missing_windows:
        evidence["data_failure"].append(f"策略级 constraint review 显示 missing_window_count={missing_windows}")
        severity["data_failure"] = _max_severity(severity["data_failure"], "high")


def _write_markdown(path: Path, attribution: pd.DataFrame, *, input_paths: dict[str, Path]) -> None:
    lines = [
        "# 策略失败归因诊断报告",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## 输入",
        "",
        "- 本报告只读取已有 admission / overfit CSV，不重新回测，不修改 admission 产物。",
    ]
    for label, input_path in input_paths.items():
        lines.append(f"- {label}: `{input_path}`")
    lines.extend(
        [
            "",
            "## 汇总",
            "",
            _md_table(
                [
                    "strategy_id",
                    "preset",
                    "action",
                    "severity",
                    "primary_failure",
                    "return",
                    "execution",
                    "construction",
                    "factor",
                    "parameter",
                    "regime",
                    "data",
                ],
                [
                    [
                        _safe_str(row["strategy_id"]),
                        _safe_str(row["walk_forward_preset"]),
                        _safe_str(row["admission_action"]),
                        SEVERITY_LABELS.get(_safe_str(row["severity"]), _safe_str(row["severity"])),
                        _dimension_label(_safe_str(row["primary_failure_dimension"])),
                        _safe_str(row["return_failure"]),
                        _safe_str(row["execution_failure"]),
                        _safe_str(row["construction_failure"]),
                        _safe_str(row["factor_failure"]),
                        _safe_str(row["parameter_failure"]),
                        _safe_str(row["regime_failure"]),
                        _safe_str(row["data_failure"]),
                    ]
                    for _, row in attribution.iterrows()
                ],
            ),
            "",
            "## 策略级建议",
            "",
        ]
    )
    for strategy_id, group in attribution.groupby("strategy_id", dropna=False):
        ordered = group.sort_values("severity", key=lambda col: col.map(lambda item: SEVERITY_RANK.get(str(item), 0)), ascending=False)
        top = ordered.iloc[0]
        lines.extend(
            [
                f"### {strategy_id}",
                "",
                f"- Admission action: `{_safe_str(top['admission_action'])}`",
                f"- 主要失败原因：{_dimension_label(_safe_str(top['primary_failure_dimension']))}（severity={_safe_str(top['severity'])}）",
                f"- 证据：{_safe_str(top['evidence'])}",
                f"- 下一步建议：{_safe_str(top['recommended_next_action'])}",
                "",
            ]
        )
        if len(group) > 1:
            lines.append("窗口差异：")
            for _, row in group.iterrows():
                lines.append(
                    f"- `{_safe_str(row['walk_forward_preset'])}`: "
                    f"{_dimension_label(_safe_str(row['primary_failure_dimension']))}, "
                    f"severity={_safe_str(row['severity'])}, "
                    f"ann={_safe_float(row['annualized_return_mean']):.4f}, "
                    f"sharpe={_safe_float(row['sharpe_mean']):.4f}, "
                    f"positive_fold_ratio={_safe_float(row['positive_fold_ratio']):.2%}"
                )
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _recommended_next_action(*, primary_dimension: str, admission_action: str, severity: str) -> str:
    prefix = {
        "reject": "当前 spec 维持 reject；",
        "retest": "先 retest 前修正主因；",
        "research_only": "降级 research-only 并收窄验证目标；",
        "eligible_for_paper_review": "不阻断模拟审查；",
    }.get(admission_action, "")
    actions = {
        "return_failure": "优先重审 alpha 假设和收益来源，不要先做参数微调。",
        "execution_failure": "先降低换手和成交暴露，补账户执行成本复核后再比较收益。",
        "construction_failure": "复核行业/持仓/股票池构造，先确认暴露是否由组合设计驱动。",
        "factor_failure": "回到因子有效性和 PIT 覆盖审计，确认质量暴露为何未转化为收益。",
        "parameter_failure": "收窄参数空间或固定稳健参数，再用同一 admission 口径复测。",
        "regime_failure": "按市场阶段切片复核，避免把最后一折行情当作稳定 alpha。",
        "data_failure": "先补齐价格口径和必要诊断产物，再重新生成 admission 产物。",
        "none": "保留现有 admission 结论，人工复核 main_reasons 是否还有未结构化原因。",
    }
    if severity == "critical" and primary_dimension != "data_failure":
        prefix += "不要进入模拟交易；"
    return prefix + actions.get(primary_dimension, actions["none"])


def _primary_dimension(severity: dict[str, str]) -> str:
    priority = {
        "data_failure": 0,
        "return_failure": 1,
        "parameter_failure": 2,
        "construction_failure": 3,
        "regime_failure": 4,
        "execution_failure": 5,
        "factor_failure": 6,
    }
    ranked = sorted(
        severity.items(),
        key=lambda item: (SEVERITY_RANK.get(item[1], 0), -priority.get(item[0], 99)),
        reverse=True,
    )
    if not ranked or SEVERITY_RANK.get(ranked[0][1], 0) == 0:
        return "none"
    return ranked[0][0]


def _dimension_order() -> list[str]:
    return [
        "return_failure",
        "execution_failure",
        "construction_failure",
        "factor_failure",
        "parameter_failure",
        "regime_failure",
        "data_failure",
    ]


def _dimension_label(dimension: str) -> str:
    return {
        "return_failure": "收益失败",
        "execution_failure": "执行失败",
        "construction_failure": "组合构造失败",
        "factor_failure": "因子失败",
        "parameter_failure": "参数失败",
        "regime_failure": "市场阶段失败",
        "data_failure": "数据质量失败",
        "none": "未归因",
    }.get(dimension, dimension)


def _fold_group(folds: pd.DataFrame, strategy_id: str, preset: str) -> pd.DataFrame:
    if folds.empty or "walk_forward_preset" not in folds.columns:
        return pd.DataFrame()
    strategy_col = "strategy_id" if "strategy_id" in folds.columns else "candidate" if "candidate" in folds.columns else ""
    if not strategy_col:
        return pd.DataFrame()
    return folds[(folds[strategy_col].astype(str) == strategy_id) & (folds["walk_forward_preset"].astype(str) == preset)]


def _read_required_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"missing required {label}: {path}")
    return pd.read_csv(path)


def _require_columns(df: pd.DataFrame, columns: list[str], path: Path) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"{path} missing required columns: {missing}")


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |")
    return "\n".join(out)


def _mean_numeric(df: pd.DataFrame, column: str) -> float | None:
    if column not in df.columns:
        return None
    values = pd.to_numeric(df[column], errors="coerce")
    return float(values.mean()) if values.notna().any() else None


def _max_severity(left: str, right: str) -> str:
    return left if SEVERITY_RANK.get(left, 0) >= SEVERITY_RANK.get(right, 0) else right


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or pd.isna(value):
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _safe_float(value: Any, default: float = 0.0) -> float:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return default if pd.isna(parsed) else float(parsed)


def _safe_int(value: Any, default: int = 0) -> int:
    return int(round(_safe_float(value, float(default))))


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
