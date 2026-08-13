"""Metadata-only daily feature registry and resolution.

A feature is a pure, versioned formula over already-local columns.  The
registry never downloads data, never precomputes a feature lake, and never
writes to disk.  A consumer asks for named features over a bounded
``symbol × date`` panel; :meth:`FeatureRegistry.build` resolves dependency
order and computes them from local fields.

Design contract (each :class:`FeatureSpec`):
    name                   stable output column name (e.g. ``ema_20``)
    version                semantic formula version; a formula change must bump it
    inputs                 canonical source columns / feature names it depends on
    lookback_sessions      largest required warm-up window
    availability_lag_sessions  0 = same-day close (post-close only); a positive
                           lag means "this many sessions before it is usable"
    missing_data_policy    preserve_nan | drop_until_warm (no backward fill)
    builder                pure callable: sorted panel -> Series (original index)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

import pandas as pd

MissingDataPolicy = Literal["preserve_nan", "drop_until_warm"]


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    version: str
    inputs: tuple[str, ...]
    lookback_sessions: int
    availability_lag_sessions: int
    missing_data_policy: MissingDataPolicy
    builder: Callable[[pd.DataFrame], pd.Series | pd.DataFrame]

    def __post_init__(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise ValueError("name must be a non-empty string")
        if not self.version or not isinstance(self.version, str):
            raise ValueError("version must be a non-empty string")
        if not isinstance(self.inputs, tuple) or not all(isinstance(i, str) for i in self.inputs):
            raise ValueError("inputs must be a tuple of strings")
        if self.lookback_sessions < 0:
            raise ValueError("lookback_sessions must be >= 0")
        if self.availability_lag_sessions < 0:
            raise ValueError("availability_lag_sessions must be >= 0")
        if self.missing_data_policy not in ("preserve_nan", "drop_until_warm"):
            raise ValueError("missing_data_policy must be 'preserve_nan' or 'drop_until_warm'")


class FeatureRegistry:
    """Immutable feature definitions with dependency resolution and pure build."""

    def __init__(self) -> None:
        self._specs: dict[str, FeatureSpec] = {}
        self._base_fields: set[str] = set()

    @classmethod
    def with_base_fields(cls, base_fields: set[str] | tuple[str, ...] | list[str]) -> "FeatureRegistry":
        registry = cls()
        registry._base_fields = set(base_fields)
        return registry

    def register(self, spec: FeatureSpec) -> None:
        if spec.name in self._specs:
            raise ValueError(f"duplicate feature: {spec.name}")
        unknown = set(spec.inputs).difference(self._base_fields, self._specs)
        if unknown:
            raise ValueError(f"unknown dependency: {sorted(unknown)}")
        self._specs[spec.name] = spec

    def resolve(self, requested: tuple[str, ...] | list[str]) -> tuple[str, ...]:
        """Return features in dependency order (dependencies before dependents)."""
        resolved: list[str] = []
        visiting: set[str] = set()

        def visit(name: str) -> None:
            if name in self._base_fields or name in resolved:
                return
            if name in visiting or name not in self._specs:
                raise ValueError(f"unknown or cyclic feature: {name}")
            visiting.add(name)
            for dependency in self._specs[name].inputs:
                visit(dependency)
            visiting.remove(name)
            resolved.append(name)

        for name in requested:
            visit(name)
        return tuple(resolved)

    def build(self, panel: pd.DataFrame, requested: tuple[str, ...] | list[str]) -> pd.DataFrame:
        """Compute requested features over ``panel`` and return a new frame.

        The input panel is not mutated.  The panel index must be unique; each
        builder receives a frame with all resolved prior columns and must
        return a Series/DataFrame aligned to that index.
        """
        result = panel.copy(deep=True)
        if not result.index.is_unique:
            raise ValueError("panel index must be unique")
        for name in self.resolve(tuple(requested)):
            spec = self._specs[name]
            built = spec.builder(result)
            if isinstance(built, pd.Series):
                built = built.rename(name).to_frame()
            if not built.index.equals(result.index) or built.columns.has_duplicates:
                raise ValueError(f"misaligned builder output: {name}")
            result = result.join(built, how="left")
        return result

    def names(self) -> tuple[str, ...]:
        return tuple(self._specs)
