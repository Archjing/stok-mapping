from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "phase0" not in data:
        raise ValueError("config.yaml missing 'phase0' section")
    return data["phase0"]
