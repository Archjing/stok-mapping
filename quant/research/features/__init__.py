"""Daily feature registry and local technical-feature builders.

Public API:
    FeatureSpec, FeatureRegistry   — metadata-only registry and resolution
    build_technical_registry       — Tier-A price/volume feature set
"""
from __future__ import annotations

from quant.research.features.registry import FeatureRegistry, FeatureSpec
from quant.research.features.technical import build_technical_registry

__all__ = ["FeatureSpec", "FeatureRegistry", "build_technical_registry"]
