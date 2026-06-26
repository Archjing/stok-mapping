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
    fold_csv_path: Path | None = None
    fold_md_path: Path | None = None


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
    fold_attribution_df = _build_fold_attribution(folds, matrix, review, gate_cfg)
    fold_csv_path = output_dir / "strategy_failure_fold_attribution.csv"
    fold_md_path = output_dir / "strategy_failure_fold_attribution.md"
    fold_attribution_df.to_csv(fold_csv_path, index=False)
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
    _write_fold_markdown(
        fold_md_path,
        fold_attribution_df,
        input_paths={
            "folds": folds_path,
            "window_matrix": matrix_path,
            "constraint_review": constraint_path,
        },
    )
    return StrategyFailureAttributionResult(
        csv_path=csv_path,
        md_path=md_path,
        rows=len(attribution_df),
        strategies=int(attribution_df["strategy_id"].nunique()) if "strategy_id" in attribution_df.columns else 0,
        fold_csv_path=fold_csv_path,
        fold_md_path=fold_md_path,
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
    severity = dimension_severity[primary] if primary and primary != "none" else "none"
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


def _build_fold_attribution(
    folds: pd.DataFrame,
    matrix: pd.DataFrame,
    review: pd.DataFrame,
    gate_cfg: dict[str, Any],
) -> pd.DataFrame:
    if folds.empty:
        return pd.DataFrame()
    matrix_by_window = {
        (_safe_str(row.get("strategy_id")), _safe_str(row.get("walk_forward_preset"))): row
        for _, row in matrix.iterrows()
    }
    review_by_strategy = {_safe_str(row.get("strategy_id")): row for _, row in review.iterrows()}
    rows: list[dict[str, Any]] = []
    for _, fold in folds.iterrows():
        strategy_id = _safe_str(fold.get("strategy_id", fold.get("candidate", "")))
        preset = _safe_str(fold.get("walk_forward_preset"))
        window = matrix_by_window.get((strategy_id, preset), pd.Series(dtype=object))
        strategy_review = review_by_strategy.get(strategy_id, pd.Series(dtype=object))
        attribution = _attribute_fold(fold, window, strategy_review, gate_cfg)
        rows.append(
            {
                "strategy_id": strategy_id,
                "walk_forward_preset": preset,
                "fold": _safe_int(fold.get("fold")),
                "valid_start": _safe_str(fold.get("valid_start")),
                "valid_end": _safe_str(fold.get("valid_end")),
                "admission_action": _safe_str(strategy_review.get("admission_action", "")),
                "window_pass": _safe_bool(window.get("is_window_pass", False)),
                "fold_status": _safe_str(fold.get("status", "")),
                "fold_severity": attribution["fold_severity"],
                "primary_fold_failure": attribution["primary_fold_failure"],
                "absolute_return_status": attribution["absolute_return_status"],
                "benchmark_relative_status": attribution["benchmark_relative_status"],
                "risk_adjusted_status": attribution["risk_adjusted_status"],
                "drawdown_status": attribution["drawdown_status"],
                "turnover_status": attribution["turnover_status"],
                "annualized_return": _optional_float(fold.get("annualized_return")),
                "benchmark_annualized_return": _optional_float(fold.get("benchmark_annualized_return")),
                "excess_annualized_return": _optional_float(fold.get("excess_annualized_return")),
                "sharpe": _optional_float(fold.get("sharpe")),
                "max_drawdown": _optional_float(fold.get("max_drawdown")),
                "turnover_annual": _optional_float(fold.get("turnover_annual")),
                "negative_fold_attribution": _safe_str(fold.get("negative_fold_attribution")),
                "selected_params": _safe_str(fold.get("selected_params")),
                "evidence": attribution["evidence"],
                "recommended_next_action": attribution["recommended_next_action"],
            }
        )
    return pd.DataFrame(rows)


def _attribute_fold(
    fold: pd.Series,
    window: pd.Series,
    strategy_review: pd.Series,
    gate_cfg: dict[str, Any],
) -> dict[str, str]:
    ann = _optional_float(fold.get("annualized_return"))
    benchmark_ann = _optional_float(fold.get("benchmark_annualized_return"))
    excess_ann = _optional_float(fold.get("excess_annualized_return"))
    sharpe = _optional_float(fold.get("sharpe"))
    max_drawdown = _optional_float(fold.get("max_drawdown"))
    turnover = _optional_float(fold.get("turnover_annual"))
    status = _safe_str(fold.get("status", "ok")) or "ok"
    benchmark_status = _safe_str(fold.get("benchmark_status", "not_available"))
    negative_attribution = _safe_str(fold.get("negative_fold_attribution"))

    ann_gate = float(gate_cfg.get("annualized_return_min", 0.0))
    sharpe_gate = float(gate_cfg.get("sharpe_min", 0.5))
    drawdown_gate = float(gate_cfg.get("max_drawdown_min", -1.0))
    turnover_gate = float(gate_cfg.get("turnover_annual_max_max", gate_cfg.get("turnover_annual_mean_max", 5.0)))

    evidence: list[str] = []
    absolute_status = "unknown"
    relative_status = "benchmark_unavailable"
    risk_status = "unknown"
    drawdown_status = "unknown"
    turnover_status = "unknown"

    if status != "ok":
        evidence.append(f"fold status={status}: {_safe_str(fold.get('failure_reason', ''))}")
        return _fold_out(
            severity="high",
            primary="data_or_fold_status",
            absolute_status=absolute_status,
            relative_status=relative_status,
            risk_status=risk_status,
            drawdown_status=drawdown_status,
            turnover_status=turnover_status,
            evidence=evidence,
            action="先修复该 fold 的数据/样本问题，再比较策略表现。",
        )

    if ann is not None:
        absolute_status = "positive_absolute" if ann > ann_gate else "negative_or_below_gate_absolute"
        evidence.append(f"ann={ann:.4f} vs gate={ann_gate:.4f}")
    if benchmark_status == "available" and excess_ann is not None:
        relative_status = "positive_excess" if excess_ann > 0 else "negative_excess"
        evidence.append(f"benchmark_ann={benchmark_ann:.4f}" if benchmark_ann is not None else "benchmark_ann=n/a")
        evidence.append(f"excess_ann={excess_ann:.4f}")
    elif benchmark_status:
        evidence.append(f"benchmark_status={benchmark_status}")
    if sharpe is not None:
        risk_status = "sharpe_pass" if sharpe >= sharpe_gate else "sharpe_below_gate"
        evidence.append(f"sharpe={sharpe:.4f} vs gate={sharpe_gate:.4f}")
    if max_drawdown is not None:
        drawdown_status = "drawdown_pass" if max_drawdown >= drawdown_gate else "drawdown_below_gate"
        evidence.append(f"max_drawdown={max_drawdown:.4f} vs gate={drawdown_gate:.4f}")
    if turnover is not None:
        turnover_status = "turnover_pass" if turnover <= turnover_gate else "turnover_above_gate"
        evidence.append(f"turnover={turnover:.2f} vs gate={turnover_gate:.2f}")

    primary = "uncategorized_fold"
    severity = "none"
    action = "保留该 fold 作为诊断样本，不用从单个 fold 反推新规则。"
    if absolute_status == "positive_absolute" and relative_status == "positive_excess":
        primary = "clean_positive_fold"
        action = "fold 绝对收益和相对基准均为正；只作为稳健样本保留。"
    if relative_status == "negative_excess" and absolute_status == "positive_absolute":
        primary = (
            "relative_failure_benchmark_strong"
            if benchmark_ann is not None and benchmark_ann > 0
            else "positive_absolute_but_benchmark_lag"
        )
        severity = "medium"
        action = "优先解释为何绝对赚钱但跑输沪深300；不要用该 fold 直接调选股参数。"
    if absolute_status == "negative_or_below_gate_absolute" and relative_status == "positive_excess":
        primary = "absolute_failure_market_weak_but_outperform"
        severity = "medium"
        action = "该 fold 更像市场下行背景中的相对抗跌，不应单独触发选股参数调整。"
    if absolute_status == "negative_or_below_gate_absolute" and relative_status == "negative_excess":
        primary = "strategy_specific_underperformance"
        severity = "high"
        action = "先复核该 fold 的持仓、行业暴露和信号来源，再考虑策略假设调整。"
    if primary == "uncategorized_fold" and risk_status == "sharpe_below_gate":
        primary = "low_risk_adjusted_return"
        severity = "medium"
        action = "拆解该 fold 的收益波动和回撤簇，确认低 Sharpe 是否来自少数日期。"
    if drawdown_status == "drawdown_below_gate":
        primary = "drawdown_pressure"
        severity = _max_severity(severity, "high")
        action = "优先定位最大回撤发生日期和持仓暴露，再谈风险过滤。"
    if turnover_status == "turnover_above_gate":
        primary = "execution_pressure"
        severity = _max_severity(severity, "high")
        action = "先降低调仓/成交暴露，否则收益改善可能被交易成本吞噬。"
    if "negative_absolute_but_positive_excess" in negative_attribution:
        primary = "absolute_failure_market_weak_but_outperform"
        severity = _max_severity(severity, "medium")
        action = "该 fold 负收益但正超额，适合作为市场状态归因样本，而不是 alpha 失败样本。"
    elif "negative_absolute_and_negative_excess" in negative_attribution:
        primary = "strategy_specific_underperformance"
        severity = _max_severity(severity, "high")
        action = "该 fold 绝对和相对都失败，优先复核 alpha 与组合暴露。"

    if _safe_str(strategy_review.get("admission_action")) in {"reject", "research_only"} and primary == "clean_positive_fold":
        action = "fold 本身不阻断；结合其他失败 fold 和 constraint review 决策。"

    return _fold_out(
        severity=severity,
        primary=primary,
        absolute_status=absolute_status,
        relative_status=relative_status,
        risk_status=risk_status,
        drawdown_status=drawdown_status,
        turnover_status=turnover_status,
        evidence=evidence,
        action=action,
    )


def _fold_out(
    *,
    severity: str,
    primary: str,
    absolute_status: str,
    relative_status: str,
    risk_status: str,
    drawdown_status: str,
    turnover_status: str,
    evidence: list[str],
    action: str,
) -> dict[str, str]:
    return {
        "fold_severity": severity,
        "primary_fold_failure": primary,
        "absolute_return_status": absolute_status,
        "benchmark_relative_status": relative_status,
        "risk_adjusted_status": risk_status,
        "drawdown_status": drawdown_status,
        "turnover_status": turnover_status,
        "evidence": "；".join(evidence),
        "recommended_next_action": action,
    }


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


def _write_fold_markdown(path: Path, fold_attribution: pd.DataFrame, *, input_paths: dict[str, Path]) -> None:
    lines = [
        "# Strategy Failure Fold Attribution",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Scope",
        "",
        "- This report is research-only fold-level attribution.",
        "- It reads existing admission CSV artifacts only; it does not rerun backtests or admission.",
        "- Benchmark / market context labels are diagnostic labels, not admission gates and not trading rules.",
        "- Do not infer a regime filter from this report alone; use it only to decide whether a later isolated I8 test is justified.",
        "",
        "## Inputs",
        "",
    ]
    for label, input_path in input_paths.items():
        lines.append(f"- {label}: `{input_path}`")
    if fold_attribution.empty:
        lines.extend(["", "No fold attribution rows were generated."])
        path.write_text("\n".join(lines), encoding="utf-8")
        return

    lines.extend(
        [
            "",
            "## Fold Summary",
            "",
            _md_table(
                [
                    "strategy_id",
                    "preset",
                    "fold",
                    "valid_window",
                    "primary_label",
                    "severity",
                    "ann",
                    "bench_ann",
                    "excess_ann",
                    "sharpe",
                    "drawdown",
                    "turnover",
                ],
                [
                    [
                        _safe_str(row["strategy_id"]),
                        _safe_str(row["walk_forward_preset"]),
                        str(_safe_int(row["fold"])),
                        f"{_safe_str(row['valid_start'])}..{_safe_str(row['valid_end'])}",
                        _safe_str(row["primary_fold_failure"]),
                        _safe_str(row["fold_severity"]),
                        _format_optional(row.get("annualized_return"), 4),
                        _format_optional(row.get("benchmark_annualized_return"), 4),
                        _format_optional(row.get("excess_annualized_return"), 4),
                        _format_optional(row.get("sharpe"), 4),
                        _format_optional(row.get("max_drawdown"), 4),
                        _format_optional(row.get("turnover_annual"), 2),
                    ]
                    for _, row in fold_attribution.iterrows()
                ],
            ),
            "",
            "## Label Counts",
            "",
        ]
    )
    label_counts = fold_attribution["primary_fold_failure"].fillna("").astype(str).value_counts().reset_index()
    label_counts.columns = ["primary_label", "fold_count"]
    lines.append(
        _md_table(
            ["primary_label", "fold_count"],
            [[_safe_str(row["primary_label"]), str(_safe_int(row["fold_count"]))] for _, row in label_counts.iterrows()],
        )
    )
    lines.extend(
        [
            "",
            "## Evidence By Fold",
            "",
        ]
    )
    for _, row in fold_attribution.iterrows():
        lines.extend(
            [
                f"### {_safe_str(row['walk_forward_preset'])} fold {_safe_int(row['fold'])}",
                "",
                f"- Valid window: `{_safe_str(row['valid_start'])}` to `{_safe_str(row['valid_end'])}`",
                f"- Primary diagnostic label: `{_safe_str(row['primary_fold_failure'])}`",
                f"- Severity: `{_safe_str(row['fold_severity'])}`",
                f"- Absolute status: `{_safe_str(row['absolute_return_status'])}`",
                f"- Benchmark-relative status: `{_safe_str(row['benchmark_relative_status'])}`",
                f"- Risk-adjusted status: `{_safe_str(row['risk_adjusted_status'])}`",
                f"- Drawdown status: `{_safe_str(row['drawdown_status'])}`",
                f"- Turnover status: `{_safe_str(row['turnover_status'])}`",
                f"- Existing fold attribution: `{_safe_str(row['negative_fold_attribution']) or 'n/a'}`",
                f"- Evidence: {_safe_str(row['evidence'])}",
                f"- Next diagnostic action: {_safe_str(row['recommended_next_action'])}",
                "",
            ]
        )
    lines.extend(
        [
            "## Interpretation Guardrails",
            "",
            "- Admission failure remains governed by the admission window matrix and constraint review.",
            "- Positive absolute return with negative excess is benchmark-context evidence, not proof that a market-state filter will work.",
            "- Negative absolute return with positive excess is market-context evidence, not standalone alpha failure.",
            "- Any I8 market-context test must keep I7 selection logic fixed and test one pre-declared variable only.",
            "",
        ]
    )
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


def _optional_float(value: Any) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _format_optional(value: Any, precision: int) -> str:
    parsed = _optional_float(value)
    return "n/a" if parsed is None else f"{parsed:.{precision}f}"


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
