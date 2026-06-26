from __future__ import annotations

import sys

from phase0.research.attribution import fold as _impl

sys.modules[__name__] = _impl
