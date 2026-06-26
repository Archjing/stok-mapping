from __future__ import annotations

import sys

from phase0.data_access.providers import tushare as _impl

sys.modules[__name__] = _impl
