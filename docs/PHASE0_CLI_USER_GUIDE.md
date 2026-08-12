# Deprecated Phase0 CLI Guide Path

The application CLI is now documented in
[`QUANT_CLI_USER_GUIDE.md`](QUANT_CLI_USER_GUIDE.md).

Use `./runit ...` or `./.venv/bin/python -m quant.cli ...`.
The legacy `python -m phase0.cli ...` entry point is temporary and emits a
deprecation warning; application code lives under the `quant` namespace.
