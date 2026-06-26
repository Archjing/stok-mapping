from __future__ import annotations

import subprocess
import sys

import scripts.export_execution_effectiveness_report as legacy_execution_effectiveness
from phase0.reporting import execution_effectiveness
from phase0.reporting.execution_effectiveness import (
    DEFAULT_OUTPUT_DIR,
    export_execution_effectiveness_report,
)


def test_execution_effectiveness_new_imports_are_available() -> None:
    assert DEFAULT_OUTPUT_DIR == "live_execution_backtest"
    assert callable(export_execution_effectiveness_report)


def test_legacy_execution_effectiveness_script_aliases_reporting_module() -> None:
    assert legacy_execution_effectiveness is execution_effectiveness
    assert legacy_execution_effectiveness.DEFAULT_OUTPUT_DIR is DEFAULT_OUTPUT_DIR
    assert legacy_execution_effectiveness.export_execution_effectiveness_report is export_execution_effectiveness_report


def test_legacy_execution_effectiveness_script_help_runs_directly() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/export_execution_effectiveness_report.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--strategy-id" in result.stdout
