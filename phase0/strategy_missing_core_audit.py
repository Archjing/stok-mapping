from __future__ import annotations

import sys

from phase0.research.core_coverage import missing_core_audit as _impl

sys.modules[__name__] = _impl
