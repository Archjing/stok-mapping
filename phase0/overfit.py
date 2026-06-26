from __future__ import annotations

import sys

from phase0.research.diagnostics import overfit as _impl

sys.modules[__name__] = _impl
