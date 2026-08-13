"""Strategy failure-attribution loop: repair hypotheses and re-verification plan.

Turns the existing fold-level market-context diagnostic (market_context_label)
into a closed loop: each fold's failure label maps to one or more *repairable*
hypotheses, each with a concrete verification step and priority.  A strategy
aggregate then classifies the evidence as proven / weakly-supported /
unproven so the next admission run is driven by an explicit hypothesis, not
"tune until it passes".

The loop is diagnostic only: it never derives a trading rule and never treats
correlation as causation (see archive plan module three).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

# ── fold-label → repair hypotheses ─────────────────────────────────────

@dataclass(frozen=True)
class RepairHypothesis:
    code: str
    label: str
    hypothesis: str
    verification: str
    priority: str  # "P0" | "P1" | "P2"
    evidence_class: str  # "proven" | "weak" | "unproven"


# Each market_context_label maps to hypotheses with concrete re-verification.
_LABEL_HYPOTHESES: dict[str, list[tuple[str, str, str, str]]] = {
    "relative_lag_in_strong_benchmark_context": [
        (
            "H-relative-lag",
            "策略在强基准环境下跑输，疑为行业/风格逆风而非策略失效",
            "对照 fold 持仓的行业与风格暴露，确认是否集中在对强基准不利的板块；再跑 factor_effectiveness 看 IC 是否在强基准月份转负",
            "P0",
        ),
    ],
    "absolute_loss_but_benchmark_weak_context": [
        (
            "H-weak-market-resilience",
            "弱市绝对亏损但相对跑赢，是防御性证据而非 alpha 失败",
            "保留为弱市韧性证据；不据此放宽准入，仅确认回撤是否在 gate 内",
            "P2",
        ),
    ],
    "risk_context_pressure": [
        (
            "H-risk-scaling",
            "亏损可能来自 risk-off 高波动期未做仓位缩放",
            "仅在多 fold 复现该模式时，立项固定风险缩放消融测试（加/不加 risk scale 对照）",
            "P1",
        ),
        (
            "H-trend-gate",
            "趋势转弱或高波动期间策略未降低暴露",
            "验证：在 risk_context_pressure 的 fold 上，检查 exposure 是否应随 trend/vol 下调",
            "P1",
        ),
    ],
    "clean_positive_context": [
        (
            "H-control-fold",
            "正收益 fold 是控制组，不应拟合新规则",
            "禁止对该 fold 拟合参数；仅作 OOS 一致性对照",
            "P2",
        ),
    ],
    "mixed_or_unresolved_context": [
        (
            "H-mixed-evidence",
            "fold 证据混杂，无法归因到单一市场环境",
            "扩大 fold 数或延长样本后再归因；不据此修改策略",
            "P2",
        ),
    ],
    "benchmark_context_unavailable": [
        (
            "H-context-data-gap",
            "基准指数上下文缺失，归因无法成立",
            "先补齐 benchmark index 日线，再重跑 market_context 与 attribution loop",
            "P0",
        ),
    ],
}


def _priority_order(priority: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2}.get(priority, 3)


def _evidence_class(label: str) -> str:
    """Map a fold label to a claim-strength class.

    Only patterns that repeat across multiple folds are ever 'proven'; a single
    fold is at best 'weak'.  The caller (aggregate) upgrades to 'proven' only
    when the same hypothesis appears in >= 2 independent folds.
    """
    if label in {"relative_lag_in_strong_benchmark_context", "risk_context_pressure"}:
        return "weak"
    if label == "clean_positive_context":
        return "proven"  # control fold is established evidence, not a hypothesis
    if label == "absolute_loss_but_benchmark_weak_context":
        return "weak"
    if label == "benchmark_context_unavailable":
        return "unproven"
    return "unproven"


def build_repair_hypotheses(context: pd.DataFrame) -> pd.DataFrame:
    """Expand fold-level market_context_label rows into hypothesis rows."""
    if context.empty:
        return pd.DataFrame(columns=[
            "strategy_id", "walk_forward_preset", "fold", "valid_start", "valid_end",
            "market_context_label", "hypothesis_code", "hypothesis", "verification",
            "priority", "evidence_class",
        ])
    rows: list[dict[str, Any]] = []
    for _, fold in context.iterrows():
        label = str(fold.get("market_context_label", "mixed_or_unresolved_context"))
        for code, hypothesis, verification, priority in _LABEL_HYPOTHESES.get(label, []):
            rows.append({
                "strategy_id": fold.get("strategy_id"),
                "walk_forward_preset": fold.get("walk_forward_preset"),
                "fold": fold.get("fold"),
                "valid_start": fold.get("valid_start"),
                "valid_end": fold.get("valid_end"),
                "market_context_label": label,
                "hypothesis_code": code,
                "hypothesis": hypothesis,
                "verification": verification,
                "priority": priority,
                "evidence_class": _evidence_class(label),
            })
    result = pd.DataFrame(rows)
    if not result.empty:
        result["priority_order"] = result["priority"].map(_priority_order)
        result = result.sort_values(
            ["strategy_id", "walk_forward_preset", "priority_order", "fold"],
            kind="stable",
        ).drop(columns="priority_order")
    return result.reset_index(drop=True)


def build_verification_plan(hypotheses: pd.DataFrame) -> pd.DataFrame:
    """Aggregate hypotheses per strategy into a ranked re-verification plan.

    A hypothesis is upgraded to 'proven' when it appears in >= 2 distinct folds;
    'weak' when it appears once; 'unproven' when it is a data gap.
    """
    if hypotheses.empty:
        return pd.DataFrame(columns=[
            "strategy_id", "walk_forward_preset", "hypothesis_code", "hypothesis",
            "verification", "priority", "distinct_folds", "evidence_class",
        ])
    grouped = (
        hypotheses.groupby(
            ["strategy_id", "walk_forward_preset", "hypothesis_code", "hypothesis", "verification", "priority"],
            dropna=False,
        )
        .agg(distinct_folds=("fold", "nunique"))
        .reset_index()
    )
    grouped["evidence_class"] = grouped["distinct_folds"].map(
        lambda n: "proven" if n >= 2 else "weak"
    )
    grouped["priority_order"] = grouped["priority"].map(_priority_order)
    grouped = grouped.sort_values(
        ["strategy_id", "walk_forward_preset", "priority_order", "distinct_folds"],
        ascending=[True, True, True, False],
        kind="stable",
    ).drop(columns="priority_order")
    return grouped.reset_index(drop=True)


def run_attribution_loop(
    *,
    market_context_csv: Path,
    output_dir: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, Path, Path]:
    """Build repair hypotheses and a re-verification plan from market-context CSV.

    Reads a ``strategy_market_context_diagnostic.csv`` (output of
    ``run_strategy_market_context``), writes ``strategy_attribution_loop_hypotheses.csv``
    and ``strategy_attribution_loop_verification.csv``, and returns both frames
    with their paths.
    """
    output_dir = output_dir or market_context_csv.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    context = pd.read_csv(market_context_csv)
    hypotheses = build_repair_hypotheses(context)
    plan = build_verification_plan(hypotheses)
    hypo_path = output_dir / "strategy_attribution_loop_hypotheses.csv"
    plan_path = output_dir / "strategy_attribution_loop_verification.csv"
    hypotheses.to_csv(hypo_path, index=False)
    plan.to_csv(plan_path, index=False)
    return hypotheses, plan, hypo_path, plan_path
