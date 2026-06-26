from __future__ import annotations

from typing import Any


def _resolve_strategy_scope(
    strategy_cfg: dict[str, Any],
    admission_cfg: dict[str, Any],
    *,
    strategy_set: str | None,
    strategies: list[str] | None,
) -> dict[str, Any]:
    if strategies:
        return {
            "source": "cli_strategies",
            "strategy_set": "",
            "description": "Explicit CLI --strategies override.",
            "strategies": [str(item) for item in strategies],
        }

    sets = admission_cfg.get("strategy_sets", {}) or {}
    selected_set = str(strategy_set or admission_cfg.get("default_strategy_set", "") or "").strip()
    if selected_set:
        if selected_set not in sets:
            raise ValueError(f"unknown admission strategy_set: {selected_set}")
        raw_set = sets[selected_set] or {}
        if isinstance(raw_set, dict):
            names = raw_set.get("strategies", [])
            description = str(raw_set.get("description", ""))
        else:
            names = raw_set
            description = ""
        return {
            "source": "strategy_set",
            "strategy_set": selected_set,
            "description": description,
            "strategies": [str(item) for item in names],
        }

    return {
        "source": "legacy_compare_strategies",
        "strategy_set": "",
        "description": "Backward-compatible strategy_v2.compare_strategies fallback.",
        "strategies": [str(item) for item in strategy_cfg.get("compare_strategies", [])],
    }


def _force_strategy_set_enabled_for_admission(strategy_cfg: dict[str, Any], strategy_names: list[str]) -> None:
    legacy_switches = {
        "ma_kline_baseline_v1": ("baseline_ma_kline",),
        "core_selection_quality_momentum_v1": ("core_selection_quality_momentum",),
        "theme_exposure_momentum_v1": ("theme_exposure_momentum",),
        "residual_momentum_reversal_v1": ("local_factor",),
        "residual_momentum_reversal_v2": ("local_factor", "residual_reversal_v2"),
        "quality_growth_price_v1": ("local_factor", "quality_growth"),
        "low_vol_low_turnover_quality_v1": ("local_factor", "low_vol_low_turnover_quality"),
        "quality_low_turnover_monthly_v1": ("local_factor", "quality_low_turnover_monthly"),
        "quality_low_turnover_regime_gate_v1": ("local_factor", "quality_low_turnover_regime_gate"),
        "price_volume_low_turnover_v1": ("local_factor", "price_volume_low_turnover"),
        "strong_index_participation_v1": ("local_factor", "strong_index_participation"),
        "strong_index_participation_dynamic_trigger_v1": ("local_factor", "strong_index_participation"),
        "strong_market_liquid_breadth_participation_v1": (
            "local_factor",
            "strong_market_liquid_breadth_participation",
        ),
        "strong_market_effective_participation_v1": (
            "local_factor",
            "strong_market_effective_participation",
        ),
        "strong_market_stable_core_base_v1": (
            "local_factor",
            "strong_market_stable_core_base",
        ),
        "strong_market_benchmark_aware_core_v1": (
            "local_factor",
            "strong_market_benchmark_aware_core",
        ),
        "benchmark_core_alpha_overlay_v1": (
            "local_factor",
            "benchmark_core_alpha_overlay",
        ),
        "strong_benchmark_participation_boost_v1": (
            "local_factor",
            "strong_benchmark_participation_boost",
        ),
        "strong_benchmark_recovery_participation_v1": (
            "local_factor",
            "strong_benchmark_recovery_participation",
        ),
        "strong_benchmark_recovery_quality_v1": (
            "local_factor",
            "strong_benchmark_recovery_quality",
        ),
        "strong_benchmark_recovery_tradable_v1": (
            "local_factor",
            "strong_benchmark_recovery_tradable",
        ),
        "strong_benchmark_recovery_leadership_v1": (
            "local_factor",
            "strong_benchmark_recovery_leadership",
        ),
        # I48/I49 attribution-only variants. They may run scoped admission
        # evidence to compare mechanics, but must not be added to default
        # candidate pools or promoted to paper-review flows.
        "strong_market_stable_core_only_v1": (
            "local_factor",
            "strong_market_stable_core_base",
        ),
        "strong_market_stable_satellite_only_v1": (
            "local_factor",
            "strong_market_stable_core_base",
        ),
        "multifactor_volume_price_filter_v1": ("local_factor", "multifactor_filter"),
        "sleeve_composite_v1": ("sleeve_composite",),
        "sleeve_composite_low_churn_v1": ("sleeve_composite_low_churn",),
    }
    for strategy_name in strategy_names:
        path = legacy_switches.get(str(strategy_name))
        if not path:
            continue
        target = strategy_cfg
        for key in path:
            target = target.setdefault(key, {})
        if isinstance(target, dict):
            target["enabled"] = True
