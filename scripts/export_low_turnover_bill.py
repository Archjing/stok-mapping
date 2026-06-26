from __future__ import annotations

"""Backward-compatible entrypoint for the historical low-turnover bill export.

New code should import from phase0.reporting.strategy_bill.
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0.reporting.strategy_bill import DEFAULT_STRATEGY_ID, export_strategy_bill


def export_low_turnover_bill(**kwargs: Any) -> dict[str, Any]:
    """Export the historical low-turnover strategy bill via the generic exporter."""
    kwargs.setdefault("strategy_id", DEFAULT_STRATEGY_ID)
    kwargs.setdefault("preview_title", "Phase 0 Low Turnover Bill Preview")
    return export_strategy_bill(**kwargs)


def main() -> int:
    from phase0.reporting.strategy_bill import main as strategy_main

    return int(strategy_main() or 0)


if __name__ == "__main__":
    raise SystemExit(main())
