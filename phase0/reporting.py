from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from phase0.data_sources import ConnectivityResult
from phase0.quality import QualityResult


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


def write_effectiveness_gate_report(path: Path, wf_summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sharpe = float(wf_summary.get("sharpe_mean", 0.0))
    mdd = float(wf_summary.get("max_drawdown_mean", 0.0))
    win = float(wf_summary.get("win_rate_mean", 0.0))
    decay = float(wf_summary.get("oos_return_decay_ratio", 0.0))
    ann = float(wf_summary.get("annualized_return_mean", 0.0))
    governance_ok = bool(wf_summary.get("selected_candidate_eligible", True))

    gates = [
        ("selected_candidate_eligible == True", governance_ok),
        ("annualized_return_mean > 0", ann > 0),
        ("sharpe_mean > 0.5", sharpe > 0.5),
        ("max_drawdown_mean > -0.25", mdd > -0.25),
        ("win_rate_mean > 0.45", win > 0.45),
        ("oos_return_decay_ratio < 0.30", decay < 0.30),
    ]
    passed = all(ok for _, ok in gates)

    lines = [
        "# Phase 0 Strategy Effectiveness Gate",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Overall verdict: {'PASS' if passed else 'FAIL'}",
        "",
        _md_table(["gate", "status"], [[name, "PASS" if ok else "FAIL"] for name, ok in gates]),
        "",
        "## Snapshot",
        "",
        _md_table(["metric", "value"], [[k, str(v)] for k, v in wf_summary.items()]),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
