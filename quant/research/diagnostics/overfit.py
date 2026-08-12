from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from quant.reporting.paths import report_path


@dataclass(frozen=True)
class OverfitDiagnosticResult:
    csv_path: Path
    md_path: Path
    rows: int
    selected_candidate: str
    selected_risk_level: str


def run_overfit_diagnostic(
    *,
    config: dict[str, Any],
    root: Path,
    candidates_path: Path | None = None,
    folds_path: Path | None = None,
    output_dir: Path | None = None,
    standard_names: bool = False,
) -> OverfitDiagnosticResult:
    candidates_path = candidates_path or report_path(root=root, config=config, category="phase0", parts=("phase0_walk_forward_candidates.csv",))
    folds_path = folds_path or report_path(root=root, config=config, category="phase0", parts=("phase0_walk_forward_folds.csv",))
    output_dir = output_dir or report_path(root=root, config=config, category="phase0", parts=("overfit_diagnostic",))
    output_dir.mkdir(parents=True, exist_ok=True)
    if standard_names:
        csv_path = output_dir / "overfit__diagnostic.csv"
        md_path = output_dir / "overfit__diagnostic.md"
    else:
        csv_path = output_dir / "strategy_overfit_diagnostic.csv"
        md_path = output_dir / "strategy_overfit_diagnostic.md"

    if not candidates_path.exists():
        raise FileNotFoundError(f"missing candidates CSV: {candidates_path}")
    candidates = pd.read_csv(candidates_path)
    folds = pd.read_csv(folds_path) if folds_path.exists() else candidates.copy()
    selected = _selected_candidate(config, candidates)
    diagnostic = _diagnose(candidates, folds, selected)
    diagnostic.to_csv(csv_path, index=False)
    _write_md(md_path, diagnostic, candidates_path=candidates_path, folds_path=folds_path, selected=selected)
    selected_row = diagnostic[diagnostic["strategy_id"] == selected]
    selected_risk = str(selected_row["overfit_risk_level"].iloc[0]) if not selected_row.empty else "unknown"
    return OverfitDiagnosticResult(
        csv_path=csv_path,
        md_path=md_path,
        rows=int(len(diagnostic)),
        selected_candidate=selected,
        selected_risk_level=selected_risk,
    )


def _selected_candidate(config: dict[str, Any], candidates: pd.DataFrame) -> str:
    for col in ["selected_candidate", "strategy_id", "candidate"]:
        if col in candidates.columns and "selected_candidate" in candidates.columns:
            vals = candidates["selected_candidate"].dropna().astype(str)
            if not vals.empty and vals.iloc[0]:
                return vals.iloc[0]
    configured = config.get("walk_forward", {}).get("selected_candidate")
    if configured:
        return str(configured)
    if "is_selected_candidate" in candidates.columns:
        selected_rows = candidates[candidates["is_selected_candidate"].astype(str).str.lower().isin({"true", "1"})]
        if not selected_rows.empty:
            return str(selected_rows.iloc[0].get("strategy_id", selected_rows.iloc[0].get("candidate", "")))
    return str(candidates.iloc[0].get("strategy_id", candidates.iloc[0].get("candidate", ""))) if not candidates.empty else ""


def _diagnose(candidates: pd.DataFrame, folds: pd.DataFrame, selected: str) -> pd.DataFrame:
    source = candidates if not candidates.empty else folds
    strategy_col = "strategy_id" if "strategy_id" in source.columns else "candidate"
    rows: list[dict[str, Any]] = []
    for strategy_id, group in source.groupby(strategy_col, dropna=False):
        sid = str(strategy_id)
        metrics = _metrics(group)
        score, reasons = _score(metrics)
        risk = _risk_level(score)
        rows.append(
            {
                "strategy_id": sid,
                "overfit_risk_level": risk,
                "overfit_score": score,
                "recommended_action": _recommended_action(risk),
                "is_selected_candidate": sid == selected,
                "fold_count": metrics["fold_count"],
                "positive_fold_ratio": metrics["positive_fold_ratio"],
                "worst_fold_annualized_return": metrics["worst_fold_annualized_return"],
                "annualized_return_mean": metrics["annualized_return_mean"],
                "sharpe_mean": metrics["sharpe_mean"],
                "max_drawdown_worst": metrics["max_drawdown_worst"],
                "turnover_annual_mean": metrics["turnover_annual_mean"],
                "parameter_unique_count": metrics["parameter_unique_count"],
                "last_fold_lift_risk": metrics["last_fold_lift_risk"],
                "last_fold_lift_preset": metrics["last_fold_lift_preset"],
                "last_fold_annualized_return": metrics["last_fold_annualized_return"],
                "prior_fold_annualized_return_mean": metrics["prior_fold_annualized_return_mean"],
                "last_fold_lift": metrics["last_fold_lift"],
                "is_oos_pass": metrics["annualized_return_mean"] > 0 and metrics["sharpe_mean"] > 0.5,
                "is_fold_stable": metrics["positive_fold_ratio"] >= 0.5 and metrics["worst_fold_annualized_return"] > -0.2,
                "is_parameter_stable": metrics["parameter_unique_count"] <= max(2, metrics["fold_count"] // 2 + 1),
                "is_cost_robust": "not_available",
                "is_market_regime_stable": "not_available",
                "main_risk_reasons": "; ".join(reasons) if reasons else "no major MVP risk flag",
            }
        )
    out = pd.DataFrame(rows).sort_values(["is_selected_candidate", "overfit_score"], ascending=[False, True])
    return out.reset_index(drop=True)


def _metrics(group: pd.DataFrame) -> dict[str, Any]:
    ann = pd.to_numeric(group.get("annualized_return"), errors="coerce")
    sharpe = pd.to_numeric(group.get("sharpe"), errors="coerce")
    mdd = pd.to_numeric(group.get("max_drawdown"), errors="coerce")
    turnover = pd.to_numeric(group.get("turnover_annual"), errors="coerce")
    params = group.get("selected_params", pd.Series(dtype=object)).fillna("").astype(str)
    fold_count = int(len(group))
    positive = float((ann > 0).mean()) if fold_count else 0.0
    last_fold = _last_fold_lift_metrics(group)
    return {
        "fold_count": fold_count,
        "positive_fold_ratio": positive,
        "worst_fold_annualized_return": float(ann.min()) if ann.notna().any() else 0.0,
        "annualized_return_mean": float(ann.mean()) if ann.notna().any() else 0.0,
        "sharpe_mean": float(sharpe.mean()) if sharpe.notna().any() else 0.0,
        "max_drawdown_worst": float(mdd.min()) if mdd.notna().any() else 0.0,
        "turnover_annual_mean": float(turnover.mean()) if turnover.notna().any() else 0.0,
        "parameter_unique_count": int(params[params != ""].nunique()),
        **last_fold,
    }


def _last_fold_lift_metrics(group: pd.DataFrame) -> dict[str, Any]:
    default = {
        "last_fold_lift_risk": False,
        "last_fold_lift_preset": "",
        "last_fold_annualized_return": 0.0,
        "prior_fold_annualized_return_mean": 0.0,
        "last_fold_lift": 0.0,
    }
    if "annualized_return" not in group.columns or "fold" not in group.columns:
        return default

    working = group.copy()
    working["annualized_return"] = pd.to_numeric(working["annualized_return"], errors="coerce")
    working["fold"] = pd.to_numeric(working["fold"], errors="coerce")
    working = working.dropna(subset=["annualized_return", "fold"])
    if working.empty:
        return default

    preset_col = "walk_forward_preset" if "walk_forward_preset" in working.columns else None
    groups = working.groupby(preset_col, dropna=False) if preset_col else [("", working)]
    strongest = default.copy()
    for preset, preset_group in groups:
        ordered = preset_group.sort_values("fold")
        if len(ordered) < 3:
            continue
        last = ordered.iloc[-1]
        prior = ordered.iloc[:-1]
        prior_mean = float(prior["annualized_return"].mean())
        last_return = float(last["annualized_return"])
        lift = last_return - prior_mean
        risky = bool(lift >= 0.10 and last_return > 0 and prior_mean < 0.03)
        if lift > float(strongest["last_fold_lift"]):
            strongest = {
                "last_fold_lift_risk": risky,
                "last_fold_lift_preset": "" if preset is None else str(preset),
                "last_fold_annualized_return": last_return,
                "prior_fold_annualized_return_mean": prior_mean,
                "last_fold_lift": lift,
            }
        elif risky and not bool(strongest["last_fold_lift_risk"]):
            strongest = {
                "last_fold_lift_risk": True,
                "last_fold_lift_preset": "" if preset is None else str(preset),
                "last_fold_annualized_return": last_return,
                "prior_fold_annualized_return_mean": prior_mean,
                "last_fold_lift": lift,
            }
    return strongest


def _score(metrics: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    if metrics["fold_count"] < 4:
        score += 20
        reasons.append("OOS fold count below governance floor")
    if metrics["positive_fold_ratio"] < 0.5:
        score += 25
        reasons.append("positive OOS fold ratio below 50%")
    elif metrics["positive_fold_ratio"] < 0.75:
        score += 12
        reasons.append("positive OOS fold ratio below 75%")
    if metrics["worst_fold_annualized_return"] < -0.2:
        score += 20
        reasons.append("worst fold annualized return below -20%")
    if metrics["sharpe_mean"] < 0.5:
        score += 15
        reasons.append("mean Sharpe below 0.5")
    if metrics["annualized_return_mean"] <= 0:
        score += 15
        reasons.append("mean annualized return is non-positive")
    if metrics["turnover_annual_mean"] > 5:
        score += 10
        reasons.append("high annual turnover increases cost sensitivity")
    if metrics["parameter_unique_count"] > max(2, metrics["fold_count"] // 2 + 1):
        score += 10
        reasons.append("selected parameters change frequently across folds")
    if metrics["last_fold_lift_risk"]:
        score += 15
        reasons.append("last fold materially lifts results")
    return min(score, 100), reasons


def _risk_level(score: int) -> str:
    if score >= 75:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def _recommended_action(risk: str) -> str:
    return {
        "low": "keep",
        "medium": "observe",
        "high": "retest",
        "critical": "reject",
    }[risk]


def _write_md(
    path: Path,
    diagnostic: pd.DataFrame,
    *,
    candidates_path: Path,
    folds_path: Path,
    selected: str,
) -> None:
    lines = [
        "# 策略过拟合诊断报告",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"- Candidates: `{candidates_path}`",
        f"- Folds: `{folds_path}`",
        f"- Selected candidate: `{selected}`",
        "",
        "## MVP 结论",
        "",
        "第一版只读取现有 walk-forward 产物，不重新回测，不做参数扰动。`not_available` 字段表示该维度需要后续输入产物。",
        "",
        "## Results",
        "",
        "| strategy_id | risk | score | action | fold_count | positive_fold_ratio | last_fold_lift_risk | last_fold_lift | main_risk_reasons |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, row in diagnostic.iterrows():
        reasons = str(row["main_risk_reasons"]).replace("|", "\\|")
        lines.append(
            f"| {row['strategy_id']} | {row['overfit_risk_level']} | {row['overfit_score']} | "
            f"{row['recommended_action']} | {row['fold_count']} | {float(row['positive_fold_ratio']):.4f} | "
            f"{row['last_fold_lift_risk']} | {float(row['last_fold_lift']):.4f} | {reasons} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
