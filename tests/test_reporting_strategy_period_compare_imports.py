from __future__ import annotations

import subprocess
import sys

import scripts.export_strategy_period_compare as legacy_period_compare
from phase0.reporting import strategy_period_compare
from phase0.reporting.strategy_period_compare import DEFAULT_COMPARE_TITLE, main


def test_strategy_period_compare_new_imports_are_available() -> None:
    assert DEFAULT_COMPARE_TITLE
    assert callable(main)


def test_legacy_strategy_period_compare_script_aliases_reporting_module() -> None:
    assert legacy_period_compare is strategy_period_compare
    assert legacy_period_compare.DEFAULT_COMPARE_TITLE is DEFAULT_COMPARE_TITLE
    assert legacy_period_compare.main is main


def test_legacy_strategy_period_compare_script_help_runs_directly() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/export_strategy_period_compare.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--early-curve" in result.stdout
