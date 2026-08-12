"""Admission research helpers.

The package root stays lazy so low-level admission helpers can be imported
without loading the strategy-admission runner through failure attribution.
"""

__all__ = [
    "StrategyFailureAttributionResult",
    "run_strategy_failure_attribution",
]


def __getattr__(name: str):
    if name in __all__:
        from quant.research.admission.failure_attribution import (
            StrategyFailureAttributionResult,
            run_strategy_failure_attribution,
        )

        values = {
            "StrategyFailureAttributionResult": StrategyFailureAttributionResult,
            "run_strategy_failure_attribution": run_strategy_failure_attribution,
        }
        return values[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
