from __future__ import annotations

import subprocess
import sys

import scripts.export_strategy_oos_report as legacy_strategy_oos
from phase0.reporting import strategy_oos
from phase0.reporting.strategy_oos import (
    DEFAULT_PROFILE_OOS_REPORT_OUTPUT,
    export_strategy_oos_report,
)


def test_strategy_oos_new_imports_are_available() -> None:
    assert DEFAULT_PROFILE_OOS_REPORT_OUTPUT == "live_execution_backtest/oos_report.html"
    assert callable(export_strategy_oos_report)


def test_legacy_strategy_oos_script_aliases_reporting_module() -> None:
    assert legacy_strategy_oos is strategy_oos
    assert legacy_strategy_oos.DEFAULT_PROFILE_OOS_REPORT_OUTPUT is DEFAULT_PROFILE_OOS_REPORT_OUTPUT
    assert legacy_strategy_oos.export_strategy_oos_report is export_strategy_oos_report


def test_legacy_strategy_oos_script_help_runs_directly() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/export_strategy_oos_report.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--strategy-id" in result.stdout
