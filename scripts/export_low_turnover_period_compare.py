from __future__ import annotations

"""Backward-compatible entrypoint for the historical low-turnover period compare.

New code should invoke scripts.export_strategy_period_compare.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.export_strategy_period_compare import main


if __name__ == "__main__":
    main()
