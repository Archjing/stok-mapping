from __future__ import annotations

from typing import Type

from quant.strategies.base import BaseStrategy


_STRATEGIES: dict[str, Type[BaseStrategy]] = {}


def register(strategy_cls: Type[BaseStrategy]) -> Type[BaseStrategy]:
    if not strategy_cls.name:
        raise ValueError("strategy class must define a non-empty name")
    _STRATEGIES[strategy_cls.name] = strategy_cls
    return strategy_cls


def get_strategy(name: str) -> BaseStrategy:
    return _STRATEGIES[name]()


def available_strategies() -> list[str]:
    return sorted(_STRATEGIES.keys())
