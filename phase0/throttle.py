from __future__ import annotations

import sys

from phase0.data_access import throttle as _impl

sys.modules[__name__] = _impl
