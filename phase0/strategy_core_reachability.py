from __future__ import annotations

import sys

from phase0.research.core_coverage import core_reachability as _impl

sys.modules[__name__] = _impl
