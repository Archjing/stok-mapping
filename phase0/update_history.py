from __future__ import annotations

import sys

from phase0.data_governance import update_history as _impl

sys.modules[__name__] = _impl
