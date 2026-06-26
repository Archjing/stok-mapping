from __future__ import annotations

import sys

from phase0.data_governance.backfills import tushare_history as _impl

sys.modules[__name__] = _impl
