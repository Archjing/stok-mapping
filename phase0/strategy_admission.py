from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from phase0.overfit import run_overfit_diagnostic
from phase0.walk_forward import run_walk_forward


@dataclass(frozen=True)
class StrategyAdmissionResult:
    output_dir: Path
    matrix_csv: Path
    constraint_csv: Path
    report_md: Path
    folds_csv: Path
    overfit_csv: Path
    strategies: int
    presets: int
    rows: int


def run_strategy_admission(
    *,
    config: dict[str, Any],
    root: Path,
    presets: list[str] | None = None,
    strategies: list[str] | None = None,
    output_dir: Path | None = None,
) -> StrategyAdmissionResult:
    output_dir = output_dir or root / "reports" / "strategy_admission"
    output_dir.mkdir(parents=True, exist_ok=True)

    wcfg = config.get("walk_forward", {})
    available_presets = wcfg.get("presets", {}) or {}
    preset_names = presets or list(available_presets.keys())
    if not preset_names:
        raise ValueError("strategy-admission requires at least one walk_forward preset")
    missing_presets = [name for name in preset_names if name not in available_presets]
    if missing_presets:
        raise ValueError(f"unknown walk_forward presets: {missing_presets}")

    strategy_cfg = wcfg.get("strategy_v2", {})
    strategy_names = strategies or [str(item) for item in strategy_cfg.get("compare_strategies", [])]
    if not strategy_names:
        raise ValueError("strategy-admission requires at least one strategy")

    all_folds: list[pd.DataFrame] = []
    failure_rows: list[dict[str, Any]] = []
    for preset_name in preset_names:
        scenario_cfg = copy.deepcopy(config)
        scenario_wcfg = scenario_cfg.setdefault("walk_forward", {})
        scenario_wcfg["preset_name"] = preset_name
        scenario_strategy_cfg = scenario_wcfg.setdefault("strategy_v2", {})
        scenario_strategy_cfg["compare_strategies"] = strategy_names
        result = run_walk_forward(scenario_cfg)
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
        folds["status"] = "ok"
        folds["failure_reason"] = ""
        all_folds.append(folds)

    folds_df = pd.concat(all_folds, ignore_index=True) if all_folds else pd.DataFrame()
    failures_df = pd.DataFrame(failure_rows)
    matrix_df = _build_window_matrix(folds_df, failures_df, strategy_names, preset_names)

    folds_csv = output_dir / "strategy_admission_candidate_folds.csv"
    if folds_df.empty:
        pd.DataFrame().to_csv(folds_csv, index=False)
    else:
        folds_df.to_csv(folds_csv, index=False)

    overfit_csv = output_dir / "overfit_diagnostic" / "strategy_overfit_diagnostic.csv"
    overfit_df = pd.DataFrame()
    if not folds_df.empty:
        overfit_result = run_overfit_diagnostic(
            config=config,
            root=root,
            candidates_path=folds_csv,
            folds_path=folds_csv,
            output_dir=output_dir / "overfit_diagnostic",
        )
        overfit_csv = overfit_result.csv_path
        overfit_df = pd.read_csv(overfit_csv)

    constraint_df = _build_constraint_review(matrix_df, overfit_df, preset_names)

    matrix_csv = output_dir / "strategy_admission_window_matrix.csv"
    constraint_csv = output_dir / "strategy_admission_constraint_review.csv"
    report_md = output_dir / "strategy_admission_report.md"
    matrix_df.to_csv(matrix_csv, index=False)
    constraint_df.to_csv(constraint_csv, index=False)
    _write_report(report_md, matrix_df, constraint_df, preset_names, strategy_names)

    return StrategyAdmissionResult(
        output_dir=output_dir,
        matrix_csv=matrix_csv,
        constraint_csv=constraint_csv,
        report_md=report_md,
        folds_csv=folds_csv,
        overfit_csv=overfit_csv,
        strategies=len(strategy_names),
        presets=len(preset_names),
        rows=len(matrix_df),
    )


def _build_window_matrix(
    folds: pd.DataFrame,
    failures: pd.DataFrame,
    strategy_names: list[str],
    preset_names: list[str],
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
                        "positive_fold_ratio": 0.0,
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
            rows.append(_window_metrics(strategy_name, preset_name, group))
    return pd.DataFrame(rows)


def _window_metrics(strategy_id: str, preset_name: str, group: pd.DataFrame) -> dict[str, Any]:
    ann = _numeric_column(group, "annualized_return")
    sharpe = _numeric_column(group, "sharpe")
    mdd = _numeric_column(group, "max_drawdown")
    turnover = _numeric_column(group, "turnover_annual")
    trades = _numeric_column(group, "trades")
    params = group.get("selected_params", pd.Series(dtype=object)).fillna("").astype(str)
    top_industry_avg = _numeric_column(group, "top_industry_avg_share")
    top_industry_p95 = _numeric_column(group, "top_industry_p95_share")
    top_industry_max = _numeric_column(group, "top_industry_max_share")
    top3_industry_avg = _numeric_column(group, "top3_industries_avg_share")
    violation_days = _numeric_column(group, "industry_constraint_violation_days")
    positive_fold_ratio = float((ann > 0).mean()) if len(group) else 0.0
    annualized_return_mean = float(ann.mean()) if ann.notna().any() else 0.0
    sharpe_mean = float(sharpe.mean()) if sharpe.notna().any() else 0.0
    max_drawdown_worst = float(mdd.min()) if mdd.notna().any() else 0.0
    turnover_annual_mean = float(turnover.mean()) if turnover.notna().any() else 0.0
    turnover_annual_max = float(turnover.max()) if turnover.notna().any() else 0.0
    fold_count = int(len(group))
    is_return_pass = annualized_return_mean > 0
    is_sharpe_pass = sharpe_mean > 0.5
    is_drawdown_pass = max_drawdown_worst > -0.25
    is_positive_fold_pass = positive_fold_ratio >= 0.75
    is_turnover_pass = turnover_annual_mean <= 3.0 and turnover_annual_max <= 5.0
    return {
        "strategy_id": strategy_id,
        "walk_forward_preset": preset_name,
        "status": "ok",
        "failure_reason": "",
        "fold_count": fold_count,
        "positive_fold_ratio": positive_fold_ratio,
        "annualized_return_mean": annualized_return_mean,
        "sharpe_mean": sharpe_mean,
        "max_drawdown_worst": max_drawdown_worst,
        "turnover_annual_mean": turnover_annual_mean,
        "turnover_annual_max": turnover_annual_max,
        "trades_total": int(trades.sum()) if trades.notna().any() else 0,
        "parameter_unique_count": int(params[params != ""].nunique()),
        "top_industry_avg_share_mean": float(top_industry_avg.mean()) if top_industry_avg.notna().any() else 0.0,
        "top_industry_p95_share_max": float(top_industry_p95.max()) if top_industry_p95.notna().any() else 0.0,
        "top_industry_max_share_max": float(top_industry_max.max()) if top_industry_max.notna().any() else 0.0,
        "top3_industries_avg_share_mean": float(top3_industry_avg.mean()) if top3_industry_avg.notna().any() else 0.0,
        "industry_violation_days_total": int(violation_days.fillna(0).sum()) if violation_days.notna().any() else 0,
        "is_return_pass": is_return_pass,
        "is_sharpe_pass": is_sharpe_pass,
        "is_drawdown_pass": is_drawdown_pass,
        "is_positive_fold_pass": is_positive_fold_pass,
        "is_turnover_pass": is_turnover_pass,
        "is_window_pass": bool(is_return_pass and is_sharpe_pass and is_drawdown_pass and is_positive_fold_pass and is_turnover_pass),
    }


def _build_constraint_review(matrix: pd.DataFrame, overfit: pd.DataFrame, preset_names: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    overfit_by_strategy = {}
    if not overfit.empty and "strategy_id" in overfit.columns:
        overfit_by_strategy = {str(row["strategy_id"]): row for _, row in overfit.iterrows()}

    for strategy_id, group in matrix.groupby("strategy_id", dropna=False):
        sid = str(strategy_id)
        ok_windows = group[group["status"] == "ok"]
        pass_count = int(pd.Series(group.get("is_window_pass", False)).astype(bool).sum())
        turnover_fail_count = int((pd.to_numeric(group.get("turnover_annual_mean"), errors="coerce") > 3.0).sum())
        missing_window_count = int((group["status"] != "ok").sum())
        industry_concentration_count = _industry_concentration_window_count(ok_windows)
        parameter_unique_total = int(pd.to_numeric(ok_windows.get("parameter_unique_count"), errors="coerce").fillna(0).sum()) if not ok_windows.empty else 0
        parameter_unstable_count = _parameter_unstable_window_count(ok_windows)
        overfit_row = overfit_by_strategy.get(sid)
        overfit_level = str(overfit_row["overfit_risk_level"]) if overfit_row is not None and "overfit_risk_level" in overfit_row else "unknown"
        overfit_score = int(overfit_row["overfit_score"]) if overfit_row is not None and "overfit_score" in overfit_row else 0
        action, reasons = _admission_action(
            pass_count=pass_count,
            preset_count=len(preset_names),
            turnover_fail_count=turnover_fail_count,
            missing_window_count=missing_window_count,
            parameter_unstable_count=parameter_unstable_count,
            industry_concentration_count=industry_concentration_count,
            overfit_level=overfit_level,
            group=group,
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
                "overfit_risk_level": overfit_level,
                "overfit_score": overfit_score,
                "parameter_unique_total": parameter_unique_total,
                "parameter_unstable_window_count": parameter_unstable_count,
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


def _industry_concentration_window_count(ok_windows: pd.DataFrame) -> int:
    if ok_windows.empty:
        return 0
    top1 = _numeric_column(ok_windows, "top_industry_avg_share_mean").fillna(0.0)
    top3 = _numeric_column(ok_windows, "top3_industries_avg_share_mean").fillna(0.0)
    violations = _numeric_column(ok_windows, "industry_violation_days_total").fillna(0)
    return int(((top1 > 0.35) | (top3 > 0.65) | (violations > 0)).sum())


def _admission_action(
    *,
    pass_count: int,
    preset_count: int,
    turnover_fail_count: int,
    missing_window_count: int,
    parameter_unstable_count: int,
    industry_concentration_count: int,
    overfit_level: str,
    group: pd.DataFrame,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if missing_window_count:
        reasons.append("one or more presets produced no valid folds")
    if overfit_level in {"critical", "high"}:
        reasons.append(f"overfit risk is {overfit_level}")
    if turnover_fail_count:
        reasons.append("annual turnover exceeds threshold in one or more windows")
    if parameter_unstable_count:
        reasons.append("selected parameters change too frequently in one or more windows")
    if industry_concentration_count:
        reasons.append("industry concentration exceeds audit threshold in one or more windows")
    positive_fail = int((_numeric_column(group, "positive_fold_ratio") < 0.75).sum())
    if positive_fail:
        reasons.append("positive fold ratio below 75% in one or more windows")
    if (
        pass_count == preset_count
        and overfit_level not in {"critical", "high"}
        and turnover_fail_count == 0
        and parameter_unstable_count == 0
        and industry_concentration_count == 0
    ):
        return "eligible_for_paper_review", reasons or ["all configured windows pass"]
    if pass_count == 1:
        reasons.append("only one preset passed; classify as research-only")
        return "research_only", reasons
    if overfit_level == "critical" or pass_count == 0:
        return "reject", reasons or ["no configured window passed"]
    return "retest", reasons or ["window robustness incomplete"]


def _write_report(path: Path, matrix: pd.DataFrame, review: pd.DataFrame, presets: list[str], strategies: list[str]) -> None:
    lines = [
        "# Strategy Admission Report",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Scope",
        "",
        f"- Presets: `{', '.join(presets)}`",
        f"- Strategies: `{', '.join(strategies)}`",
        "",
        "## Constraint Review",
        "",
        _md_table(
            ["strategy_id", "action", "window_pass", "turnover_fail", "param_unstable", "industry_conc", "overfit", "reasons"],
            [
                [
                    str(row["strategy_id"]),
                    str(row["admission_action"]),
                    f"{int(row['window_pass_count'])}/{int(row['window_count'])}",
                    str(int(row["turnover_fail_count"])),
                    str(int(row["parameter_unstable_window_count"])),
                    str(int(row.get("industry_concentration_window_count", 0))),
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
            ["strategy_id", "preset", "status", "folds", "ann", "sharpe", "mdd", "turnover", "top1_ind", "top3_ind", "pass"],
            [
                [
                    str(row["strategy_id"]),
                    str(row["walk_forward_preset"]),
                    str(row["status"]),
                    str(int(row["fold_count"])),
                    f"{float(row['annualized_return_mean']):.4f}",
                    f"{float(row['sharpe_mean']):.4f}",
                    f"{float(row['max_drawdown_worst']):.4f}",
                    f"{float(row['turnover_annual_mean']):.2f}",
                    f"{float(row.get('top_industry_avg_share_mean', 0.0)):.2f}",
                    f"{float(row.get('top3_industries_avg_share_mean', 0.0)):.2f}",
                    str(bool(row["is_window_pass"])),
                ]
                for _, row in matrix.iterrows()
            ],
        ),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |")
    return "\n".join(out)


def _numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return pd.to_numeric(df[column], errors="coerce")
