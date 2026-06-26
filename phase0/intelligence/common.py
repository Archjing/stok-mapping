from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd


def resolve_path(root: Path, raw: str | Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else root / path


def date_tag() -> str:
    return date.today().isoformat()


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def configured_path(
    *,
    root: Path,
    intel_cfg: dict[str, Any],
    override: str | Path | None,
    config_key: str,
    fallback: str | Path,
) -> Path:
    raw = override or intel_cfg.get(config_key) or fallback
    return resolve_path(root, raw)
