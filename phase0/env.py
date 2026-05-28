from __future__ import annotations

import sys
from pathlib import Path


def prepare_imports() -> Path:
    """
    Reuse stok-quant backend modules directly for Phase 0.
    """
    root = Path(__file__).resolve().parents[1]
    stok_quant = root.parent / "stok-quant"
    if str(stok_quant) not in sys.path:
        sys.path.insert(0, str(stok_quant))
    return root
