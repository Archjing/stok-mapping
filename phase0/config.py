from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from phase0.env import load_project_env


def load_config(config_path: Path) -> dict[str, Any]:
    load_project_env(config_path.parent)
    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "phase0" not in data:
        raise ValueError("config.yaml missing 'phase0' section")
    return data["phase0"]
