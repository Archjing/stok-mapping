from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Mapping

import yaml

from quant.env import load_project_env


def select_quant_config(data: Mapping[str, Any]) -> dict[str, Any]:
    has_quant = "quant" in data
    has_legacy = "phase0" in data
    if has_quant and has_legacy:
        raise ValueError("config contains both 'quant' and legacy 'phase0' sections")
    if has_quant:
        selected = data["quant"]
    elif has_legacy:
        warnings.warn(
            "config root 'phase0' is deprecated; rename it to 'quant'",
            DeprecationWarning,
            stacklevel=2,
        )
        selected = data["phase0"]
    else:
        raise ValueError("config.yaml missing 'quant' section")
    if not isinstance(selected, dict):
        raise ValueError("selected quant configuration must be a mapping")
    return selected


def load_config_document(config_path: Path) -> dict[str, Any]:
    load_project_env(config_path.parent)
    with config_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError("config document must be a mapping")
    return data


def load_config(config_path: Path) -> dict[str, Any]:
    return select_quant_config(load_config_document(config_path))
