from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0.data_governance import universe_pit as _impl

sys.modules[__name__] = _impl
