from __future__ import annotations

from typing import Any


def resolve_admission_gate(wcfg: dict[str, Any]) -> dict[str, Any]:
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


def resolve_diagnostic_suites(admission_cfg: dict[str, Any]) -> list[str]:
    diagnostics = admission_cfg.get("diagnostics", {}) or {}
    return [str(item) for item in diagnostics.get("suites", [])]


def overfit_blocks_admission(level: str, gate_cfg: dict[str, Any]) -> bool:
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3, "unknown": 99}
    max_level = str(gate_cfg.get("overfit_risk_max", "medium"))
    return order.get(str(level), 99) > order.get(max_level, 1)
