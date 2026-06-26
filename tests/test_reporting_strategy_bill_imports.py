from __future__ import annotations

import subprocess
import sys

import scripts.export_strategy_bill as legacy_strategy_bill
from phase0.reporting import strategy_bill
from phase0.reporting.strategy_bill import (
    DEFAULT_PANEL_CACHE,
    DEFAULT_STRATEGY_ID,
    _execution_settings,
    _load_or_build_panel,
    _panel_cache_key,
    export_strategy_bill,
)


def test_strategy_bill_new_imports_are_available() -> None:
    assert DEFAULT_STRATEGY_ID == "legacy_momentum_low_turnover_v1"
    assert DEFAULT_PANEL_CACHE
    assert callable(export_strategy_bill)
    assert callable(_execution_settings)
    assert callable(_panel_cache_key)
    assert callable(_load_or_build_panel)


def test_legacy_strategy_bill_script_aliases_reporting_module() -> None:
    assert legacy_strategy_bill is strategy_bill
    assert legacy_strategy_bill.DEFAULT_STRATEGY_ID is DEFAULT_STRATEGY_ID
    assert legacy_strategy_bill.DEFAULT_PANEL_CACHE is DEFAULT_PANEL_CACHE
    assert legacy_strategy_bill.export_strategy_bill is export_strategy_bill
    assert legacy_strategy_bill._execution_settings is _execution_settings
    assert legacy_strategy_bill._panel_cache_key is _panel_cache_key
    assert legacy_strategy_bill._load_or_build_panel is _load_or_build_panel


def test_legacy_strategy_bill_script_help_runs_directly() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/export_strategy_bill.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--strategy-id" in result.stdout
