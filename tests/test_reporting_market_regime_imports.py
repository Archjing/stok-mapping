from __future__ import annotations

import subprocess
import sys

import scripts.export_market_regime_report as legacy_market_regime
from phase0.reporting import market_regime
from phase0.reporting.market_regime import export_market_regime_report


def test_market_regime_new_imports_are_available() -> None:
    assert callable(export_market_regime_report)


def test_legacy_market_regime_script_aliases_reporting_module() -> None:
    assert legacy_market_regime is market_regime
    assert legacy_market_regime.export_market_regime_report is export_market_regime_report


def test_legacy_market_regime_script_help_runs_directly() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/export_market_regime_report.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--summary-output" in result.stdout
