from __future__ import annotations

"""Backward-compatible entrypoint for the historical low-turnover OOS report.

New code should import from scripts.export_strategy_oos_report.
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.export_strategy_bill import DEFAULT_STRATEGY_ID
from scripts.export_strategy_oos_report import export_strategy_oos_report


def export_low_turnover_oos_report(**kwargs: Any) -> dict[str, Path | str]:
    """Export the historical low-turnover OOS report via the generic exporter."""
    kwargs.setdefault("strategy_id", DEFAULT_STRATEGY_ID)
    kwargs.setdefault("title", "Phase 0 Low Turnover Continuous OOS Report")
    return export_strategy_oos_report(**kwargs)


def main() -> None:
    from scripts.export_strategy_oos_report import main as strategy_main

    strategy_main()


if __name__ == "__main__":
    main()
