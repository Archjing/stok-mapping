from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from quant.data_access.connectivity import ConnectivityResult
from quant.data_governance.quality import QualityResult


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = []
    out.append("| " + " | ".join(headers) + " |")
    out.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)


def write_data_source_report(
    path: Path,
    connectivity: list[ConnectivityResult],
    quality: list[QualityResult],
    quality_summary: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con_rows = []
    for r in connectivity:
        con_rows.append(
            [
                r.source,
                r.target,
                "OK" if r.ok else "FAIL",
                str(r.rows),
                r.latest_date,
                r.error[:120],
            ]
        )
    q_rows = []
    for q in quality:
        q_rows.append(
            [
                q.symbol,
                str(q.rows),
                f"{q.missing_ratio:.4f}",
                str(q.ohlc_violation_count),
                str(q.non_positive_price_count),
                str(q.duplicate_date_count),
                q.latest_date,
                str(q.data_delay_days),
            ]
        )

    lines = [
        "# Phase 0 Data Source & Quality Report",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Connectivity",
        "",
        _md_table(
            ["source", "target", "status", "rows", "latest_date", "error"],
            con_rows,
        ),
        "",
        "## Quality Audit",
        "",
        _md_table(
            ["symbol", "rows", "missing_ratio", "ohlc_viol", "non_pos", "dup_date", "latest_date", "delay_days"],
            q_rows,
        ),
        "",
        "## Quality Summary",
        "",
        _md_table(
            ["metric", "value"],
            [[k, str(v)] for k, v in quality_summary.items()],
        ),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_walk_forward_report(path: Path, summary: dict[str, Any], folds_df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if not folds_df.empty:
        for _, row in folds_df.iterrows():
            rows.append(
                [
                    str(row["symbol"]),
                    str(int(row["fold"])),
                    str(row["train_start"]),
                    str(row["train_end"]),
                    str(row["valid_start"]),
                    str(row["valid_end"]),
                    f"{float(row['annualized_return']):.4f}",
                    f"{float(row['sharpe']):.4f}",
                    f"{float(row['max_drawdown']):.4f}",
                    f"{float(row['win_rate']):.4f}",
                    f"{float(row['turnover_annual']):.2f}",
                    str(int(row["trades"])),
                    str(row.get("selected_params", "")),
                ]
            )

    candidate_summary_rows = summary.get("candidate_summary_rows", []) or []
    summary_table_rows = [[k, str(v)] for k, v in summary.items() if k != "candidate_summary_rows"]
    candidate_rows = [
        [
            str(row.get("candidate", "")),
            f"{float(row.get('score', 0.0)):.4f}",
            f"{float(row.get('selection_score', row.get('score', 0.0))):.4f}",
            str(bool(row.get("eligible_for_selection", False))),
            str(row.get("governance_reason", "")),
            str(int(row.get("fold_count", 0))),
            str(int(row.get("symbol_count", 0))),
            str(row.get("panel_scope", "")),
            f"{float(row.get('annualized_return_mean', 0.0)):.4f}",
            f"{float(row.get('sharpe_mean', 0.0)):.4f}",
            f"{float(row.get('max_drawdown_mean', 0.0)):.4f}",
            f"{float(row.get('win_rate_mean', 0.0)):.4f}",
            f"{float(row.get('turnover_annual_mean', 0.0)):.2f}",
        ]
        for row in candidate_summary_rows
    ]

    lines = [
        "# Phase 0 Walk-Forward Report",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Universe Guard",
        "",
        (
            "Historical walk-forward uses a fold-local point-in-time universe when "
            "`universe_mode=point_in_time`; live watchlist and simulated account reports keep using the current daily universe."
        ),
        "",
        "## Summary",
        "",
        _md_table(["metric", "value"], summary_table_rows),
        "",
    ]
    if candidate_rows:
        lines.extend(
            [
                "## Candidate Summary",
                "",
                _md_table(
                    [
                        "candidate",
                        "score",
                        "selection_score",
                        "eligible",
                        "governance_reason",
                        "fold_count",
                        "symbol_count",
                        "panel_scope",
                        "annualized_return_mean",
                        "sharpe_mean",
                        "max_drawdown_mean",
                        "win_rate_mean",
                        "turnover_annual_mean",
                    ],
                    candidate_rows,
                ),
                "",
            ]
        )
    lines.extend(
        [
            "## Fold Details",
            "",
            _md_table(
                [
                    "symbol",
                    "fold",
                    "train_start",
                    "train_end",
                    "valid_start",
                    "valid_end",
                    "annual_ret",
                    "sharpe",
                    "max_dd",
                    "win_rate",
                    "turnover_annual",
                    "trades",
                    "selected_params",
                ],
                rows,
            ),
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_effectiveness_gate_report(path: Path, wf_summary: dict[str, Any], gate_cfg: dict[str, Any] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    gate_cfg = gate_cfg or {}
    sharpe = float(wf_summary.get("sharpe_mean", 0.0))
    mdd = float(wf_summary.get("max_drawdown_mean", 0.0))
    win = float(wf_summary.get("win_rate_mean", 0.0))
    decay = float(wf_summary.get("oos_return_decay_ratio", 0.0))
    ann = float(wf_summary.get("annualized_return_mean", 0.0))
    governance_ok = bool(wf_summary.get("selected_candidate_eligible", True))
    oos_fold_count = int(wf_summary.get("oos_fold_count", 0))
    oos_ann = float(wf_summary.get("oos_annualized_return_mean", 0.0))
    oos_sharpe = float(wf_summary.get("oos_sharpe_mean", 0.0))
    positive_fold_ratio = float(wf_summary.get("positive_fold_ratio", 0.0))
    negative_fold_count = int(wf_summary.get("negative_fold_count", 0))
    min_fold_ann = float(wf_summary.get("min_fold_annualized_return", 0.0))
    oos_positive_fold_ratio = float(wf_summary.get("oos_positive_fold_ratio", 0.0))

    annualized_return_min = float(gate_cfg.get("annualized_return_min", 0.0))
    sharpe_min = float(gate_cfg.get("sharpe_min", 0.5))
    max_drawdown_min = float(gate_cfg.get("max_drawdown_min", -0.25))
    win_rate_min = float(gate_cfg.get("win_rate_min", 0.45))
    oos_return_decay_ratio_max = float(gate_cfg.get("oos_return_decay_ratio_max", 0.30))
    min_oos_fold_count = int(gate_cfg.get("min_oos_fold_count", 1))
    oos_annualized_return_min = float(gate_cfg.get("oos_annualized_return_min", 0.0))
    oos_sharpe_min = float(gate_cfg.get("oos_sharpe_min", 0.5))
    min_positive_fold_ratio = float(gate_cfg.get("min_positive_fold_ratio", 0.0))
    max_negative_fold_count = int(gate_cfg.get("max_negative_fold_count", 10**9))
    min_fold_annualized_return_min = float(gate_cfg.get("min_fold_annualized_return_min", -1.0))
    min_oos_positive_fold_ratio = float(gate_cfg.get("min_oos_positive_fold_ratio", 0.0))

    base_gates = [
        ("selected_candidate_eligible == True", governance_ok),
        (f"annualized_return_mean > {annualized_return_min:.2f}", ann > annualized_return_min),
        (f"sharpe_mean > {sharpe_min:.2f}", sharpe > sharpe_min),
        (f"max_drawdown_mean > {max_drawdown_min:.2f}", mdd > max_drawdown_min),
        (f"win_rate_mean > {win_rate_min:.2f}", win > win_rate_min),
        (f"oos_return_decay_ratio < {oos_return_decay_ratio_max:.2f}", decay < oos_return_decay_ratio_max),
    ]
    robustness_gates = [
        (f"oos_fold_count >= {min_oos_fold_count}", oos_fold_count >= min_oos_fold_count),
        (f"oos_annualized_return_mean > {oos_annualized_return_min:.2f}", oos_ann > oos_annualized_return_min),
        (f"oos_sharpe_mean > {oos_sharpe_min:.2f}", oos_sharpe > oos_sharpe_min),
        (f"positive_fold_ratio >= {min_positive_fold_ratio:.2f}", positive_fold_ratio >= min_positive_fold_ratio),
        (f"negative_fold_count <= {max_negative_fold_count}", negative_fold_count <= max_negative_fold_count),
        (f"min_fold_annualized_return > {min_fold_annualized_return_min:.2f}", min_fold_ann > min_fold_annualized_return_min),
        (f"oos_positive_fold_ratio >= {min_oos_positive_fold_ratio:.2f}", oos_positive_fold_ratio >= min_oos_positive_fold_ratio),
    ]
    gates = base_gates + robustness_gates
    passed = all(ok for _, ok in gates)

    lines = [
        "# Phase 0 Strategy Effectiveness Gate",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Overall verdict: {'PASS' if passed else 'FAIL'}",
        "",
        "## Base Gate",
        "",
        _md_table(["gate", "status"], [[name, "PASS" if ok else "FAIL"] for name, ok in base_gates]),
        "",
        "## Robustness Gate",
        "",
        _md_table(["gate", "status"], [[name, "PASS" if ok else "FAIL"] for name, ok in robustness_gates]),
        "",
        "## Snapshot",
        "",
        _md_table(["metric", "value"], [[k, str(v)] for k, v in wf_summary.items()]),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_cost_sensitivity_report(path: Path, sensitivity_df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[list[str]] = []
    if not sensitivity_df.empty:
        for _, row in sensitivity_df.iterrows():
            rows.append(
                [
                    str(row.get("scenario", "")),
                    str(row.get("candidate", "")),
                    str(row.get("selected_candidate", "")),
                    str(bool(row.get("eligible_for_selection", False))),
                    str(row.get("governance_reason", "")),
                    str(int(row.get("fold_count", 0))),
                    str(row.get("panel_scope", "")),
                    f"{float(row.get('slippage', 0.0)):.5f}",
                    f"{float(row.get('commission', 0.0)):.5f}",
                    f"{float(row.get('stamp_duty_sell', 0.0)):.5f}",
                    f"{float(row.get('annualized_return_mean', 0.0)):.4f}",
                    f"{float(row.get('sharpe_mean', 0.0)):.4f}",
                    f"{float(row.get('max_drawdown_mean', 0.0)):.4f}",
                    f"{float(row.get('win_rate_mean', 0.0)):.4f}",
                    f"{float(row.get('turnover_annual_mean', 0.0)):.2f}",
                ]
            )

    lines = [
        "# Phase 0 Cost Sensitivity Report",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        _md_table(
            [
                "scenario",
                "candidate",
                "selected_candidate",
                "eligible",
                "governance_reason",
                "fold_count",
                "panel_scope",
                "slippage",
                "commission",
                "stamp_duty_sell",
                "annualized_return_mean",
                "sharpe_mean",
                "max_drawdown_mean",
                "win_rate_mean",
                "turnover_annual_mean",
            ],
            rows,
        ),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
