from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0.config import load_config
from phase0.reporting.paths import report_config_path
from scripts.export_strategy_bill import (
    _default_report_strategy_id,
    _execution_settings,
    export_strategy_bill,
)


DEFAULT_OUTPUT_DIR = "live_execution_backtest"
DEFAULT_BILL_OUTPUT = f"{DEFAULT_OUTPUT_DIR}/live_execution_bill.csv"
DEFAULT_DAILY_OUTPUT = f"{DEFAULT_OUTPUT_DIR}/live_execution_daily_assets.csv"
DEFAULT_PREVIEW_OUTPUT = f"{DEFAULT_OUTPUT_DIR}/live_execution_bill_preview.html"
DEFAULT_FOLD_OUTPUT = f"{DEFAULT_OUTPUT_DIR}/live_execution_walk_forward_folds.csv"
DEFAULT_REPORT_OUTPUT = f"{DEFAULT_OUTPUT_DIR}/live_execution_effectiveness_report.md"


def _deep_update(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_update(out[key], value)
        else:
            out[key] = value
    return out


def _live_backtest_settings(config: dict[str, Any]) -> dict[str, Any]:
    cfg = config.get("live_execution_backtest", {})
    return {
        "name": str(cfg.get("name", "实盘仿真回测")),
        "output_dir": str(cfg.get("output_dir", DEFAULT_OUTPUT_DIR)),
        "bill_output": str(cfg.get("bill_output", DEFAULT_BILL_OUTPUT)),
        "daily_output": str(cfg.get("daily_output", DEFAULT_DAILY_OUTPUT)),
        "preview_output": str(cfg.get("preview_output", DEFAULT_PREVIEW_OUTPUT)),
        "fold_output": str(cfg.get("fold_output", DEFAULT_FOLD_OUTPUT)),
        "report_output": str(cfg.get("report_output", DEFAULT_REPORT_OUTPUT)),
        "gate_source": str(cfg.get("gate_source", "account_daily_assets")),
    }


def _resolve_cli_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _profile_settings(config: dict[str, Any], profile: str) -> dict[str, Any]:
    live_cfg = config.get("live_execution_backtest", {})
    profiles = live_cfg.get("profiles", {})
    selected = profiles.get(profile, {})
    if not selected:
        known = ", ".join(sorted(str(name) for name in profiles)) or "none"
        raise ValueError(f"live_execution_backtest profile '{profile}' is not configured; known profiles: {known}")
    return {
        "profile": profile,
        "name": str(selected.get("name", profile)),
        "walk_forward": dict(selected.get("walk_forward", {})),
        "execution": dict(selected.get("execution", {})),
    }


def _apply_profile_to_config(
    config: dict[str, Any],
    profile_cfg: dict[str, Any],
    *,
    slippage: float | None = None,
    commission: float | None = None,
    stamp_duty_sell: float | None = None,
    price_mode: str | None = None,
    lot_size: int | None = None,
    max_participation_rate: float | None = None,
    enable_limit_check: bool | None = None,
    enable_suspension_check: bool | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    effective_config = _deep_update(config, {"walk_forward": profile_cfg.get("walk_forward", {}), "execution": profile_cfg.get("execution", {})})
    walk_forward_overrides: dict[str, Any] = {}
    execution_overrides: dict[str, Any] = {}
    if slippage is not None:
        walk_forward_overrides["slippage"] = float(slippage)
    if commission is not None:
        walk_forward_overrides["commission"] = float(commission)
    if stamp_duty_sell is not None:
        walk_forward_overrides["stamp_duty_sell"] = float(stamp_duty_sell)
    if price_mode is not None:
        execution_overrides["price_mode"] = str(price_mode)
    if lot_size is not None:
        execution_overrides["lot_size"] = int(lot_size)
    if max_participation_rate is not None:
        execution_overrides["max_participation_rate"] = float(max_participation_rate)
    if enable_limit_check is not None:
        execution_overrides["enable_limit_check"] = bool(enable_limit_check)
    if enable_suspension_check is not None:
        execution_overrides["enable_suspension_check"] = bool(enable_suspension_check)
    if walk_forward_overrides:
        effective_config.setdefault("walk_forward", {}).update(walk_forward_overrides)
    if execution_overrides:
        effective_config.setdefault("execution", {}).update(execution_overrides)
    return effective_config, walk_forward_overrides, execution_overrides


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)


def _annualized_return(returns: pd.Series) -> float:
    returns = returns.dropna()
    if returns.empty:
        return 0.0
    total_return = float((1.0 + returns).prod() - 1.0)
    years = max(len(returns) / 252.0, 1.0 / 252.0)
    return float((1.0 + total_return) ** (1.0 / years) - 1.0)


def _sharpe(returns: pd.Series) -> float:
    returns = returns.dropna()
    if len(returns) < 2:
        return 0.0
    std = float(returns.std(ddof=1))
    if std == 0.0 or not np.isfinite(std):
        return 0.0
    return float((returns.mean() / std) * np.sqrt(252.0))


def _max_drawdown(returns: pd.Series) -> float:
    returns = returns.dropna()
    if returns.empty:
        return 0.0
    equity = (1.0 + returns).cumprod()
    peak = equity.cummax()
    return float((equity / peak - 1.0).min())


def _fold_metrics(daily: pd.DataFrame, bill: pd.DataFrame, *, strategy_id: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    bill_by_fold = bill.groupby("折号") if not bill.empty and "折号" in bill.columns else {}
    for fold, fold_df in daily.groupby("fold", sort=True):
        one = fold_df.copy().sort_values("date").reset_index(drop=True)
        one["account_return"] = one["account_total_assets"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
        exposure = pd.to_numeric(one.get("exposure", 0.0), errors="coerce").fillna(0.0)
        realized_returns = one.loc[exposure > 0, "account_return"]
        fold_bill = bill_by_fold.get_group(fold) if hasattr(bill_by_fold, "groups") and fold in bill_by_fold.groups else pd.DataFrame()
        executed = (
            fold_bill[fold_bill["交易状态"].isin(["全部成交", "部分成交"])]
            if not fold_bill.empty and "交易状态" in fold_bill.columns
            else fold_bill
        )
        rows.append(
            {
                "symbol": "PORTFOLIO_ACCOUNT_EXECUTION",
                "fold": int(fold),
                "valid_start": one["date"].iloc[0].date().isoformat(),
                "valid_end": one["date"].iloc[-1].date().isoformat(),
                "annualized_return": _annualized_return(one["account_return"]),
                "sharpe": _sharpe(one["account_return"]),
                "max_drawdown": _max_drawdown(one["account_return"]),
                "win_rate": float((realized_returns > 0).mean()) if len(realized_returns) else 0.0,
                "turnover_annual": 0.0,
                "trades": int(len(executed)),
                "passed_min_samples": True,
                "selected_params": str(one["selected_params"].dropna().iloc[0]) if "selected_params" in one.columns and one["selected_params"].notna().any() else "",
                "candidate": f"{strategy_id}_account_execution_v2",
                "panel_scope": "portfolio",
                "final_account_assets": float(one["account_total_assets"].iloc[-1]),
                "min_cash_assets": float(one["cash_assets"].min()) if "cash_assets" in one.columns else 0.0,
                "unfilled_orders": int(pd.to_numeric(one.get("unfilled_orders", 0), errors="coerce").fillna(0).sum()),
                "stale_valuation_positions": int(pd.to_numeric(one.get("stale_valuation_positions", 0), errors="coerce").fillna(0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _summary_from_folds(
    folds: pd.DataFrame,
    governance_cfg: dict[str, Any],
    *,
    strategy_id: str,
    bill: pd.DataFrame | None = None,
    daily: pd.DataFrame | None = None,
) -> dict[str, Any]:
    fold_count = int(len(folds))
    min_portfolio_fold_count = int(governance_cfg.get("min_portfolio_fold_count", 4))
    selected_candidate_eligible = fold_count >= min_portfolio_fold_count
    summary: dict[str, Any] = {
        "status": "ok" if fold_count else "failed",
        "selected_candidate": f"{strategy_id}_account_execution_v2",
        "selected_candidate_eligible": selected_candidate_eligible,
        "selected_candidate_governance_reason": "eligible" if selected_candidate_eligible else f"portfolio_fold_count<{min_portfolio_fold_count}",
        "fold_count": fold_count,
        "symbol_count": 1 if fold_count else 0,
        "annualized_return_mean": float(folds["annualized_return"].mean()) if fold_count else 0.0,
        "sharpe_mean": float(folds["sharpe"].mean()) if fold_count else 0.0,
        "max_drawdown_mean": float(folds["max_drawdown"].mean()) if fold_count else 0.0,
        "win_rate_mean": float(folds["win_rate"].mean()) if fold_count else 0.0,
        "turnover_annual_mean": float(folds["turnover_annual"].mean()) if fold_count else 0.0,
        "positive_fold_count": int((folds["annualized_return"] > 0).sum()) if fold_count else 0,
        "negative_fold_count": int((folds["annualized_return"] < 0).sum()) if fold_count else 0,
        "positive_fold_ratio": float((folds["annualized_return"] > 0).mean()) if fold_count else 0.0,
        "min_fold_annualized_return": float(folds["annualized_return"].min()) if fold_count else 0.0,
        "min_fold_sharpe": float(folds["sharpe"].min()) if fold_count else 0.0,
    }
    if fold_count:
        cutoff = max(1, int(fold_count * 0.2))
        ordered = folds.sort_values("valid_end")
        oos = ordered.tail(cutoff)
        train_like = ordered.head(fold_count - cutoff)
        summary["oos_fold_count"] = int(len(oos))
        summary["oos_annualized_return_mean"] = float(oos["annualized_return"].mean())
        summary["oos_sharpe_mean"] = float(oos["sharpe"].mean())
        summary["oos_positive_fold_count"] = int((oos["annualized_return"] > 0).sum())
        summary["oos_positive_fold_ratio"] = float((oos["annualized_return"] > 0).mean()) if len(oos) else 0.0
        summary["oos_min_fold_annualized_return"] = float(oos["annualized_return"].min()) if len(oos) else 0.0
        if len(train_like):
            base = float(train_like["annualized_return"].mean())
            oos_value = float(oos["annualized_return"].mean())
            summary["oos_return_decay_ratio"] = float((base - oos_value) / abs(base)) if base else 0.0
        else:
            summary["oos_return_decay_ratio"] = 0.0
    else:
        summary["oos_fold_count"] = 0
        summary["oos_annualized_return_mean"] = 0.0
        summary["oos_sharpe_mean"] = 0.0
        summary["oos_positive_fold_count"] = 0
        summary["oos_positive_fold_ratio"] = 0.0
        summary["oos_min_fold_annualized_return"] = 0.0
        summary["oos_return_decay_ratio"] = 0.0
    bill = bill if bill is not None else pd.DataFrame()
    daily = daily if daily is not None else pd.DataFrame()
    executable_order_count = int(len(bill)) if not bill.empty else 0
    if executable_order_count and "交易状态" in bill.columns:
        statuses = bill["交易状态"].fillna("")
        unfilled_or_partial = statuses.isin(["未成交", "部分成交"])
        partial = statuses.eq("部分成交")
        summary["executable_order_count"] = executable_order_count
        summary["unfilled_or_partial_order_count"] = int(unfilled_or_partial.sum())
        summary["unfilled_or_partial_order_ratio"] = float(unfilled_or_partial.mean())
        summary["partial_fill_order_count"] = int(partial.sum())
        summary["partial_fill_order_ratio"] = float(partial.mean())
    else:
        summary["executable_order_count"] = executable_order_count
        summary["unfilled_or_partial_order_count"] = 0
        summary["unfilled_or_partial_order_ratio"] = 0.0
        summary["partial_fill_order_count"] = 0
        summary["partial_fill_order_ratio"] = 0.0
    summary["stale_valuation_positions_total"] = (
        int(pd.to_numeric(daily.get("stale_valuation_positions", 0), errors="coerce").fillna(0).sum())
        if not daily.empty
        else 0
    )
    return summary


def _gate_groups(summary: dict[str, Any], gate_cfg: dict[str, Any] | None = None) -> dict[str, list[tuple[str, bool]]]:
    gate_cfg = gate_cfg or {}
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
    max_unfilled_or_partial_order_ratio = float(gate_cfg.get("max_unfilled_or_partial_order_ratio", 1.0))
    max_partial_fill_order_ratio = float(gate_cfg.get("max_partial_fill_order_ratio", 1.0))
    max_stale_valuation_positions_total = int(gate_cfg.get("max_stale_valuation_positions_total", 10**9))
    return {
        "base": [
            ("selected_candidate_eligible == True", bool(summary.get("selected_candidate_eligible", True))),
            (f"annualized_return_mean > {annualized_return_min:.2f}", float(summary.get("annualized_return_mean", 0.0)) > annualized_return_min),
            (f"sharpe_mean > {sharpe_min:.2f}", float(summary.get("sharpe_mean", 0.0)) > sharpe_min),
            (f"max_drawdown_mean > {max_drawdown_min:.2f}", float(summary.get("max_drawdown_mean", 0.0)) > max_drawdown_min),
            (f"win_rate_mean > {win_rate_min:.2f}", float(summary.get("win_rate_mean", 0.0)) > win_rate_min),
            (f"oos_return_decay_ratio < {oos_return_decay_ratio_max:.2f}", float(summary.get("oos_return_decay_ratio", 0.0)) < oos_return_decay_ratio_max),
        ],
        "robustness": [
            (f"oos_fold_count >= {min_oos_fold_count}", int(summary.get("oos_fold_count", 0)) >= min_oos_fold_count),
            (f"oos_annualized_return_mean > {oos_annualized_return_min:.2f}", float(summary.get("oos_annualized_return_mean", 0.0)) > oos_annualized_return_min),
            (f"oos_sharpe_mean > {oos_sharpe_min:.2f}", float(summary.get("oos_sharpe_mean", 0.0)) > oos_sharpe_min),
            (f"positive_fold_ratio >= {min_positive_fold_ratio:.2f}", float(summary.get("positive_fold_ratio", 0.0)) >= min_positive_fold_ratio),
            (f"negative_fold_count <= {max_negative_fold_count}", int(summary.get("negative_fold_count", 0)) <= max_negative_fold_count),
            (f"min_fold_annualized_return > {min_fold_annualized_return_min:.2f}", float(summary.get("min_fold_annualized_return", 0.0)) > min_fold_annualized_return_min),
            (f"oos_positive_fold_ratio >= {min_oos_positive_fold_ratio:.2f}", float(summary.get("oos_positive_fold_ratio", 0.0)) >= min_oos_positive_fold_ratio),
        ],
        "execution_quality": [
            (
                f"unfilled_or_partial_order_ratio <= {max_unfilled_or_partial_order_ratio:.2f}",
                float(summary.get("unfilled_or_partial_order_ratio", 0.0)) <= max_unfilled_or_partial_order_ratio,
            ),
            (
                f"partial_fill_order_ratio <= {max_partial_fill_order_ratio:.2f}",
                float(summary.get("partial_fill_order_ratio", 0.0)) <= max_partial_fill_order_ratio,
            ),
            (
                f"stale_valuation_positions_total <= {max_stale_valuation_positions_total}",
                int(summary.get("stale_valuation_positions_total", 0)) <= max_stale_valuation_positions_total,
            ),
        ],
    }


def _gate_rows(summary: dict[str, Any], gate_cfg: dict[str, Any] | None = None) -> list[tuple[str, bool]]:
    groups = _gate_groups(summary, gate_cfg)
    return [row for rows in groups.values() for row in rows]


def _write_report(
    path: Path,
    *,
    summary: dict[str, Any],
    folds: pd.DataFrame,
    bill: pd.DataFrame,
    daily: pd.DataFrame,
    execution_cfg: dict[str, Any],
    live_cfg: dict[str, Any],
    gate_cfg: dict[str, Any] | None = None,
) -> None:
    gate_groups = _gate_groups(summary, gate_cfg)
    gates = [row for rows in gate_groups.values() for row in rows]
    passed = all(ok for _, ok in gates)
    status_counts = bill["交易状态"].value_counts(dropna=False).to_dict() if not bill.empty and "交易状态" in bill.columns else {}
    min_cash = float(daily["cash_assets"].min()) if not daily.empty and "cash_assets" in daily.columns else 0.0
    execution_rows = [
        ["profile", str(live_cfg.get("profile", ""))],
        ["universe_mode", str(live_cfg.get("universe_mode", ""))],
        ["universe_audit_rows", str(live_cfg.get("universe_audit_rows", ""))],
        ["slippage", str(live_cfg.get("slippage", ""))],
        ["commission", str(live_cfg.get("commission", ""))],
        ["stamp_duty_sell", str(live_cfg.get("stamp_duty_sell", ""))],
        ["price_mode", str(execution_cfg.get("price_mode", ""))],
        ["lot_size", str(execution_cfg.get("lot_size", ""))],
        ["max_participation_rate", str(execution_cfg.get("max_participation_rate", ""))],
        ["enable_limit_check", str(execution_cfg.get("enable_limit_check", ""))],
        ["enable_suspension_check", str(execution_cfg.get("enable_suspension_check", ""))],
    ]
    lines = [
        "# Phase 0 实盘仿真回测 Effectiveness Gate",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Pipeline: {live_cfg.get('name', '实盘仿真回测')}",
        "",
        f"Gate source: {live_cfg.get('gate_source', 'account_daily_assets')}",
        "",
        f"Overall verdict: {'PASS' if passed else 'FAIL'}",
        "",
        "## Base Gate",
        "",
        _md_table(["gate", "status"], [[name, "PASS" if ok else "FAIL"] for name, ok in gate_groups["base"]]),
        "",
        "## Robustness Gate",
        "",
        _md_table(["gate", "status"], [[name, "PASS" if ok else "FAIL"] for name, ok in gate_groups["robustness"]]),
        "",
        "## Execution Quality Gate",
        "",
        _md_table(["gate", "status"], [[name, "PASS" if ok else "FAIL"] for name, ok in gate_groups["execution_quality"]]),
        "",
        "## Execution Config",
        "",
        _md_table(["key", "value"], execution_rows),
        "",
        "## Snapshot",
        "",
        _md_table(["metric", "value"], [[key, str(value)] for key, value in summary.items()]),
        "",
        "## Account Simulation Stats",
        "",
        _md_table(
            ["metric", "value"],
            [
                ["bill_rows", str(len(bill))],
                ["daily_rows", str(len(daily))],
                ["trade_status_counts", str(status_counts)],
                ["min_cash_assets", f"{min_cash:.2f}"],
                ["unfilled_orders_total", str(int(pd.to_numeric(daily.get("unfilled_orders", 0), errors="coerce").fillna(0).sum()) if not daily.empty else 0)],
                [
                    "stale_valuation_positions_total",
                    str(int(pd.to_numeric(daily.get("stale_valuation_positions", 0), errors="coerce").fillna(0).sum()) if not daily.empty else 0),
                ],
            ],
        ),
        "",
        "## Fold Details",
        "",
    ]
    fold_rows = []
    for _, row in folds.iterrows():
        fold_rows.append(
            [
                str(int(row["fold"])),
                str(row["valid_start"]),
                str(row["valid_end"]),
                f"{float(row['annualized_return']):.4f}",
                f"{float(row['sharpe']):.4f}",
                f"{float(row['max_drawdown']):.4f}",
                f"{float(row['win_rate']):.4f}",
                str(int(row["trades"])),
                f"{float(row['final_account_assets']):.2f}",
                str(int(row["unfilled_orders"])),
            ]
        )
    lines.append(
        _md_table(
            ["fold", "valid_start", "valid_end", "annual_ret", "sharpe", "max_dd", "win_rate", "trades", "final_assets", "unfilled_orders"],
            fold_rows,
        )
    )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def export_execution_effectiveness_report(
    *,
    config_path: Path,
    strategy_id: str | None = None,
    profile: str | None = None,
    output_dir: str | Path | None = None,
    fold_output: str | Path | None = None,
    report_output: str | Path | None = None,
    refresh_cache: bool = False,
    no_panel_cache: bool = False,
    slippage: float | None = None,
    commission: float | None = None,
    stamp_duty_sell: float | None = None,
    price_mode: str | None = None,
    lot_size: int | None = None,
    max_participation_rate: float | None = None,
    enable_limit_check: bool | None = None,
    enable_suspension_check: bool | None = None,
) -> dict[str, Any]:
    root = Path.cwd()
    config_path = config_path if config_path.is_absolute() else root / config_path
    config = load_config(config_path)
    strategy_id = str(strategy_id or _default_report_strategy_id(config))
    selected_profile = str(profile or config.get("live_execution_backtest", {}).get("default_profile", "live"))
    profile_cfg = _profile_settings(config, selected_profile)
    effective_config, walk_forward_overrides, execution_overrides = _apply_profile_to_config(
        config,
        profile_cfg,
        slippage=slippage,
        commission=commission,
        stamp_duty_sell=stamp_duty_sell,
        price_mode=price_mode,
        lot_size=lot_size,
        max_participation_rate=max_participation_rate,
        enable_limit_check=enable_limit_check,
        enable_suspension_check=enable_suspension_check,
    )
    live_cfg = _live_backtest_settings(config)
    live_cfg["profile"] = selected_profile
    live_cfg["name"] = profile_cfg.get("name", live_cfg["name"])
    if output_dir is not None:
        output_root = Path(output_dir)
        output_root = output_root if output_root.is_absolute() else root / output_root
        live_cfg["output_dir"] = str(output_root)
        live_cfg["bill_output"] = str(output_root / "live_execution_bill.csv")
        live_cfg["daily_output"] = str(output_root / "live_execution_daily_assets.csv")
        live_cfg["preview_output"] = str(output_root / "live_execution_bill_preview.html")
        live_cfg["fold_output"] = str(output_root / "live_execution_walk_forward_folds.csv")
        live_cfg["report_output"] = str(output_root / "live_execution_effectiveness_report.md")
    if fold_output is not None:
        live_cfg["fold_output"] = str(fold_output)
    if report_output is not None:
        live_cfg["report_output"] = str(report_output)
    bill_output_path = report_config_path(root=root, config=config, value=live_cfg["bill_output"], default_category="phase0")
    daily_output_path = report_config_path(root=root, config=config, value=live_cfg["daily_output"], default_category="phase0")
    preview_output_path = report_config_path(root=root, config=config, value=live_cfg["preview_output"], default_category="phase0")
    fold_path = _resolve_cli_path(root, fold_output) if fold_output is not None else report_config_path(root=root, config=config, value=live_cfg["fold_output"], default_category="phase0")
    report_path = _resolve_cli_path(root, report_output) if report_output is not None else report_config_path(root=root, config=config, value=live_cfg["report_output"], default_category="phase0")
    live_cfg["bill_output"] = str(bill_output_path)
    live_cfg["daily_output"] = str(daily_output_path)
    live_cfg["preview_output"] = str(preview_output_path)
    live_cfg["fold_output"] = str(fold_path)
    live_cfg["report_output"] = str(report_path)
    bill_walk_forward_overrides = {
        key: effective_config.get("walk_forward", {}).get(key)
        for key in ["slippage", "commission", "stamp_duty_sell"]
        if key in effective_config.get("walk_forward", {})
    }
    bill_result = export_strategy_bill(
        config_path=config_path,
        strategy_id=strategy_id,
        output=bill_output_path,
        daily_output=daily_output_path,
        preview_output=preview_output_path,
        refresh_cache=refresh_cache,
        no_panel_cache=no_panel_cache,
        walk_forward_overrides=bill_walk_forward_overrides,
        execution_overrides=effective_config.get("execution", {}),
    )
    live_cfg["universe_mode"] = bill_result.get("universe_mode", "")
    live_cfg["universe_audit_rows"] = bill_result.get("universe_audit_rows", "")
    bill = pd.read_csv(bill_result["bill"])
    daily = pd.read_csv(bill_result["daily"])
    daily["date"] = pd.to_datetime(daily["date"])
    folds = _fold_metrics(daily, bill, strategy_id=strategy_id)
    gate_cfg = effective_config.get("live_execution_backtest", {}).get("gate", {})
    summary = _summary_from_folds(
        folds,
        effective_config.get("walk_forward", {}).get("strategy_v2", {}).get("candidate_governance", {}),
        strategy_id=strategy_id,
        bill=bill,
        daily=daily,
    )
    execution_cfg = _execution_settings(effective_config)
    live_cfg["slippage"] = effective_config.get("walk_forward", {}).get("slippage", "")
    live_cfg["commission"] = effective_config.get("walk_forward", {}).get("commission", "")
    live_cfg["stamp_duty_sell"] = effective_config.get("walk_forward", {}).get("stamp_duty_sell", "")

    fold_path.parent.mkdir(parents=True, exist_ok=True)
    folds.to_csv(fold_path, index=False, encoding="utf-8-sig")
    _write_report(
        report_path,
        summary=summary,
        folds=folds,
        bill=bill,
        daily=daily,
        execution_cfg=execution_cfg,
        live_cfg=live_cfg,
        gate_cfg=gate_cfg,
    )
    return {
        "folds": fold_path,
        "report": report_path,
        "verdict": "PASS" if all(ok for _, ok in _gate_rows(summary, gate_cfg)) else "FAIL",
        "summary": summary,
        "bill": bill_result["bill"],
        "daily": bill_result["daily"],
        "preview": bill_result["preview"],
        "pipeline": live_cfg["name"],
        "strategy_id": strategy_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--strategy-id", default=None)
    parser.add_argument("--profile", default=None, choices=["research", "live"])
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--fold-output", default=None)
    parser.add_argument("--report-output", default=None)
    parser.add_argument("--slippage", type=float, default=None)
    parser.add_argument("--commission", type=float, default=None)
    parser.add_argument("--stamp-duty-sell", type=float, default=None)
    parser.add_argument("--price-mode", choices=["close", "next_open", "conservative"], default=None)
    parser.add_argument("--lot-size", type=int, default=None)
    parser.add_argument("--max-participation-rate", type=float, default=None)
    parser.add_argument("--enable-limit-check", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--enable-suspension-check", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--no-panel-cache", action="store_true")
    args = parser.parse_args()
    result = export_execution_effectiveness_report(
        config_path=Path(args.config),
        strategy_id=args.strategy_id,
        profile=args.profile,
        output_dir=args.output_dir,
        fold_output=args.fold_output,
        report_output=args.report_output,
        refresh_cache=bool(args.refresh_cache),
        no_panel_cache=bool(args.no_panel_cache),
        slippage=args.slippage,
        commission=args.commission,
        stamp_duty_sell=args.stamp_duty_sell,
        price_mode=args.price_mode,
        lot_size=args.lot_size,
        max_participation_rate=args.max_participation_rate,
        enable_limit_check=args.enable_limit_check,
        enable_suspension_check=args.enable_suspension_check,
    )
    print(f"verdict={result['verdict']}")
    print(f"folds={result['folds']}")
    print(f"report={result['report']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
