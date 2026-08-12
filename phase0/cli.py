from __future__ import annotations

import sys

from quant.cli import main


def _warn() -> None:
    print(
        "DEPRECATION: 'python -m phase0.cli' is deprecated; use "
        "'python -m quant.cli' or './runit'.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    _warn()
    raise SystemExit(main())
