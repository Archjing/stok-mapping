from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from phase0.research.admission.gate import overfit_blocks_admission


def attach_price_adjustment_status(matrix: pd.DataFrame, config: dict[str, Any], gate_cfg: dict[str, Any]) -> None:
    local_cfg = config.get("local_history", {}) or {}
    adjust_type = str(local_cfg.get("adjust_type", "qfq"))
    mode = str(local_cfg.get("price_adjustment_for_backtest", "qfq_current" if adjust_type == "qfq" else adjust_type))
    required = bool(gate_cfg.get("require_qfq_asof", True))
    matrix["price_adjustment_for_backtest"] = mode
    matrix["price_adjustment_status"] = "qfq_asof" if mode == "qfq_asof" else ("not_required" if not required else "not_qfq_asof")


def build_window_matrix(
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
            rows.append(window_metrics(strategy_name, preset_name, group, gate_cfg))
    return pd.DataFrame(rows)


def window_metrics(strategy_id: str, preset_name: str, group: pd.DataFrame, gate_cfg: dict[str, Any]) -> dict[str, Any]:
    ann = numeric_column(group, "annualized_return")
    sharpe = numeric_column(group, "sharpe")
    mdd = numeric_column(group, "max_drawdown")
    turnover = numeric_column(group, "turnover_annual")
    trades = numeric_column(group, "trades")
    params = group.get("selected_params", pd.Series(dtype=object)).fillna("").astype(str)
    account_status = status_summary(group, "account_execution_status", default="not_enabled")
    industry_status = industry_status_summary(group)
    financial_status = status_summary(group, "financial_diagnostic_status", default="not_available")
    top_industry_avg = numeric_column(group, "top_industry_avg_share")
    top_industry_p95 = numeric_column(group, "top_industry_p95_share")
    top_industry_max = numeric_column(group, "top_industry_max_share")
    top3_industry_avg = numeric_column(group, "top3_industries_avg_share")
    violation_days = numeric_column(group, "industry_constraint_violation_days")
    account_ann = numeric_column(group, "account_annualized_return")
    account_sharpe = numeric_column(group, "account_sharpe")
    account_mdd = numeric_column(group, "account_max_drawdown")
    account_orders = numeric_column(group, "account_executed_order_count")
    account_unfilled = numeric_column(group, "account_unfilled_order_count")
    account_partial = numeric_column(group, "account_partial_fill_order_count")
    account_unfilled_or_partial_ratio = numeric_column(group, "account_unfilled_or_partial_order_ratio")
    account_partial_ratio = numeric_column(group, "account_partial_fill_order_ratio")
    financial_announce = numeric_column(group, "financial_pit_announce_coverage")
    selected_financial_announce = numeric_column(group, "selected_financial_pit_announce_coverage")
    financial_field_coverage = numeric_column(group, "financial_field_coverage_mean")
    selected_financial_field_coverage = numeric_column(group, "selected_financial_field_coverage_mean")
    missing_blocked = numeric_column(group, "financial_missing_blocked_ratio")
    quality_lift = numeric_column(group, "selected_quality_score_lift")
    cash_flow_component = numeric_column(group, "selected_quality_cash_flow_component_mean")
    supports_paper_trade = bool_all(group, "supports_paper_trade", default=True)
    benchmark_status = status_summary(group, "benchmark_status", default="not_available")
    benchmark_ann = numeric_column(group, "benchmark_annualized_return")
    excess_ann = numeric_column(group, "excess_annualized_return")
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


def status_summary(group: pd.DataFrame, column: str, *, default: str) -> str:
    if column not in group.columns:
        return default
    values = group[column].dropna().astype(str).map(str.strip)
    values = values[(values != "") & (values.str.lower() != "nan")]
    if values.empty:
        return default
    unique = sorted(set(values))
    return unique[0] if len(unique) == 1 else "mixed:" + ",".join(unique)


def bool_all(group: pd.DataFrame, column: str, *, default: bool = True) -> bool:
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


def industry_status_summary(group: pd.DataFrame) -> str:
    if "industry_constraint_enabled" not in group.columns:
        return "not_enabled"
    enabled = group["industry_constraint_enabled"].dropna()
    if enabled.empty:
        return "not_enabled"
    enabled_bool = enabled.astype(bool)
    if not enabled_bool.any():
        return "not_enabled"
    status = status_summary(group, "constraint_status", default="enabled")
    return f"enabled:{status}"


def build_constraint_review(matrix: pd.DataFrame, overfit: pd.DataFrame, preset_names: list[str], gate_cfg: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    overfit_by_strategy = {}
    if not overfit.empty and "strategy_id" in overfit.columns:
        overfit_by_strategy = {str(row["strategy_id"]): row for _, row in overfit.iterrows()}

    for strategy_id, group in matrix.groupby("strategy_id", dropna=False):
        sid = str(strategy_id)
        ok_windows = group[group["status"] == "ok"]
        pass_count = int(pd.Series(group.get("is_window_pass", False)).astype(bool).sum())
        turnover_fail_count = turnover_fail_window_count(group, gate_cfg)
        missing_window_count = int((group["status"] != "ok").sum())
        industry_concentration_count = industry_concentration_window_count(ok_windows) if bool(gate_cfg.get("require_industry_concentration_check", True)) else 0
        industry_missing_count = industry_missing_window_count(ok_windows) if bool(gate_cfg.get("require_industry_concentration_check", True)) else 0
        factor_missing_count = factor_missing_window_count(ok_windows) if bool(gate_cfg.get("require_factor_diagnostics", True)) else 0
        price_adjustment_fail_count = price_adjustment_fail_window_count(ok_windows) if bool(gate_cfg.get("require_qfq_asof", True)) else 0
        parameter_unique_total = int(pd.to_numeric(ok_windows.get("parameter_unique_count"), errors="coerce").fillna(0).sum()) if not ok_windows.empty else 0
        parameter_unstable_count = parameter_unstable_window_count(ok_windows) if bool(gate_cfg.get("require_parameter_stability", True)) else 0
        overfit_row = overfit_by_strategy.get(sid)
        overfit_level = str(overfit_row["overfit_risk_level"]) if overfit_row is not None and "overfit_risk_level" in overfit_row else "unknown"
        overfit_score = int(overfit_row["overfit_score"]) if overfit_row is not None and "overfit_score" in overfit_row else 0
        supports_paper_trade = bool_all(group, "supports_paper_trade", default=True)
        action, reasons = admission_action(
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


def parameter_unstable_window_count(ok_windows: pd.DataFrame) -> int:
    if ok_windows.empty:
        return 0
    fold_counts = numeric_column(ok_windows, "fold_count").fillna(0).astype(int)
    param_counts = numeric_column(ok_windows, "parameter_unique_count").fillna(0).astype(int)
    limits = fold_counts.map(lambda fold_count: max(2, fold_count // 2 + 1))
    return int((param_counts > limits).sum())


def industry_concentration_window_count(ok_windows: pd.DataFrame) -> int:
    if ok_windows.empty:
        return 0
    status = ok_windows.get("industry_diagnostic_status", pd.Series("not_enabled", index=ok_windows.index)).astype(str)
    ok_windows = ok_windows[~status.isin({"not_enabled", "not_available"})]
    if ok_windows.empty:
        return 0
    top1 = numeric_column(ok_windows, "top_industry_avg_share_mean").fillna(0.0)
    top3 = numeric_column(ok_windows, "top3_industries_avg_share_mean").fillna(0.0)
    violations = numeric_column(ok_windows, "industry_violation_days_total").fillna(0)
    return int(((top1 > 0.35) | (top3 > 0.65) | (violations > 0)).sum())


def industry_missing_window_count(ok_windows: pd.DataFrame) -> int:
    if ok_windows.empty:
        return 0
    status = ok_windows.get("industry_diagnostic_status", pd.Series("not_enabled", index=ok_windows.index)).astype(str)
    return int(status.isin({"not_enabled", "not_available"}).sum())


def factor_missing_window_count(ok_windows: pd.DataFrame) -> int:
    if ok_windows.empty:
        return 0
    status = ok_windows.get("financial_diagnostic_status", pd.Series("not_available", index=ok_windows.index)).astype(str)
    requires = ~status.isin({"not_applicable"})
    missing = status.isin({"not_available", ""})
    return int((requires & missing).sum())


def price_adjustment_fail_window_count(ok_windows: pd.DataFrame) -> int:
    if ok_windows.empty:
        return 0
    status = ok_windows.get("price_adjustment_status", pd.Series("unknown", index=ok_windows.index)).astype(str)
    return int((status != "qfq_asof").sum())


def admission_action(
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
    overfit_blocks = overfit_blocks_admission(overfit_level, gate_cfg)
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
    positive_fail = int((numeric_column(group, "positive_fold_ratio") < float(gate_cfg["positive_fold_ratio_min"])).sum())
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


def turnover_fail_window_count(group: pd.DataFrame, gate_cfg: dict[str, Any]) -> int:
    if group.empty:
        return 0
    mean_turnover = pd.to_numeric(group.get("turnover_annual_mean"), errors="coerce")
    max_turnover = pd.to_numeric(group.get("turnover_annual_max"), errors="coerce")
    mean_fail = mean_turnover > float(gate_cfg["turnover_annual_mean_max"])
    max_fail = max_turnover > float(gate_cfg["turnover_annual_max_max"])
    return int((mean_fail.fillna(False) | max_fail.fillna(False)).sum())


def numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return pd.to_numeric(df[column], errors="coerce")
