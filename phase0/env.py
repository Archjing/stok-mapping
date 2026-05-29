from __future__ import annotations

from pathlib import Path


def prepare_imports() -> Path:
    """
    Return the project root for local Phase 0 modules.
    """
    return Path(__file__).resolve().parents[1]
