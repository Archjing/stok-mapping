from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from phase0.overfit import run_overfit_diagnostic
from phase0.reporting.paths import create_report_run
from phase0.research.admission.strategy_scope import (
    _force_strategy_set_enabled_for_admission,
    _resolve_strategy_scope,
)
from phase0.walk_forward import run_walk_forward


@dataclass(frozen=True)
class StrategyAdmissionResult:
    output_dir: Path
    matrix_csv: Path
    constraint_csv: Path
    report_md: Path
    governance_md: Path
    folds_csv: Path
    overfit_csv: Path
    strategies: int
    presets: int
    rows: int


def _resolve_admission_gate(wcfg: dict[str, Any]) -> dict[str, Any]:
    legacy_gate = wcfg.get("gate", {}) or {}
    configured = (wcfg.get("admission", {}) or {}).get("gate", {}) or {}
    return {
        "annualized_return_min": float(configured.get("annualized_return_min", legacy_gate.get("annualized_return_min", 0.0))),
        "sharpe_min": float(configured.get("sharpe_min", legacy_gate.get("sharpe_min", 0.5))),
        "max_drawdown_min": float(configured.get("max_drawdown_min", legacy_gate.get("max_drawdown_min", -0.25))),
        "positive_fold_ratio_min": float(configured.get("positive_fold_ratio_min", legacy_gate.get("min_positive_fold_ratio", 0.75))),
        "turnover_annual_mean_max": float(configured.get("turnover_annual_mean_max", 3.0)),
        "turnover_annual_max_max": float(configured.get("turnover_annual_max_max", 5.0)),
        "overfit_risk_max": str(configured.get("overfit_risk_max", "medium")),
        "require_parameter_stability": bool(configured.get("require_parameter_stability", True)),
        "require_industry_concentration_check": bool(configured.get("require_industry_concentration_check", True)),
        "require_factor_diagnostics": bool(configured.get("require_factor_diagnostics", True)),
        "require_qfq_asof": bool(configured.get("require_qfq_asof", True)),
    }


def _resolve_diagnostic_suites(admission_cfg: dict[str, Any]) -> list[str]:
    diagnostics = admission_cfg.get("diagnostics", {}) or {}
    return [str(item) for item in diagnostics.get("suites", [])]


def run_strategy_admission(
    *,
    config: dict[str, Any],
    root: Path,
    config_path: Path | None = None,
    presets: list[str] | None = None,
    strategy_set: str | None = None,
    strategies: list[str] | None = None,
    output_dir: Path | None = None,
    trace_callback: Any | None = None,
) -> StrategyAdmissionResult:
    wcfg = config.get("walk_forward", {})
    available_presets = wcfg.get("presets", {}) or {}
    preset_names = presets or list(available_presets.keys())
    if not preset_names:
        raise ValueError("strategy-admission requires at least one walk_forward preset")
    missing_presets = [name for name in preset_names if name not in available_presets]
    if missing_presets:
        raise ValueError(f"unknown walk_forward presets: {missing_presets}")

    admission_cfg = wcfg.get("admission", {}) or {}
    gate_cfg = _resolve_admission_gate(wcfg)
    diagnostics_suites = _resolve_diagnostic_suites(admission_cfg)
    strategy_cfg = wcfg.get("strategy_v2", {})
    strategy_scope = _resolve_strategy_scope(strategy_cfg, admission_cfg, strategy_set=strategy_set, strategies=strategies)
    strategy_names = strategy_scope["strategies"]
    if not strategy_names:
        raise ValueError("strategy-admission requires at least one strategy")

    explicit_output_dir = output_dir is not None
    if output_dir is None:
        scope_name = strategy_scope.get("strategy_set") or "_".join(strategy_names[:3]) or "default"
        report_run = create_report_run(root=root, config=config, command="strategy-admission", scope=str(scope_name))
        output_dir = report_run.run_dir
    else:
        report_run = None
    output_dir.mkdir(parents=True, exist_ok=True)

    all_folds: list[pd.DataFrame] = []
    failure_rows: list[dict[str, Any]] = []
    for preset_name in preset_names:
        scenario_cfg = copy.deepcopy(config)
        scenario_wcfg = scenario_cfg.setdefault("walk_forward", {})
        scenario_wcfg["preset_name"] = preset_name
        scenario_strategy_cfg = scenario_wcfg.setdefault("strategy_v2", {})
        scenario_strategy_cfg["compare_strategies"] = strategy_names
        _force_strategy_set_enabled_for_admission(scenario_strategy_cfg, strategy_names)
        result = run_walk_forward(scenario_cfg, trace_callback=trace_callback)
        summary = result.get("summary", {}) or {}
        folds = result.get("candidate_folds", pd.DataFrame())
        if folds is None or folds.empty:
            reason = str(summary.get("reason", "no valid folds"))
            for strategy_name in strategy_names:
                failure_rows.append(
                    {
                        "strategy_id": strategy_name,
                        "candidate": strategy_name,
                        "walk_forward_preset": preset_name,
                        "status": "failed",
                        "failure_reason": reason,
                    }
                )
            continue
        folds = folds.copy()
        folds["walk_forward_preset"] = preset_name
        folds["walk_forward_train_years"] = int(summary.get("walk_forward_train_years", available_presets[preset_name].get("train_years", 0)))
        folds["walk_forward_validate_years"] = int(summary.get("walk_forward_validate_years", available_presets[preset_name].get("validate_years", 0)))
        folds["walk_forward_start_date"] = str(summary.get("walk_forward_start_date", available_presets[preset_name].get("start_date", "")))
        folds["walk_forward_end_date"] = str(summary.get("walk_forward_end_date", available_presets[preset_name].get("end_date", "")))
        folds["walk_forward_expected_folds"] = summary.get("walk_forward_expected_folds", available_presets[preset_name].get("expected_folds", ""))
        folds["walk_forward_actual_folds"] = summary.get("walk_forward_actual_folds", folds["fold"].nunique() if "fold" in folds.columns else 0)
        folds["walk_forward_fold_generation_warning"] = str(summary.get("walk_forward_fold_generation_warning", ""))
        folds["status"] = "ok"
        folds["failure_reason"] = ""
        all_folds.append(folds)

    folds_df = pd.concat(all_folds, ignore_index=True) if all_folds else pd.DataFrame()
    failures_df = pd.DataFrame(failure_rows)
    matrix_df = _build_window_matrix(folds_df, failures_df, strategy_names, preset_names, gate_cfg)
    _attach_price_adjustment_status(matrix_df, config, gate_cfg)

    folds_csv = (
        output_dir / "strategy_admission_candidate_folds.csv"
        if explicit_output_dir
        else report_run.artifact("strategy_admission", "candidate_folds", "csv")
    )
    if folds_df.empty:
        pd.DataFrame().to_csv(folds_csv, index=False)
    else:
        folds_df.to_csv(folds_csv, index=False)

    overfit_output_dir = output_dir / "overfit_diagnostic" if explicit_output_dir else output_dir
    overfit_csv = (
        overfit_output_dir / "strategy_overfit_diagnostic.csv"
        if explicit_output_dir
        else report_run.artifact("overfit", "diagnostic", "csv")
    )
    overfit_df = pd.DataFrame()
    if not folds_df.empty:
        overfit_result = run_overfit_diagnostic(
            config=config,
            root=root,
            candidates_path=folds_csv,
            folds_path=folds_csv,
            output_dir=overfit_output_dir,
            standard_names=not explicit_output_dir,
        )
        overfit_csv = overfit_result.csv_path
        overfit_df = pd.read_csv(overfit_csv)

    constraint_df = _build_constraint_review(matrix_df, overfit_df, preset_names, gate_cfg)

    if explicit_output_dir:
        matrix_csv = output_dir / "strategy_admission_window_matrix.csv"
        constraint_csv = output_dir / "strategy_admission_constraint_review.csv"
        report_md = output_dir / "strategy_admission_report.md"
        governance_md = output_dir / "strategy_admission_governance_report.md"
    else:
        matrix_csv = report_run.artifact("strategy_admission", "window_matrix", "csv")
        constraint_csv = report_run.artifact("strategy_admission", "constraint_review", "csv")
        report_md = report_run.artifact("strategy_admission", "report", "md")
        governance_md = report_run.artifact("strategy_admission", "governance", "md")
    matrix_df.to_csv(matrix_csv, index=False)
    constraint_df.to_csv(constraint_csv, index=False)
    _write_report(
        report_md,
        matrix_df,
        constraint_df,
        preset_names,
        strategy_names,
        root=root,
        strategy_scope=strategy_scope,
        gate_cfg=gate_cfg,
        diagnostics_suites=diagnostics_suites,
    )
    _write_governance_report(
        governance_md,
        matrix_df,
        constraint_df,
        preset_names,
        strategy_names,
        strategy_scope=strategy_scope,
        gate_cfg=gate_cfg,
        diagnostics_suites=diagnostics_suites,
        required_artifacts=_required_artifact_names(
            output_dir=output_dir,
            folds_csv=folds_csv,
            matrix_csv=matrix_csv,
            constraint_csv=constraint_csv,
            report_md=report_md,
            overfit_csv=overfit_csv,
        ),
        command_hint=_admission_command_hint(
            config_arg=_config_command_arg(config_path, root),
            presets=preset_names,
            strategy_scope=strategy_scope,
            output_dir=output_dir if explicit_output_dir else None,
        ),
    )

    return StrategyAdmissionResult(
        output_dir=output_dir,
        matrix_csv=matrix_csv,
        constraint_csv=constraint_csv,
        report_md=report_md,
        governance_md=governance_md,
        folds_csv=folds_csv,
        overfit_csv=overfit_csv,
        strategies=len(strategy_names),
        presets=len(preset_names),
        rows=len(matrix_df),
    )


def _attach_price_adjustment_status(matrix: pd.DataFrame, config: dict[str, Any], gate_cfg: dict[str, Any]) -> None:
    local_cfg = config.get("local_history", {}) or {}
    adjust_type = str(local_cfg.get("adjust_type", "qfq"))
    mode = str(local_cfg.get("price_adjustment_for_backtest", "qfq_current" if adjust_type == "qfq" else adjust_type))
    required = bool(gate_cfg.get("require_qfq_asof", True))
    matrix["price_adjustment_for_backtest"] = mode
    matrix["price_adjustment_status"] = "qfq_asof" if mode == "qfq_asof" else ("not_required" if not required else "not_qfq_asof")


def _build_window_matrix(
    folds: pd.DataFrame,
    failures: pd.DataFrame,
    strategy_names: list[str],
    preset_names: list[str],
    gate_cfg: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    strategy_col = "strategy_id" if "strategy_id" in folds.columns else "candidate"
    for strategy_name in strategy_names:
        for preset_name in preset_names:
            group = pd.DataFrame()
            if not folds.empty and strategy_col in folds.columns:
                group = folds[(folds[strategy_col].astype(str) == strategy_name) & (folds["walk_forward_preset"].astype(str) == preset_name)]
            if group.empty:
                failure_reason = "no valid folds"
                if not failures.empty:
                    match = failures[(failures["strategy_id"].astype(str) == strategy_name) & (failures["walk_forward_preset"].astype(str) == preset_name)]
                    if not match.empty:
                        failure_reason = str(match["failure_reason"].iloc[0])
                rows.append(
                    {
                        "strategy_id": strategy_name,
                        "walk_forward_preset": preset_name,
                        "status": "failed",
                        "failure_reason": failure_reason,
                        "fold_count": 0,
                        "walk_forward_start_date": "",
                        "walk_forward_end_date": "",
                        "walk_forward_expected_folds": "",
                        "walk_forward_actual_folds": 0,
                        "walk_forward_fold_generation_warning": failure_reason,
                        "positive_fold_ratio": 0.0,
                        "benchmark_status": "not_available",
                        "benchmark_available_fold_count": 0,
                        "benchmark_annualized_return_mean": np.nan,
                        "excess_annualized_return_mean": np.nan,
                        "excess_annualized_return_min": np.nan,
                        "positive_excess_fold_ratio": np.nan,
                        "negative_absolute_fold_count": 0,
                        "negative_absolute_positive_excess_count": 0,
                        "negative_absolute_negative_excess_count": 0,
                        "negative_absolute_benchmark_unavailable_count": 0,
                        "annualized_return_mean": 0.0,
                        "sharpe_mean": 0.0,
                        "max_drawdown_worst": 0.0,
                        "turnover_annual_mean": 0.0,
                        "turnover_annual_max": 0.0,
                        "trades_total": 0,
                        "parameter_unique_count": 0,
                        "is_return_pass": False,
                        "is_sharpe_pass": False,
                        "is_drawdown_pass": False,
                        "is_positive_fold_pass": False,
                        "is_turnover_pass": False,
                        "is_window_pass": False,
                    }
                )
                continue
            rows.append(_window_metrics(strategy_name, preset_name, group, gate_cfg))
    return pd.DataFrame(rows)


def _window_metrics(strategy_id: str, preset_name: str, group: pd.DataFrame, gate_cfg: dict[str, Any]) -> dict[str, Any]:
    ann = _numeric_column(group, "annualized_return")
    sharpe = _numeric_column(group, "sharpe")
    mdd = _numeric_column(group, "max_drawdown")
    turnover = _numeric_column(group, "turnover_annual")
    trades = _numeric_column(group, "trades")
    params = group.get("selected_params", pd.Series(dtype=object)).fillna("").astype(str)
    account_status = _status_summary(group, "account_execution_status", default="not_enabled")
    industry_status = _industry_status_summary(group)
    financial_status = _status_summary(group, "financial_diagnostic_status", default="not_available")
    top_industry_avg = _numeric_column(group, "top_industry_avg_share")
    top_industry_p95 = _numeric_column(group, "top_industry_p95_share")
    top_industry_max = _numeric_column(group, "top_industry_max_share")
    top3_industry_avg = _numeric_column(group, "top3_industries_avg_share")
    violation_days = _numeric_column(group, "industry_constraint_violation_days")
    account_ann = _numeric_column(group, "account_annualized_return")
    account_sharpe = _numeric_column(group, "account_sharpe")
    account_mdd = _numeric_column(group, "account_max_drawdown")
    account_orders = _numeric_column(group, "account_executed_order_count")
    account_unfilled = _numeric_column(group, "account_unfilled_order_count")
    account_partial = _numeric_column(group, "account_partial_fill_order_count")
    account_unfilled_or_partial_ratio = _numeric_column(group, "account_unfilled_or_partial_order_ratio")
    account_partial_ratio = _numeric_column(group, "account_partial_fill_order_ratio")
    financial_announce = _numeric_column(group, "financial_pit_announce_coverage")
    selected_financial_announce = _numeric_column(group, "selected_financial_pit_announce_coverage")
    financial_field_coverage = _numeric_column(group, "financial_field_coverage_mean")
    selected_financial_field_coverage = _numeric_column(group, "selected_financial_field_coverage_mean")
    missing_blocked = _numeric_column(group, "financial_missing_blocked_ratio")
    quality_lift = _numeric_column(group, "selected_quality_score_lift")
    cash_flow_component = _numeric_column(group, "selected_quality_cash_flow_component_mean")
    supports_paper_trade = _bool_all(group, "supports_paper_trade", default=True)
    benchmark_status = _status_summary(group, "benchmark_status", default="not_available")
    benchmark_ann = _numeric_column(group, "benchmark_annualized_return")
    excess_ann = _numeric_column(group, "excess_annualized_return")
    valid_excess = excess_ann.dropna()
    benchmark_statuses = group.get("benchmark_status", pd.Series("not_available", index=group.index)).fillna("not_available").astype(str)
    attribution = group.get("negative_fold_attribution", pd.Series("", index=group.index)).fillna("").astype(str)
    positive_fold_ratio = float((ann > 0).mean()) if len(group) else 0.0
    positive_excess_fold_ratio = float((valid_excess > 0).mean()) if len(valid_excess) else np.nan
    annualized_return_mean = float(ann.mean()) if ann.notna().any() else 0.0
    benchmark_annualized_return_mean = float(benchmark_ann.mean()) if benchmark_ann.notna().any() else np.nan
    excess_annualized_return_mean = float(excess_ann.mean()) if excess_ann.notna().any() else np.nan
    excess_annualized_return_min = float(excess_ann.min()) if excess_ann.notna().any() else np.nan
    sharpe_mean = float(sharpe.mean()) if sharpe.notna().any() else 0.0
    max_drawdown_worst = float(mdd.min()) if mdd.notna().any() else 0.0
    turnover_annual_mean = float(turnover.mean()) if turnover.notna().any() else 0.0
    turnover_annual_max = float(turnover.max()) if turnover.notna().any() else 0.0
    fold_count = int(len(group))
    is_return_pass = annualized_return_mean > float(gate_cfg["annualized_return_min"])
    is_sharpe_pass = sharpe_mean > float(gate_cfg["sharpe_min"])
    is_drawdown_pass = max_drawdown_worst > float(gate_cfg["max_drawdown_min"])
    is_positive_fold_pass = positive_fold_ratio >= float(gate_cfg["positive_fold_ratio_min"])
    is_turnover_pass = turnover_annual_mean <= float(gate_cfg["turnover_annual_mean_max"]) and turnover_annual_max <= float(gate_cfg["turnover_annual_max_max"])
    expected_folds = group.get("walk_forward_expected_folds", pd.Series(dtype=object)).dropna()
    expected_folds_value = expected_folds.iloc[0] if not expected_folds.empty else ""
    actual_folds = group.get("walk_forward_actual_folds", pd.Series(dtype=object)).dropna()
    actual_folds_value = int(actual_folds.iloc[0]) if not actual_folds.empty and str(actual_folds.iloc[0]).strip() != "" else int(group["fold"].nunique()) if "fold" in group.columns else fold_count
    return {
        "strategy_id": strategy_id,
        "walk_forward_preset": preset_name,
        "status": "ok",
        "failure_reason": "",
        "fold_count": fold_count,
        "walk_forward_start_date": str(group["walk_forward_start_date"].iloc[0]) if "walk_forward_start_date" in group.columns else "",
        "walk_forward_end_date": str(group["walk_forward_end_date"].iloc[0]) if "walk_forward_end_date" in group.columns else "",
        "walk_forward_expected_folds": expected_folds_value,
        "walk_forward_actual_folds": actual_folds_value,
        "walk_forward_fold_generation_warning": str(group["walk_forward_fold_generation_warning"].iloc[0]) if "walk_forward_fold_generation_warning" in group.columns else "",
        "positive_fold_ratio": positive_fold_ratio,
        "benchmark_status": benchmark_status,
        "benchmark_available_fold_count": int((benchmark_statuses == "available").sum()),
        "benchmark_annualized_return_mean": benchmark_annualized_return_mean,
        "excess_annualized_return_mean": excess_annualized_return_mean,
        "excess_annualized_return_min": excess_annualized_return_min,
        "positive_excess_fold_ratio": positive_excess_fold_ratio,
        "negative_absolute_fold_count": int((ann < 0).sum()) if ann.notna().any() else 0,
        "negative_absolute_positive_excess_count": int((attribution == "negative_absolute_but_positive_excess: market_down_or_benchmark_weaker").sum()),
        "negative_absolute_negative_excess_count": int((attribution == "negative_absolute_and_negative_excess: strategy_specific_underperformance").sum()),
        "negative_absolute_benchmark_unavailable_count": int((attribution == "negative_absolute: benchmark_unavailable").sum()),
        "annualized_return_mean": annualized_return_mean,
        "sharpe_mean": sharpe_mean,
        "max_drawdown_worst": max_drawdown_worst,
        "turnover_annual_mean": turnover_annual_mean,
        "turnover_annual_max": turnover_annual_max,
        "trades_total": int(trades.sum()) if trades.notna().any() else 0,
        "parameter_unique_count": int(params[params != ""].nunique()),
        "account_execution_status": account_status,
        "industry_diagnostic_status": industry_status,
        "financial_diagnostic_status": financial_status,
        "top_industry_avg_share_mean": float(top_industry_avg.mean()) if top_industry_avg.notna().any() else 0.0,
        "top_industry_p95_share_max": float(top_industry_p95.max()) if top_industry_p95.notna().any() else 0.0,
        "top_industry_max_share_max": float(top_industry_max.max()) if top_industry_max.notna().any() else 0.0,
        "top3_industries_avg_share_mean": float(top3_industry_avg.mean()) if top3_industry_avg.notna().any() else 0.0,
        "industry_violation_days_total": int(violation_days.fillna(0).sum()) if violation_days.notna().any() else 0,
        "account_annualized_return_mean": float(account_ann.mean()) if account_ann.notna().any() else 0.0,
        "account_sharpe_mean": float(account_sharpe.mean()) if account_sharpe.notna().any() else 0.0,
        "account_max_drawdown_worst": float(account_mdd.min()) if account_mdd.notna().any() else 0.0,
        "account_executed_order_count_total": int(account_orders.fillna(0).sum()) if account_orders.notna().any() else 0,
        "account_unfilled_order_count_total": int(account_unfilled.fillna(0).sum()) if account_unfilled.notna().any() else 0,
        "account_partial_fill_order_count_total": int(account_partial.fillna(0).sum()) if account_partial.notna().any() else 0,
        "account_unfilled_or_partial_order_ratio_mean": float(account_unfilled_or_partial_ratio.mean()) if account_unfilled_or_partial_ratio.notna().any() else 0.0,
        "account_partial_fill_order_ratio_mean": float(account_partial_ratio.mean()) if account_partial_ratio.notna().any() else 0.0,
        "financial_pit_announce_coverage_mean": float(financial_announce.mean()) if financial_announce.notna().any() else 0.0,
        "selected_financial_pit_announce_coverage_mean": float(selected_financial_announce.mean()) if selected_financial_announce.notna().any() else 0.0,
        "financial_field_coverage_mean": float(financial_field_coverage.mean()) if financial_field_coverage.notna().any() else 0.0,
        "selected_financial_field_coverage_mean": float(selected_financial_field_coverage.mean()) if selected_financial_field_coverage.notna().any() else 0.0,
        "financial_missing_blocked_ratio_mean": float(missing_blocked.mean()) if missing_blocked.notna().any() else 0.0,
        "selected_quality_score_lift_mean": float(quality_lift.mean()) if quality_lift.notna().any() else 0.0,
        "selected_cash_flow_quality_component_mean": float(cash_flow_component.mean()) if cash_flow_component.notna().any() else 0.0,
        "supports_paper_trade": supports_paper_trade,
        "is_return_pass": is_return_pass,
        "is_sharpe_pass": is_sharpe_pass,
        "is_drawdown_pass": is_drawdown_pass,
        "is_positive_fold_pass": is_positive_fold_pass,
        "is_turnover_pass": is_turnover_pass,
        "is_window_pass": bool(is_return_pass and is_sharpe_pass and is_drawdown_pass and is_positive_fold_pass and is_turnover_pass),
    }


def _status_summary(group: pd.DataFrame, column: str, *, default: str) -> str:
    if column not in group.columns:
        return default
    values = group[column].dropna().astype(str).map(str.strip)
    values = values[(values != "") & (values.str.lower() != "nan")]
    if values.empty:
        return default
    unique = sorted(set(values))
    return unique[0] if len(unique) == 1 else "mixed:" + ",".join(unique)


def _bool_all(group: pd.DataFrame, column: str, *, default: bool = True) -> bool:
    if column not in group.columns:
        return default
    values = group[column]
    if values is None:
        return default
    normalized = values.fillna(default).map(
        lambda value: str(value).strip().lower() if isinstance(value, str) else value
    )
    parsed = normalized.map(
        lambda value: (
            False
            if value in {False, 0, "0", "false", "no", "n", "off"}
            else True
            if value in {True, 1, "1", "true", "yes", "y", "on"}
            else default
        )
    )
    return bool(parsed.all())


def _industry_status_summary(group: pd.DataFrame) -> str:
    if "industry_constraint_enabled" not in group.columns:
        return "not_enabled"
    enabled = group["industry_constraint_enabled"].dropna()
    if enabled.empty:
        return "not_enabled"
    enabled_bool = enabled.astype(bool)
    if not enabled_bool.any():
        return "not_enabled"
    status = _status_summary(group, "constraint_status", default="enabled")
    return f"enabled:{status}"


def _build_constraint_review(matrix: pd.DataFrame, overfit: pd.DataFrame, preset_names: list[str], gate_cfg: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    overfit_by_strategy = {}
    if not overfit.empty and "strategy_id" in overfit.columns:
        overfit_by_strategy = {str(row["strategy_id"]): row for _, row in overfit.iterrows()}

    for strategy_id, group in matrix.groupby("strategy_id", dropna=False):
        sid = str(strategy_id)
        ok_windows = group[group["status"] == "ok"]
        pass_count = int(pd.Series(group.get("is_window_pass", False)).astype(bool).sum())
        turnover_fail_count = _turnover_fail_window_count(group, gate_cfg)
        missing_window_count = int((group["status"] != "ok").sum())
        industry_concentration_count = _industry_concentration_window_count(ok_windows) if bool(gate_cfg.get("require_industry_concentration_check", True)) else 0
        industry_missing_count = _industry_missing_window_count(ok_windows) if bool(gate_cfg.get("require_industry_concentration_check", True)) else 0
        factor_missing_count = _factor_missing_window_count(ok_windows) if bool(gate_cfg.get("require_factor_diagnostics", True)) else 0
        price_adjustment_fail_count = _price_adjustment_fail_window_count(ok_windows) if bool(gate_cfg.get("require_qfq_asof", True)) else 0
        parameter_unique_total = int(pd.to_numeric(ok_windows.get("parameter_unique_count"), errors="coerce").fillna(0).sum()) if not ok_windows.empty else 0
        parameter_unstable_count = _parameter_unstable_window_count(ok_windows) if bool(gate_cfg.get("require_parameter_stability", True)) else 0
        overfit_row = overfit_by_strategy.get(sid)
        overfit_level = str(overfit_row["overfit_risk_level"]) if overfit_row is not None and "overfit_risk_level" in overfit_row else "unknown"
        overfit_score = int(overfit_row["overfit_score"]) if overfit_row is not None and "overfit_score" in overfit_row else 0
        supports_paper_trade = _bool_all(group, "supports_paper_trade", default=True)
        action, reasons = _admission_action(
            pass_count=pass_count,
            preset_count=len(preset_names),
            turnover_fail_count=turnover_fail_count,
            missing_window_count=missing_window_count,
            parameter_unstable_count=parameter_unstable_count,
            industry_concentration_count=industry_concentration_count,
            industry_missing_count=industry_missing_count,
            factor_missing_count=factor_missing_count,
            price_adjustment_fail_count=price_adjustment_fail_count,
            overfit_level=overfit_level,
            supports_paper_trade=supports_paper_trade,
            group=group,
            gate_cfg=gate_cfg,
        )
        rows.append(
            {
                "strategy_id": sid,
                "admission_action": action,
                "window_pass_count": pass_count,
                "window_count": len(preset_names),
                "turnover_fail_count": turnover_fail_count,
                "missing_window_count": missing_window_count,
                "industry_concentration_window_count": industry_concentration_count,
                "industry_diagnostic_missing_window_count": industry_missing_count,
                "factor_diagnostic_missing_window_count": factor_missing_count,
                "price_adjustment_fail_window_count": price_adjustment_fail_count,
                "overfit_risk_level": overfit_level,
                "overfit_score": overfit_score,
                "parameter_unique_total": parameter_unique_total,
                "parameter_unstable_window_count": parameter_unstable_count,
                "supports_paper_trade": supports_paper_trade,
                "main_reasons": "; ".join(reasons),
            }
        )
    return pd.DataFrame(rows).sort_values(["admission_action", "strategy_id"]).reset_index(drop=True)


def _parameter_unstable_window_count(ok_windows: pd.DataFrame) -> int:
    if ok_windows.empty:
        return 0
    fold_counts = _numeric_column(ok_windows, "fold_count").fillna(0).astype(int)
    param_counts = _numeric_column(ok_windows, "parameter_unique_count").fillna(0).astype(int)
    limits = fold_counts.map(lambda fold_count: max(2, fold_count // 2 + 1))
    return int((param_counts > limits).sum())


def _overfit_blocks_admission(level: str, gate_cfg: dict[str, Any]) -> bool:
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3, "unknown": 99}
    max_level = str(gate_cfg.get("overfit_risk_max", "medium"))
    return order.get(str(level), 99) > order.get(max_level, 1)


def _industry_concentration_window_count(ok_windows: pd.DataFrame) -> int:
    if ok_windows.empty:
        return 0
    status = ok_windows.get("industry_diagnostic_status", pd.Series("not_enabled", index=ok_windows.index)).astype(str)
    ok_windows = ok_windows[~status.isin({"not_enabled", "not_available"})]
    if ok_windows.empty:
        return 0
    top1 = _numeric_column(ok_windows, "top_industry_avg_share_mean").fillna(0.0)
    top3 = _numeric_column(ok_windows, "top3_industries_avg_share_mean").fillna(0.0)
    violations = _numeric_column(ok_windows, "industry_violation_days_total").fillna(0)
    return int(((top1 > 0.35) | (top3 > 0.65) | (violations > 0)).sum())


def _industry_missing_window_count(ok_windows: pd.DataFrame) -> int:
    if ok_windows.empty:
        return 0
    status = ok_windows.get("industry_diagnostic_status", pd.Series("not_enabled", index=ok_windows.index)).astype(str)
    return int(status.isin({"not_enabled", "not_available"}).sum())


def _factor_missing_window_count(ok_windows: pd.DataFrame) -> int:
    if ok_windows.empty:
        return 0
    status = ok_windows.get("financial_diagnostic_status", pd.Series("not_available", index=ok_windows.index)).astype(str)
    requires = ~status.isin({"not_applicable"})
    missing = status.isin({"not_available", ""})
    return int((requires & missing).sum())


def _price_adjustment_fail_window_count(ok_windows: pd.DataFrame) -> int:
    if ok_windows.empty:
        return 0
    status = ok_windows.get("price_adjustment_status", pd.Series("unknown", index=ok_windows.index)).astype(str)
    return int((status != "qfq_asof").sum())


def _admission_action(
    *,
    pass_count: int,
    preset_count: int,
    turnover_fail_count: int,
    missing_window_count: int,
    parameter_unstable_count: int,
    industry_concentration_count: int,
    industry_missing_count: int,
    factor_missing_count: int,
    price_adjustment_fail_count: int,
    overfit_level: str,
    supports_paper_trade: bool,
    group: pd.DataFrame,
    gate_cfg: dict[str, Any],
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    overfit_blocks = _overfit_blocks_admission(overfit_level, gate_cfg)
    if missing_window_count:
        reasons.append("one or more presets produced no valid folds")
    if overfit_blocks:
        reasons.append(f"overfit risk is {overfit_level}")
    if turnover_fail_count:
        reasons.append("annual turnover exceeds threshold in one or more windows")
    if parameter_unstable_count:
        reasons.append("selected parameters change too frequently in one or more windows")
    if industry_missing_count:
        reasons.append("industry concentration check is required but not available in one or more windows")
    if industry_concentration_count:
        reasons.append("industry concentration exceeds audit threshold in one or more windows")
    if factor_missing_count:
        reasons.append("factor diagnostics are required but not available in one or more windows")
    if price_adjustment_fail_count:
        reasons.append("qfq_asof price adjustment is required but not active in one or more windows")
    if not supports_paper_trade:
        reasons.append("strategy does not support paper trade review")
    positive_fail = int((_numeric_column(group, "positive_fold_ratio") < float(gate_cfg["positive_fold_ratio_min"])).sum())
    if positive_fail:
        reasons.append(f"positive fold ratio below {float(gate_cfg['positive_fold_ratio_min']):.0%} in one or more windows")
    if (
        pass_count == preset_count
        and not overfit_blocks
        and turnover_fail_count == 0
        and (parameter_unstable_count == 0 or not bool(gate_cfg.get("require_parameter_stability", True)))
        and industry_missing_count == 0
        and factor_missing_count == 0
        and price_adjustment_fail_count == 0
        and supports_paper_trade
        and (industry_concentration_count == 0 or not bool(gate_cfg.get("require_industry_concentration_check", True)))
    ):
        return "eligible_for_paper_review", reasons or ["all configured windows pass"]
    if pass_count == preset_count and not supports_paper_trade:
        return "research_only", reasons
    if pass_count == 1:
        reasons.append("only one preset passed; classify as research-only")
        return "research_only", reasons
    if overfit_level == "critical" or pass_count == 0:
        return "reject", reasons or ["no configured window passed"]
    return "retest", reasons or ["window robustness incomplete"]


def _turnover_fail_window_count(group: pd.DataFrame, gate_cfg: dict[str, Any]) -> int:
    if group.empty:
        return 0
    mean_turnover = pd.to_numeric(group.get("turnover_annual_mean"), errors="coerce")
    max_turnover = pd.to_numeric(group.get("turnover_annual_max"), errors="coerce")
    mean_fail = mean_turnover > float(gate_cfg["turnover_annual_mean_max"])
    max_fail = max_turnover > float(gate_cfg["turnover_annual_max_max"])
    return int((mean_fail.fillna(False) | max_fail.fillna(False)).sum())


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
    research_or_reject = review[
        review.get("admission_action", pd.Series(dtype=object)).astype(str).isin(
            {"reject", "retest", "research_only"}
        )
    ] if not review.empty and "admission_action" in review.columns else pd.DataFrame()

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
    strategy_id = str(row.get("strategy_id", ""))
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


def _numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return pd.to_numeric(df[column], errors="coerce")
